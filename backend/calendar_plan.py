"""Validate and merge calendar proposals without mutating confirmed state."""

from __future__ import annotations

import re
import uuid
from datetime import date, datetime, timedelta
from time_utils import shanghai_today

MAX_EVENTS = 40
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
TIME_RE = re.compile(r"^(?:[01]\d|2[0-3]):[0-5]\d$")
REMINDER_RE = re.compile(r"^20\d{2}-\d{2}-\d{2}T(?:[01]\d|2[0-3]):[0-5]\d$")
ID_RE = re.compile(r"^[A-Za-z0-9_-]{1,40}$")


def _date(value):
    if value is None:
        return None
    if not isinstance(value, str) or not DATE_RE.fullmatch(value):
        raise ValueError("Invalid calendar date format")
    try:
        date.fromisoformat(value)
    except ValueError as error:
        raise ValueError("Invalid calendar date") from error
    return value


def _time(value):
    if value in (None, ""):
        return None
    if not isinstance(value, str) or not TIME_RE.fullmatch(value):
        raise ValueError("Invalid event time format")
    return value


def _reminder(value):
    if value in (None, ""):
        return None
    if not isinstance(value, str) or not REMINDER_RE.fullmatch(value):
        raise ValueError("Invalid reminder time format")
    _date(value[:10])
    return value


def _short(value, limit):
    if not isinstance(value, str):
        raise ValueError("Invalid event text format")
    return value.strip()[:limit]


def _english_display(value):
    # Keep original values intact while planning. The HTTP response boundary
    # sanitizes user-facing output; redacting here destroys task matching and
    # dependency information before the planner can use it.
    return value


def _english_result(result):
    result["answer"] = _english_display(result.get("answer", ""))
    result["quick_choices"] = [_english_display(item) for item in result.get("quick_choices", [])]
    result["follow_ups"] = [_english_display(item) for item in result.get("follow_ups", [])]
    for item in result.get("advice_items", []):
        if isinstance(item, dict):
            for field in ("title", "why", "when", "prerequisite", "completion", "basis"):
                if field in item:
                    item[field] = _english_display(item[field])
    for operation in result.get("operations", []):
        if isinstance(operation, dict):
            for field in ("title", "detail", "source_note"):
                if field in operation:
                    operation[field] = _english_display(operation[field])
    return result


def _title_key(value):
    return re.sub(r"[\s\u3000，。、“”‘’：:；;（）()、/·-]", "", value or "").lower()


def _task_kind(title):
    """Return a conservative semantic group for tasks that should share one plan item."""
    value = _title_key(title)
    groups = (
        ("rental_online_signing", ("租赁网签", "合同网签", "online lease signing", "rental contract online signing")),
        ("rental_filing", ("租赁备案", "合同备案", "rental filing", "lease registration")),
        ("electricity_handover", ("水电", "用电", "电表", "电力", "utility handover", "electricity", "meter readings")),
        ("gas_handover", ("燃气", "燃气表", "gas meter")),
        ("water_handover", ("用水", "水表", "water meter")),
        ("move_preparation", ("搬家安排", "搬家车辆", "搬运报价", "入住条件", "moving arrangements", "move preparation", "handover arrangements")),
        ("new_home_handover", ("交房", "新房交接", "new-home handover", "new home handover", "key handover")),
        ("move_completion", ("完成搬家", "搬家完成", "搬入新住处", "新住所入住", "complete the move", "move into the new home", "move-in inspection", "move completion", "moving completion")),
        ("old_home_handover", ("旧住处交接", "旧住处退租", "退租交接", "钥匙交接", "old home handover", "lease handover", "move-out handover")),
        ("old_home_inspection", ("旧住处验房", "退租验房", "move-out inspection")),
        ("housing_screening", ("筛选房源", "房源筛选", "租房筛选", "筛选住房", "housing screening", "find a home", "rental search")),
        ("housing_viewing", ("实地看房", "预约看房", "看房", "home viewing", "property viewing")),
        ("rental_contract", ("租赁签约", "租房签约", "确认住所", "lease signing", "rental contract")),
        ("onboarding_medical", ("入职体检", "体检要求", "体检机构", "onboarding health check", "medical check requirements")),
        ("hr_onboarding", ("hr确认入职", "报到地点", "入职信息", "confirm onboarding", "check in with hr", "reporting location")),
        ("broadband", ("宽带", "网络", "broadband", "internet installation", "wifi")),
        ("housing_fund", ("公积金", "housing provident fund", "housing fund")),
        ("social_insurance", ("社保", "social insurance", "social security")),
        ("medical_insurance", ("医保", "medical insurance", "health insurance")),
        ("residency_registration", ("居住登记", "residence registration")),
        ("residence_permit", ("居住证", "residence permit")),
        ("commute_walkthrough", ("通勤试走", "试走通勤", "commute walkthrough", "test the commute")),
        ("move_inventory", ("盘点物品", "搬运条件", "inventory and moving", "inventory items")),
        ("full_process_milestone", ("全流程目标完成里程碑", "full-process completion milestone")),
    )
    for group, keywords in groups:
        if any(_title_key(keyword) in value for keyword in keywords):
            return group
    return None


def _event_difference(existing, proposed):
    """Return fields a duplicate add would change on an existing event."""
    changed = []
    if _title_key(existing.get("title")) != _title_key(proposed.get("title")):
        changed.append("title")
    fields = ("start_date", "due_date", "due_time", "reminder_at", "detail", "kind", "date_basis", "source_note", "sources")
    changed.extend(field for field in fields if existing.get(field) != proposed.get(field))
    return changed


def _clarification(existing, proposed, status="confirmed"):
    return {
        "existing_status": status,
        "existing_id": existing["id"],
        "existing_title": existing["title"],
        "existing_date": existing.get("due_date"),
        "proposed_title": proposed["title"],
        "proposed_date": proposed.get("due_date"),
        "different_fields": _event_difference(existing, proposed),
    }


def clean_sources(raw):
    if not isinstance(raw, list):
        return []
    result = []
    for source in raw[:5]:
        if not isinstance(source, dict):
            continue
        url = source.get("source_url", "")
        if not isinstance(url, str) or not url.startswith("https://"):
            url = ""
        result.append({
            "source_name": _short(str(_english_display(source.get("source_name") or "Information to be confirmed")), 120),
            "source_url": url[:1000],
            "source_status": _short(str(_english_display(source.get("source_status") or "Information to be confirmed")), 120),
            "verified_at": _short(str(source.get("verified_at") or ""), 40),
        })
    return result


def clean_event(raw):
    if not isinstance(raw, dict):
        raise ValueError("Invalid calendar event format")
    event_id = raw.get("id")
    if not isinstance(event_id, str) or not ID_RE.fullmatch(event_id):
        raise ValueError("Invalid event ID format")
    title = _short(_english_display(raw.get("title")), 80)
    if not title:
        raise ValueError("Event title cannot be empty")
    due_date = _date(raw.get("due_date"))
    start_date = _date(raw.get("start_date", due_date))
    if start_date and due_date and start_date > due_date:
        raise ValueError("Start date cannot be later than end date")
    return {
        "id": event_id,
        "title": title,
        "start_date": start_date,
        "due_date": due_date,
        "due_time": _time(raw.get("due_time")),
        "reminder_at": _reminder(raw.get("reminder_at")),
        "detail": _short(_english_display(raw.get("detail", "")), 300),
        "kind": raw.get("kind") if raw.get("kind") in ("task", "deadline") else "task",
        "hard_deadline": raw.get("hard_deadline") is True,
        "date_basis": raw.get("date_basis") if raw.get("date_basis") in ("用户明确", "建议日期", "日期待确认") else "日期待确认",
        "source_note": _short(_english_display(raw.get("source_note", "Information to be confirmed")), 400),
        "sources": clean_sources(raw.get("sources", [])),
        "depends_on_ids": [value for value in raw.get("depends_on_ids", []) if isinstance(value, str) and ID_RE.fullmatch(value) and value != event_id][:12] if isinstance(raw.get("depends_on_ids", []), list) else [],
        "done": raw.get("done") is True,
    }


def clean_events(raw):
    if not isinstance(raw, list) or len(raw) > MAX_EVENTS:
        raise ValueError("The calendar event limit has been exceeded")
    events = [clean_event(item) for item in raw]
    if len({item["id"] for item in events}) != len(events):
        raise ValueError("Duplicate calendar event ID")
    return events


def clean_calendar(raw):
    if raw is None:
        raw = {}
    if not isinstance(raw, dict):
        raise ValueError("Invalid calendar state format")
    confirmed = clean_events(raw.get("confirmed", []))
    pending_raw = raw.get("pending")
    pending = clean_events(pending_raw) if pending_raw is not None else None
    return {"confirmed": confirmed, "pending": pending}


