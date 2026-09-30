"""English retrieval over the supplied Shanghai research snapshot."""

from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
AREA_DATA = json.loads((ROOT / "data" / "shanghai_area_data_en.json").read_text(encoding="utf-8"))
CITY_KNOWLEDGE = json.loads((ROOT / "data" / "shanghai_knowledge_en.json").read_text(encoding="utf-8"))
TASK_TEMPLATES = json.loads((ROOT / "data" / "task_templates_en.json").read_text(encoding="utf-8"))["templates"]

TOPIC_TERMS = {
    "Pre-employment Health Check": ("health check", "medical check", "onboarding", "physical examination"),
    "Renting": ("rent", "rental", "lease", "housing", "deposit", "landlord", "apartment"),
    "Moving": ("move", "moving", "relocation", "mover", "moving company"),
    "Second-hand": ("second-hand", "used furniture", "used item", "furniture"),
    "Life Service Hotlines": ("hotline", "complaint", "property management", "utility number"),
    "Pets": ("pet", "cat", "dog"),
    "Residence Permit Points": ("points", "residence permit points"),
    "Hukou (Household Registration)": ("hukou", "household registration", "settlement", "graduate settlement"),
    "Social Security Card": ("social security", "social insurance card"),
    "Medical Appointments": ("medical insurance", "health insurance", "hospital", "doctor", "appointment"),
    "Waste Sorting": ("waste sorting", "garbage", "recycling"),
    "Transport": ("transport", "commute", "metro", "subway", "bus", "transit"),
    "Broadband": ("broadband", "internet", "wifi", "mobile broadband"),
    "Gas": ("gas", "natural gas", "gas bill"),
    "Utility Account Transfer": ("utility", "electricity", "water bill", "meter", "account transfer"),
}
PLANNING_TERMS = ("plan", "schedule", "next step", "move to", "relocate", "moving timeline")
AREA_TERMS = ("rent", "rental", "area", "commute", "mall", "supermarket", "market", "where to live", "utilities", "broadband", "move", "plan", "next step")


