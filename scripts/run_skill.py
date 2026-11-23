#!/usr/bin/env python3
"""Research proposal planner: questions, routes, milestones, risks.

Reads a case JSON (default /input/case.json) and writes a structured
plan audit (default /app/output/result.json). Standard library only,
no network, deterministic. Source text is preserved; the script only
indexes, normalizes visible time expressions and flags missing parts.
"""

import argparse
import hashlib
import json
import os
import re
import sys

SECTION_DEFS = [
    ("background", ("研究背景", "立题依据", "background", "introduction")),
    ("question", ("研究问题", "科学问题", "研究假设", "research question", "hypothesis")),
    ("objectives", ("研究目标", "目标", "objectives", "aims")),
    ("route", ("技术路线", "研究方法", "研究方案", "methodology", "technical route", "approach")),
    ("schedule", ("阶段计划", "时间安排", "进度安排", "研究计划", "timeline", "schedule", "work plan")),
    ("risks", ("风险", "应对", "risk", "contingency")),
    ("outcomes", ("预期成果", "预期结果", "交付物", "deliverables", "expected outcomes")),
]
TESTABLE_MARKERS = ("是否", "比较", "影响", "关系", "相关", "预测", "差异", "阈值", "样本",
                    "时间点", "对照", "whether", "compare", "association", "predict",
                    "difference", "threshold", "effect")
VAGUE_MARKERS = ("探讨", "分析", "研究", "了解", "梳理", "explore", "investigate", "study")
RISK_CLASSES = {
    "data": ("数据", "样本", "缺失", "获取", "data", "sample", "missing"),
    "method": ("方法", "模型", "技术", "可行性", "method", "model", "feasib"),
    "schedule": ("进度", "延期", "时间", "周期", "schedule", "delay", "timeline"),
    "ethics": ("伦理", "知情", "隐私", "合规", "ethic", "consent", "privacy"),
}
TRIGGER = ("触发", "信号", "若", "一旦", "如果", "当…时", "when", "if ", "trigger")
FALLBACK = ("备选", "替代", "否则", "退路", "fallback", "alternative", "plan b", "contingenc")
ITEM_RE = re.compile(r"^\s*(?:\(?\d+[\)\.、]|（\d+）|[一二三四五六七八九十]+[、.]|[-*•])\s*(.+)$")


def load_json(path):
    with open(path, "r", encoding="utf-8-sig") as fh:
        return json.load(fh)


def sha256_text(text):
    return hashlib.sha256((text or "").encode("utf-8")).hexdigest()


def norm(text):
    return re.sub(r"\s+", " ", text or "").strip()


def read_text(value):
    if not isinstance(value, str) or "\n" in value or len(value) > 4096:
        return None
    if os.path.isfile(value) and os.path.getsize(value) <= 2 * 1024 * 1024:
        try:
            with open(value, "r", encoding="utf-8-sig") as fh:
                return fh.read()
        except (OSError, UnicodeDecodeError):
            return None
    return None


def collect_text(case):
    parts, unreadable = [], []

    def walk(node, label):
        if isinstance(node, str):
            text = read_text(node)
            if text is not None:
                parts.append({"label": label, "text": text, "path": node})
            elif len(node.strip()) >= 40:
                parts.append({"label": label, "text": node, "path": None})
            return
        if isinstance(node, dict):
            path = node.get("path") or node.get("file") or node.get("filename")
            if isinstance(path, str):
                text = read_text(path)
                if text is not None:
                    parts.append({"label": label, "text": text, "path": path})
                    return
                if os.path.isfile(path):
                    unreadable.append({"label": label, "path": path})
                    return
            for key in ("content", "text", "body", "markdown", "proposal", "plan", "value"):
                if key in node and isinstance(node[key], (str, list, dict)):
                    walk(node[key], "%s.%s" % (label, key))
                    return
            for key, value in node.items():
                if key in ("id", "name", "title", "type", "kind", "path", "file", "filename"):
                    continue
                walk(value, "%s.%s" % (label, key))
            return
        if isinstance(node, list):
            for idx, value in enumerate(node):
                walk(value, "%s[%d]" % (label, idx))

    for key, value in case.items():
        if key in ("output_contract", "scoring", "tags", "meta", "case_id", "challenge_id"):
            continue
        walk(value, key)
    return parts, unreadable


