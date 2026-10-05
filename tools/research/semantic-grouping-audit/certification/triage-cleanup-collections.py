#!/usr/bin/env python3
"""Build a curated, exact-Wiki proposal set for cleanup collection items.

This is research output only. It reads the frozen coverage export, reviewer
packet, cleanup decisions, and pinned article index, then writes a reviewable
JSON file. It does not change catalog data or apply category proposals.
"""
from __future__ import annotations

import csv
import hashlib
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
INDEX = ROOT / "tmp/category-certification/wiki-articles/article-index.json"
PACKET = ROOT / "tmp/category-certification/reviewer-packets/cleanup-other.jsonl"
DECISIONS = ROOT / "tmp/category-certification/reviews/cleanup-other/decisions.jsonl"
COVERAGE = ROOT / "tmp/category-certification/current-coverage.tsv"
OUTPUT = ROOT / "tools/research/semantic-grouping-audit/certification/cleanup-collections-proposals.json"

# Directly described aesthetic clue items. Reward origin alone is never used
# as evidence; the exact pinned item's own article must say cosmetic/aesthetic.
COSMETIC_IDS = {
    12245, 12251, 12319, 12335, 12351, 12353, 12355, 12359, 12361,
    12393, 12395, 12397, 12428, 12432, 12439, 12540, 19915,
    19943, 19946, 19949, 19952, 19955, 20029, 20032, 20056,
    20240, 20243, 20246, 20266, 20269, 23224, 23252, 23255,
    23285, 23288, 23291, 23294, 23300, 23312, 23407, 23410,
}

# Exact source-documented home displays; display and alternate functions are
# represented independently in roles. IDs are checked against source variants.
TROPHY_IDS = {
    7976, 7978, 7979, 7980, 12936, 13245, 13277, 19701, 21745,
    21907, 22106, 23525, 24495, 25521, 25524, 29786,
    31408, 31412, 31416, 31420, 31424, 31428,
}

# Exact materials with explicit equipment/ability upgrade mechanics.
UPGRADE_IDS = {30793, 30806, 31109, 31111, 33634}
WEAPON_UPGRADE_IDS = {27627}
PET_UNLOCK_IDS = {24733, 26820, 27377, 27378, 27379, 27380, 27381, 29781}

EXCLUDED_NO_PET = {
    7771,   # Toy cat, a toy rather than a companion pet
    19558,  # Nieve inventory failsafe while an NPC follows during a quest
    26594,  # Grubfoot follower failsafe item, not intended to be received
    28410,  # Dr Banikan follower failsafe item
    28809,  # Elias White quest follower failsafe item
    29867,  # Prince Itzla Arkan follower item
    33720, 33721,  # quest NPC follower failsafe items
}


def read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def quote_for(text: str, patterns: list[str]) -> str | None:
    for line in text.splitlines():
        candidate = line.strip()
        if len(candidate) < 25 or len(candidate) > 900:
            continue
        if all(re.search(p, candidate, re.I) for p in patterns):
            return candidate[:700]
    return None


def exact_article(item_id: int, index: dict, by_id: dict, item_name: str | None = None) -> tuple[str, dict, str]:
    candidates = by_id.get(item_id, [])
    if item_name:
        exact_name = [pair for pair in candidates if pair[1].get("variants", {}).get(str(item_id), {}).get("name", "").casefold() == item_name.casefold()]
        if exact_name:
            candidates = exact_name
    title, article = sorted(candidates, key=lambda pair: (pair[0].casefold() != (item_name or "").casefold(), pair[0].casefold()))[0] if candidates else (None, None)
    if not article or item_id not in article.get("exactInfoboxItemIds", []):
        raise ValueError(f"ID {item_id} has no exact pinned infobox variant")
    text_path = ROOT / article["path"].replace("\\", "/")
    text = text_path.read_text(encoding="utf-8")
    return title, article, text


