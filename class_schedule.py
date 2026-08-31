#!/usr/bin/env python3
"""课程表模块 —— 高中生课程表查询与摘要。

数据源：config.yaml 的 class_schedule 段（dashboard 课程表 tab 可视化编辑，
server 持久化写入本文件；gateway / server 两进程通过文件 mtime 缓存自动同步，
改完课表无需重启）。

对 work_shift（朋友版排班）的替代：接口风格保持一致，但数据来自配置而非硬编码。

config 结构：
class_schedule:
  enabled: true            # 总开关，false 时所有摘要返回空串
  owner: "小如"            # 称呼（可选，用于文案）
  term_start: "2026-09-01" # 开学日期（可选，预留学期周次计算）
  weekly:                  # 每周课表，键 mon/tue/wed/thu/fri/sat/sun
    mon:
      - {name: 早自习, start: "07:30", end: "08:00"}
      - {name: 语文,   start: "08:10", end: "08:55"}
  overrides:               # 特殊日期覆盖（放假/考试/调课）
    "2026-10-01": {label: 国庆假期, kind: holiday}
"""

from __future__ import annotations

import os
from datetime import date, datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

import yaml

LOCAL_TZ = ZoneInfo(os.environ.get("OMBRE_TZ", "Asia/Shanghai"))
CONFIG_PATH = os.environ.get("OMBRE_CONFIG_PATH", "/app/config.yaml")

WEEKDAY_KEYS = ("mon", "tue", "wed", "thu", "fri", "sat", "sun")
WEEKDAY_NAMES = ("周一", "周二", "周三", "周四", "周五", "周六", "周日")

# 标准高中默认模板（周一~周五相同；可在 dashboard 课程表 tab 任意修改）
_DEFAULT_DAY = [
    {"name": "早自习", "start": "07:30", "end": "08:00"},
    {"name": "第1节", "start": "08:10", "end": "08:55"},
    {"name": "第2节", "start": "09:05", "end": "09:50"},
    {"name": "第3节", "start": "10:10", "end": "10:55"},
    {"name": "第4节", "start": "11:05", "end": "11:50"},
    {"name": "午休", "start": "12:00", "end": "14:00"},
    {"name": "第5节", "start": "14:30", "end": "15:15"},
    {"name": "第6节", "start": "15:25", "end": "16:10"},
    {"name": "第7节", "start": "16:20", "end": "17:05"},
]

_DEFAULT_DATA: dict[str, Any] = {
    "enabled": True,
    "owner": "",
    "term_start": "",
    "weekly": {key: (list(_DEFAULT_DAY) if key in ("mon", "tue", "wed", "thu", "fri") else []) for key in WEEKDAY_KEYS},
    "overrides": {},
}

_cache: dict[str, Any] = {"mtime": None, "data": None}


def _load() -> dict[str, Any]:
    """读取 config.yaml 的 class_schedule 段；mtime 未变时用缓存。"""
    try:
        mtime = os.stat(CONFIG_PATH).st_mtime
    except OSError:
        return dict(_DEFAULT_DATA)
    if _cache["data"] is not None and _cache["mtime"] == mtime:
        return _cache["data"]
    data: dict[str, Any] = {}
    try:
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            cfg = yaml.safe_load(f) or {}
        section = cfg.get("class_schedule")
        if isinstance(section, dict):
            data = section
    except Exception:
        data = {}
    if not data:
        data = {}
    _cache["mtime"] = mtime
    _cache["data"] = data
    return data


def reload() -> None:
    """强制丢弃缓存，下次调用重新读文件。"""
    _cache["mtime"] = None
    _cache["data"] = None


def _hm(value: Any) -> str:
    """规整时间为 HH:MM，非法返回空串。"""
    text = str(value or "").strip()
    if len(text) >= 4 and text.count(":") >= 1:
        try:
            parts = text.split(":")
            return f"{int(parts[0]):02d}:{int(parts[1]):02d}"
        except (ValueError, IndexError):
            return ""
    return ""


def _sorted_items(raw: Any) -> list[dict[str, str]]:
    """规整一天的课程列表：只留有效项，按开始时间排序。"""
    items: list[dict[str, str]] = []
    if not isinstance(raw, list):
        return items
    for entry in raw:
        if not isinstance(entry, dict):
            continue
        name = str(entry.get("name") or "").strip()
        start = _hm(entry.get("start"))
        end = _hm(entry.get("end"))
        if not name or not start or not end:
            continue
        items.append({"name": name, "start": start, "end": end})
    items.sort(key=lambda item: item["start"])
    return items