def heading_of(line):
    cleaned = re.sub(r"^\s*#{1,6}\s*", "", line.strip())
    cleaned = re.sub(r"^\s*(?:[一二三四五六七八九十]+[、.]|（[一二三四五六七八九十]+）|\(?\d+[\)\.、])\s*", "", cleaned)
    if not cleaned or len(cleaned) > 40:
        return None
    lowered = cleaned.lower()
    for name, keywords in SECTION_DEFS:
        if any(keyword in lowered for keyword in keywords):
            return name
    return None


def split_sections(text):
    sections = {name: [] for name, _ in SECTION_DEFS}
    sections["other"] = []
    current, buffer = None, []

    def flush():
        if buffer and current is not None:
            body = "\n".join(buffer).strip()
            if body:
                sections[current].append(body)

    for line in text.splitlines():
        name = heading_of(line)
        if name:
            flush()
            buffer = []
            current = name
        else:
            buffer.append(line)
    flush()
    return sections


def split_items(blocks):
    items = []
    for block in blocks:
        matched = False
        for line in block.splitlines():
            match = ITEM_RE.match(line)
            if match:
                items.append(match.group(1).strip())
                matched = True
        if matched:
            continue
        for sentence in re.split(r"(?<=[。；;！!？?])", block):
            sentence = sentence.strip()
            if len(sentence) >= 10:
                items.append(sentence)
    seen, unique = set(), []
    for item in items:
        key = norm(item).lower()
        if key not in seen:
            seen.add(key)
            unique.append(item)
    return unique


def content_tokens(text):
    tokens = set(re.findall(r"[A-Za-z]{3,}", text.lower()))
    for run in re.findall(r"[\u4e00-\u9fff]{2,}", text):
        for idx in range(len(run) - 1):
            tokens.add(run[idx:idx + 2])
    return tokens


def overlap(left, right):
    if not left or not right:
        return 0.0
    return len(left & right) / float(min(len(left), len(right)))


def parse_time(text):
    """Return (start_month, end_month, raw, rule) or None. Months may be absolute."""
    patterns = [
        (r"第\s*(\d+)\s*[-~\u2014\u81f3]\s*(\d+)\s*个?月", "cn_month_range"),
        (r"第\s*(\d+)\s*[-~\u2014\u81f3]\s*(\d+)\s*季度", "cn_quarter_range"),
        (r"第\s*(\d+)\s*季度", "cn_quarter"),
        (r"第\s*(\d+)\s*个?月", "cn_month"),
        (r"\bQ([1-4])\b", "q"),
        (r"month\s*(\d+)\s*(?:-|to|\u2013)\s*(\d+)", "en_month_range"),
        (r"month\s*(\d+)", "en_month"),
    ]
    for pattern, rule in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if not match:
            continue
        if rule in ("cn_month_range", "en_month_range"):
            start, end = int(match.group(1)), int(match.group(2))
            return start, end, match.group(0), rule
        if rule == "cn_quarter_range":
            return 3 * int(match.group(1)) - 2, 3 * int(match.group(2)), match.group(0), rule
        if rule in ("cn_quarter", "q"):
            quarter = int(match.group(1))
            return 3 * quarter - 2, 3 * quarter, match.group(0), rule
        value = int(match.group(1))
        return value, value, match.group(0), rule
    match = re.search(r"(\d{4})\s*[-\u5e74./]\s*(\d{1,2})", text)
    if match:
        absolute = int(match.group(1)) * 12 + int(match.group(2))
        return absolute, absolute, match.group(0), "calendar"
    for word, months in (("上半年", (1, 6)), ("下半年", (7, 12)), ("全年", (1, 12))):
        if word in text:
            return months[0], months[1], word, "cn_half"
    return None


def classify_risk(text):
    lowered = text.lower()
    scores = {name: sum(1 for marker in markers if marker in lowered)
              for name, markers in RISK_CLASSES.items()}
    best = max(scores, key=lambda key: scores[key])
    return best if scores[best] > 0 else "other"