def proposal(item_id: int, group: str, title: str, article: dict, quote: str,
             target_category: str, target_subcategory: str, tab: str,
             roles: list[str], tags: list[str], rationale: str) -> dict:
    return {
        "itemId": item_id,
        "currentCategory": "CLEANUP",
        "currentSubcategory": "cleanup",
        "targetCategory": target_category,
        "targetSubcategory": target_subcategory,
        "targetIronmanTabKey": tab,
        "proposedRoles": roles,
        "proposedTags": tags,
        "proposalGroup": group,
        "rationale": rationale,
        "exactVariant": {
            "id": item_id,
            "idField": next((k for k, v in article.get("variants", {}).get(str(item_id), {}).get("params", {}).items()
                              if k == "id" or re.fullmatch(r"id\d+", k) if str(v) == str(item_id)), None),
            "name": article.get("variants", {}).get(str(item_id), {}).get("params", {}).get("name", ""),
            "variant": article.get("variants", {}).get(str(item_id), {}).get("variant", ""),
            "suffix": article.get("variants", {}).get(str(item_id), {}).get("suffix", ""),
            "variantLabel": article.get("variants", {}).get(str(item_id), {}).get("label", ""),
            "bankable": article.get("variants", {}).get(str(item_id), {}).get("params", {}).get("bankable"),
            "tradeable": article.get("variants", {}).get(str(item_id), {}).get("params", {}).get("tradeable"),
            "equipable": article.get("variants", {}).get(str(item_id), {}).get("params", {}).get("equipable"),
            "options": article.get("variants", {}).get(str(item_id), {}).get("params", {}).get("options"),
        },
        "evidence": [{
            "kind": "exact_wiki",
            "sourceTitle": title,
            "source": article["sourceUrl"],
            "sourceRevision": article["revid"],
            "sourceHash": "sha256:" + article["sha256"],
            "itemId": item_id,
            "quote": quote,
        }],
    }


