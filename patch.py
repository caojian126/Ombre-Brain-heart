#!/usr/bin/env python3
"""
Startup patch（用户环境增强版 = 朋友 DCM 补丁 + enable_thinking 补丁）:
1. DCM fix in reflection_engine.py（朋友原版）
2. enable_thinking patches ×6 处（persona/dehydrator/reflection×3/dream/portrait）
   —— 修复 commandcode 中转站不认 {"thinking":{"type":...}} 旧格式、
      导致思考关不掉 → content 空返回的根因
"""

import os
import sys

print("========== PATCH.PY STARTING ==========", file=sys.stderr, flush=True)

patches_applied = 0
patches_failed = 0


def patch_text(code, old, new, label):
    global patches_applied, patches_failed
    if old not in code:
        print(f'PATCH: WARN: {label} not found', file=sys.stderr, flush=True)
        patches_failed += 1
        return code
    patches_applied += 1
    return code.replace(old, new, 1)


# ============================================================
# 1. DCM fix（reflection_engine.py）
# ============================================================
try:
    path = '/app/reflection_engine.py'
    with open(path, 'r') as f:
        code = f.read()

    code = patch_text(code,
        'confidence = self._clamp(candidate.get("confidence", 0.0))\n            threshold = self.daily_chat_memory_min_confidence if min_confidence is None else min_confidence',
        'confidence = self._clamp(candidate.get("confidence", 0.75))\n            threshold = self.daily_chat_memory_min_confidence if min_confidence is None else min_confidence',
        'confidence fix')

    code = patch_text(code,
        '            if self._daily_chat_memory_low_value_social_noise(content, kind):\n                continue\n',
        '            # low_value_social disabled for relationship deployment\n',
        'low_value_social fix')

    code = patch_text(code,
        '            if not kind or kind == "love_letter":\n                continue\n',
        '            if not kind:\n                kind = "key_event"\n            if kind == "love_letter":\n                continue\n',
        'bad_kind fix')

    with open(path, 'w') as f:
        f.write(code)
    print('PATCH: DCM fix applied', file=sys.stderr, flush=True)
except Exception as e:
    print(f'PATCH: DCM fix FAILED: {e}', file=sys.stderr, flush=True)

# ============================================================
# 2. enable_thinking patches（commandcode 中转站的思考关闭格式）
# ============================================================
ENABLE_THINKING_OLD_TAIL = '''        if self.thinking_mode:
            options["extra_body"] = {"thinking": {"type": self.thinking_mode}}'''
ENABLE_THINKING_NEW_TAIL = '''        if self.thinking_mode == "disabled":
            options["extra_body"] = {"enable_thinking": False}
        elif self.thinking_mode:
            options["extra_body"] = {"thinking": {"type": self.thinking_mode}}'''

THINK_PATCHES = [
    ("/app/persona_engine.py",
     ENABLE_THINKING_OLD_TAIL + '\n        if self.json_response_format:',
     ENABLE_THINKING_NEW_TAIL + '\n        if self.json_response_format:',
     "enable_thinking: persona_engine.py"),
    ("/app/dehydrator.py",
     ENABLE_THINKING_OLD_TAIL + '\n        return options',
     ENABLE_THINKING_NEW_TAIL + '\n        return options',
     "enable_thinking: dehydrator.py"),
    ("/app/reflection_engine.py",
     '''        mode = self.thinking_mode if thinking_mode is None else thinking_mode
        if mode:
            options["extra_body"] = {"thinking": {"type": mode}}
        return options''',
     '''        mode = self.thinking_mode if thinking_mode is None else thinking_mode
        if mode == "disabled":
            options["extra_body"] = {"enable_thinking": False}
        elif mode:
            options["extra_body"] = {"thinking": {"type": mode}}
        return options''',
     "enable_thinking: reflection_engine.py _completion_options"),
    ("/app/reflection_engine.py",
     'thinking_mode="" if use_dehydration else None,',
     'thinking_mode="disabled" if use_dehydration else None,',
     "enable_thinking: reflection_engine.py _api_reflect"),
    ("/app/reflection_engine.py",
     '''            completion_options = self._completion_options(
                max_tokens=max_tokens,
                temperature=temperature,
                thinking_mode="",
            )''',
     '''            completion_options = self._completion_options(
                max_tokens=max_tokens,
                temperature=temperature,
                thinking_mode="disabled",
            )''',
     "enable_thinking: reflection_engine.py _daily_chat_memory_create_completion"),
    ("/app/dream_engine.py",
     ENABLE_THINKING_OLD_TAIL + '\n        response = await self.client.chat.completions.create(**options)',
     ENABLE_THINKING_NEW_TAIL + '\n        response = await self.client.chat.completions.create(**options)',
     "enable_thinking: dream_engine.py"),
    ("/app/portrait_engine.py",
     ENABLE_THINKING_OLD_TAIL + '\n        return options',
     ENABLE_THINKING_NEW_TAIL + '\n        return options',
     "enable_thinking: portrait_engine.py"),
]

for patch_path, old, new, label in THINK_PATCHES:
    try:
        if not os.path.exists(patch_path):
            print(f'PATCH: WARN: {label} - file not found', file=sys.stderr, flush=True)
            patches_failed += 1
            continue
        with open(patch_path, 'r') as f:
            code = f.read()
        if old not in code:
            print(f'PATCH: WARN: {label} - pattern not found', file=sys.stderr, flush=True)
            patches_failed += 1
            continue
        code = code.replace(old, new, 1)
        with open(patch_path, 'w') as f:
            f.write(code)
        print(f'PATCH: OK: {label}', file=sys.stderr, flush=True)
        patches_applied += 1
    except Exception as e:
        print(f'PATCH: {label} FAILED: {e}', file=sys.stderr, flush=True)
        patches_failed += 1

print(f"========== PATCH.PY DONE (applied={patches_applied}, failed={patches_failed}) ==========", file=sys.stderr, flush=True)