def _from_operation(op, event_id, done=False, previous=None):
    previous = previous or {}
    due_date = op.get("due_date")
    reminder_at = op.get("reminder_at", previous.get("reminder_at"))
    if (reminder_at and reminder_at == previous.get("reminder_at") and previous.get("due_date")
            and due_date and due_date != previous["due_date"]):
        reminder_at = _shift_date(reminder_at[:10], (date.fromisoformat(due_date) - date.fromisoformat(previous["due_date"])).days) + reminder_at[10:]
    start_date = op.get("start_date") or previous.get("start_date") or due_date
    if previous.get("due_date") and previous.get("start_date") == previous.get("due_date") and due_date != previous.get("due_date") and not op.get("start_date"):
        start_date = due_date
    keep_manual_range = event_id.startswith("m_") and previous.get("start_date") != previous.get("due_date") and not op.get("start_date")
    if op.get("date_basis") == "建议日期" and not keep_manual_range:
        start_date = due_date
    return clean_event({
        "id": event_id,
        "title": _english_display(op.get("title", "")),
        "start_date": start_date,
        "due_date": due_date,
        "due_time": op.get("due_time"),
        "reminder_at": reminder_at,
        "detail": _english_display(op.get("detail", "")),
        "kind": op.get("kind", "task"),
        "hard_deadline": (op.get("hard_deadline", previous.get("hard_deadline", False)) if previous.get("hard_deadline") or op.get("date_basis") != "建议日期" else False),
        "date_basis": op.get("date_basis", "日期待确认"),
        "source_note": _english_display(op.get("source_note", "Information to be confirmed")),
        "sources": op.get("sources", previous.get("sources", [])),
        "depends_on_ids": op.get("depends_on_ids", previous.get("depends_on_ids", [])),
        "done": done,
    })


def _changes(previous, candidate):
    """Describe only the delta between the current proposal base and candidate."""
    old = {item["id"]: item for item in previous}
    new = {item["id"]: item for item in candidate}
    changed = []
    for item in candidate:
        before = old.get(item["id"])
        if before is None:
            changed.append({"id": item["id"], "type": "新增", "title": item["title"]})
        elif before != item:
            changed.append({"id": item["id"], "type": "修改", "title": item["title"]})
    for item in previous:
        if item["id"] not in new:
            changed.append({"id": item["id"], "type": "删除", "title": item["title"]})
    return changed


def _shift_date(value, days):
    if not value:
        return value
    return (date.fromisoformat(value) + timedelta(days=days)).isoformat()


def _profile_date(value, today):
    if not isinstance(value, str):
        return None
    match = re.fullmatch(r"\s*(?:(20\d{2})[年/-])?(0?[1-9]|1[0-2])[月/-](0?[1-9]|[12]\d|3[01])[日号]?\s*", value)
    if not match:
        parsed = _english_date(value, today)
        return parsed.isoformat() if parsed else None
    year = int(match.group(1) or today.year)
    try:
        return date(year, int(match.group(2)), int(match.group(3))).isoformat()
    except ValueError:
        return None


def _apply_planning_constraints(candidate, touched_ids, profile, today):
    """Enforce explicit target dates on model-touched relocation events."""
    move_target = _profile_date((profile or {}).get("move_deadline"), today)
    handover_target = _profile_date((profile or {}).get("housing_handover_date"), today)
    full_target = _profile_date((profile or {}).get("full_process_deadline"), today)
    today_key = today.isoformat()
    for event in candidate:
        if event["id"] not in touched_ids:
            continue
        title = _title_key(event["title"])
        kind = _task_kind(event.get("title", ""))
        completion = kind == "move_completion"
        preparation = kind == "move_preparation" or kind == "old_home_handover"
        if move_target and completion and event.get("date_basis") != "用户明确":
            # 交房延期已把该事项推至新交房日时，不用旧的搬家资料日期
            # 将其重新拉回交房之前。
            if not (handover_target and move_target < handover_target and event.get("due_date") and event["due_date"] >= handover_target):
                event["start_date"] = move_target
                event["due_date"] = move_target
                event["date_basis"] = "用户明确"
        elif move_target and preparation and event.get("date_basis") == "建议日期" and event.get("due_date"):
            safe_date = min(max(event["due_date"], today_key), move_target)
            event["due_date"] = safe_date
            event["start_date"] = safe_date
        if handover_target and ("交房" in title or "handover" in title or "key handover" in title) and "before handover" not in title:
            event["start_date"] = handover_target
            event["due_date"] = handover_target
            event["date_basis"] = "用户明确"
        actual_service = any(word in title for word in ("宽带安装", "broadband installation", "booked moving service", "已预约搬家服务", "搬家服务", "搬入新住处", "入住交接", "move-in handover"))
        if handover_target and actual_service and event.get("due_date") and event["due_date"] < handover_target:
            event["start_date"] = handover_target
            event["due_date"] = handover_target
        if full_target and "全流程" in title and "里程碑" in title:
            event["start_date"] = full_target
            event["due_date"] = full_target
            event["date_basis"] = "用户明确"


def _operation(action, event=None, *, title="", due_date=None, due_time=None, reminder_at=None, detail="", date_basis="日期待确认", source_note="Information to be confirmed", sources=None):
    event = event or {}
    return {
        "action": action,
        "id": event.get("id", ""),
        "title": title or event.get("title", ""),
        "due_date": due_date if due_date is not None else event.get("due_date"),
        "due_time": due_time if due_time is not None else event.get("due_time"),
        "reminder_at": reminder_at if reminder_at is not None else event.get("reminder_at"),
        "detail": detail or event.get("detail", ""),
        "kind": event.get("kind", "task"),
        "date_basis": date_basis or event.get("date_basis", "日期待确认"),
        "source_note": source_note or event.get("source_note", "Information to be confirmed"),
        "sources": sources if sources is not None else event.get("sources", []),
        "depends_on_ids": event.get("depends_on_ids", []),
        "hard_deadline": event.get("hard_deadline", False),
    }


def _delete_all_requested(message):
    text = re.sub(r"\s+", "", message or "")
    lowered = text.lower()
    if any(word in text for word in ("不要删除", "别删除", "不要清空", "别清空", "不删除所有")) or re.search(r"\b(?:do\s+not|don't|dont|never)\s+(?:delete|clear|remove)\b", lowered):
        return False
    return bool(
        re.search(r"(?:删除|清空|移除)(?:当前|现有|我的|日历中|计划日历中|待确认或已确认)?(?:所有|全部|整个)(?:计划|日程|待办|事项)|(?:把|将)?(?:所有|全部)(?:计划|日程|待办|事项)(?:都|全部)?(?:删除|清空|移除)", text)
        or re.search(r"\b(?:delete|clear|remove)\s+(?:all|every|the entire)\s+(?:of\s+)?(?:my\s+)?(?:plans?|schedules?|calendar events?|tasks?|to-?dos?)\b|\b(?:delete|clear|remove)\s+(?:my\s+)?(?:entire\s+)?calendar\b", lowered)
    )


def _initial_plan_requested(message):
    value = re.sub(r"\s+", "", message or "")
    lowered = (message or "").lower()
    if re.search(r"(?:不要|别|无需|不用)(?:生成|制定|安排|规划).{0,8}(?:计划|日程)", value):
        return False
    return bool(
        re.search(r"(?:生成|制定|做|给我|出)(?:一份|我的|完整的?)?(?:搬家|安家|完整)?(?:计划|日程|安排)|计划表|日程安排", value)
        or re.search(r"(?:根据|按照|基于).{0,12}(?:资料|信息|情况).{0,12}(?:如何安排|怎么安排|帮我安排|安排一下|规划一下)", value)
        or re.search(r"\b(?:create|generate|make|build|draft|prepare)\b.{0,55}\b(?:relocation|moving|move|settling[- ]in)?\s*(?:plan|schedule|timeline|checklist)\b|\b(?:plan|schedule|timeline|checklist)\b.{0,35}\b(?:for my move|for moving|for relocation|for settling in)\b", lowered)
        or re.search(r"\b(?:organize|map out)\b.{0,40}\b(?:my move|my relocation|my schedule|all the tasks)\b", lowered)
        or re.search(r"\b(?:give|make|build|prepare|create)\s+me\s+(?:a|the|my)\s+(?:full\s+)?(?:relocation\s+|moving\s+)?(?:plan|schedule|timeline|checklist)\b|\bplan\s+my\s+(?:move|relocation)\b", lowered)
    )


def _pending_rejected(message):
    value = re.sub(r"\s+", "", message or "")
    english = (message or "").lower()
    return bool(
        re.search(r"不需要改动当前日程表|(?:算了|先别|暂时别|还是别)(?:，|,)?(?:先)?(?:别|不)?(?:改|调整|动|安排)|(?:不用|不要|取消|拒绝|撤销)(?:这次|当前|刚才|上述|待确认)?(?:的)?(?:日程)?(?:改动|修改|提议|草案|安排)|(?:保持|维持)(?:原|现有|当前)(?:计划|日程)(?:不变)?", value)
        or re.search(r"\b(?:keep|leave|retain)\s+(?:the\s+)?(?:current|existing|original)\s+(?:schedule|calendar|plan)\s+(?:unchanged|as\s+is)\b|\b(?:don't|do\s+not|cancel|reject|decline)\s+(?:this\s+)?(?:proposal|change|update|schedule|plan)\b|\bno\s+changes?\s+(?:please|for\s+now)?\b|\bno\s+need\s+to\s+(?:change|modify|adjust)\s+(?:the\s+)?(?:current|existing|original)?\s*(?:schedule|calendar|plan)\b", english)
    )


