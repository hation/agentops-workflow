import json
import time
import urllib.request


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
        return json.loads(resp.read().decode('utf-8')), time.time() - started


def make_json_tool_output():
    records = []
    for i in range(600):
        records.append({
            'file': f'video_analyzer/module_{i % 12}.py',
            'line': i + 1,
            'severity': ['info', 'warning', 'error'][i % 3],
            'rule': ['missing-timeout', 'unsafe-cleanup', 'unvalidated-arg', 'deprecated-api'][i % 4],
            'message': 'This diagnostic entry is a repeated tool result with structured fields for compression testing.',
            'snippet': 'response = requests.post(url, headers=headers, json=payload, timeout=self.timeout)',
            'recommendation': 'Keep only grouped counts and representative examples; original rows can be retrieved when needed.',
        })
    return json.dumps(records, ensure_ascii=False, indent=2)


def make_log_tool_output():
    lines = []
    for i in range(1400):
        lines.append(
            f'2026-06-11 09:{i % 60:02d}:00 pytest[{i % 8}] WARNING video_analyzer/module_{i % 12}.py:{i % 200}: '
            f'repeated diagnostic missing timeout / unsafe cleanup / unvalidated arg, case={i % 30}'
        )
    return '\n'.join(lines)


def run_case(name, content):
    messages = [
        {'role': 'system', 'content': '你是代码执行 agent。旧工具输出可以压缩，只保留摘要和可检索线索。'},
        {'role': 'assistant', 'content': f'下面是旧工具输出：{name}'},
        {'role': 'user', 'content': content},
        {'role': 'user', 'content': '请压缩上面的旧工具输出，保留后续分析需要的摘要。'},
    ]
    payload = {
        'model': 'ark-code-latest',
        'messages': messages,
        'token_budget': 12000,
        'config': {
            'compress_user_messages': True,
            'target_ratio': 0.35,
            'protect_recent': 0,
            'protect_analysis_context': False,
        },
    }
    chars = sum(len(m['content']) for m in messages)
    result, elapsed = post_json('http://127.0.0.1:8790/v1/compress', payload)
    before = result.get('tokens_before') or 0
    after = result.get('tokens_after') or 0
    saved = result.get('tokens_saved') or 0
    print(f'=== {name} ===')
    print(f'chars={chars} estimated_tokens~{int(chars / 3.5)} elapsed={elapsed:.2f}s')
    print(f'tokens_before={before}')
    print(f'tokens_after={after}')
    print(f'tokens_saved={saved}')
    print(f'savings_pct={round(saved / before * 100, 2) if before else 0}')
    print(f'compression_ratio={result.get("compression_ratio")}')
    print(f'transforms_applied={result.get("transforms_applied")}')
    print(f'transforms_summary={result.get("transforms_summary")}')
    compressed = result.get('messages', [])
    for m in compressed:
        text = str(m.get('content', ''))
        if 'Retrieve' in text or len(text) < 1200:
            print('--- compressed preview ---')
            print(m.get('role'), text[:1000])
    print()


def main():
    run_case('structured_json_tool_output', make_json_tool_output())
    run_case('repeated_log_tool_output', make_log_tool_output())


if __name__ == '__main__':
    main()