def _day_key(d: date) -> str:
    return WEEKDAY_KEYS[d.weekday()]


def _override_for(d: date, data: dict[str, Any]) -> dict[str, Any] | None:
    overrides = data.get("overrides")
    if not isinstance(overrides, dict):
        return None
    entry = overrides.get(d.isoformat())
    return entry if isinstance(entry, dict) else None


def schedule_for_date(d: date) -> dict[str, Any]:
    """某天的课表。返回 {date, weekday, items, override}。"""
    data = _load()
    override = _override_for(d, data)
    if override is not None:
        label = str(override.get("label") or "").strip()
        kind = str(override.get("kind") or "special").strip()
        return {"date": d.isoformat(), "weekday": WEEKDAY_NAMES[d.weekday()], "items": [], "override": {"label": label, "kind": kind}}
    weekly = data.get("weekly")
    raw = weekly.get(_day_key(d)) if isinstance(weekly, dict) else None
    return {
        "date": d.isoformat(),
        "weekday": WEEKDAY_NAMES[d.weekday()],
        "items": _sorted_items(raw),
        "override": None,
    }


def _current_status(items: list[dict[str, str]], now_hm: str) -> str:
    """根据当前时间生成节次状态文案。"""
    for index, item in enumerate(items):
        if item["start"] <= now_hm < item["end"]:
            return f"当前第{index + 1}项 {item['name']} 进行中（{item['end']} 结束）"
    for item in items:
        if now_hm < item["start"]:
            return f"课间休息，{item['start']} 开始下一项 {item['name']}"
    return "今天课程已全部结束"


def today_summary(now: datetime | None = None) -> str:
    """今天的课表摘要（gateway 每轮注入 / MCP 无参查询）。禁用时返回空串。"""
    data = _load()
    if data.get("enabled") is False:
        return ""
    if now is None:
        now = datetime.now(LOCAL_TZ)
    info = schedule_for_date(now.date())
    owner = str(data.get("owner") or "").strip()
    owner_prefix = f"{owner}的" if owner else ""
    if info["override"] is not None:
        label = info["override"].get("label") or "特殊安排"
        return f"今天{info['weekday']}，{owner_prefix}课程表：{label}（无常规课程）"
    items = info["items"]
    if not items:
        return f"今天{info['weekday']}，{owner_prefix}课表没有课程安排（休息日）"
    now_hm = now.strftime("%H:%M")
    status = _current_status(items, now_hm)
    items_text = "、".join(f"{item['start']}{item['name']}" for item in items)
    return (
        f"今天{info['weekday']}，{owner_prefix}课表：{status}。"
        f"今日安排：{items_text}（{items[-1]['end']} 结束）"
    )


def range_summary(start: date, days: int = 7) -> str:
    """从 start 起连续 days 天的课表概览（MCP 查询用）。"""
    data = _load()
    if data.get("enabled") is False:
        return "课程表功能未启用。"
    days = max(1, min(int(days or 7), 90))
    owner = str(data.get("owner") or "").strip()
    owner_prefix = f"{owner}的" if owner else ""
    lines: list[str] = []
    for offset in range(days):
        d = start + timedelta(days=offset)
        info = schedule_for_date(d)
        if info["override"] is not None:
            label = info["override"].get("label") or "特殊安排"
            lines.append(f"{info['date']}（{info['weekday']}）{label}")
        elif not info["items"]:
            lines.append(f"{info['date']}（{info['weekday']}）无课程安排")
        else:
            items_text = "、".join(f"{item['start']}{item['name']}" for item in info["items"])
            lines.append(f"{info['date']}（{info['weekday']}）{items_text}")
    return f"{owner_prefix}课程表：\n" + "\n".join(lines)


def term_week(d: date | None = None) -> int | None:
    """开学第几周（按 term_start 所在周为第 1 周）；未配置返回 None。"""
    data = _load()
    term_start = str(data.get("term_start") or "").strip()
    if not term_start:
        return None
    try:
        start = date.fromisoformat(term_start)
    except ValueError:
        return None
    if d is None:
        d = datetime.now(LOCAL_TZ).date()
    delta = (d - start).days
    if delta < 0:
        return None
    return delta // 7 + 1
