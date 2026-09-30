"""Conservative, display-only labels for the answer's source lines."""

import re


def annotate_answer(answer: str, evidence: dict) -> list[dict]:
    official = {item["source"] for item in evidence.get("policies", []) if item.get("status") == "verified"}
    area = evidence.get("area_data") or {}
    rent_url = area.get("rent_source")
    labels = []
    city = evidence.get("city_knowledge") or {}
    source_states = {}
    for record in city.get("knowledge_entries", []):
        for source in record.get("evidence") or []:
            if source.get("url"):
                source_states.setdefault(source["url"], set()).add(record["status"])
    entry_urls = {entry["url"] for entry in city.get("entries", [])
                  if entry.get("url") and entry.get("status") == "verified"}
    for index, line in enumerate(answer.splitlines()):
        if "Evidence and status" not in line and "Information and entry point" not in line:
            continue
        tags = []
        link = None
        matched = next((url for url in official if url in line), None)
        if matched:
            tags.append("Official source verified")
            link = matched
        for url, states in source_states.items():
            if url not in line:
                continue
            link = link or url
            # A shared source can back both checked and unchecked claims.
            if "pending_verification" in states:
                tags.append("Pending verification")
            elif "sample_reference" in states:
                tags.append("Sample reference")
            elif states == {"verified"}:
                tags.append("Knowledge source verified")
        entry_link = next((url for url in entry_urls if url in line), None)
        if entry_link:
            tags.append("Service entry verified")
            link = link or entry_link
        if rent_url and rent_url in line:
            tags.append("Listing sample" + (" · " + str(area["rent_as_of"]) if area.get("rent_as_of") else ""))
            link = link or rent_url
        if "commute" in line.lower() and ("estimate" in line.lower() or "estimated" in line.lower()):
            tags.append("Commute estimate")
        if any(term in line.lower() for term in ("amenities pending verification", "map verification", "poi pending verification")):
            tags.append("Amenities pending verification")
        if any(term in line.lower() for term in ("pending verification", "needs verification", "date to be confirmed")):
            tags.append("Partially verified" if tags else "Pending verification")
        if not tags:
            tags.append("Entry point or evidence needs verification")
        labels.append({"line": index, "tags": list(dict.fromkeys(tags)), "verified_url": link})
    return labels