def _complete_first_plan(ops, profile, today):
    """Fill missing stages of a first plan without treating an unknown handover as fact."""
    titles = [item.get("title", "") for item in ops if item.get("action") == "add"]
    move = _profile_date((profile or {}).get("move_deadline"), today)
    hire = _profile_date((profile or {}).get("start_date"), today)
    if not (move and hire):
        return ops
    move_day, hire_day = date.fromisoformat(move), date.fromisoformat(hire)
    def add_if_missing(words, title, day, detail):
        if any(any(word.lower() in existing.lower() for word in words) for existing in titles):
            return
        ops.append(_operation("add", title=title, due_date=max(today, day).isoformat(), detail=detail,
                              date_basis="建议日期", source_note="Suggested from the user's move or start date; verify actual requirements and availability."))
        titles.append(title)

    if not (profile or {}).get("current_housing") and not (profile or {}).get("housing_handover_date"):
        add_if_missing(("area screening", "housing screening", "rental search", "房源筛选"), "Screen rental areas and housing options", move_day - timedelta(days=10), "Filter areas using office location, rent budget, and commute preferences. Listing rents and commute times are references that need verification.")
        add_if_missing(("viewing", "看房"), "View apartments and verify lease terms", move_day - timedelta(days=5), "Inspect the home and verify fees, contract responsibilities, and move-in conditions yourself.")
        add_if_missing(("lease signing", "rental contract", "签约"), "Review and sign the rental agreement", move_day - timedelta(days=3), "Verify the parties, rent, deposit, handover date, and move-out terms yourself.")
    add_if_missing(("handover", "move-in conditions", "交房"), "Confirm the new-home handover and move-in conditions", move_day - timedelta(days=2), "Confirm the actual handover date, keys, and access conditions with the landlord. This is a suggested verification date.")
    add_if_missing(("moving arrangements", "move preparation", "moving service", "搬家安排"), "Confirm moving arrangements and old-home handover", move_day - timedelta(days=1), "Confirm the moving method, old-home handover, and access to the new home.")
    add_if_missing(("complete the move", "move into the new home", "move-in inspection", "完成搬家"), "Move into the new home and complete an inspection", move_day, "Check the keys, home condition, and completion of the move.")
    add_if_missing(("broadband", "internet", "宽带"), "Verify broadband installation conditions", move_day - timedelta(days=1), "Confirm address coverage and installation availability; make any booking yourself.")
    add_if_missing(("utility handover", "water and gas", "meter readings", "水电"), "Verify utility handover", move_day, "Check meter readings, billing responsibility, and the condition of the home at move-in.")
    add_if_missing(("hr", "onboarding requirements", "employment check-in", "入职材料"), "Confirm onboarding location, documents, and health-check requirements with HR", hire_day - timedelta(days=3), "Ask your employer to confirm check-in, required documents, and any health-check requirements. Do not book anything on your behalf.")
    add_if_missing(("commute walkthrough", "commute trial", "通勤试走"), "Test the commute before your start date", hire_day - timedelta(days=1), "Try the route during the actual morning peak and confirm the arrival time.")
    add_if_missing(("check in with your employer", "first day at work", "start date milestone", "入职报到"), "Check in with your employer and confirm benefit enrollment arrangements", hire_day, "Confirm onboarding and the employer's social-insurance, medical-insurance, and housing-fund arrangements with HR.")
    add_if_missing(("residence registration", "居住登记"), "Verify residence-registration requirements", move_day + timedelta(days=1), "After moving in, verify eligibility, required documents, and the official service entry for your situation.")
    return ops


def _move_change_requested(message):
    value = re.sub(r"\s+", "", message or "")
    english = (message or "").lower()
    return bool(
        re.search(r"(?:把|将)?(?:完成)?搬家(?:完成)?(?:时间|日期|日)?(?:改到|改为|调整到|推迟到|提前到|延到)", value)
        or re.search(r"\b(?:move|shift|reschedule|change)\s+(?:(?:my|our|the)\s+)?(?:moving date|move date|move-in date|move completion(?: date)?|move)\s+(?:to|until)\b", english)
    )


def _english_date(value, today):
    """Parse ISO or English month-name dates used in chat and profile values."""
    text = (value or "").strip()
    try:
        return date.fromisoformat(text)
    except ValueError:
        pass
    for fmt in ("%B %d, %Y", "%B %d %Y", "%B %d"):
        try:
            parsed = datetime.strptime(text, fmt).date()
            return parsed.replace(year=today.year) if fmt == "%B %d" else parsed
        except ValueError:
            continue
    return None


def _date_from_message(message, today):
    """Return the first explicit ISO or English month-name date in a message."""
    pattern = r"\b20\d{2}-\d{2}-\d{2}\b|\b(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2}(?:,?\s+20\d{2})?\b"
    matches = list(re.finditer(pattern, message or "", re.I))
    for match in reversed(matches):
        parsed = _english_date(match.group(), today)
        if parsed:
            return parsed
    return None


def _explicit_move_target(message, today):
    """Read the date in an explicit move-date command, independent of profile updates."""
    value = re.sub(r"\s+", "", message or "")
    marker = re.search(r"(?:搬家(?:完成)?(?:时间|日期|日)?|完成搬家|搬入|入住)[^。；，,？！?!]{0,16}(?:改到|改为|调整到|推迟到|提前到|延到)", value)
    if not marker:
        english = re.search(r"\b(?:move|shift|reschedule|change)\s+(?:(?:my|our|the)\s+)?(?:moving date|move date|move-in date|move completion(?: date)?|move)\s+(?:to|until)\s+", message or "", re.I)
        if not english:
            return None
        return _date_from_message((message or "")[english.end():], today).isoformat() if _date_from_message((message or "")[english.end():], today) else None
    dates = list(re.finditer(r"(?:(20\d{2})年)?(0?[1-9]|1[0-2])月((?:[12]\d|3[01]|0?[1-9]))日?", value[marker.end():]))
    if not dates:
        return None
    match = dates[-1]
    try:
        return date(int(match.group(1) or today.year), int(match.group(2)), int(match.group(3))).isoformat()
    except ValueError:
        return None


def _accepted_move_after_hire(message):
    value = re.sub(r"\s+", "", message or "")
    return bool(
        re.search(r"(?:接受|确认|坚持|仍要|仍然要|决定|选择).{0,16}入职后.{0,8}搬家|入职后搬家.{0,12}(?:确认|可以|接受|就这样)", value)
        or re.search(r"\b(?:i\s+)?(?:accept|choose|agree\s+to)\s+(?:moving|the\s+move)\s+after\s+(?:my\s+)?(?:start|onboarding)\s+date\b", message or "", re.I)
    )


