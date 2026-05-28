from __future__ import annotations

import re
from typing import Any

from .llm_config import chat_json


DEFAULT_SOURCE_ROW = {
    "日期": "2026-05-11",
    "序号": 1,
    "达人ID": "creator_001",
    "达人昵称": "示例达人",
    "蒲公英链接": "https://pgy.xiaohongshu.com/solar/pre-trade/blogger-detail/example",
    "主页链接": "https://www.xiaohongshu.com/user/profile/example",
    "小红书号": "example",
    "账号类型": "母婴/vlog",
    "达人类型": "母婴/vlog",
    "粉丝量级": "tier2",
    "达人量级": "tier2",
    "粉丝数": 86000,
    "粉丝数/w": 8.6,
    "粉丝量（w）": 8.6,
    "获赞与收藏": 520000,
    "赞藏数/w": 52,
    "赞藏量（w）": 52,
    "阅读中位数": 22000,
    "互动中位数": 1200,
    "曝光中位数": 88000,
    "近30天商单互动中位数": 900,
    "粉丝画像年龄": "25-34 40%；35-44 42%；35岁以上 50%",
    "粉丝女性用户占比": "92%",
    "粉丝年龄25-34占比": "40%",
    "粉丝年龄25-44占比": "82%",
    "25-44岁粉丝占比（25-34+35-44）": "82%",
    "粉丝年龄34岁以上占比": "50%",
    "35岁以上粉丝占比": "50%",
    "粉丝年龄34岁以上占比（35-44+44岁以上）": "50%",
    "35岁以上粉丝占比（35-44+44岁以上）": "50%",
    "粉丝年龄35-44占比": "42%",
    "粉丝年龄44岁以上占比": "8%",
    "孩子年级": "6-12岁",
    "孩子性别": "需人工获取",
    "图文报备价": 6000,
    "图文报备裸价": 6000,
    "图文报价": 6000,
    "图文笔记一口价": 6000,
    "平台报价": 6000,
    "报价": 6000,
    "视频报备价": 12000,
    "视频报备裸价": 12000,
    "视频报价": 12000,
    "视频笔记一口价": 12000,
    "图文执行价（含平台服务费）": 6600,
    "视频执行价（含平台服务费）": 13200,
    "合作价格（含服务费）": 6600,
    "视频完播率": "35%",
    "活跃粉丝占比": "70%",
    "预估cpe": 8,
    "预估CPE": 8,
    "预估cpm": 80,
    "预估CPM": 80,
    "CPE": 8,
    "cpe（不超过20，最好10以下）": 8,
    "粉丝画像": "runtime/pgy_detail_screenshots/example.png",
    "粉丝画像截图": "runtime/pgy_detail_screenshots/example.png",
    "笔记类型（视频or图文）": "视频or图文",
    "合作形式": "视频or图文",
    "推荐理由": "示例推荐理由",
    "推荐理由/项目契合点": "内容场景契合项目推广，适合做产品种草",
    "项目推广契合点": "内容场景契合项目推广，适合做产品种草",
    "达人契合该项目推广的地方": "内容场景契合项目推广，适合做产品种草",
    "品牌反馈": "",
    "品牌备注": "",
    "达人反馈": "",
    "SOLO备注": "",
    "客户备注": "",
    "没选中的原因": "",
}


def default_source_rows() -> list[dict[str, Any]]:
    return [dict(DEFAULT_SOURCE_ROW)]


def _field_name(field: dict[str, Any]) -> str:
    return str(field.get("field_name") or field.get("name") or field.get("title") or "").strip()


def _norm(value: str) -> str:
    text = str(value or "").lower()
    text = re.sub(r"\s+", "", text)
    text = re.sub(r"[()（）【】\\[\\]{}:：,，/、|｜;；<>=≤≥￥¥元%+＋\\-—_]", "", text)
    return text


def _sample_values(rows: list[dict[str, Any]], key: str, limit: int = 3) -> list[str]:
    values: list[str] = []
    for row in rows[:limit]:
        value = row.get(key)
        if value not in (None, ""):
            values.append(str(value))
    return values


