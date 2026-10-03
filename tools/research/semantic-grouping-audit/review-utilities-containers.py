"""Build the utilities/containers review from the shared offline Wiki join."""

import csv
import json
import re
from collections import Counter, defaultdict
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
REVIEW = ROOT / "tmp/semantic-audit/reviews/utilities-containers"
REVIEW.mkdir(parents=True,exist_ok=True)
JOINED = ROOT / "tmp/semantic-audit/joined.jsonl"
TARGETED = ROOT / "tmp/semantic-audit/cache/targeted-utilities-pages.json"
OVERLAPS = ROOT / "tmp/semantic-audit/cache/targeted-utility-overlaps.json"
RUNECRAFT = ROOT / "tmp/semantic-audit/cache/targeted-runecraft-pages.json"

WIKI_CATEGORIES = (
    "Currency",
    "Runes",
    "Runecraft",
    "Teleportation items",
    "Tools",
    "Light sources",
    "Storage items",
    "Skilling equipment",
)
CURRENT_CATEGORIES = {"CURRENCY", "RUNE", "TELEPORT", "TOOL"}
CURRENT_TAGS = {"currency", "runes", "teleports", "tools", "containers"}
NAME_CANDIDATE = re.compile(
    r"coin|currency|token|ticket|numulite|stardust|mark of grace|rune|teleport|"
    r"tablet|scroll|amulet|necklace|ring of|whistle|chronicle|pouch|sack|box|bag|"
    r"basket|barrel|bucket|bottle|waterskin|case|kit|storage|pickaxe|axe|spade|"
    r"hammer|chisel|lantern|torch|candle|light source|compass|wrench|tool|key ring|"
    r"lockpick|seed dibber|trowel|harpoon|net|fishing rod|knife|needle|scissors|slayer",
    re.IGNORECASE,
)
CONTEXT_CATEGORIES = {
    "storage-cleanup", "resources", "currency-utilities", "skilling-tools",
    "teleports-runes", "currency-tradeables", "teleports-escapes",
    "cosmetics-outfits", "tools-outfits-pets", "loot-clues-storage", "junk-review",
    "skilling-supplies", "crafting-rc-construction", "farming-herblore",
}

# Reviewed placement candidates. Exact Wiki item states remain separate IDs.
MOVE = {}


def add(ids, role, destination, reason):
    for item_id in ids:
        MOVE[str(item_id)] = (role, destination, reason)


add(
    (6183, 6306, 6529, 12012, 21555, 25527),
    "currency",
    "currency-utilities/currency",
    "Exact Wiki page mechanics identify a spendable exchange currency. This is a semantic role; a preset may retain activity grouping.",
)
add(
    (24607,),
    "restricted-spell-supply",
    "currency-utilities/runes",
    "The exact item page identifies a consumable Ice-spell supply restricted to the Wilderness; preserve that restriction in its spell-supply role.",
)
add(
    (1436, 7936, 24704),
    "runecrafting-resource",
    "resources/raw-resources",
    "The exact item page identifies this as a Runecraft input; keep it with other essence materials rather than castable spell runes.",
)
add(
    (32, 38, 594, 4522, 4524, 4537, 4539, 4700, 4701, 4702),
    "light-source",
    "skilling-tools/tools",
    "The exact item page identifies this state as part of a reusable light-source family. Keep empty, unlit, and lit IDs distinct.",
)
add(
    (5418, 12854, 25459, 25461, 25463, 25465, 25467, 25469, 25470,
     25471, 25472, 25473, 29295, 29299, 29301, 29309, 29462, 29466,
     29468, 33395),
    "resource-container",
    "skilling-tools/containers",
    "The exact item page documents carrying or storage behavior. Preserve capacity and open/closed states as individual item IDs.",
)
add(
    (12791, 24416, 27281, 27509),
    "rune-container",
    "currency-utilities/runes",
    "The exact item page documents rune storage. Locked/normal divine and rune pouch variants remain separate; frequent-use placement is optional.",
)