def augment_model_result(calendar_state, model_result, profile, latest_message, today=None):
    """Add deterministic operations for facts that invalidate an existing plan."""
    today = today or shanghai_today()
    result = dict(model_result)
    ops = [dict(item) for item in result.get("operations", []) if isinstance(item, dict)]
    base = calendar_state["pending"] if calendar_state["pending"] is not None else calendar_state["confirmed"]

    if calendar_state["pending"] is not None and _pending_rejected(latest_message):
        result.update({"response_mode": "C", "calendar_intent": "none", "operations": [],
                       "advice_items": [], "follow_ups": [], "quick_choices": [],
                       "clear_pending": True,
                       "answer": "The pending schedule changes were withdrawn. Your confirmed calendar remains unchanged."})
        return _english_result(result)

    # “请安排”有可能是新增，也有可能是改已有搬家事项；未明确要求改期时先确认意图。
    message = latest_message or ""
    if re.search(r"(?:请|帮我)?安排.{0,20}搬家|(?:请|帮我)?安排.{0,20}入住", message) and not _move_change_requested(message):
        existing_move = next((item for item in base if not item.get("done") and any(word in item.get("title", "") for word in ("完成搬家", "搬入新住处", "新住所入住"))), None)
        mentioned_date = re.search(r"(?:20\d{2}年)?\d{1,2}月\d{1,2}日", message)
        if existing_move and mentioned_date:
            result.update({"response_mode": "E", "calendar_intent": "none", "operations": [],
                           "advice_items": [], "follow_ups": [], "quick_choices": [],
                           "suppress_profile_fields": ["move_deadline"],
                           "answer": f"Your calendar already contains “{_english_display(existing_move['title'])}” ({existing_move.get('due_date') or 'Date to be confirmed'}). Would you like to move this event to {mentioned_date.group()}, or add a separate moving event? Nothing will change before confirmation."})
            return _english_result(result)

    if _delete_all_requested(latest_message):
        confirmed = calendar_state["confirmed"]
        pending = calendar_state["pending"] or []
        unique = {item["id"]: item for item in confirmed + pending}
        result.update({
            "response_mode": "D",
            "calendar_intent": "propose" if unique else "none",
            "operations": [_operation("delete", item) for item in unique.values()],
            "delete_all": bool(unique),
            "advice_items": [],
            "follow_ups": [],
            "quick_choices": [],
            "answer": f"This proposal would delete {len(confirmed)} confirmed event(s)" + (f" and withdraw {len([item for item in pending if item['id'] not in {event['id'] for event in confirmed}])} pending draft item(s)" if pending else "") + ". Review the list below; your calendar will not change until you confirm." if unique else "There are no calendar events to delete.",
        })
        return _english_result(result)

    # 首次完成信息采集后，模型偶尔只返回文字而遗漏 operations。为避免
    # 用户看到“计划生成失败”，用用户明确提供的日期生成一版待确认草案。
    # 这只是提议，不会绕过前端确认直接写入日历。
    plan_request = _initial_plan_requested(latest_message)
    empty_calendar = not calendar_state["confirmed"] and not calendar_state["pending"]
    if plan_request and empty_calendar and ops:
        result["response_mode"] = "B"
        result["calendar_intent"] = "propose"
    if plan_request and empty_calendar and not ops:
        move_target = _profile_date((profile or {}).get("move_deadline"), today)
        hire_target = _profile_date((profile or {}).get("start_date"), today)
        if move_target or hire_target:
            move_day = date.fromisoformat(move_target) if move_target else None
            hire_day = date.fromisoformat(hire_target) if hire_target else None
            if move_target and hire_target:
                ops = _complete_first_plan([], profile, today)
            elif move_day:
                ops.extend([
                    _operation("add", title="Confirm the new-home handover and move-in conditions", due_date=max(today, move_day - timedelta(days=2)).isoformat(), detail="Confirm the actual handover date, keys, and access conditions with the landlord.", date_basis="建议日期", source_note="Suggested verification date; the actual handover must be confirmed."),
                    _operation("add", title="Move into the new home and complete an inspection", due_date=move_day.isoformat(), detail="Check the keys, home condition, and completion of the move.", date_basis="用户明确", source_note="Date based on the user's saved move deadline."),
                    _operation("add", title="Verify broadband installation conditions", due_date=max(today, move_day - timedelta(days=1)).isoformat(), detail="Confirm address coverage and installation availability; make any booking yourself.", date_basis="建议日期", source_note="Suggested from the move date; provider availability must be confirmed."),
                ])
            elif hire_day:
                ops.extend([
                    _operation("add", title="Confirm onboarding location, documents, and health-check requirements with HR", due_date=max(today, hire_day - timedelta(days=3)).isoformat(), detail="Ask your employer to confirm check-in, required documents, and any health-check requirements.", date_basis="建议日期", source_note="Suggested from the saved start date; confirm details with HR."),
                    _operation("add", title="Check in with your employer and confirm benefit enrollment arrangements", due_date=hire_day.isoformat(), detail="Confirm onboarding and the employer's social-insurance, medical-insurance, and housing-fund arrangements with HR.", date_basis="用户明确", source_note="Date based on the user's saved start date."),
                ])
            result["response_mode"] = "B"
            result["calendar_intent"] = "propose"
            result["advice_items"] = []
            result["follow_ups"] = []
            result["operations"] = ops
            result["answer"] = "Summary of current information: I drafted an initial relocation plan from your saved start and move dates. Review the suggested dates below; nothing will be added to your calendar until you confirm."

    if empty_calendar and ops and (plan_request or result.get("response_mode") == "B"):
        result["operations"] = _complete_first_plan(ops, profile, today)
        result["quick_choices"] = []
        result["follow_ups"] = [
            question for question in result.get("follow_ups", [])
            if isinstance(question, str) and not re.search(r"(?:是否|要不要|需不需要)[^。！？\n]{0,60}(?:生成|制定|安排)[^。！？\n]{0,15}(?:计划|日程)", question)
        ]
        result["answer"] = re.sub(
            r"(?:请确认)?(?:是否|要不要|需不需要)[^。！？\n]{0,60}(?:生成|制定|安排)[^。！？\n]{0,15}(?:计划|日程)[。！？?]?",
            "", str(result.get("answer", "")),
        ).strip()

    completion_signal = re.search(r"(?:已经|已|刚刚|刚)\s*(?:搬好家|搬完家|完成搬家|入住了|搬家完成)", latest_message or "") or re.search(r"\b(?:i have already moved|i already moved|the move is complete|i have completed the move)\b", latest_message or "", re.I)
    delete_confirmed = re.search(r"(?:已完成|已经完成|完成了)[^\n]{0,20}(?:删除|移除)|(?:删除|移除)[^\n]{0,20}(?:已完成|已经完成)", latest_message or "")
    if completion_signal and not delete_confirmed:
        affected_kinds = {"housing_screening", "housing_viewing", "rental_contract", "rental_filing", "old_home_handover", "old_home_inspection", "move_preparation", "move_completion", "broadband", "water_handover", "gas_handover", "electricity_handover"}
        affected_events = [event for event in base if not event.get("done") and (_task_kind(event.get("title", "")) in affected_kinds or re.search(r"\b(?:lease|rental|moving|move-in|handover|viewing|broadband|utility|meter)\b", event.get("title", ""), re.I))]
        result["response_mode"] = "D"
        result["calendar_intent"] = "propose" if affected_events else "none"
        result["operations"] = [_operation("delete", event, title="盘点物品并核对搬运条件" if any(word in event.get("detail", "") for word in ("盘点物品", "搬运条件")) else event.get("title", "")) for event in affected_events]
        result["quick_choices"] = []
        result["answer"] = "You mentioned that the move is complete. Please confirm whether to remove the completed relocation tasks listed below:"
        return _english_result(result)
    if delete_confirmed:
        affected_kinds = {"housing_screening", "housing_viewing", "rental_contract", "rental_filing", "old_home_handover", "old_home_inspection", "move_preparation", "move_completion", "broadband", "water_handover", "gas_handover", "electricity_handover"}
        removed = [event for event in base if not event.get("done") and (_task_kind(event.get("title", "")) in affected_kinds or re.search(r"\b(?:lease|rental|moving|move-in|handover|viewing|broadband|utility|meter)\b", event.get("title", ""), re.I))]
        if removed:
            result["response_mode"] = "D"
            result["calendar_intent"] = "propose"
            ops = [item for item in ops if item.get("id") not in {event.get("id") for event in removed}]
            ops.extend(_operation("delete", event) for event in removed)
            result["operations"] = ops
            result["answer"] = "Your move is marked complete. The list below includes only completed relocation tasks proposed for removal; onboarding, social-insurance, and housing-fund tasks will remain."

    # 交房完成只说明住所已可进入，不能误当作“搬家完成”。旧找房任务
    # 提议移除，后续事项按交房事实解锁；历史已完成事项继续保留。
    if re.search(r"(?:已经|已)交房完成|交房(?:已|已经)完成|(?:已经|已)完成交房", latest_message or ""):
        search_words = ("找房", "看房", "筛选房源", "区域参考", "租房注意", "租住区域")
        result["response_mode"] = "D"
        ops = []
        for event in base:
            if not event.get("done") and any(word in event["title"] for word in search_words):
                ops = [item for item in ops if item.get("id") != event["id"]]
                ops.append(_operation("delete", event))
        handover = _profile_date((profile or {}).get("housing_handover_date"), today)
        ready = max(today.isoformat(), handover or today.isoformat())
        follow_up = (date.fromisoformat(ready) + timedelta(days=1)).isoformat()
        unlocked = (
            ("Verify broadband installation conditions", ready, "Confirm address coverage, installation requirements, and availability; make any booking yourself.", ("网络", "宽带", "broadband", "internet")),
            ("Confirm moving arrangements and service window", ready, "Confirm the moving method, vehicle, elevator, and parking requirements directly with the provider.", ("搬家安排", "搬家方案", "搬家服务", "moving arrangements", "moving service")),
            ("Move in and verify utility handover", follow_up, "Record water, electricity, and gas meter readings, billing responsibility, and home condition.", ("搬入", "入住交接", "水电交接", "完成搬家", "搬家完成", "move-in", "utility handover", "move completion")),
            ("Verify residence-registration requirements", follow_up, "After moving in, verify required documents, eligibility, and the official service entry for your situation.", ("居住登记", "residence registration")),
        )
        for title, due, detail, equivalent in unlocked:
            existing = next((event for event in base if not event.get("done") and any(word in event["title"] for word in equivalent)), None)
            if existing:
                if existing.get("due_date") and existing["due_date"] < due and not existing.get("hard_deadline") and not any(word in existing["title"] for word in ("已预约", "已预订")):
                    ops.append(_operation("update", existing, due_date=due, detail=existing.get("detail", "") + " This can be done only after the new-home handover is complete.", date_basis="建议日期", source_note="Rescheduled after the completed handover; verify the execution requirements."))
                continue
            if any(item.get("action") == "add" and any(word in item.get("title", "") for word in equivalent) for item in ops):
                continue
            ops.append(_operation("add", title=title, due_date=due, detail=detail, date_basis="建议日期", source_note="Follow-up checks after the user-reported handover; verify service times and eligibility directly."))
        result.update({
            "calendar_intent": "propose" if ops else "none", "operations": ops,
            "advice_items": [], "follow_ups": [],
            "answer": "The new-home handover is recorded. The proposal below removes no-longer-needed home-search tasks and schedules checks for internet, utilities, moving, and residence registration after move-in. Review and confirm; your calendar will not change beforehand." if ops else "Home-search cleanup and post-handover tasks are already in your plan or pending draft. No new changes are proposed.",
        })
        return _english_result(result)

    # 提醒属于“我的”页面的设置项，不作为日程变更提议，避免在问答页
    # 出现计划清单确认卡片。微信提醒也只能在具备订阅能力后由设置页处理。
    if re.search(r"\b(?:reminder|notification)s?\b", latest_message or "", re.I) and re.search(r"\b(?:change|set|turn on|enable|disable|adjust)\b", latest_message or "", re.I):
        result.update({
            "response_mode": "C", "calendar_intent": "none", "operations": [],
            "advice_items": [], "follow_ups": [], "quick_choices": [],
            "answer": "Reminder preferences can be saved under Profile → Reminder settings. Chat cannot change individual reminder times. In-app reminders appear only when you open the page; WeChat authorization and message delivery are not connected, so I cannot enable or send WeChat reminders.",
        })
        return _english_result(result)

    if "提醒" in (latest_message or "") and re.search(r"(?:改|设置|设为|提前)", latest_message or ""):
        message = latest_message or ""
        matches = [event for event in base if not event.get("done") and (
            event["title"] in message or
            ("搬家" in message and any(word in event["title"] for word in ("完成搬家", "搬入新住处"))) or
            ("向单位确认入职" in message and "向单位确认入职" in event["title"])
        )]
        if len(matches) == 1:
            event = matches[0]
            target = re.search(r"(?:(20\d{2})[年/-])?(\d{1,2})[月/-](\d{1,2})日?", message)
            offset = re.search(r"提前([一二三四五六七八九十\d]+)天", message)
            hour = re.search(r"(?:上午|早上|下午|晚上)?\s*(\d{1,2})\s*[点时](?:\s*(\d{1,2})分?)?", message)
            if target:
                year = int(target.group(1) or (event.get("due_date") or today.isoformat())[:4])
                try:
                    reminder_day = date(year, int(target.group(2)), int(target.group(3)))
                except ValueError:
                    reminder_day = None
            elif offset and event.get("due_date"):
                days = int(offset.group(1)) if offset.group(1).isdigit() else {"一": 1, "二": 2, "三": 3, "四": 4, "五": 5, "六": 6, "七": 7}.get(offset.group(1))
                reminder_day = date.fromisoformat(event["due_date"]) - timedelta(days=days) if days is not None else None
            else:
                reminder_day = None
            if reminder_day:
                reminder_hour = int(hour.group(1)) if hour else 9
                if hour and re.search(r"下午|晚上", message) and reminder_hour < 12:
                    reminder_hour += 12
                reminder_minute = int(hour.group(2) or 0) if hour else 0
                if reminder_hour <= 23 and reminder_minute <= 59:
                    reminder_at = f"{reminder_day.isoformat()}T{reminder_hour:02d}:{reminder_minute:02d}"
                    changed_task_date = bool(target and re.search(r"(?:任务|事项).{0,8}改到|改到.{0,20}提醒", message))
                    result.update({
                        "response_mode": "C", "calendar_intent": "none", "quick_choices": [],
                        "operations": [], "advice_items": [], "follow_ups": [],
                        "answer": f"Reminder settings cannot be changed from chat. Go to Profile → Reminder settings to adjust the reminder for “{_english_display(event['title'])}”. In-app reminders appear only when you open the page; WeChat subscription and background notifications are not connected.",
                    })
                    return _english_result(result)

    # 全局提醒偏好及尚未接入的微信提醒仍引导到设置页。
    if "提醒" in (latest_message or "") and re.search(r"(?:改|设置|设为|开启|打开|关闭|提前)", latest_message or ""):
        result.update({
            "response_mode": "C", "calendar_intent": "none", "operations": [],
            "advice_items": [], "follow_ups": [],
            "answer": "Reminder preferences are saved under Profile → Reminder settings. Chat cannot change individual reminder times or background scheduling. In-app reminders appear only when you open the page; WeChat notifications are not connected and cannot be enabled or sent here.",
        })
        return _english_result(result)

    # 月租数额不说明是否包含水电、网络等经常性费用。区域结论前
    # 先问清预算口径，避免把抽样租金当成可负担总费用。
    region_question = re.search(r"(?:哪些|哪个|什么).{0,12}区域|区域.{0,12}(?:适合|推荐)|住哪里", latest_message or "") or re.search(r"\b(?:which|what)\s+(?:areas?|neighborhoods?).{0,35}\b(?:suit|consider|live)|\bwhere\s+(?:should|can)\s+i\s+live\b", latest_message or "", re.I)
    budget_available = re.search(r"(?:租金|月租|租房预算).{0,8}\d{3,5}|\d{3,5}.{0,8}(?:租金|月租)", latest_message or "") or re.search(r"\b(?:rent|monthly rent|rent budget|housing budget)\D{0,18}\d{1,3}(?:,\d{3})?\b|\b\d{1,3}(?:,\d{3})?\s*(?:yuan|cny)?\s*(?:monthly rent|rent budget|housing budget)\b", latest_message or "", re.I) or (profile or {}).get("monthly_rent_budget")
    if region_question and budget_available:
        scope_known = re.search(r"(?:只算|仅含|不含|包含|包括|含).{0,12}(?:水电|网费|物业|杂费|房租|租金)", latest_message or "") or re.search(r"\b(?:rent only|including (?:utilities|internet|fees)|(?:utilities|internet|property fees) included|excluding (?:utilities|internet))\b", latest_message or "", re.I)
        scope_saved = re.search(r"(?:只算|仅含|不含|包含|包括|含).{0,12}(?:水电|网费|物业|杂费)", str((profile or {}).get("monthly_rent_budget", "")))
        if not scope_known and not scope_saved:
            questions = ["Does your monthly budget cover rent only, or also utilities, internet, and property fees?"]
            if not (profile or {}).get("shared_housing") and not re.search(r"合租|整租|shared|entire unit|whole apartment", latest_message or "", re.I):
                questions.append("Are you open to shared housing, or are you looking for an entire unit only?")
            result.update({
                "response_mode": "C", "calendar_intent": "none", "operations": [],
                "advice_items": [], "follow_ups": questions,
                "answer": "Summary of current information: I have your monthly rent limit. Before comparing areas, I need to clarify whether that budget includes recurring fees; utilities, internet, and property fees may be charged separately.\n" + "\n".join(questions),
            })
            return _english_result(result)

    # 用户明确要求将搬家推到已知入职日之后时，先提供处理方向。
    # 只有其后明确选择接受该方案，才继续生成改期提议。
    if _move_change_requested(latest_message) and not _accepted_move_after_hire(latest_message):
        move_target = _profile_date((profile or {}).get("move_deadline"), today)
        hire_target = _profile_date((profile or {}).get("start_date"), today)
        if move_target and hire_target and move_target > hire_target:
            previous_day = (date.fromisoformat(hire_target) - timedelta(days=1)).isoformat()
            result.update({
                "response_mode": "E", "calendar_intent": "none", "operations": [],
                "advice_items": [], "follow_ups": [],
                "quick_choices": [f"Move before my start date ({previous_day})", f"Accept moving after my start date ({move_target}) and verify transition arrangements"],
                "answer": f"Your move completion target ({move_target}) is after your start date ({hire_target}), which may affect your pre-start commute, housing, and belongings. Choose whether to move before your start date or accept moving afterward and verify temporary housing and commute arrangements first. A schedule proposal will be prepared after you choose.",
            })
            return _english_result(result)

    # 冲突选项带回明确日期后，也必须形成真正的待确认 update。
    # 同时兜住模型只写文字、不输出 operations 的情况。
    explicit_move_choice = _move_change_requested(latest_message) or _accepted_move_after_hire(latest_message)
    explicit_target = _explicit_move_target(latest_message, today)
    has_date = bool(re.search(r"(?:20\d{2}[年/-])?\d{1,2}[月/-]\d{1,2}[日号]?", latest_message or "") or _date_from_message(latest_message, today))
    if explicit_move_choice and (explicit_target or (_accepted_move_after_hire(latest_message) and has_date)):
        # Prefer the date in this explicit command. The profile may still contain
        # the previous target while the user is revising an existing pending draft.
        move_target = explicit_target or _profile_date((profile or {}).get("move_deadline"), today)
        move_events = [
            event for event in base if not event.get("done")
            and _task_kind(event["title"]) == "move_completion"
        ]
        if move_target and move_events:
            move_ids = {event["id"] for event in move_events}
            ops = [item for item in ops if item.get("id") not in move_ids]
            for event in move_events:
                if event.get("due_date") != move_target:
                    ops.append(_operation("update", event, due_date=move_target, date_basis="用户明确", source_note="Move date explicitly selected by the user; not saved until confirmation."))
            hire_target = _profile_date((profile or {}).get("start_date"), today)
            if _accepted_move_after_hire(latest_message) and hire_target and move_target > hire_target:
                title = "Verify temporary housing and commute between start date and move-in"
                if not any(title == event["title"] and not event.get("done") for event in base):
                    due = max(today, date.fromisoformat(hire_target) - timedelta(days=1)).isoformat()
                    ops.append(_operation("add", title=title, due_date=due, detail="Confirm accommodation, luggage storage, the route to work, and costs between the start date and move-in. Contact any accommodation or transport provider yourself.", date_basis="建议日期", source_note="Risk check based on the user choosing to move after their start date; no temporary accommodation has been booked."))
            if ops:
                result["response_mode"] = "D"
                result["calendar_intent"] = "propose"
                result["answer"] = f"The move completion target is proposed to change to {move_target}. Please also verify housing and commute arrangements between your start date and move-in. Review the changes below; your calendar will remain unchanged until you confirm."
                result["advice_items"] = []
                result["follow_ups"] = []

    # 入职日期是硬顺序约束：通勤试走必须发生在报到日前，不能随着原日期
    # 留在入职后。模型漏提或误排时，在确认表中补上确定的关联变更。
    initial_plan_request = plan_request and empty_calendar
    hire_match = None if initial_plan_request else re.search(r"入职(?:日期|时间)?[^\n]{0,16}?(?:改到|改到了|改为|调整到|调整为|变更为)\s*(?:(\d{4})年)?(\d{1,2})月(\d{1,2})[日号]?", latest_message or "")
    english_hire_date = None
    if not initial_plan_request and not hire_match:
        english_hire_match = re.search(r"\b(?:start date|onboarding date|start work date)\s+(?:has been changed to|has changed to|was changed to|changed to|is now|to|is)\s+([^,.\n]+)", latest_message or "", re.I)
        if english_hire_match:
            english_hire_date = _english_date(english_hire_match.group(1).strip(), today)
    if hire_match or english_hire_date:
        if english_hire_date:
            hire_date = english_hire_date
        else:
            year = int(hire_match.group(1) or today.year)
            month, day = int(hire_match.group(2)), int(hire_match.group(3))
            try:
                hire_date = date(year, month, day)
            except ValueError:
                hire_date = None
        if hire_date:
            commute_date = (hire_date - timedelta(days=1)).isoformat()
            result["quick_choices"] = []
            answer_parts = [f"Your start date is now {hire_date.isoformat()}. Only affected tasks are listed below; your calendar will not change until you confirm."]
            commute_events = [event for event in base if _task_kind(event.get("title", "")) == "commute_walkthrough" and not event.get("done")]
            for event in commute_events:
                ops = [item for item in ops if item.get("id") != event.get("id")]
                if not event.get("due_date") or event["due_date"] >= hire_date.isoformat():
                    ops.append(_operation("update", event, due_date=commute_date, detail=event.get("detail", "") + " The commute walkthrough must take place before the updated start date.", date_basis="建议日期", source_note="Prerequisite scheduled before the updated start date."))
                    answer_parts.append(f"The commute walkthrough is proposed for the day before your start date ({commute_date}).")

            # 入职提前不等于每一项搬家安排都要重写。只有原有的“完成搬家”
            # 目标晚于新入职日时，才需要把它提前到入职前一天并出现在确认表。
            # 已经早于新入职日的目标是有效安排，既不修改，也不作为无变化项展示。
            move_events = [
                event for event in base
                if not event.get("done")
                and _task_kind(event.get("title", "")) == "move_completion"
                and event.get("due_date")
            ]
            moved_earlier = []
            stable_move_ids = set()
            for event in move_events:
                move_day = date.fromisoformat(event["due_date"])
                if move_day > hire_date:
                    target = commute_date
                    ops = [item for item in ops if item.get("id") != event["id"]]
                    ops.append(_operation(
                        "update", event, due_date=target,
                        detail=event.get("detail", "") + " The start date moved earlier, so the target move completion date should be before it.",
                        date_basis="建议日期", source_note="Suggested order to complete the move before the new start date; not saved until confirmed.",
                    ))
                    moved_earlier.append(target)
                else:
                    stable_move_ids.add(event["id"])

            if stable_move_ids:
                # 模型可能会把无变化的搬家任务一并带入 operations；明确剔除，
                # 让确认表只保留实际变化的事项。
                ops = [
                    item for item in ops
                    if item.get("id") not in stable_move_ids
                    and not (
                        item.get("action") == "add"
                        and _task_kind(item.get("title", "")) == "move_completion"
                    )
                ]

            if moved_earlier:
                answer_parts.append(f"The original move completion target is after the new start date and is proposed to move to {moved_earlier[0]}; please confirm below.")
            elif move_events:
                answer_parts.append("The current move completion target is already before your new start date, so it remains unchanged and is omitted from the confirmation list.")
            result["answer"] = "\n".join(answer_parts)
            result["calendar_intent"] = "propose" if ops else "none"
            if ops:
                result["response_mode"] = "D"
                result["advice_items"] = []
                result["follow_ups"] = []

    # A request to move the relocation completion date must not silently rewrite
    # unrelated onboarding tasks that happen to be in the model's plan output.
    if re.search(r"搬家完成(?:时间|日)?.{0,20}(?:改到|调整|变更)", latest_message or ""):
        relocation_words = ("搬家", "搬入", "入住", "旧住处", "退租", "交接", "宽带", "网络", "水电", "燃气", "居住登记")
        related_ids = {
            event["id"] for event in base
            if any(word in event["title"] for word in relocation_words)
        }
        ops = [
            item for item in ops
            if item.get("id") in related_ids
            or (item.get("action") == "add" and any(word in item.get("title", "") for word in relocation_words))
        ]

    if re.search(r"已(?:经)?找到房子|已(?:经)?确定住处", latest_message or "") or re.search(r"\b(?:apartment|place|home)\s+(?:is\s+)?(?:settled|confirmed|secured)|\bfound\s+(?:an?\s+)?(?:apartment|place|home)\b", latest_message or "", re.I):
        result["calendar_intent"] = "propose"
        search_words = ("区域参考", "租房注意", "找房", "看房", "筛选房源", "筛选允许养猫", "area screening", "home search", "apartment search", "property viewing", "viewing")
        dependency_words = ("交房", "网络", "宽带", "搬家", "入住", "水电", "燃气", "handover", "broadband", "moving", "move-in", "utilities")
        ops = [
            item for item in ops
            if not (item.get("action") in ("add", "update") and any(word in item.get("title", "") for word in dependency_words))
        ]
        for event in base:
            if not event.get("done") and any(word in event["title"].lower() for word in search_words):
                ops.append(_operation("delete", event))
        handover = _profile_date((profile or {}).get("housing_handover_date"), today)
        def ensure(words, title, detail, basis="建议日期"):
            existing = next((item for item in base if not item.get("done") and any(word.lower() in item["title"].lower() for word in words)), None)
            note = "依据用户已确定住所及交房日期重排；确认前不写入计划日历。"
            if existing:
                ops.append(_operation("update", existing, title=title, due_date=handover, detail=detail, date_basis=basis, source_note=note))
            else:
                ops.append(_operation("add", title=title, due_date=handover, detail=detail, date_basis=basis, source_note=note))
        ensure(("交房", "handover"), "Complete the new-home handover and inspection", "Collect the keys, inspect the home, and record meter readings.", "用户明确")
        ensure(("网络", "宽带", "broadband", "internet"), "Verify broadband installation conditions", "Confirm address coverage, installation availability, and required information with the provider; no appointment will be made for you.")
        ensure(("搬家安排", "搬家方案", "moving arrangements", "move preparation"), "Confirm moving arrangements and service window", "Choose a moving method and confirm availability and rescheduling terms directly with the provider.")
        ensure(("水电交接", "utilities handover", "utility handover"), "Move in and verify utility handover", "Check water, electricity, and gas meter readings, billing responsibility, and fixture condition.")

    handover_delayed = re.search(r"交房.{0,30}(?:晚|延期|改到|调整到|延到|推迟到)", latest_message or "") or re.search(r"\bhandover\b.{0,60}\b(?:delayed|postponed|moved)\b", latest_message or "", re.I)
    if handover_delayed:
        has_new_date = bool(re.search(r"(?:改到|延期至|延到|调整到|推迟到)[^。；\n]{0,8}(?:(?:20\d{2})[年/-])?\d{1,2}[月/-]\d{1,2}", latest_message or "") or _date_from_message(latest_message, today))
        if not has_new_date:
            result.update({
                "response_mode": "E", "calendar_intent": "none", "operations": [],
                "advice_items": [], "follow_ups": ["What is the new handover date?"],
                "answer": "A delayed handover may affect moving, internet installation, and move-in arrangements. Please provide the new handover date so the affected proposal can be reviewed. Contact any service provider yourself to reschedule existing bookings.",
            })
            return _english_result(result)
        result["response_mode"] = "D"
        result["calendar_intent"] = "propose"
        target = _profile_date((profile or {}).get("housing_handover_date"), today)
        affected_ids = {
            item["id"] for item in base
            if _task_kind(item["title"]) in {"move_completion", "move_preparation", "broadband", "old_home_handover", "new_home_handover"} or re.search(r"\b(?:handover|broadband|internet installation|moving service|move-in)\b|已预约搬家服务|搬家服务", item["title"], re.I)
        }
        ops = []
        for event in base:
            if event.get("done") or event["id"] not in affected_ids or not target:
                continue
            if _task_kind(event["title"]) in {"old_home_handover", "new_home_handover"} or re.search(r"\b(?:new[- ]home )?handover\b", event["title"], re.I):
                ops.append(_operation("update", event, due_date=target, detail=event.get("detail", "") + " The handover date was updated based on your latest information.", date_basis="用户明确", source_note="New handover date provided by the user."))
            elif _task_kind(event["title"]) == "broadband" and (not event.get("due_date") or event["due_date"] < target):
                service_date = (date.fromisoformat(target) + timedelta(days=1)).isoformat()
                old_date = event.get("due_date") or "Date to be confirmed"
                ops.append(_operation("update", event, title="Confirm broadband rescheduling", due_date=service_date, detail=f"The original booking is {old_date}; it has not been rescheduled with the provider. {event.get('detail', '')}", date_basis="建议日期", source_note="Suggested date only; confirm the actual service time directly with the provider."))
            elif _task_kind(event["title"]) in {"move_completion", "move_preparation"} or re.search(r"\b(?:moving service|move-in handover)\b|已预约搬家服务|搬家服务", event["title"], re.I):
                if event.get("due_date") and event["due_date"] >= target:
                    continue
                booked = "booked" in event["title"].lower() or "reserved" in event["title"].lower() or "已预约" in event["title"] or "已预订" in event["title"]
                new_title = "Confirm moving-service reschedule" if booked else event["title"]
                old_date = event.get("due_date") or "Date to be confirmed"
                detail = (f"The original booking is {old_date}; it has not been rescheduled with the provider. " if booked else "") + event.get("detail", "") + " This is only a proposed in-app date; confirm it yourself."
                ops.append(_operation("update", event, title=new_title, due_date=target, detail=detail, date_basis="建议日期", source_note="Moving and move-in must not occur before the new handover date; external bookings have not been rescheduled."))
        if target:
            if any(_task_kind(event["title"]) == "broadband" for event in base) or re.search(r"\b(?:broadband|internet)\b.{0,20}\bbooked\b", latest_message or "", re.I):
                if not any("contact internet provider to confirm rescheduling" in event["title"].lower() for event in base):
                    ops.append(_operation("add", title="Contact internet provider to confirm rescheduling", due_date=today.isoformat(), detail="Contact the original provider to cancel or reschedule after handover; record the cost and new service window.", date_basis="建议日期", source_note="Reminder for you to confirm directly; no rescheduling has been performed."))
            if any(_task_kind(event["title"]) == "move_preparation" or re.search(r"\bmoving service\b|搬家服务", event["title"], re.I) for event in base):
                if not any("contact moving provider to confirm rescheduling" in event["title"].lower() for event in base):
                    ops.append(_operation("add", title="Contact moving provider to confirm rescheduling", due_date=today.isoformat(), detail="Contact the original moving provider to cancel or reschedule for the handover date or later; record the cost and new service window.", date_basis="建议日期", source_note="Reminder for you to confirm directly; no rescheduling has been performed."))
            result["calendar_intent"] = "propose" if ops else "none"
            result["answer"] = f"The handover date is proposed to change to {target}. Affected internet, moving, or move-in tasks are listed below. Contact providers directly about existing bookings; no changes will be made for you. Your calendar remains unchanged until you confirm." if ops else f"The handover date change to {target} is recorded. No current plan items need adjustment. Verify any external bookings directly with the providers."
            result["advice_items"] = []
            result["follow_ups"] = []

    if re.search(r"周末[^\n]{0,10}只有半天|半天[^\n]{0,10}有空", latest_message or "") or re.search(r"\bhalf\s+(?:a|one)\s+day\s+(?:free|available)|\bonly\s+3[-– ]?4\s+hours\b", latest_message or "", re.I):
        dated = {}
        for event in base:
            if event.get("due_date") and not event.get("done"):
                dated.setdefault(event["due_date"], []).append(event)
        if dated:
            crowded_date, crowded = max(dated.items(), key=lambda item: len(item[1]))
            if len(crowded) > 3:
                result["response_mode"] = "D"
                result["calendar_intent"] = "propose"
                result["answer"] = f"Summary of current information: You have about 3–4 hours available on weekends. {len(crowded)} tasks currently fall on {crowded_date}; the proposal keeps blockers in place and moves lighter tasks to nearby weekday evenings. Nothing will be written to your calendar until you confirm."
                result["advice_items"] = []
                result["follow_ups"] = []
                result["quick_choices"] = []
                def priority(event):
                    title = event["title"]
                    if _task_kind(title) in {"housing_viewing", "rental_contract"} or re.search(r"\b(?:viewing|lease signing|rental contract)\b", title, re.I):
                        return 0
                    if _task_kind(title) == "hr_onboarding" or re.search(r"\b(?:hr|onboarding|start date)\b", title, re.I):
                        return 1
                    return 2
                def estimated_hours(event):
                    detail = event.get("detail", "")
                    match = re.search(r"(?:预计|约|需|about|approx(?:imately)?|takes?)?\s*(\d+(?:\.\d+)?)\s*(?:小时|hours?|h)(?![a-z])", detail, re.I)
                    if match:
                        return float(match.group(1))
                    if "半小时" in detail or "half an hour" in detail.lower():
                        return 0.5
                    return 3.0 if priority(event) == 0 else 0.5 if priority(event) == 1 else 1.0
                kept, movable, used_hours = [], [], 0.0
                for event in sorted(crowded, key=priority):
                    duration = estimated_hours(event)
                    if event.get("hard_deadline") or (len(kept) < 3 and used_hours + duration <= 4):
                        kept.append(event)
                        used_hours += duration
                    else:
                        movable.append(event)
                if used_hours > 4 or len(kept) > 3:
                    result.update({"response_mode": "E", "calendar_intent": "none", "operations": [],
                                   "answer": f"Hard deadlines or immovable tasks on {crowded_date} exceed your half-day availability. Please identify which items may move; no conflicting schedule changes are proposed."})
                    return _english_result(result)
                # Keep blockers at their original date. The model may have
                # proposed arbitrary dates for the same crowded events; this
                # deterministic capacity rule owns those updates instead.
                crowded_ids = {event["id"] for event in crowded}
                ops = [item for item in ops if item.get("id") not in crowded_ids]
                base_day = date.fromisoformat(crowded_date)
                offsets = (-1, 1, -2, 2, -3, 3)
                slots = []
                for offset in offsets:
                    slot = base_day + timedelta(days=offset)
                    if slot >= today and slot.weekday() < 5:
                        slots.append(slot.isoformat())
                for index, event in enumerate(movable):
                    target = slots[index % len(slots)] if slots else crowded_date
                    ops.append(_operation(
                        "update", event, due_date=target, due_time="19:00",
                        detail=event.get("detail", "") + " Moved to a weekday evening because weekend availability is limited to half a day.",
                        date_basis="建议日期", source_note="Rescheduled based on the user's 3–4-hour weekend availability.",
                    ))

    full_target = _profile_date((profile or {}).get("full_process_deadline"), today)
    if full_target and re.search(r"\d{1,2}\s*(?:周|天)内完成(?:搬家)?全流程", latest_message or ""):
        result["calendar_intent"] = "propose"
        existing = next((item for item in base if "全流程目标完成里程碑" in item["title"]), None)
        detail = "完成入住后的网络就绪、水电交接及其他基础生活配置核验；该日期与入职日分别管理。"
        planned = next((item for item in ops if "全流程" in item.get("title", "") and "里程碑" in item.get("title", "") and item.get("action") != "delete"), None)
        if planned:
            planned["due_date"] = full_target
            planned["date_basis"] = "用户明确"
            planned["source_note"] = "按用户指定的开始规划日加完整天数换算。"
        else:
            ops.append(_operation("update" if existing else "add", existing, title="全流程目标完成里程碑", due_date=full_target, detail=detail, date_basis="用户明确", source_note="按用户指定的开始规划日加完整天数换算。"))

    result["operations"] = ops[:30]
    return _english_result(result)