def _available_sources(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    keys = sorted({str(key) for row in rows for key in row.keys() if not str(key).startswith("_")})
    return [{"field": key, "samples": _sample_values(rows, key)} for key in keys]


def _target_hints(target: str) -> list[str]:
    text = _norm(target)
    raw = str(target or "")
    hints: list[str] = []

    def add(*keys: str) -> None:
        for key in keys:
            if key not in hints:
                hints.append(key)

    if "序号" in text:
        add("序号")
    if "达人id" in text or "博主id" in text:
        add("达人ID")
    if "昵称" in text or "博主名称" in text:
        add("达人昵称")
    if "蒲公英" in text and "链接" in text:
        add("蒲公英链接")
    if "主页链接" in text or "小红书主页" in text:
        add("主页链接")
    if "小红书号" in text:
        add("小红书号")
    if "账号类型" in text or "达人类型" in text or "博主类目" in text:
        add("账号类型", "达人类型")
    if "粉丝量级" in text or "达人量级" in text:
        add("达人量级", "粉丝量级")
    if "粉丝数" in text or "粉丝量" in text:
        if "w" in raw.lower() or "万" in raw:
            add("粉丝数/w", "粉丝量（w）")
        add("粉丝数")
    if "赞藏" in text or "获赞收藏" in text or "获赞与收藏" in text:
        if "w" in raw.lower() or "万" in raw:
            add("赞藏数/w", "赞藏量（w）")
        add("获赞与收藏")
    if "孩子年级" in text or "母婴阶段" in text or "孩子阶段" in text:
        add("孩子年级")
    if "孩子性别" in text:
        add("孩子性别")
    if "女性" in text and "粉丝" in text:
        add("粉丝女性用户占比")
    wants_25_to_44 = (
        "2544" in text
        or "25-44" in raw
        or "25~44" in raw
        or "25～44" in raw
        or "25至44" in raw
        or "25到44" in raw
    )
    if wants_25_to_44:
        add("25-44岁粉丝占比（25-34+35-44）", "粉丝年龄25-44占比")
    elif "2534" in text or "25-34" in raw or "25～34" in raw:
        add("粉丝年龄25-34占比")
    if "34岁以上" in text or "35岁以上" in text or "35以上" in text:
        add("粉丝年龄34岁以上占比（35-44+44岁以上）", "35岁以上粉丝占比（35-44+44岁以上）", "粉丝年龄34岁以上占比", "35岁以上粉丝占比")
    if "粉丝画像" in text:
        add("粉丝画像", "粉丝画像截图")
    if "图文" in text and ("执行价" in text or "服务费" in text):
        add("图文执行价（含平台服务费）")
    elif "图文" in text and ("报备" in text or "裸价" in text or "报价" in text):
        add("图文报价", "图文笔记一口价", "图文报备价", "图文报备裸价", "平台报价")
    elif "图文" in text and "一口价" in text:
        add("图文笔记一口价", "图文报价", "图文报备价")
    if "视频" in text and ("执行价" in text or "服务费" in text):
        add("视频执行价（含平台服务费）")
    elif "视频" in text and ("报备" in text or "裸价" in text or "报价" in text):
        add("视频报价", "视频笔记一口价", "视频报备价", "视频报备裸价")
    elif "视频" in text and "一口价" in text:
        add("视频笔记一口价", "视频报价", "视频报备价")
    if "平台报价" in text or text == "报价":
        add("平台报价", "报价")
    if "合作价格" in text:
        add("合作价格（含服务费）", "图文执行价（含平台服务费）")
    if "完播率" in text:
        add("视频完播率")
    if "活跃粉丝" in text:
        add("活跃粉丝占比")
    if "商单" in text and "互动中位数" in text:
        add("近30天商单互动中位数", "互动中位数（合作）")
    elif "互动中位数" in text:
        add("互动中位数", "互动中位数（日常）")
    if "阅读中位数" in text:
        add("阅读中位数", "阅读中位数（日常）")
    if "曝光中位数" in text:
        add("曝光中位数", "曝光中位数（日常）")
    if "预估cpe" in text or text == "cpe" or "自然cpe" in text:
        add("预估cpe", "合作笔记自然CPE", "cpe（不超过20，最好10以下）")
    if "预估cpm" in text:
        add("预估cpm")
    if "笔记类型" in text:
        add("笔记类型（视频or图文）", "合作形式")
    if "推荐理由" in text or "推荐原因" in text:
        add("推荐理由", "推荐理由/项目契合点", "项目推广契合点", "达人契合该项目推广的地方", "备注")
    if ("契合" in text and ("项目" in text or "推广" in text)) or ("适合" in text and "推广" in text):
        add("达人契合该项目推广的地方", "项目推广契合点", "推荐理由/项目契合点", "推荐理由")
    if "品牌反馈" in text or "确认是否合作" in text:
        add("品牌反馈", "品牌确认是否合作")
    if "品牌备注" in text:
        add("品牌备注")
    if "客户备注" in text:
        add("客户备注")
    if "达人反馈" in text:
        add("达人反馈")
    if "solo备注" in text:
        add("SOLO备注")
    if "没选中" in text or "没选中的原因" in text:
        add("没选中的原因")
    if "日期" in text:
        add("日期")
    return hints


def _fallback_mapping(target_fields: list[str], rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    source_keys = sorted({str(key) for row in rows for key in row.keys()})
    by_norm = {_norm(key): key for key in source_keys}
    mappings: list[dict[str, Any]] = []
    for target in target_fields:
        source = by_norm.get(_norm(target))
        reason = "字段名一致"
        if not source:
            for hint in _target_hints(target):
                source = by_norm.get(_norm(hint))
                if source:
                    reason = f"同义字段：{hint}"
                    break
        if not source:
            target_norm = _norm(target)
            for key in source_keys:
                key_norm = _norm(key)
                if key_norm and (key_norm in target_norm or target_norm in key_norm):
                    source = key
                    reason = "字段名模糊包含"
                    break
        if source:
            mappings.append(
                {
                    "target_field": target,
                    "source_field": source,
                    "confidence": 0.86 if reason != "字段名一致" else 0.99,
                    "reason": reason,
                }
            )
    return mappings


def _llm_mapping(target_fields: list[str], rows: list[dict[str, Any]]) -> dict[str, Any]:
    sources = _available_sources(rows)
    result = chat_json(
        [
            {
                "role": "system",
                "content": (
                    "你是飞书表格字段映射 agent。你的任务是把目标表头映射到工具可提供的数据源字段。"
                    "只输出 JSON，不要输出解释文字。"
                ),
            },
            {
                "role": "user",
                "content": (
                    "请分析目标飞书表头和可用数据源字段，判断哪些字段是同一个意思或可直接写入。"
                    "注意粉丝年龄分布：目标字段“25-44岁占比/粉丝年龄25~44占比”应优先匹配"
                    "“25-44岁粉丝占比（25-34+35-44）”或“粉丝年龄25-44占比”，"
                    "它是 25-34 占比和 35-44 占比的合计。"
                    "目标字段“粉丝年龄34岁以上占比/35岁以上占比”应优先匹配"
                    "“粉丝年龄34岁以上占比（35-44+44岁以上）”或“35岁以上粉丝占比（35-44+44岁以上）”，"
                    "它是 35-44 占比和 44岁以上占比的合计，不要只映射到单独的 35-44 占比。"
                    "不要臆造 source_field；source_field 必须来自 available_sources.field。"
                    "如果目标字段是人工决策/客户备注且没有数据源，不要映射。\n"
                    "输出格式：{\"mappings\":[{\"target_field\":\"目标表头\",\"source_field\":\"数据源字段\",\"confidence\":0.0,\"reason\":\"简短原因\"}],"
                    "\"unmatched\":[{\"target_field\":\"目标表头\",\"reason\":\"为什么暂不映射\"}]}。\n"
                    f"target_fields={target_fields}\n"
                    f"available_sources={sources}"
                ),
            },
        ],
        config={"max_tokens": 2600, "temperature": 0.1},
    )
    return result


def analyze_field_mapping(
    target_fields: list[str],
    rows: list[dict[str, Any]],
    *,
    use_llm: bool = False,
) -> dict[str, Any]:
    fallback = _fallback_mapping(target_fields, rows)
    fallback_by_target = {item["target_field"]: item for item in fallback}
    source_keys = {str(key) for row in rows for key in row.keys()}
    llm_items: list[dict[str, Any]] = []
    error = ""
    source = "fallback"
    if use_llm and rows:
        try:
            result = _llm_mapping(target_fields, rows)
            for item in result.get("mappings") or []:
                target = str(item.get("target_field") or "").strip()
                source_field = str(item.get("source_field") or "").strip()
                try:
                    confidence = float(item.get("confidence") or 0)
                except (TypeError, ValueError):
                    confidence = 0
                if target in target_fields and source_field in source_keys and confidence >= 0.55:
                    llm_items.append(
                        {
                            "target_field": target,
                            "source_field": source_field,
                            "confidence": confidence,
                            "reason": str(item.get("reason") or "模型语义匹配"),
                        }
                    )
            if llm_items:
                source = "llm"
        except Exception as exc:
            error = str(exc)

    merged = dict(fallback_by_target)
    for item in llm_items:
        fallback_item = merged.get(item["target_field"])
        if not fallback_item or item["confidence"] >= float(fallback_item.get("confidence") or 0):
            merged[item["target_field"]] = item
    mappings = [merged[target] for target in target_fields if target in merged]
    matched_targets = {item["target_field"] for item in mappings}
    unmatched = [{"target_field": field, "reason": "没有找到可靠数据源字段"} for field in target_fields if field not in matched_targets]
    return {
        "source": source,
        "mappings": mappings,
        "unmatched": unmatched,
        "fallback_count": len(fallback),
        "llm_count": len(llm_items),
        "error": error,
    }


def apply_field_mapping(
    rows: list[dict[str, Any]],
    fields: list[dict[str, Any]],
    *,
    use_llm: bool = False,
    mapping_plan: dict[str, Any] | None = None,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    target_fields = [_field_name(field) for field in fields]
    target_fields = [field for field in target_fields if field]
    plan = mapping_plan if isinstance(mapping_plan, dict) and mapping_plan.get("mappings") else analyze_field_mapping(target_fields, rows, use_llm=use_llm)
    mapping = {item["target_field"]: item["source_field"] for item in plan["mappings"]}
    mapped_rows: list[dict[str, Any]] = []
    for row in rows:
        mapped: dict[str, Any] = {}
        for target in target_fields:
            source = mapping.get(target)
            if source:
                value = row.get(source)
            else:
                value = row.get(target, "")
            mapped[target] = "" if value is None else value
        mapped_rows.append(mapped)
    return mapped_rows, plan