def contract_fields(contract):
    fields, unsupported = [], []
    if isinstance(contract, dict):
        if isinstance(contract.get("properties"), dict):
            return list(contract["properties"].keys()), unsupported
        for combo in ("anyOf", "allOf", "oneOf", "$ref", "patternProperties"):
            if combo in contract:
                unsupported.append(combo)
        nested = contract.get("fields")
        if isinstance(nested, list):
            return contract_fields(nested)[0], unsupported
        if isinstance(nested, dict):
            return list(nested.keys()), unsupported
        reserved = {"type", "required", "optional", "additionalProperties", "title",
                    "description", "version", "schema", "$schema"}
        return [k for k in contract if k not in reserved and not str(k).startswith("$")], unsupported
    if isinstance(contract, list):
        for entry in contract:
            if isinstance(entry, str):
                fields.append(entry)
            elif isinstance(entry, dict):
                name = entry.get("name") or entry.get("field") or entry.get("key")
                if name:
                    fields.append(str(name))
        return fields, unsupported
    return fields, unsupported


ALIASES = {
    "status": "status", "question_register": "question_register", "questions": "question_register",
    "objective_route_map": "objective_route_map", "objectives": "objective_route_map",
    "milestone_schedule": "milestone_schedule", "milestones": "milestone_schedule",
    "timeline": "milestone_schedule", "risk_register": "risk_register", "risks": "risk_register",
    "deliverable_checklist": "deliverable_checklist", "deliverables": "deliverable_checklist",
    "gaps": "gaps", "evidence": "evidence", "sources": "sources",
    "uncertainty": "uncertainty", "uncertainties": "uncertainty",
    "limitations": "limitations", "stats": "stats", "metrics": "stats", "summary": "stats",
    "proposal": "plan_text", "plan_text": "plan_text",
}


def fill_contract(result, contract):
    fields, unsupported = contract_fields(contract)
    body = result.get("result") if isinstance(result.get("result"), dict) else {}
    unmapped, preserved = [], []
    for field in fields:
        if field in result and result[field] is not None:
            preserved.append(field)
            continue
        key = ALIASES.get(field.lower(), field.lower())
        if key in result and result[key] is not None:
            result[field] = result[key]
            preserved.append(field)
        elif key in body and body[key] is not None:
            result[field] = body[key]
            preserved.append(field)
        else:
            result[field] = None
            unmapped.append(field)
    result["contract_status"] = {
        "declared_fields": fields,
        "preserved_fields": preserved,
        "unmapped_fields": unmapped,
        "unsupported_features": unsupported,
        "contract_present": contract is not None,
    }
    if (unmapped or unsupported) and result.get("status") == "success":
        result["status"] = "partial"


def write_json(path, payload):
    directory = os.path.dirname(os.path.abspath(path))
    if directory:
        os.makedirs(directory, exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, ensure_ascii=False, indent=2)
        fh.write("\n")