def _propagate_move_date(confirmed, candidate, touched_ids=None, today=None):
    """Keep the common move handoff task aligned when the move date changes."""
    today = today or shanghai_today()
    old_moves = {item["id"]: item for item in confirmed if _task_kind(item["title"]) == "move_completion"}
    for event in candidate:
        if touched_ids is not None and event["id"] not in touched_ids:
            continue
        old = old_moves.get(event["id"])
        if not old or not old.get("due_date") or not event.get("due_date") or old["due_date"] == event["due_date"]:
            continue
        delta = (date.fromisoformat(event["due_date"]) - date.fromisoformat(old["due_date"])).days
        for dependent in candidate:
            if dependent["id"] == event["id"] or dependent.get("hard_deadline") or (touched_ids is not None and dependent["id"] in touched_ids):
                continue
            if _task_kind(dependent["title"]) in {"old_home_handover", "move_preparation"}:
                dependent_due = dependent.get("due_date")
                if not dependent_due:
                    continue
                # Only shift a real move dependency. A stale or unrelated event
                # months away must not be dragged by the same date delta.
                distance = abs((date.fromisoformat(dependent_due) - date.fromisoformat(old["due_date"])).days)
                shifted_due = _shift_date(dependent_due, delta)
                if distance > 60 or date.fromisoformat(shifted_due) < today:
                    continue
                dependent["due_date"] = shifted_due
                dependent["start_date"] = _shift_date(dependent.get("start_date"), delta)