SPECIAL_CONTEXT = {
    "16": (
        "quest-transport-access",
        "storage-cleanup/quest-items",
        "Wiki says the Magic whistle only works in the Fisher Realm, where it returns the player to Karamja; it is a Holy Grail quest item, so retain its restricted quest-access grouping.",
    ),
    "13666": (
        "moderator-event-teleport",
        "storage-cleanup/cleanup",
        "Wiki identifies the Deadman teleport tablet as a Jagex Moderator-only item used in an old event; do not treat it as a general player teleport.",
    ),
    "20527": (
        "historical-currency",
        "storage-cleanup/cleanup",
        "Wiki identifies Survival tokens as Last Man Standing currency removed in 2019; preserve the historical/obsolete role in cleanup.",
    ),
    "25588": (
        "fishing-consumable-with-shop-use",
        "resources/raw-resources",
        "Wiki says spirit flakes are consumed to improve fishing catches and can also buy fishing equipment; retain their fishing-supply role instead of mapping by Currency category alone.",
    ),
    "33103": (
        "skilling-access-with-teleport",
        "skilling-tools/tools",
        "The amulet improves the milking activity while worn and also provides a charge-based teleport to the cow field; retain the skill-utility role and record transport as secondary use.",
    ),
    "33104": (
        "skilling-access-with-teleport",
        "skilling-tools/tools",
        "Wiki documents faster cow milking while worn and a charge-based teleport to the cow field; retain the skill utility role and record teleport as a secondary use.",
    ),
}

ESSENCE_POUCH_IDS = {5509, 5510, 5511, 5512, 5513, 5514, 5515, 26784, 26786}


def load_pages(path):
    if not path.exists():
        return {}
    payload = json.loads(path.read_text(encoding="utf-8"))
    pages = {}
    for page in payload.get("data", {}).get("query", {}).get("pages", []):
        revisions = page.get("revisions") or []
        if not revisions:
            continue
        revision = revisions[0]
        content = revision.get("slots", {}).get("main", {}).get("content", "")
        rev_id = revision.get("revid", "")
        title = page.get("title", "")
        pages[title.casefold()] = {
            "title": title,
            "revision": rev_id,
            "url": "https://oldschool.runescape.wiki/w/"
                  + title.replace(" ", "_") + ("?oldid=" + str(rev_id) if rev_id else ""),
            "content": content,
        }
    return pages


def mechanic_verified(content, categories, name):
    """Presence only; raw Wiki wording stays in the ignored source cache."""
    return bool(content and (categories or name))