def main() -> None:
    index = json.loads(INDEX.read_text(encoding="utf-8"))
    by_id: dict[int, list[tuple[str, dict]]] = {}
    for title, article in index.items():
        for exact_id in article.get("exactInfoboxItemIds", []):
            by_id.setdefault(exact_id, []).append((title, article))

    cleanup_rows = {r["itemId"]: r for r in read_jsonl(PACKET)}
    excluded = sorted({r["itemId"] for r in read_jsonl(DECISIONS) if r["decision"] == "revise"})
    current = {int(r["itemId"]): r for r in csv.DictReader(COVERAGE.open(encoding="utf-8-sig", newline=""), delimiter="\t")}
    proposals: list[dict] = []
    unresolved: list[dict] = []

    def add_exact(i: int, group: str, regexes: list[str], category: str,
                  subcategory: str, roles: list[str], tags: list[str],
                  rationale: str) -> None:
        row = cleanup_rows.get(i)
        if not row or i in excluded or current.get(i, {}).get("itemCategory") != "CLEANUP":
            return
        try:
            title, article, text = exact_article(i, index, by_id, row.get("catalogName"))
            quote = quote_for(text, regexes)
            if not quote:
                raise ValueError("no exact literal article line matched the required mechanics")
            proposals.append(proposal(i, group, title, article, quote, category,
                                      subcategory, "clues-cosmetics", roles, tags, rationale))
        except (OSError, ValueError) as exc:
            unresolved.append({"itemId": i, "proposalGroup": group, "reason": str(exc)})

    for i in sorted(COSMETIC_IDS):
        before = len(proposals)
        add_exact(i, "treasure-trail-cosmetic", [r"cosmetic|aesthetic"], "CLUE", "cosmetic",
                  ["cosmetic_or_style_retention"], ["cosmetic"],
                  "The exact item article explicitly describes cosmetic or aesthetic use; clue reward provenance is context only.")
        if len(proposals) > before:
            item = proposals[-1]
            record = next((w for w in cleanup_rows[i]["sourceEvidence"].get("wikiRecords", [])
                           if str(i) in [str(x) for x in w.get("item_id", [])]), {})
            if record.get("Category:Warm clothing", False):
                item["proposedTags"].append("warm-clothing")
                item["proposedRoles"].append("warm_clothing")
            if i == 20056:
                item["proposedRoles"].append("walk_animation_modifier")
            elif i == 20243:
                item["proposedRoles"].append("emote_prop")

    # Discover exact collectible pets only where the item article itself says
    # it is a pet; category facets and Collection Log membership are not used.
    for i, row in cleanup_rows.items():
        if i in excluded or current.get(i, {}).get("itemCategory") != "CLEANUP" or i in EXCLUDED_NO_PET:
            continue
        exacts = by_id.get(i)
        if not exacts:
            continue
        title, article, text = exact_article(i, index, by_id, row.get("catalogName"))
        text_path = ROOT / article["path"].replace("\\", "/")
        text = text_path.read_text(encoding="utf-8")
        # Exclude NPC-following failsafes and require a positive direct pet predicate.
        exact_record = next((w for w in row["sourceEvidence"].get("wikiRecords", [])
                             if str(i) in [str(x) for x in w.get("item_id", [])]), {})
        if not exact_record.get("Category:Pets", False):
            continue
        if re.search(r"unobtainable item|not intended to be received by players|follower is forced into the player's backpack", text, re.I):
            continue
        quote = quote_for(text, [r"\bpet\b", r"\bis a\b|\bis an\b|\bis the\b"])
        if not quote or not re.search(r"\bis (?:a|an|the)\b.{0,140}\bpet\b|\bpet\b.{0,140}\b(?:is|dropped|obtained|received)\b", quote, re.I):
            continue
        tags = ["pet"]
        exact_page_item_ids = [i for i in article.get("exactInfoboxItemIds", [])]
        collection_log_page_facet = bool(exact_record.get("Category:Collection log items", False))
        collection_log_exact_item = collection_log_page_facet and len(exact_page_item_ids) == 1 and exact_page_item_ids[0] == i
        if collection_log_exact_item:
            tags.append("collection-log")
        item_proposal = proposal(
            i, "collectible-pet", title, article, quote, "CLUE", "collection-pet",
            "clues-cosmetics", ["pet_companion"], tags,
            "The exact item page directly identifies this retained item as a pet companion. Its reward source and Collection Log status are not used to establish the pet role.",
        )
        item_proposal["collectionLogPageFacet"] = collection_log_page_facet
        item_proposal["collectionLogFact"] = collection_log_exact_item
        item_proposal["collectionLogAttribution"] = (
            "supported_exact_single_item_page" if collection_log_exact_item else
            "unresolved_multi_variant_page_facet" if collection_log_page_facet else
            "not_listed_on_exact_item_page"
        )
        if collection_log_exact_item:
            category_line = next((line.strip() for line in text.splitlines() if line.strip() == "[[Category:Collection log items]]"), None)
            if category_line:
                item_proposal["evidence"].append({
                    "kind": "exact_wiki", "sourceTitle": title, "source": article["sourceUrl"],
                    "sourceRevision": article["revid"], "sourceHash": "sha256:" + article["sha256"],
                    "itemId": i, "quote": category_line,
                })
        proposals.append(item_proposal)

    for i in sorted(TROPHY_IDS):
        before = len(proposals)
        add_exact(i, "display-trophy", [r"mounted|mountable|display", r"player-owned house|achievement gallery|skill hall|boss lair display"],
                  "CLUE", "collection-trophy", ["display_trophy"], [],
                  "The exact item article documents a player-owned display or trophy use; any source/drop or Collection Log fact is independent.")
        if len(proposals) > before:
            item = proposals[-1]
            record = next((w for w in cleanup_rows[i]["sourceEvidence"].get("wikiRecords", [])
                           if str(i) in [str(x) for x in w.get("item_id", [])]), {})
            if record.get("Category:Collection log items", False):
                item["proposedTags"].append("collection-log")

    # Capture competing, source-explicit uses on the same trophy item.
    for item in proposals:
        if item["proposalGroup"] != "display-trophy":
            continue
        i = item["itemId"]
        _, article, text = exact_article(i, index, by_id, current[i]["catalogName"])
        functional = []
        if re.search(r"sacrificed? to the \[\[Dark Altar\]\].{0,120}Prayer", text, re.I | re.S):
            functional.append("prayer_experience_source")
            item["proposedTags"].append("prayer-use")
        if re.search(r"used to (?:assemble|upgrade|create|make) \[\[", text, re.I):
            functional.append("equipment_upgrade_material")
            item["proposedTags"].append("equipment-upgrade")
        if item["itemId"] == 31111:
            item["proposedRoles"].append("equipment_charge_resource")
            item["proposedTags"].append("equipment-charge")
        if item["itemId"] == 30806:
            item["proposedRoles"].append("combat_ability_upgrade")
        if functional:
            item["proposedRoles"].extend(functional)
            item["rationale"] += " The page also documents an independent non-display function; roles/tags retain that overlap for root's primary-placement review."

    for i in sorted(UPGRADE_IDS):
        add_exact(i, "equipment-upgrade-component", [r"upgrade|convert|used to|items used", r"armour|weapon|necklace|bracelet|staff|sceptre|spell|gauntlet|treads|eye of"],
                  "UNIQUE", "equipment-upgrade", ["equipment_upgrade_material"], ["equipment-upgrade"],
                  "The exact item article documents its equipment or combat-ability upgrade mechanic.")

    for i in sorted(WEAPON_UPGRADE_IDS):
        add_exact(i, "weapon-upgrade-component", [r"upgrade|used to", r"staff|sceptre|ancient"],
                  "UNIQUE", "weapon-upgrade", ["equipment_upgrade_material"], ["equipment-upgrade"],
                  "The exact item article documents this as a component used to upgrade a weapon.")

    for i in sorted(PET_UNLOCK_IDS):
        add_exact(i, "pet-metamorphosis-unlock", [r"pet", r"metamorphosis|change between|unlock|recolour|recolor|variant"],
                  "CLUE", "collection-pet", ["pet_metamorphosis_unlock"], ["pet-growth"],
                  "The exact item page documents unlocking a pet's metamorphosis; this item is classified as the pet-state unlock component, not as the pet itself.")

    # Functional conflicts in the frozen CLUE/cosmetic certification output:
    # locate source-explicit nonzero Infobox Bonuses values, without changing
    # that original 1,761-row ledger.
    clue_decisions = read_jsonl(ROOT / "tmp/category-certification/reviews/collections/clue-unique.jsonl")
    clue_packets = {r["itemId"]: r for r in read_jsonl(ROOT / "tmp/category-certification/reviewer-packets/clue-unique.jsonl")}
    conflicts = []
    for decision in clue_decisions:
        i = decision["itemId"]
        packet_row = clue_packets[i]
        current_row = packet_row.get("current", {})
        if current_row.get("category") != "CLUE" or current_row.get("subcategory") != "cosmetic":
            continue
        if i not in by_id:
            continue
        title, article, text = exact_article(i, index, by_id, clue_packets[i].get("catalogName"))
        match = re.search(r"(?is)\{\{Infobox Bonuses(.*?)\n\}\}", text)
        if not match:
            continue
        block = match.group(1)
        values = re.findall(r"\|\s*(astab|aslash|acrush|amagic|arange|dstab|dslash|dcrush|dmagic|drange|str|rstr|mdmg|prayer)\s*=\s*([+-]?\d+(?:\.\d+)?)", block, re.I)
        nonzero = [(key.lower(), value) for key, value in values if float(value) != 0]
        if nonzero and any(float(value) > 0 for _, value in nonzero):
            conflicts.append({
                "itemId": i,
                "name": packet_row.get("catalogName"),
                "currentAssignment": current_row,
                "existingDecision": decision.get("decision"),
                "conflict": "Pinned exact article's Infobox Bonuses contains nonzero combat/prayer values; cosmetic assignment may need an explicit primary-placement policy and role overlap review.",
                "structuredFacts": {key: value for key, value in nonzero},
                "evidence": [{
                    "kind": "exact_wiki", "sourceTitle": title,
                    "source": article["sourceUrl"], "sourceRevision": article["revid"],
                    "sourceHash": "sha256:" + article["sha256"], "itemId": i,
                    "quote": quote_for(block, [r"\|\s*(?:astab|aslash|acrush|amagic|arange|dstab|dslash|dcrush|dmagic|drange|str|rstr|mdmg|prayer)\s*="]) or block[:400].strip(),
                }],
            })

    proposals.sort(key=lambda r: (r["proposalGroup"], r["itemId"]))
    pet_groups = {}
    for item in proposals:
        if item["proposalGroup"] != "collectible-pet":
            continue
        title = item["evidence"][0]["sourceTitle"]
        group = pet_groups.setdefault(title, {"sourceTitle": title, "supportedRole": "pet_companion", "exactIDs": [], "petRoleIDs": [], "collectionLogExactItemIDs": [], "collectionLogMultiVariantUnresolvedIDs": [], "collectionLogNotListedIDs": [], "bankabilityCaveat": "Pinned infobox variants do not state bankable status; tradeable=No and follower/drop behavior do not prove non-bankability.", "exactStates": []})
        group["exactIDs"].append(item["itemId"])
        group["petRoleIDs"].append(item["itemId"])
        if item["collectionLogAttribution"] == "supported_exact_single_item_page":
            group["collectionLogExactItemIDs"].append(item["itemId"])
        elif item["collectionLogAttribution"] == "unresolved_multi_variant_page_facet":
            group["collectionLogMultiVariantUnresolvedIDs"].append(item["itemId"])
        else:
            group["collectionLogNotListedIDs"].append(item["itemId"])
        state = dict(item["exactVariant"])
        state["itemId"] = item["itemId"]
        group["exactStates"].append(state)
    result = {
        "schemaVersion": 1,
        "purpose": "Curated research proposals for exact CLEANUP items with directly documented cosmetic, companion, display-trophy, pet-unlock, or equipment-upgrade mechanics. Root review is required before any application.",
        "inputs": {
            "articleIndex": "tmp/category-certification/wiki-articles/article-index.json",
            "articleIndexSha256": hashlib.sha256(INDEX.read_bytes()).hexdigest(),
            "coverageSha256": hashlib.sha256(COVERAGE.read_bytes()).hexdigest(),
            "cleanupPacket": "tmp/category-certification/reviewer-packets/cleanup-other.jsonl",
            "cleanupDecisions": "tmp/category-certification/reviews/cleanup-other/decisions.jsonl",
            "coverage": "tmp/category-certification/current-coverage.tsv",
        },
        "excludedRootCleanupOtherPolicyIds": excluded,
        "counts": {"proposals": len(proposals), "functionalGearConflicts": len(conflicts), "unresolvedCandidates": len(unresolved)},
        "proposals": proposals,
        "petBreakdown": sorted(pet_groups.values(), key=lambda g: g["sourceTitle"].casefold()),
        "strictRules": [
            "Pet role is supported only by a direct article statement identifying a pet/follower/companion, with that exact numeric ID present in the article's parsed item infobox variants; interface-only NPC follower entries are excluded.",
            "Morph, color, or stage facts are retained as exact variantName/variant/suffix/idField facts for every exact item ID; the page's broad pet statement is not transferred to sibling IDs unless its article text describes the corresponding states.",
            "A Category:Collection log items page facet is credited to an exact pet item only when its pinned article contains one exact item ID. On multi-ID variant pages, page-level log membership is left unresolved for each exact variant; category membership is not copied across morph IDs.",
            "Absent bankable infobox fields mean unknown bankability. tradeable=No and follower/drop behavior do not establish bankability.",
        ],
        "functionalGearConflicts": conflicts,
        "unresolvedCandidates": unresolved,
    }
    OUTPUT.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result["counts"], sort_keys=True))
    if unresolved:
        print("unresolved", json.dumps(unresolved, ensure_ascii=False))


if __name__ == "__main__":
    main()