def _propagate_explicit_dependencies(base, candidate, touched_ids):
    """Shift linked, unfinished tasks with their prerequisite; never move hard dates."""
    old = {item["id"]: item for item in base}
    current = {item["id"]: item for item in candidate}
    changed = set(touched_ids)
    for _ in range(len(candidate)):
        new_changes = set()
        for item in candidate:
            if item.get("done") or item.get("hard_deadline") or not item.get("due_date"):
                continue
            for prerequisite_id in item.get("depends_on_ids", []):
                prerequisite = current.get(prerequisite_id)
                previous = old.get(prerequisite_id)
                if prerequisite_id not in changed or not prerequisite or not previous or not prerequisite.get("due_date") or not previous.get("due_date"):
                    continue
                delta = (date.fromisoformat(prerequisite["due_date"]) - date.fromisoformat(previous["due_date"])).days
                if not delta:
                    continue
                if item["id"] not in old or item["id"] in touched_ids:
                    continue
                shifted = _shift_date(old[item["id"]]["due_date"], delta)
                if shifted < prerequisite["due_date"]:
                    shifted = prerequisite["due_date"]
                if shifted != item["due_date"]:
                    offset = (date.fromisoformat(shifted) - date.fromisoformat(item["due_date"])).days
                    item["due_date"] = shifted
                    item["start_date"] = _shift_date(item.get("start_date"), offset)
                    new_changes.add(item["id"])
        if not new_changes:
            break
        changed.update(new_changes)