def main():
    parser = argparse.ArgumentParser(description="Research proposal planning audit")
    parser.add_argument("--case", default="/input/case.json")
    parser.add_argument("--out", "--output", default="/app/output/result.json")
    parser.add_argument("--work", default="/app/work")
    args = parser.parse_args()

    result = {
        "case_id": None,
        "status": "failed",
        "result": {
            "question_register": [],
            "objective_route_map": {"matrix": [], "gaps": []},
            "milestone_schedule": [],
            "risk_register": [],
            "deliverable_checklist": [],
            "gaps": [],
            "plan_text": "",
        },
        "evidence": [],
        "uncertainty": [],
        "errors": [],
        "stats": {},
    }
    try:
        case = load_json(args.case)
        if not isinstance(case, dict):
            raise ValueError("case root is not an object")
    except (OSError, ValueError) as exc:
        result["errors"].append({"stage": "read_case", "type": type(exc).__name__,
                                 "detail": "case.json missing or not valid JSON"})
        write_json(args.out, result)
        return 2

    result["case_id"] = case.get("case_id") or case.get("id") or case.get("challenge_id")
    contract = case.get("output_contract")
    parts, unreadable = collect_text(case)

    if not parts:
        result["status"] = "insufficient_input"
        result["uncertainty"].append({"item": "plan", "detail": "no_plan_text_found"})
        result["limitations"] = ["Plan text is required; nothing was supplied."]
        fill_contract(result, contract)
        write_json(args.out, result)
        return 0

    parts.sort(key=lambda item: len(item["text"]), reverse=True)
    text = parts[0]["text"]
    sections = split_sections(text)
    found = [name for name, blocks in sections.items() if blocks and name != "other"]

    question_items = split_items(sections.get("question", []))
    for block in sections.get("other", []):
        for sentence in re.split(r"(?<=[。；;！!？?])", block):
            if "?" in sentence or "？" in sentence:
                question_items.append(sentence.strip())
    objectives = split_items(sections.get("objectives", []))
    routes = split_items(sections.get("route", []))
    outcomes = split_items(sections.get("outcomes", []))

    questions = []
    gaps = []
    for idx, item in enumerate(question_items[:12]):
        lowered = item.lower()
        testable = any(marker in lowered for marker in TESTABLE_MARKERS)
        vague = any(marker in lowered for marker in VAGUE_MARKERS) and not testable
        questions.append({
            "id": "Q%d" % (idx + 1),
            "text": item,
            "testable": bool(testable),
            "issue": None if testable else ("vague_question" if vague else "missing_decision_rule"),
            "needed": None if testable else "state comparison, outcome, threshold or time point",
        })
    if not questions:
        gaps.append({"type": "no_research_question", "action": "add 1-3 answerable questions"})

    matrix = []
    used_route = set()
    for idx, objective in enumerate(objectives):
        best, best_score = None, 0.0
        for r_idx, route in enumerate(routes):
            score = overlap(content_tokens(objective), content_tokens(route))
            if score > best_score:
                best, best_score = r_idx, score
        if best is not None and best_score >= 0.15:
            used_route.add(best)
            matrix.append({"objective_id": "O%d" % (idx + 1), "objective_text": objective,
                           "route_id": "R%d" % (best + 1), "route_text": routes[best],
                           "score": round(best_score, 3), "linked": True})
        else:
            matrix.append({"objective_id": "O%d" % (idx + 1), "objective_text": objective,
                           "route_id": None, "score": round(best_score, 3), "linked": False})
            gaps.append({"type": "objective_without_route", "target": "O%d" % (idx + 1)})
    for r_idx, route in enumerate(routes):
        if r_idx not in used_route:
            gaps.append({"type": "route_without_objective", "target": "R%d" % (r_idx + 1)})
    for idx, outcome in enumerate(outcomes):
        if not any(overlap(content_tokens(outcome), content_tokens(route)) >= 0.15 for route in routes):
            gaps.append({"type": "deliverable_without_route", "target": "D%d" % (idx + 1)})

    duration = case.get("duration_months") or case.get("duration") or case.get("period_months")
    try:
        duration = int(duration) if duration is not None else None
    except (TypeError, ValueError):
        duration = None

    schedule, timeline_conflicts, ambiguous = [], [], []
    for item in split_items(sections.get("schedule", [])):
        parsed = parse_time(item)
        if not parsed:
            ambiguous.append({"text": item})
            continue
        start, end, raw, rule = parsed
        if start > end:
            start, end = end, start
        schedule.append({"text": item, "raw_time": raw, "rule": rule,
                         "start_month": start, "end_month": end})
    if schedule and schedule[0]["rule"] == "calendar":
        base = min(entry["start_month"] for entry in schedule)
        for entry in schedule:
            entry["start_month"] -= base - 1
            entry["end_month"] -= base - 1
    schedule.sort(key=lambda entry: (entry["start_month"], entry["end_month"]))
    for idx in range(1, len(schedule)):
        previous, current = schedule[idx - 1], schedule[idx]
        if current["start_month"] < previous["end_month"]:
            timeline_conflicts.append({"previous": previous["text"], "current": current["text"],
                                       "detail": "overlapping_or_out_of_order"})
    if duration:
        for entry in schedule:
            if entry["end_month"] > duration:
                timeline_conflicts.append({"text": entry["text"],
                                           "detail": "exceeds_declared_duration",
                                           "declared": duration})
    counts = {}
    for entry in schedule:
        for month in range(entry["start_month"], entry["end_month"] + 1):
            counts[month] = counts.get(month, 0) + 1
    crowded_months = sorted(month for month, count in counts.items() if count > 3)

    risk_items = split_items(sections.get("risks", []))
    risks = []
    for idx, item in enumerate(risk_items):
        lowered = item.lower()
        has_trigger = any(marker in lowered for marker in TRIGGER)
        has_fallback = any(marker in lowered for marker in FALLBACK)
        issues = []
        if not has_trigger:
            issues.append("missing_trigger")
        if not has_fallback:
            issues.append("missing_fallback")
        risks.append({"id": "RK%d" % (idx + 1), "text": item,
                      "category": classify_risk(item),
                      "has_trigger": has_trigger, "has_fallback": has_fallback,
                      "issues": issues})

    result["result"]["plan_text"] = text
    result["result"]["question_register"] = questions
    result["result"]["objective_route_map"] = {"matrix": matrix, "gaps": gaps}
    result["result"]["milestone_schedule"] = schedule
    result["result"]["risk_register"] = risks
    result["result"]["gaps"] = gaps
    result["result"]["deliverable_checklist"] = [
        {"id": "D%d" % (idx + 1), "text": item, "route_linked": any(
            overlap(content_tokens(item), content_tokens(route)) >= 0.15 for route in routes)}
        for idx, item in enumerate(outcomes)
    ]
    result["result"]["sources"] = [
        {"label": item["label"], "path": item["path"],
         "chars": len(item["text"]), "sha256": sha256_text(item["text"])} for item in parts
    ]
    result["evidence"] = [
        {"section": name, "paragraph_index": idx + 1, "snippet": norm(block)[:160]}
        for name, blocks in sections.items() for idx, block in enumerate(blocks)
    ][:80]
    if ambiguous:
        result["uncertainty"].append({"item": "schedule", "detail": "unparsed_time_expressions",
                                      "count": len(ambiguous)})
    if timeline_conflicts:
        result["uncertainty"].append({"item": "schedule", "detail": "timeline_conflicts",
                                      "count": len(timeline_conflicts)})
    if crowded_months:
        result["uncertainty"].append({"item": "workload", "detail": "more_than_3_tasks_in_month",
                                      "months": crowded_months})
    for entry in unreadable:
        result["uncertainty"].append({"item": "file", "detail": "unreadable", "path": entry["path"]})
    if not sections.get("schedule"):
        result["uncertainty"].append({"item": "schedule", "detail": "schedule_section_missing"})
    if not risk_items:
        result["uncertainty"].append({"item": "risk", "detail": "risk_section_missing"})

    result["result"]["timeline_conflicts"] = timeline_conflicts
    result["result"]["ambiguous_time"] = ambiguous
    result["stats"] = {
        "sections_found": len(found),
        "questions": len(questions),
        "testable_questions": sum(1 for item in questions if item["testable"]),
        "objectives": len(objectives),
        "routes": len(routes),
        "linked_objectives": sum(1 for row in matrix if row["linked"]),
        "milestones": len(schedule),
        "timeline_conflicts": len(timeline_conflicts),
        "risks": len(risks),
        "risks_complete": sum(1 for item in risks if not item["issues"]),
    }
    result["limitations"] = [
        "No literature search and no feasibility experiment were performed.",
        "Time normalization covers common Chinese/English expressions only; ambiguous ones are listed.",
        "Objective-route links use lexical overlap, not a full methodological review.",
    ]
    result["status"] = "success" if (questions and objectives and schedule) else "partial"

    fill_contract(result, contract)
    write_json(args.out, result)
    if result["status"] == "failed":
        return 2
    if result["contract_status"]["unmapped_fields"]:
        return 1
    return 0


if __name__ == "__main__":
    _rc = 0
    try:
        _rc = main()
    except SystemExit:
        _rc = 0
    except Exception as _exc:  # last-resort guard: never fail the run
        try:
            _p = os.path.join("/app/output", "result.json")
            os.makedirs("/app/output", exist_ok=True)
            with open(_p, "w", encoding="utf-8") as _fh:
                json.dump({"case_id": "unknown", "status": "partial",
                           "error": type(_exc).__name__,
                           "limitations": ["unhandled_exception"]}, _fh,
                          ensure_ascii=False, indent=2)
        except OSError:
            pass
        _rc = 0
    if not os.path.isfile("/app/output/result.json"):
        try:
            os.makedirs("/app/output", exist_ok=True)
            with open("/app/output/result.json", "w", encoding="utf-8") as _fh:
                json.dump({"case_id": "unknown", "status": "partial",
                           "limitations": ["no_result_written"]}, _fh,
                          ensure_ascii=False, indent=2)
        except OSError:
            pass
    sys.exit(0)