def main():
    joined_path = JOINED
    if not joined_path.exists():
        raise SystemExit(f"Missing shared joined dataset: {joined_path}")
    pages = load_pages(TARGETED)
    pages.update(load_pages(OVERLAPS))
    pages.update(load_pages(RUNECRAFT))
    all_records = []
    with joined_path.open(encoding="utf-8") as source:
        for line in source:
            if line.strip():
                all_records.append(json.loads(line))

    universe = []
    for item in all_records:
        records = item.get("wiki_records", [])
        hits = [category for category in WIKI_CATEGORIES if any(
            record.get("Category:" + category) is True for record in records
        )]
        reasons = []
        if item.get("catalog_category") in CURRENT_CATEGORIES:
            reasons.append("current-category:" + item["catalog_category"])
        if item.get("preset_tag") in CURRENT_TAGS or item.get("preset_tag_by_family") in CURRENT_TAGS:
            reasons.append("current-preset-tag")
        if hits:
            reasons.append("wiki-category")
        if any(detector in item.get("detectors", []) for detector in (
            "TOOL_ROLE_IN_CLEANUP", "CURRENCY_ROLE_OUTSIDE_CURRENCY", "TELEPORT_ROLE_IN_CLEANUP"
        )):
            reasons.append("mechanical-cross-tag-candidate")
        if NAME_CANDIDATE.search(item.get("name", "")) and item.get("preset_category") in CONTEXT_CATEGORIES:
            reasons.append("name-review-candidate")
        if not reasons:
            continue
        universe.append((item, hits, reasons))

    base_fields = [
        "item_id", "name", "catalog_category", "subcategory", "preset_category", "preset_tag",
        "preset_tag_by_family", "wiki_join_status", "wiki_pages", "wiki_urls", "wiki_categories",
        "wiki_examine_available", "quest", "variant_flags", "family_hint", "roles", "detectors", "include_reason",
    ]
    write_csv(REVIEW / "candidate-universe.csv", base_fields, (
        candidate_row(item, hits, reasons) for item, hits, reasons in universe
    ))

    per_id = []
    for item, hits, reasons in universe:
        row = triage_row(item, hits, reasons, pages)
        per_id.append(row)
    fields = list(per_id[0].keys()) if per_id else []
    write_csv(REVIEW / "per-id-review.csv", fields, per_id)
    moves = [row for row in per_id if row["recommendation"] in {"MOVE_CANDIDATE", "ROLE_LABEL_CANDIDATE"}]
    write_csv(REVIEW / "role-grouping-candidates.csv", fields, moves)

    page_rows = {}
    for row in per_id:
        if row["recommendation"] not in {"MOVE_CANDIDATE", "ROLE_LABEL_CANDIDATE", "RETAIN_SPECIAL_CONTEXT"}:
            continue
        key = row.get("wiki_source_url", "")
        if not key:
            continue
        entry = page_rows.setdefault(key, {
            "wiki_source_url": key,
            "wiki_page": row.get("wiki_source_page", ""),
            "wiki_revision": row.get("wiki_source_revision", ""),
            "item_ids": [], "names": [], "roles": [], "evidence": [],
        })
        entry["item_ids"].append(row["item_id"])
        entry["names"].append(row["name"])
        entry["roles"].append(row["candidate_role"])
        entry["evidence"].append(row.get("review_reason", ""))
    page_fields = ["wiki_source_url", "wiki_page", "wiki_revision", "item_ids", "names", "roles", "evidence"]
    page_output = []
    for entry in page_rows.values():
        page_output.append({
            **entry,
            "item_ids": "|".join(dict.fromkeys(entry["item_ids"])),
            "names": "|".join(dict.fromkeys(entry["names"])),
            "roles": "|".join(dict.fromkeys(entry["roles"])),
            "evidence": " || ".join(dict.fromkeys(entry["evidence"])),
        })
    write_csv(REVIEW / "targeted-pages.csv", page_fields, page_output)

    group_rows = build_state_families(all_records, pages)
    group_fields = list(group_rows[0].keys()) if group_rows else []
    write_csv(REVIEW / "state-families.csv", group_fields, group_rows)
    (REVIEW / "state-families.json").write_text(
        json.dumps(group_rows, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )

    category_counts = Counter(category for _, hits, _ in universe for category in hits)
    recommendation_counts = Counter(row["recommendation"] for row in per_id)
    confidence_counts = Counter(row["confidence"] for row in per_id)
    exact_counts = Counter(row["wiki_join_status"] for row in per_id)
    catalog_counts = Counter(row["current_category"] for row in per_id)
    frequent_count = sum(row["frequently_used"] == "true" for row in per_id)
    summary = {
        "domain": "utilities-containers",
        "global_registry_ids": len(all_records),
        "candidate_universe_rows": len(universe),
        "wiki_join_status_counts": dict(exact_counts),
        "current_catalog_category_counts": dict(catalog_counts),
        "wiki_category_item_hit_counts": dict(category_counts),
        "candidate_action_count": len(moves),
        "move_candidates": sum(row["recommendation"] == "MOVE_CANDIDATE" for row in per_id),
        "role_label_candidates": sum(row["recommendation"] == "ROLE_LABEL_CANDIDATE" for row in per_id),
        "state_family_count": len(group_rows),
        "state_family_memberships": sum(len(row["member_ids"].split("|")) for row in group_rows),
        "state_family_tree_edges": sum(max(0, len(row["member_ids"].split("|")) - 1) for row in group_rows),
        "targeted_exact_wiki_page_count": len(page_output),
        "current_frequently_used_count": frequent_count,
        "recommendation_counts": dict(recommendation_counts),
        "confidence_counts": dict(confidence_counts),
        "policy": "Use item function and exact state; frequency is an optional player preference; Wiki category false/missing does not disprove a role.",
        "limitations": [
            "Candidate universe includes all current Currency/Rune/Teleport/Tool rows, positive relevant Wiki category rows, mechanical cross-tag findings, and broad name-based review candidates.",
            "Wiki categories are page-scoped and may cover several variants; exact-ID matching does not make every category claim variant-specific.",
            "No absent Wiki category or page match is used as negative evidence.",
            "Per-ID move rows are review candidates, not production edits; quest, restricted-use, and multi-use roles remain in evidence notes.",
            "Charge, open/closed, capacity, fuel, lit/unlit, and state variants remain separate item IDs.",
        ],
    }
    (REVIEW / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def candidate_row(item, hits, reasons):
    records = item.get("wiki_records", [])
    return {
        "item_id": item.get("item_id"),
        "name": item.get("name"),
        "catalog_category": item.get("catalog_category"),
        "subcategory": item.get("subcategory"),
        "preset_category": item.get("preset_category"),
        "preset_tag": item.get("preset_tag"),
        "preset_tag_by_family": item.get("preset_tag_by_family"),
        "wiki_join_status": item.get("wiki_join_status"),
        "wiki_pages": " | ".join(record.get("page_name", "") for record in records if record.get("page_name")),
        "wiki_urls": " | ".join(item.get("wiki_urls", [])),
        "wiki_categories": " | ".join(hits),
        "wiki_examine_available": "true" if any(record.get("examine") for record in records) else "false",
        "quest": " | ".join(dict.fromkeys(str(record.get("quest", "")) for record in records if record.get("quest"))),
        "variant_flags": " | ".join(item.get("variant_flags", [])),
        "family_hint": item.get("family_hint", ""),
        "roles": " | ".join(item.get("roles", [])),
        "detectors": " | ".join(item.get("detectors", [])),
        "include_reason": " | ".join(reasons),
    }


def triage_row(item, hits, reasons, pages):
    item_id = str(item.get("item_id"))
    name = item.get("name", "")
    category = item.get("catalog_category", "")
    subcategory = item.get("subcategory", "")
    preset_tag = item.get("preset_tag", "")
    records = item.get("wiki_records", [])
    wiki_url = next(iter(item.get("wiki_urls", [])), "")
    wiki_name = next((record.get("page_name", "") for record in records if record.get("page_name")), "")
    page = pages.get(wiki_name.casefold())
    source_url = page["url"] if page else ""
    source_verified = mechanic_verified(page["content"], hits, name) if page else False
    evidence = ["Wiki category: " + hit for hit in hits]
    if page:
        evidence.append("Exact article content reviewed at revision " + str(page["revision"]))
    elif records:
        evidence.append("Exact-ID structured match; targeted page text not cached")

    role = "possible-utility-or-container"
    destination = "unresolved"
    confidence = "LOW"
    recommendation = "LOW_CONFIDENCE_CANDIDATE"
    reason = "Name/current taxonomy made this a candidate; no negative conclusion is drawn from missing Wiki data."

    if item_id in MOVE:
        role, destination, reason = MOVE[item_id]
        confidence = "HIGH" if source_verified else "MEDIUM"
        recommendation = "MOVE_CANDIDATE"
    elif int(item_id) in ESSENCE_POUCH_IDS:
        role = "runecrafting-essence-container"
        destination = "skilling-tools/tools (container role label correction)"
        confidence = "HIGH" if page else "MEDIUM"
        recommendation = "ROLE_LABEL_CANDIDATE"
        reason = "Wiki identifies an essence-holding Runecraft pouch; this is distinct from a spell-rune pouch. Keep it with Runecraft skill tools and preserve each capacity/damaged state ID."
    elif item_id in SPECIAL_CONTEXT:
        role, destination, reason = SPECIAL_CONTEXT[item_id]
        confidence = "HIGH" if source_verified else "MEDIUM"
        recommendation = "RETAIN_SPECIAL_CONTEXT"
    elif "Teleportation items" in hits and (category in {"GEAR", "TOOL"} or "Skilling equipment" in hits):
        role = "secondary-transport-use"
        destination = "current gear/tool role"
        confidence = "MEDIUM" if item.get("wiki_join_status") == "EXACT_ID_SINGLE" else "LOW"
        recommendation = "REVIEW_OVERLAP"
        reason = "Wiki confirms transport, but an equipment/skilling role may remain primary; retain both facets in the evidence."
    elif "Currency" in hits and "Tools" in hits:
        role = "currency-and-skill-supply-overlap"
        destination = "current resource role pending primary-use review"
        confidence = "MEDIUM" if item.get("wiki_join_status") == "EXACT_ID_SINGLE" else "LOW"
        recommendation = "REVIEW_OVERLAP"
        reason = "Wiki page carries both Currency and Tools categories; full mechanics show both purchase and activity-supply roles."
    elif "Storage items" in hits and category in {"GEAR", "RUNE"}:
        role = "container-with-current-specialized-role"
        destination = "retain current gear/rune destination pending review"
        confidence = "MEDIUM" if item.get("wiki_join_status") == "EXACT_ID_SINGLE" else "LOW"
        recommendation = "REVIEW_OVERLAP"
        reason = "Wiki confirms storage, while current equipment or rune use may define primary placement."
    elif category in CURRENT_CATEGORIES:
        role = category.lower() + (":" + subcategory if subcategory else "")
        destination = "current functional destination"
        confidence = "MEDIUM" if hits and item.get("wiki_join_status") == "EXACT_ID_SINGLE" else "LOW"
        if hits:
            recommendation = "CONFIRM_CURRENT_ROLE"
            reason = "Positive exact-item Wiki category evidence aligns with the current functional role."
        else:
            recommendation = "CURRENT_ROLE_UNVERIFIED"
            reason = "Current role retained; no positive Wiki evidence was joined and category absence is not disproof."
    elif hits:
        role = "wiki-category-candidate"
        destination = "review against exact item mechanics"
        confidence = "MEDIUM" if item.get("wiki_join_status") == "EXACT_ID_SINGLE" else "LOW"
        recommendation = "REVIEW_FUNCTION_OR_ACTIVITY_SCOPE"
        reason = "Page-scoped Wiki categories establish a candidate facet; verify exact state and primary use before changing the current group."

    if category == "CLEANUP" and "Tools" in hits:
        if re.search(r"broken|corrupted|echo (?:axe|pickaxe|harpoon)|mould|mold|fishbowl and net", name, re.I):
            recommendation = "REVIEW_FUNCTION_OR_ACTIVITY_SCOPE"
            confidence = "LOW"
            reason = "Wiki Tools category is page-scoped; current state or quest/activity-only use needs exact review before promotion."

    return {
        "item_id": item_id,
        "name": name,
        "current_category": category,
        "current_subcategory": subcategory,
        "current_preset_category": item.get("preset_category", ""),
        "current_preset_tag": preset_tag,
        "current_family_tag": item.get("preset_tag_by_family", ""),
        "candidate_role": role,
        "candidate_destination": destination,
        "recommendation": recommendation,
        "confidence": confidence,
        "wiki_join_status": item.get("wiki_join_status", ""),
        "wiki_categories": " | ".join(hits),
        "wiki_evidence": " | ".join(evidence),
        "wiki_urls": " | ".join(item.get("wiki_urls", [])),
        "wiki_source_page": page["title"] if page else "",
        "wiki_source_revision": page["revision"] if page else "",
        "wiki_source_url": source_url or wiki_url,
        "wiki_examine_available": "true" if any(record.get("examine") for record in records) else "false",
        "variant_flags": " | ".join(item.get("variant_flags", [])),
        "family_hint": item.get("family_hint", ""),
        "quest": " | ".join(dict.fromkeys(str(record.get("quest", "")) for record in records if record.get("quest"))),
        "review_reason": reason,
        "frequently_used": "true" if preset_tag == "frequently-used" else "false",
        "include_reason": " | ".join(reasons),
    }


def write_csv(path, fieldnames, rows):
    with path.open("w", encoding="utf-8-sig", newline="") as output:
        writer = csv.DictWriter(output, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def build_state_families(records, pages):
    by_id = {str(row.get("item_id")): row for row in records}
    specs = [
        ("light:oil-lamp", "Oil lamp states", [4522, 4524], "light-source", "skilling-tools/tools", "Empty/unlit and lit forms remain distinct item IDs."),
        ("light:oil-lantern", "Oil lantern states", [4537, 4539], "light-source", "skilling-tools/tools", "Unlit and lit forms remain distinct item IDs."),
        ("light:torch", "Torch states", [596, 594], "light-source", "skilling-tools/tools", "Unlit and lit forms remain distinct item IDs."),
        ("light:black-candle", "Black candle states", [38, 32], "light-source", "skilling-tools/tools", "Unlit and lit forms remain distinct; quest use does not eliminate later illumination utility."),
        ("light:sapphire-lantern", "Sapphire lantern states", [4700, 4701, 4702], "light-source", "skilling-tools/tools", "Empty, unlit, and lit forms remain distinct item IDs."),
        ("runes:rune-pouch", "Rune pouch states", [12791, 24416], "spell-rune-container", "currency-utilities/runes", "Locked and usable pouch states retain distinct IDs; both have the spell-rune container role."),
        ("runes:divine-rune-pouch", "Divine rune pouch states", [27281, 27509], "spell-rune-container", "currency-utilities/runes", "Divine pouch variants retain distinct IDs and capacity/state semantics."),
        ("runecraft:essence-pouch", "Runecraft essence pouch states", [5509, 5510, 5511, 5512, 5513, 5514, 5515, 26784, 26786], "runecrafting-essence-container", "skilling-tools/tools", "Pouch size, damaged state, and colossal capacity remain distinct; these hold essence for Runecrafting rather than spell runes."),
        ("container:coffin-bronze", "Bronze coffin states", [25459, 25469], "activity-storage", "skilling-tools/containers", "Closed/open forms share material tier and capacity; preserve both IDs."),
        ("container:coffin-steel", "Steel coffin states", [25461, 25470], "activity-storage", "skilling-tools/containers", "Closed/open forms share material tier and capacity; preserve both IDs."),
        ("container:coffin-black", "Black coffin states", [25463, 25471], "activity-storage", "skilling-tools/containers", "Closed/open forms share material tier and capacity; preserve both IDs."),
        ("container:coffin-silver", "Silver coffin states", [25465, 25472], "activity-storage", "skilling-tools/containers", "Closed/open forms share material tier and capacity; preserve both IDs."),
        ("container:coffin-gold", "Gold coffin states", [25467, 25473], "activity-storage", "skilling-tools/containers", "Closed/open forms share material tier and capacity; preserve both IDs."),
        ("container:meat-pouch-small", "Small meat pouch states", [29295, 29462], "resource-container", "skilling-tools/containers", "Open/closed state IDs remain separate."),
        ("container:fur-pouch-small", "Small fur pouch states", [29299, 29466], "resource-container", "skilling-tools/containers", "Open/closed state IDs remain separate."),
        ("container:fur-pouch-medium", "Medium fur pouch states", [29301, 29468], "resource-container", "skilling-tools/containers", "Open/closed state IDs remain separate; size tier remains distinct."),
        ("utility:cowbell-amulet", "Cowbell amulet charge states", [33103, 33104], "skilling-access-with-teleport", "skilling-tools/tools", "Worn cow-milking utility remains primary; charge-based cow-field transport is secondary. Empty/charged IDs remain distinct."),
    ]
    output = []
    for key, label, ids, role, dest, note in specs:
        available = [by_id[str(item_id)] for item_id in ids if str(item_id) in by_id]
        if len(available) < 2:
            continue
        article_names = []
        for row in available:
            for rec in row.get("wiki_records", []):
                if rec.get("page_name") and rec["page_name"] not in article_names:
                    article_names.append(rec["page_name"])
        page = next((pages.get(name.casefold()) for name in article_names if pages.get(name.casefold())), None)
        cited_pages = [pages[name.casefold()] for name in article_names if pages.get(name.casefold())]
        coverage = len(cited_pages) / max(1, len(article_names))
        output.append({
            "family_key": key, "family_name": label,
            "member_ids": "|".join(str(row["item_id"]) for row in available),
            "member_names": "|".join(str(row.get("name", "")) for row in available),
            "current_categories": "|".join(dict.fromkeys(str(row.get("catalog_category", "")) for row in available)),
            "candidate_role": role, "candidate_destination": dest,
            "source_pages": "|".join(article_names),
            "source_revision": "|".join(f"{entry['title']}:{entry['revision']}" for entry in cited_pages),
            "source_url": "|".join(entry["url"] for entry in cited_pages) if cited_pages else (next(iter(available[0].get("wiki_urls", [])), "")),
            "page_text_coverage": f"{len(cited_pages)}/{len(article_names)}",
            "state_relation": note,
            "confidence": "HIGH" if article_names and coverage == 1 else "MEDIUM" if cited_pages else "LOW",
        })
    return output


if __name__ == "__main__":
    main()
