"""Clearly labelled, deterministic English UI demo. Never presented as an LLM answer."""

from __future__ import annotations

from datetime import date, timedelta

from knowledge import area_references, extract_constraints
from time_utils import shanghai_today


def answer(messages: list[dict]) -> str:
    latest = messages[-1]["content"]
    constraints = extract_constraints(messages)
    missing = []
    if not constraints["office_hub"]:
        missing.append("office location (area references currently cover Lujiazui, Zhangjiang Hi-Tech, and Xujiahui)")
    if constraints["commute_minutes"] is None:
        missing.append("your preferred one-way commute time")
    if constraints["monthly_rent"] is None:
        missing.append("your monthly rent budget, separate from your one-time moving budget")
    if constraints["shared"] is None:
        missing.append("whether you are open to shared housing")
    parts = ["Local demo mode — no language model was called."]
    if any(word in latest.lower() for word in ("rent", "commute", "area", "where to live", "moving", "relocation")):
        if missing:
            parts.append("To compare area references, please share " + "; ".join(missing) + ".")
        else:
            rows = area_references(messages)["areas"]
            if rows:
                for row in rows[:3]:
                    commute = row["commute_estimate"]
                    rents = row["rent_sample"]
                    descriptions = "; ".join(f"{'shared single room' if rent['type'] == 'rent_shared_single_room' else 'entire one-bedroom'} listing sample: CNY {rent['min']}–{rent['max']}/month" for rent in rents)
                    parts.append(f"{row['area']}: {descriptions}; estimated network commute to {constraints['office_hub']}: {commute['minutes_min']}–{commute['minutes_max']} minutes.")
                parts.append("These are September 22, 2026 listing samples and metro-network estimates, not live listings or measured commute times. Nearby amenities still need map verification.")
            else:
                parts.append("No reference among the eight sampled areas meets all of these conditions. You could widen the budget or commute range.")
    if any(word in latest.lower() for word in ("social insurance", "social security")):
        parts.append("Employers must register employees for social insurance within 30 days from the start of employment. Residence registration is not a prerequisite for employer enrollment. Source: https://www.samr.gov.cn/zw/zfxxgk/fdzdgknr/bgt/art/2023/art_e81d115419b4463ebb59ec46467fb136.html")
    if "residence permit" in latest.lower() or "residence registration" in latest.lower():
        parts.append("Residence registration for six months is one route to a Shanghai residence permit when the applicable conditions are met. A separate route may apply after six consecutive months of Shanghai social-insurance contributions. Verify your eligibility and current requirements through the official service channel: https://www.shanghai.gov.cn/nw17239/20251217/676967f3436c49ea8dfe28fb117a89e9.html")
    if len(parts) == 1:
        parts.append("I received your question. Demo mode shows the interface and a small set of prepared examples. Configure a language model to enable follow-up questions and personalized plans.")
    return "\n\n".join(parts)


def response(messages: list[dict], profile: dict | None = None, calendar: dict | None = None) -> dict:
    """Return deterministic, explicitly labelled demo responses and proposals."""
    latest = messages[-1]["content"] if messages else ""
    lowered = latest.lower()
    plan_requested = any(term in lowered for term in ("create a plan", "make a plan", "generate a plan", "relocation plan", "full plan"))
    if not plan_requested:
        return {
            "response_mode": "C",
            "answer": answer(messages),
            "quick_choices": [],
            "advice_items": [],
            "follow_ups": [],
            "calendar_intent": "none",
            "operations": [],
            "profile_updates": [],
        }

    today = shanghai_today()
    profile = profile if isinstance(profile, dict) else {}
    raw_start = profile.get("start_date")
    try:
        start = date.fromisoformat(raw_start) if isinstance(raw_start, str) else today + timedelta(days=21)
    except ValueError:
        start = today + timedelta(days=21)
    first_date = max(today + timedelta(days=2), start - timedelta(days=14))
    plan_items = [
        ("Compare Shanghai area reference ranges", first_date, "Review sample rent ranges and estimated metro journeys; they are not live quotes or measured trips."),
        ("Prepare questions for the housing handover", max(first_date, start - timedelta(days=7)), "Confirm access, utility responsibilities, and move-in conditions directly with the relevant contact."),
        ("Review move-day tasks and dependencies", max(first_date, start - timedelta(days=3)), "Check the move sequence and keep any fixed deadlines unchanged."),
    ]
    operations = [{
        "action": "add", "id": "", "title": title,
        "start_date": due.isoformat(), "due_date": due.isoformat(), "due_time": None,
        "detail": detail, "kind": "task", "date_basis": "建议日期",
        "source_note": "Illustrative demo suggestion; verify the date and details before confirming.",
        "sources": [], "hard_deadline": False, "depends_on_ids": [], "depends_on_titles": [],
    } for title, due, detail in plan_items]
    return {
        "response_mode": "B",
        "answer": "Demo plan prepared from the fictional sample profile. Review the suggested tasks and dates; they are not verified deadlines and will be added only if you confirm.",
        "quick_choices": [],
        "advice_items": [],
        "follow_ups": [],
        "calendar_intent": "propose",
        "operations": operations,
        "profile_updates": [],
    }