def _english_only(value):
    """Remove original-Chinese annotations from model context, keeping source data intact."""
    if isinstance(value, dict):
        return {key: _english_only(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_english_only(item) for item in value]
    if isinstance(value, str):
        value = re.sub(r"\s*[（(][^（）()]*[\u3400-\u9fff]+[^（）()]*[）)]", "", value)
        value = re.sub(r"[\u3400-\u9fff]+", "", value)
        return re.sub(r"\s{2,}", " ", value).strip()
    return value


def _all_text(messages: list[dict], profile: dict | None = None) -> str:
    return " ".join(str(m.get("content", "")) for m in messages) + " " + json.dumps(profile or {}, ensure_ascii=False)


def _user_text(messages: list[dict]) -> str:
    """Extract user-provided facts without letting assistant prose spoof constraints."""
    return " ".join(str(message.get("content", "")) for message in messages if message.get("role") == "user")


def supplemental_context(messages: list[dict], profile: dict | None = None) -> dict:
    text = _all_text(messages, profile).lower()
    latest = str(messages[-1].get("content", "")).lower() if messages else ""
    categories = {category for category, terms in TOPIC_TERMS.items() if any(term in text for term in terms)}
    if any(term in latest for term in PLANNING_TERMS):
        categories.update(("Renting", "Moving", "Pre-employment Health Check", "Utility Account Transfer", "Broadband"))
    records = []
    for raw in CITY_KNOWLEDGE.get("knowledge_entries", []):
        if raw.get("category") in categories:
            records.append(dict(raw))
    templates = [dict(row) for row in TASK_TEMPLATES]
    selected_ids = {row.get("id") for row in records}
    for template in templates:
        ids = template.get("knowledge_entry_ids", [])
        template["available_knowledge_entry_ids"] = [entry_id for entry_id in ids if entry_id in selected_ids]
    entries = []
    for raw in CITY_KNOWLEDGE.get("entries", []):
        row = dict(raw)
        row["status"] = "verified" if all(row.get(key) for key in ("url", "service_name", "last_verified", "fallback")) else "pending_verification"
        entries.append(row)
    return {
        "version": CITY_KNOWLEDGE.get("version"),
        "collected_at": CITY_KNOWLEDGE.get("collected_at"),
        "knowledge_entries": _english_only(records),
        "entries": _english_only(entries),
        "task_templates": _english_only(templates),
        "cost_updates": _english_only(CITY_KNOWLEDGE.get("cost_updates", [])),
        "data_gaps": _english_only(CITY_KNOWLEDGE.get("data_gaps", [])),
    }


def _amount(text: str, labels: str) -> int | None:
    normalized = (text or "").replace(",", "")
    match = re.search(rf"(?:{labels})[^\d]{{0,18}}(\d{{3,5}})\s*(?:CNY|yuan)?", normalized, re.I)
    return int(match.group(1)) if match else None


def _commute_limit(text: str) -> int | None:
    text = text.lower()
    if re.search(r"\b(?:flexible|any(?:\s+commute\s+time)?)\b", text):
        return None
    found = re.search(r"(\d{1,3})\s*(?:-|–|to)\s*(\d{1,3})\s*(?:minutes|min)", text)
    if found:
        return int(found.group(2))
    if re.search(r"(?:under|within|less than)\s*2\s*hours", text):
        return 120
    found = re.search(r"(?:commute|one-way)[^\d]{0,16}(\d{1,3})\s*(?:minutes|min)", text) or re.search(r"(\d{1,3})\s*(?:minutes|min)", text)
    return int(found.group(1)) if found else None


HUBS = {
    "Lujiazui": ("lujiazui",),
    "Zhangjiang Hi-Tech": ("zhangjiang hi-tech", "zhangjiang"),
    "Xujiahui": ("xujiahui",),
}


def _matching_hubs(text: str) -> set[str]:
    lowered = (text or "").lower()
    return {name for name, aliases in HUBS.items() if any(alias in lowered for alias in aliases)}


def extract_constraints(messages: list[dict], profile: dict | None = None) -> dict:
    profile = profile or {}
    user_messages = [message for message in messages if message.get("role") == "user"]
    latest = str(user_messages[-1].get("content", "")) if user_messages else ""
    text = (_user_text(messages) + " " + json.dumps(profile, ensure_ascii=False)).lower()
    profile_hubs = _matching_hubs(str(profile.get("company_location", "")))
    user_text = _user_text(messages)
    contextual_office = re.search(r"\b(?:my\s+)?(?:company|office|workplace|work)\b.{0,28}?\b(?:near|at|in|around)\s+([^,.;!?\n]+)", user_text, re.I)
    contextual_hubs = _matching_hubs(contextual_office.group(1)) if contextual_office else set()
    mentioned_hubs = _matching_hubs(user_text)
    hub = next(iter(profile_hubs)) if len(profile_hubs) == 1 else next(iter(contextual_hubs)) if len(contextual_hubs) == 1 else next(iter(mentioned_hubs)) if len(mentioned_hubs) == 1 else None
    commute_text = latest if any(x in latest.lower() for x in ("commute", "one-way")) else str(profile.get("commute_preference", "")) or text
    monthly = str(profile.get("monthly_rent_budget", ""))
    rent = _amount(latest, "monthly rent|rent budget|monthly housing budget|rent") or _amount(text, "monthly rent|rent budget|monthly housing budget|rent") or _amount(monthly, "budget|rent") or (int(m.group(1)) if (m := re.search(r"(\d{3,5})", monthly)) else None)
    shared_text = (text + " " + str(profile.get("shared_housing", ""))).lower()
    shared = False if any(x in shared_text for x in ("not open to shared", "no shared", "entire apartment only")) else True if any(x in shared_text for x in ("open to shared", "shared housing is ok", "accept shared", "shared rental is acceptable", "okay with shared")) else None
    return {"office_hub": hub, "commute_minutes": _commute_limit(commute_text), "monthly_rent": rent, "shared": shared}


def area_references(messages: list[dict], profile: dict | None = None) -> dict:
    constraints = extract_constraints(messages, profile)
    areas = []
    for area in AREA_DATA.get("areas", []):
        commute = next((row for row in area.get("commute", []) if constraints["office_hub"] and constraints["office_hub"].lower() in row.get("to", "").lower()), None)
        if constraints["office_hub"] and commute is None:
            continue
        rent_keys = ["rent_shared_single_room", "rent_whole_1br"] if constraints["shared"] is None else (["rent_shared_single_room"] if constraints["shared"] else ["rent_whole_1br"])
        rents = [{"type": key, **area[key]} for key in rent_keys if area.get(key)]
        fits = None if constraints["commute_minutes"] is None or commute is None else commute["minutes_max"] <= constraints["commute_minutes"]
        if fits is False:
            continue
        relation = "unknown"
        if constraints["monthly_rent"] is not None and rents:
            relation = "sample_within_budget" if any(row["max"] <= constraints["monthly_rent"] for row in rents) else "sample_partly_within_budget" if any(row["min"] <= constraints["monthly_rent"] for row in rents) else "sample_above_budget"
        if relation == "sample_above_budget":
            continue
        areas.append({"area": area["name"], "boundary": area["boundary"], "station": area["reference_station"], "rent_sample": rents, "rent_status": area["data_status"], "rent_note": area["rent_note"], "commute_estimate": commute, "fits_time": fits, "rent_budget_relation": relation, "facilities_pending_verification": {key: [item["name"] for item in values] for key, values in area.get("facilities", {}).items()}})
    return _english_only({"constraints": constraints, "areas": areas[:8], "rent_source": "https://sh.zu.anjuke.com/?from=HomePage_TopBar", "rent_as_of": AREA_DATA["meta"]["researched_at"], "rent_method": AREA_DATA["meta"]["rent_method"], "commute_method": AREA_DATA["meta"]["commute_method"]})


def context_for(messages: list[dict], profile: dict | None = None) -> dict:
    latest = str(messages[-1].get("content", "")).lower() if messages else ""
    area = area_references(messages, profile) if any(term in latest for term in AREA_TERMS) else None
    utilities = _english_only(AREA_DATA.get("utilities", [])) if any(term in latest for term in ("utility", "electricity", "water bill", "gas", "broadband", "internet")) else None
    return {"policies": [], "plan_guidance": [], "area_data": area, "utilities": utilities, "city_knowledge": supplemental_context(messages, profile)}