def _dependency_conflicts(candidate, affected_ids):
    by_id = {item["id"]: item for item in candidate}
    conflicts = []
    for item in candidate:
        for parent_id in item.get("depends_on_ids", []):
            parent = by_id.get(parent_id)
            if not parent or not parent.get("due_date") or not item.get("due_date"):
                continue
            if parent_id in affected_ids or item["id"] in affected_ids:
                if parent["due_date"] > item["due_date"]:
                    conflicts.append(f"{item['title']} ({item['due_date']}) is earlier than prerequisite {parent['title']} ({parent['due_date']}).")
    moved = [item for item in candidate if item["id"] in affected_ids and _task_kind(item["title"]) == "move_completion" and item.get("due_date")]
    for move in moved:
        for item in candidate:
            if item.get("due_date") and _task_kind(item["title"]) == "old_home_handover" and item["due_date"] > move["due_date"]:
                conflicts.append(f"{move['title']} ({move['due_date']}) is earlier than the new-home {item['title']} ({item['due_date']}).")
            if item.get("hard_deadline") and item.get("due_date") and _task_kind(item["title"]) == "old_home_handover" and item["due_date"] < move["due_date"]:
                conflicts.append(f"Hard deadline: {item['title']} ({item['due_date']}) is before the proposed move date ({move['due_date']}). Verify the old-home handover and temporary storage arrangements first.")
    return conflicts


