import json
import os
import pathlib
import time
import urllib.request

PROJECT = pathlib.Path(os.environ.get('BENCHMARK_PROJECT', '/path/to/your/video-analyzer'))
FILES = [
    PROJECT / 'video_analyzer/cli.py',
    PROJECT / 'video_analyzer/prompt.py',
    PROJECT / 'video_analyzer/clients/generic_openai_api.py',
    PROJECT / 'video_analyzer/clients/ollama.py',
    PROJECT / 'video-analyzer-ui/video_analyzer_ui/server.py',
]


def post_json(url, payload, timeout=240):
    body = json.dumps(payload, ensure_ascii=False).encode('utf-8')
    req = urllib.request.Request(
        url,
        data=body,
        headers={
            'Content-Type': 'application/json',
            'Authorization': 'Bearer PROXY_MANAGED',
        },
        method='POST',
    )
    started = time.time()
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        raw = resp.read().decode('utf-8')
    return json.loads(raw), time.time() - started


def get_json(url, timeout=20):
    with urllib.request.urlopen(url, timeout=timeout) as resp:
        return json.loads(resp.read().decode('utf-8'))


def build_chat_payload():
    messages = [
        {'role': 'system', 'content': '你是一个代码审查助手。请基于工具输出总结问题，答案简洁。'},
        {'role': 'user', 'content': '请审查 video-analyzer 的关键文件。'},
    ]
    for path in FILES:
        content = path.read_text(encoding='utf-8').replace('\r', '')
        messages.append({'role': 'assistant', 'content': f'我将读取 {path.name}。'})
        messages.append({'role': 'user', 'content': f'[Tool output: read_file {path.name}]\n{content}\n[EOF]'})
    messages.append({'role': 'user', 'content': '请按优先级列出 10 条问题，每条不超过 40 字。'})
    return {'model': 'ark-code-latest', 'messages': messages, 'max_tokens': 900}


def build_responses_payload():
    parts = []
    parts.append('你是 Codex 风格代码 agent。以下是多次工具读取结果，请压缩上下文后总结问题。')
    for path in FILES:
        content = path.read_text(encoding='utf-8').replace('\r', '')
        parts.append(f'\n<tool_result tool="read_file" file="{path.name}">\n{content}\n</tool_result>')
    parts.append('\n请按优先级输出 10 条问题，每条不超过 40 字。')
    return {
        'model': 'ark-code-latest',
        'input': '\n'.join(parts),
        'max_output_tokens': 900,
    }


def summarize_result(label, result, elapsed):
    usage = result.get('usage') or {}
    print(f'=== {label} ===')
    print(f'耗时: {elapsed:.1f}s')
    print(f"prompt/input tokens: {usage.get('prompt_tokens') or usage.get('input_tokens')}")
    print(f"completion/output tokens: {usage.get('completion_tokens') or usage.get('output_tokens')}")
    print(f"total tokens: {usage.get('total_tokens')}")
    text = ''
    if 'choices' in result:
        text = result['choices'][0].get('message', {}).get('content') or ''
    elif 'output_text' in result:
        text = result.get('output_text') or ''
    elif 'output' in result:
        text = json.dumps(result.get('output'), ensure_ascii=False)[:400]
    print(f'回答预览: {text[:200]}')
    print()


def show_stats(stage):
    stats = get_json('http://127.0.0.1:8790/stats')
    summary = stats.get('summary', {})
    comp = summary.get('compression', {})
    tokens = stats.get('tokens', {})
    print(f'--- 8790 stats {stage} ---')
    print('api_requests:', summary.get('api_requests'))
    print('requests_compressed:', comp.get('requests_compressed'))
    print('avg_compression_pct:', comp.get('avg_compression_pct'))
    print('best_compression_pct:', comp.get('best_compression_pct'))
    print('total_tokens_removed:', comp.get('total_tokens_removed'))
    print('proxy_compression_saved:', tokens.get('proxy_compression_saved'))
    print('proxy_total_before_compression:', tokens.get('proxy_total_before_compression'))
    print('proxy_savings_percent:', tokens.get('proxy_savings_percent'))
    print('uncompressed_requests:', summary.get('uncompressed_requests'))
    print()


def main():
    chat_payload = build_chat_payload()
    chat_chars = sum(len(m['content']) for m in chat_payload['messages'])
    print(f'Chat payload messages={len(chat_payload["messages"])} chars={chat_chars} estimated_tokens~{chat_chars//3.5:.0f}')
    show_stats('before')

    for label, url in [
        ('chat direct 15721', 'http://127.0.0.1:15721/v1/chat/completions'),
        ('chat headroom 8790', 'http://127.0.0.1:8790/v1/chat/completions'),
    ]:
        result, elapsed = post_json(url, chat_payload)
        summarize_result(label, result, elapsed)

    show_stats('after chat')

    responses_payload = build_responses_payload()
    resp_chars = len(responses_payload['input'])
    print(f'Responses payload chars={resp_chars} estimated_tokens~{resp_chars//3.5:.0f}')
    for label, url in [
        ('responses direct 15721', 'http://127.0.0.1:15721/v1/responses'),
        ('responses headroom 8790', 'http://127.0.0.1:8790/v1/responses'),
    ]:
        result, elapsed = post_json(url, responses_payload)
        summarize_result(label, result, elapsed)

    show_stats('after responses')


if __name__ == '__main__':
    main()
