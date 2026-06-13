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


def post_json(url, payload, timeout=180):
    body = json.dumps(payload, ensure_ascii=False).encode('utf-8')
    req = urllib.request.Request(
        url,
        data=body,
        headers={'Content-Type': 'application/json', 'Authorization': 'Bearer PROXY_MANAGED'},
        method='POST',
    )
    started = time.time()
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        raw = resp.read().decode('utf-8')
    return json.loads(raw), time.time() - started


def build_messages():
    messages = [
        {'role': 'system', 'content': '你是代码执行 agent。当前上下文包含多个旧工具输出，请压缩旧上下文以节省 token。'},
    ]
    for idx, path in enumerate(FILES):
        content = path.read_text(encoding='utf-8').replace('\r', '')
        messages.append({'role': 'assistant', 'content': f'读取第 {idx + 1} 个文件：{path.name}'})
        messages.append({
            'role': 'user',
            'content': f'[old tool output: read_file {path.name}]\n{content}\n[EOF old tool output]'
        })
    messages.append({'role': 'user', 'content': '现在只需要保留足够的信息用于后续总结，不需要逐字保留全部旧工具输出。'})
    return messages


def main():
    messages = build_messages()
    chars = sum(len(m['content']) for m in messages)
    print(f'messages={len(messages)} chars={chars} estimated_tokens~{int(chars/3.5)}')

    payload = {
        'model': 'ark-code-latest',
        'messages': messages,
        'token_budget': 12000,
        'config': {
            'compress_user_messages': True,
            'target_ratio': 0.55,
            'protect_recent': 0,
            'protect_analysis_context': False,
        },
    }
    result, elapsed = post_json('http://127.0.0.1:8790/v1/compress', payload)
    print(f'elapsed={elapsed:.1f}s')
    print('tokens_before=', result.get('tokens_before'))
    print('tokens_after=', result.get('tokens_after'))
    print('tokens_saved=', result.get('tokens_saved'))
    print('compression_ratio=', result.get('compression_ratio'))
    before = result.get('tokens_before') or 0
    saved = result.get('tokens_saved') or 0
    if before:
        print('savings_pct=', round(saved / before * 100, 2))
    print('transforms_applied=', result.get('transforms_applied'))
    print('transforms_summary=', result.get('transforms_summary'))
    compressed_messages = result.get('messages', [])
    compressed_chars = sum(len(str(m.get('content', ''))) for m in compressed_messages)
    print('compressed_chars=', compressed_chars)
    for message in compressed_messages[:8]:
        content = str(message.get('content', ''))
        if 'Retrieve' in content or 'Compressed' in content or len(content) < 500:
            print('--- message preview ---')
            print(message.get('role'), content[:500])


if __name__ == '__main__':
    main()
