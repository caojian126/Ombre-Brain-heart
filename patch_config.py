#!/usr/bin/env python3
"""
Startup patch: configure multi-upstream gateway in config.yaml
Runs AFTER the config.yaml symlink is set up.
Does NOT change gateway port (stays 8010).

用户环境增强版：额外包含 max_tokens 补丁（确保 thinking 关闭后各摘要/评估任务
token 预算充足，防 JSON 截断）。仅当键缺失或当前值 < 4000 时提升到 4000，
不覆盖更大的用户配置。
"""

import os
import sys

print("========== PATCH_CONFIG.PY STARTING ==========", file=sys.stderr, flush=True)

path = '/app/config.yaml'
if not os.path.exists(path):
    print('PATCH_CONFIG: WARN: config.yaml not found', file=sys.stderr, flush=True)
    sys.exit(0)

with open(path, 'r') as f:
    content = f.read()

print(f'PATCH_CONFIG: config.yaml loaded, {len(content)} bytes', file=sys.stderr, flush=True)

# Idempotency: skip if already patched
if 'upstreams:' in content and 'refable' in content:
    print('PATCH_CONFIG: multi-upstream already configured', file=sys.stderr, flush=True)
else:
    old = '  upstream_base_url: "https://opencode.ai/zen/go/v1"\n  upstream_default_model: "deepseek-v4-flash"\n  upstream_models:\n    - "deepseek-v4-flash"'

    new = '  upstreams:\n    - name: "refable"\n      protocol: "openai"\n      base_url: "https://api.refable.ai/v1"\n      api_key_env: "OMBRE_GATEWAY_REFABLE_API_KEY"\n      default_model: "gemini-3.7-flash-tiered"\n      prompt_cache: ""\n      models:\n        - id: "gemini-flash"\n          upstream_model: "gemini-3.7-flash-tiered"\n    - name: "kiro"\n      protocol: "openai"\n      base_url: "https://hk.xn--0xv303ar5c.com/v1"\n      api_key_env: "OMBRE_GATEWAY_KIRO_API_KEY"\n      default_model: "[kiro量高缓]claude-opus-4-6"\n      prompt_cache: ""\n      models:\n        - id: "claude-opus"\n          upstream_model: "[kiro量高缓]claude-opus-4-6"'

    if old in content:
        content = content.replace(old, new, 1)
        print('PATCH_CONFIG: multi-upstream replaced', file=sys.stderr, flush=True)
    else:
        print('PATCH_CONFIG: WARN: upstream block not found (keeping existing upstreams)', file=sys.stderr, flush=True)

    content = content.replace('  prompt_cache: "openai"', '  prompt_cache: ""', 1)

with open(path, 'w') as f:
    f.write(content)

# ============================================================
# max_tokens 补丁（每次启动执行；只提低不降高）
# ============================================================
try:
    import yaml

    with open(path, 'r') as f:
        cfg = yaml.safe_load(f) or {}

    targets = [
        ("persona", "max_tokens", 4000),
        ("reflection", "max_tokens", 4000),
        ("dehydration", "max_tokens", 4000),
        ("dream", "max_tokens", 4000),
        ("reflection", "daily_chat_memory_summary_max_tokens", 4000),
        ("reflection", "daily_chat_memory_candidate_max_tokens", 4000),
        ("reflection", "daily_activity_summary_max_tokens", 4000),
        ("gateway", "domain_sentinel_max_tokens", 4000),
        ("gateway", "query_planner_max_tokens", 4000),
    ]

    changes = []
    for section, key, floor_value in targets:
        sec = cfg.get(section)
        if not isinstance(sec, dict):
            continue
        current = sec.get(key)
        if not isinstance(current, (int, float)) or current < floor_value:
            sec[key] = floor_value
            changes.append(f"{section}.{key}: {current} -> {floor_value}")

    if changes:
        with open(path, 'w') as f:
            yaml.dump(cfg, f, default_flow_style=False, allow_unicode=True, sort_keys=False)
        print('PATCH_CONFIG: max_tokens patched:', ', '.join(changes), file=sys.stderr, flush=True)
    else:
        print('PATCH_CONFIG: max_tokens already sufficient, no changes', file=sys.stderr, flush=True)
except Exception as e:
    print(f'PATCH_CONFIG: max_tokens patch FAILED: {e}', file=sys.stderr, flush=True)

print("========== PATCH_CONFIG.PY DONE ==========", file=sys.stderr, flush=True)