def _remove_past_suggestions(candidate, today=None):
    """Do not surface stale model backfills as current plan items."""
    today = today or shanghai_today()
    kept = []
    for event in candidate:
        due = event.get("due_date")
        if event.get("date_basis") == "建议日期" and due:
            due_day = date.fromisoformat(due)
            if due_day < today:
                continue
            start = event.get("start_date")
            if start and date.fromisoformat(start) < today:
                event["start_date"] = today.isoformat()
        kept.append(event)
    return kept


def build_proposal(calendar_state, model_result, profile=None, today=None):
    """Return the complete proposed schedule and diff, or None.

    The caller sends this to the browser; only the browser's confirm action saves it.
    """
    if model_result.get("calendar_intent") != "propose":
        return None
    if model_result.get("delete_all"):
        confirmed = calendar_state["confirmed"]
        pending = calendar_state["pending"] or []
        original = confirmed if confirmed else pending
        if not original:
            return None
        return {
            "events": [],
            "changes": _changes(original, []),
            "clarifications": [],
            "bulk_delete_all": True,
            "pending_only_delete": not bool(confirmed),
            "removed_pending": [item for item in pending if item["id"] not in {event["id"] for event in confirmed}],
        }
    ops = model_result.get("operations", [])
    if not isinstance(ops, list) or not ops or len(ops) > 30:
        return None
    confirmed = calendar_state["confirmed"]
    today = today or shanghai_today()
    base = calendar_state["pending"] if calendar_state["pending"] is not None else confirmed
    candidate = [dict(item) for item in base]
    clarifications = []
    removed_pending = []
    touched_ids = set()
    title_dependencies = {}
    confirmed_ids = {item["id"] for item in confirmed}
    for op in ops:
        if not isinstance(op, dict):
            continue
        action = op.get("action")
        event_id = op.get("id")
        idx = next((i for i, item in enumerate(candidate) if item["id"] == event_id), None)
        if action == "add":
            try:
                event = _from_operation(op, "e_" + uuid.uuid4().hex[:12])
            except ValueError:
                continue
            same_title = next((item for item in candidate if _title_key(item["title"]) == _title_key(event["title"])), None)
            if same_title is not None:
                if same_title["id"] not in touched_ids and _event_difference(same_title, event):
                    status = "confirmed" if same_title["id"] in confirmed_ids else "pending"
                    clarifications.append(_clarification(same_title, event, status))
                continue
            group = _task_kind(event["title"])
            similar = next((item for item in candidate if group and _task_kind(item["title"]) == group), None)
            if similar is not None and similar["id"] not in touched_ids:
                status = "confirmed" if similar["id"] in confirmed_ids else "pending"
                clarifications.append(_clarification(similar, event, status))
            else:
                candidate.append(event)
                touched_ids.add(event["id"])
                title_dependencies[event["id"]] = op.get("depends_on_titles", [])
        elif action == "update" and idx is not None:
            try:
                candidate[idx] = _from_operation(op, event_id, candidate[idx]["done"], candidate[idx])
                touched_ids.add(event_id)
                title_dependencies[event_id] = op.get("depends_on_titles", [])
            except ValueError:
                continue
        elif action == "delete" and idx is not None:
            if calendar_state["pending"] is not None and candidate[idx]["id"] not in confirmed_ids:
                removed_pending.append({"id": candidate[idx]["id"], "title": candidate[idx]["title"]})
            candidate.pop(idx)
    for item in candidate:
        titles = title_dependencies.get(item["id"], [])
        if not isinstance(titles, list):
            continue
        for title in titles[:12]:
            if not isinstance(title, str):
                continue
            match = next((other for other in candidate if other["id"] != item["id"] and _title_key(other["title"]) == _title_key(title)), None)
            if match and match["id"] not in item["depends_on_ids"]:
                item["depends_on_ids"].append(match["id"])
    _apply_planning_constraints(candidate, touched_ids, profile, today)
    _propagate_move_date(confirmed, candidate, touched_ids, today)
    _propagate_explicit_dependencies(base, candidate, touched_ids)
    for item in candidate:
        item["depends_on_ids"] = [key for key in item.get("depends_on_ids", []) if key in {event["id"] for event in candidate}]
    conflicts = _dependency_conflicts(candidate, touched_ids)
    if conflicts:
        return {"events": base, "changes": [], "clarifications": clarifications, "conflicts": conflicts}
    if len(candidate) > MAX_EVENTS:
        return None
    # When revising an unconfirmed proposal, show only this turn's delta,
    # never every item that was already pending.
    changes = _changes(base, candidate)
    if calendar_state["pending"] is not None and candidate == confirmed:
        return {"events": candidate, "changes": [], "clarifications": clarifications, "removed_pending": removed_pending, "clear_pending": True}
    if not changes and not clarifications:
        if calendar_state["pending"] is not None and candidate != confirmed:
            return None
        return None
    candidate.sort(key=lambda x: (x["due_date"] is None, x["due_date"] or "9999-12-31", x["due_time"] or "99:99", x["title"]))
    return {"events": candidate, "changes": changes, "clarifications": clarifications, "removed_pending": removed_pending}
