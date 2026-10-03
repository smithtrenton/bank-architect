from __future__ import annotations
import collections
import csv
import json
import re
from pathlib import Path

OUT = Path.cwd() / "tmp/semantic-audit/reviews/loot-quests-clues"
OUT.mkdir(parents=True,exist_ok=True)
REPO = Path(__file__).resolve().parents[3]
JOINED = REPO / "tmp/semantic-audit/joined.jsonl"
WIKI_EXTRA = REPO / "tmp/semantic-audit/cache/collection-log-page.json"

PRIORITY_CASES = [
    ("579", "CLUE_REQUIREMENT_AND_EQUIPMENT", "Keep Combat Gear as primary placement; add optional clue-requirement metadata/family.", "Exact Wiki page is in Items needed for an emote clue and Magic armour/Equipable categories. Clue requirement is a secondary task role; the baseline CLEANUP category should not suppress equipment/clue-kit routing.", "https://oldschool.runescape.wiki/w/Blue_wizard_hat"),
    ("2577", "CLUE_REWARD_AND_LOGGED_GEAR", "Keep Combat Gear as primary placement; record Treasure Trails reward provenance and Medium Treasure Trails log activity.", "Ranger boots are Treasure Trails rewards, equipable ranged armour, and a formal Collection Log entry under Medium Treasure Trails. Reward source does not erase wearable gear role.", "https://oldschool.runescape.wiki/w/Ranger_boots"),
    ("2631", "CLUE_REWARD_COSMETIC_STORAGE", "Review current cleanup fallback; propose a cosmetic/outfit family with clue-reward and collection-log metadata.", "Highwayman mask is a Treasure Trails reward, costume-room storable, and listed under Easy Treasure Trails in the formal log. These facts support a retained cosmetics/collection role but do not prove every player wants it banked.", "https://oldschool.runescape.wiki/w/Highwayman_mask"),
    ("23083", "SLAYER_TASK_REWARD_KEY", "Route to Slayer/Boss loot or reward keys; retain key/chest function metadata.", "Brimstone key opens Konar's chest and drops from Slayer-task monsters/superior Slayer monsters. Current cleanup fallback misses a repeatable reward-opening function.", "https://oldschool.runescape.wiki/w/Brimstone_key?oldid=15198903"),
    ("11932", "BOSS_UNIQUE_COMPONENT_AND_LOG", "Route as Wilderness boss/unique loot or a ward component family; preserve recipe-material role and Crazy archaeologist provenance.", "Malediction shard 2 is dropped by the Crazy archaeologist and combines with shards 1 and 3 to forge the malediction ward; the page is a formal Collection Log item.", "https://oldschool.runescape.wiki/w/Malediction_shard_2?oldid=15185377"),
    ("28798", "BOSS_UNIQUE_COMPONENT_AND_LOG", "Route as Scurrius unique loot with a weapon-component/material role; keep the Scurrius log provenance.", "Scurrius' spine is a Scurrius drop used with weapons to create rat bone weapons and has formal Collection Log membership.", "https://oldschool.runescape.wiki/w/Scurrius%27_spine?oldid=15192238"),
    ("7977", "SLAYER_TROPHY_AND_LOG", "Keep a Slayer trophy/Collection Log role; record Taxidermy and Construction display use.", "Basilisk head is a Slayer-level-gated drop, can be stuffed by the Taxidermist, and mounted for Slayer/Construction XP; its formal Collection Log section is Slayer.", "https://oldschool.runescape.wiki/w/Basilisk_head?oldid=15183801"),
    ("6807", "CHAMPION_CHALLENGE_AND_LOG", "Keep a Champion's Challenge/Collection Log role; distinguish the one-use challenge scroll from a generic trophy.", "Zombie champion scroll has Champions' Challenge and Collection Log categories; the structured log puts it in Champion's Challenge. The page says it is removed from inventory after completing the challenge.", "https://oldschool.runescape.wiki/w/Zombie_champion_scroll?oldid=15313720"),
    ("4601", "QUEST_ASSOCIATION_AND_TELEPORT_RECHARGE", "Keep quest association; add Camulet recharge/teleport-charge role.", "Ugthanki dung is used by quest workflows and recharges the Camulet (one bucket provides four charges), so quest provenance and utility belong in separate fields.", "https://oldschool.runescape.wiki/w/Ugthanki_dung?oldid=15359738"),
    ("9082", "QUEST_ASSOCIATION_AND_FARMING_MATERIAL", "Keep quest association; add Farming payment and quest-reagent roles.", "Ground tooth protects a Spirit Tree and makes the Waking sleep vial during Lunar Diplomacy. The quest item therefore has post-quest Farming utility.", "https://oldschool.runescape.wiki/w/Ground_tooth?oldid=15184930"),
    ("589", "QUEST_REWARD_AND_COMBAT_GEAR", "Keep Combat Gear as primary placement and retain Tree Gnome Village provenance.", "Gnome amulet is awarded after Tree Gnome Village and has +13 melee defence in each melee defence style. Quest origin does not replace its combat role.", "https://oldschool.runescape.wiki/w/Gnome_amulet?oldid=15183040"),
    ("10491", "QUEST_TOOL_WITH_SPECIAL_FUNCTION", "Keep specialized Skilling Tool role plus Animal Magnetism provenance; do not count it as the account's ordinary best axe.", "Blessed axe can damage vampyres and cuts undead trees, but cannot chop ordinary trees. The Wiki states this specialized function directly.", "https://oldschool.runescape.wiki/w/Blessed_axe?oldid=15320072"),
    ("30970", "QUEST_ORIGIN_PET", "Keep pet/collectible role with quest-origin metadata; avoid ordinary Egg classification from display name alone.", "The exact ID joins to Humphrey Dumphrey, a post-quest pet page with Pets and Quest items categories. Pet status is separate from Collection Log membership and personal storage preference.", "https://oldschool.runescape.wiki/w/Humphrey_Dumphrey"),
]

REVIEW_CATEGORIES = {"slayer-boss-loot", "boss-slayer-loot", "loot-drops", "clues-cosmetics", "clues-collection-log", "loot-clues-storage", "cosmetics-outfits"}
REVIEW_TAGS = {"boss-loot", "collection-log", "collection-pet", "clues", "cosmetics", "quest-items", "cleanup"}


def norm(value: object) -> str:
    return re.sub(r"[_\s]+", " ", str(value)).strip().casefold()


def formal_log_sources() -> tuple[dict[str, set[str]], int, int, str]:
    source = json.loads(WIKI_EXTRA.read_text(encoding="utf-8-sig"))
    page = next(p for p in source["query"]["pages"] if p.get("title", "").casefold() == "collection log")
    revision = page["revisions"][0]
    body = revision["slots"]["main"]["content"]
    start = body.find("==Bosses==")
    end = body.find("{{Collection log}}", start)
    section = body[start:end] if start >= 0 and end > start else ""
    item_sources: dict[str, set[str]] = collections.defaultdict(set)
    heading = ""
    for line in section.splitlines():
        match = re.match(r"^(={2,4})\s*(.*?)\s*\1\s*$", line)
        if match:
            heading = match.group(2).strip()
            continue
        for item in re.findall(r"\{\{plink\|([^}|]+)", line, flags=re.I):
            item_sources[norm(item)].add(heading or "Collection Log structured activity section")
    occurrences = len(re.findall(r"\{\{plink\|", section, flags=re.I))
    url = f"https://oldschool.runescape.wiki/w/Collection_log?oldid={revision['revid']}"
    return item_sources, occurrences, revision["revid"], url


def main() -> None:
    joined = [json.loads(line) for line in JOINED.open(encoding="utf-8")]
    log_sources, plink_occurrences, log_revision, log_url = formal_log_sources()
    rows: list[dict[str, str]] = []
    role_counts: collections.Counter[str] = collections.Counter()
    tag_counts: collections.Counter[str] = collections.Counter()
    join_counts: collections.Counter[str] = collections.Counter()
    section_counts: collections.Counter[str] = collections.Counter()
    role_join_counts: collections.Counter[str] = collections.Counter()
    role_tag_counts: collections.Counter[str] = collections.Counter()
    for item in joined:
        records = item.get("wiki_records", [])
        categories: set[str] = set()
        quests: set[str] = set()
        page_names: set[str] = set()
        for record in records:
            if record.get("page_name"):
                page_names.add(str(record["page_name"]))
            quest = record.get("quest")
            if quest not in (None, "", "No", "no", "N/A"):
                quests.add(str(quest))
            for field, value in record.items():
                if field.startswith("Category:") and value is True:
                    categories.add(field[9:])
        activity_sections = sorted({activity for title in page_names for activity in log_sources.get(norm(title), set())})
        log_table = bool(activity_sections)
        log_category = "Collection log items" in categories
        clue_requirement = bool(categories & {"Items needed for an emote clue", "Items used in emote clues", "Treasure Trails emote items"})
        clue_reward = "Treasure Trails rewards" in categories
        quest_category = "Quest items" in categories
        quest_association = bool(quests)
        pet = "Pets" in categories
        slayer_equipment = "Slayer equipment" in categories
        tag = item.get("preset_tag") or ""
        preset_category = item.get("preset_category") or ""
        cleanup_route = tag == "cleanup" or item.get("catalog_category") == "CLEANUP"
        route_in_scope = tag in REVIEW_TAGS or preset_category in REVIEW_CATEGORIES or item.get("catalog_category") == "CLEANUP"
        review_roles: list[str] = []
        if quest_association:
            review_roles.append("quest_association")
        if quest_category:
            review_roles.append("wiki_quest_items_category")
        if clue_requirement:
            review_roles.append("clue_step_requirement")
        if "Clue scrolls" in categories:
            review_roles.append("clue_scroll_or_container")
        if clue_reward:
            review_roles.append("treasure_trails_reward")
        if log_category or log_table:
            review_roles.append("formal_collection_log_membership")
        if pet:
            review_roles.append("wiki_pet")
        if slayer_equipment:
            review_roles.append("slayer_equipment")
        if "Items storable in the costume room" in categories:
            review_roles.append("costume_room_storable")
        if "Champions' Challenge" in categories:
            review_roles.append("champions_challenge")
        if "Keys" in categories:
            review_roles.append("key_function")
        if route_in_scope:
            review_roles.append("current_route_or_cleanup_review_scope")
        # This identifies evidence needing review; it does not prove post-quest reuse or a preferred destination.
        if cleanup_route and (quest_association or quest_category or clue_requirement or clue_reward or log_category or log_table or pet or slayer_equipment):
            review_roles.append("cleanup_route_or_baseline_with_role_provenance_review")
        if activity_sections:
            review_roles.append("activity_collection_log_provenance")
        if "Slayer" in activity_sections:
            review_roles.append("slayer_activity_provenance")
        if any("Treasure Trail" in name for name in activity_sections):
            review_roles.append("clue_activity_provenance")
        if not review_roles:
            continue
        functional_roles = [str(role) for role in item.get("roles", []) if not str(role).startswith("wiki_category:")]
        facts: list[str] = []
        if quests:
            facts.append("quest=" + " / ".join(sorted(quests)))
        facts.extend("Category:" + name for name in sorted(categories))
        if activity_sections:
            facts.append("Collection Log structured-table sections=" + ", ".join(activity_sections))
        if functional_roles:
            facts.append("joined functional roles=" + ", ".join(functional_roles))
        join_status = item.get("wiki_join_status", "")
        join_counts[join_status] += 1
        tag_counts[tag] += 1
        role_counts.update(review_roles)
        for role in review_roles:
            role_join_counts[role + "|" + join_status] += 1
            if role in {"clue_step_requirement", "treasure_trails_reward", "formal_collection_log_membership", "quest_association", "wiki_quest_items_category", "wiki_pet", "slayer_activity_provenance"}:
                role_tag_counts[role + "|" + tag] += 1
        for activity in activity_sections:
            section_counts[activity] += 1
        fact_present = bool(quests or categories or activity_sections)
        if join_status == "EXACT_ID_SINGLE" and fact_present:
            confidence = "EXACT_ID_SINGLE_PAGE_EVIDENCE"
        elif join_status == "EXACT_ID_MULTIPLE":
            confidence = "MULTI_ID_PAGE_SCOPE_REVIEW"
        elif not fact_present:
            confidence = "ROUTE_ONLY_NO_EXACT_ID_FACT"
        else:
            confidence = "PAGE_OR_ID_JOIN_REVIEW"
        urls = list(item.get("wiki_urls", []))
        if log_table:
            urls.append(log_url)
        rows.append({
            "item_id": str(item.get("item_id")), "name": str(item.get("name", "")),
            "preset_category": str(preset_category), "preset_tag": str(tag),
            "catalog_category": str(item.get("catalog_category", "")), "subcategory": str(item.get("subcategory", "")),
            "wiki_join_status": str(join_status), "review_roles": " | ".join(review_roles),
            "functional_roles": " | ".join(functional_roles), "quest_field_values": " | ".join(sorted(quests)),
            "clue_requirement_category": str(clue_requirement).lower(), "clue_reward_category": str(clue_reward).lower(),
            "formal_collection_log_category": str(log_category).lower(), "formal_collection_log_structured_table_match": str(log_table).lower(),
            "collection_log_activity_sections": " | ".join(activity_sections), "wiki_pet_category": str(pet).lower(),
            "slayer_equipment_category": str(slayer_equipment).lower(),
            "cleanup_route_or_baseline_with_role_provenance_review": str("cleanup_route_or_baseline_with_role_provenance_review" in review_roles).lower(),
            "personal_collectible_preference": "USER_SPECIFIC_UNKNOWN", "wiki_fact_pages": " | ".join(sorted(page_names)),
            "evidence": " ; ".join(facts),
            "evidence_scope": "Positive Wiki category/quest facts are page-scoped; item-ID match status is preserved. Structured Collection Log membership comes only from plink item links in activity tables. Personal collecting remains user-specific. No missing flag is treated as a negative fact.",
            "confidence": confidence, "source_urls": " | ".join(urls),
        })
    rows.sort(key=lambda row: int(row["item_id"]))
    fields = list(rows[0])
    with (OUT / "review-candidates.csv").open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)

    by_id = {row["item_id"]: row for row in rows}
    priority: list[dict[str, str]] = []
    for item_id, kind, proposal, reason, source in PRIORITY_CASES:
        row = by_id[item_id]
        clog_source = " | ".join(url for url in row["source_urls"].split(" | ") if "Collection_log?oldid=" in url)
        sources = source + (" | " + clog_source if clog_source and "Collection_log?oldid=" not in source else "")
        priority.append({
            "item_id": item_id, "item": row["name"], "current_catalog_category": row["catalog_category"],
            "current_preset_category": row["preset_category"], "current_preset_tag": row["preset_tag"],
            "wiki_join_status": row["wiki_join_status"], "proposal": proposal, "source_backed_reason": reason,
            "joined_evidence": row["evidence"], "collection_log_activity_sections": row["collection_log_activity_sections"],
            "personal_collectible_preference": "Unknown/user-specific; no inference from pet, trophy or log membership.",
            "confidence": "DIRECT_WIKI_CATEGORY_OR_ITEM_TEXT; candidate proposal only", "sources": sources,
        })
    with (OUT / "priority-cases.csv").open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(priority[0]))
        writer.writeheader()
        writer.writerows(priority)

    summary = {
        "source_dataset": "tmp/semantic-audit/joined.jsonl", "generated_for_snapshot": "2026-10-02",
        "effective_rows": len(joined), "review_candidate_id_count": len(rows),
        "candidate_counts_by_role": dict(role_counts), "candidate_counts_by_current_tag": dict(tag_counts),
        "candidate_counts_by_wiki_join_status": dict(join_counts),
        "candidate_counts_by_role_and_wiki_join_status": dict(role_join_counts),
        "core_role_counts_by_preset_tag": dict(role_tag_counts),
        "cleanup_route_or_baseline_with_role_provenance_review_count": role_counts["cleanup_route_or_baseline_with_role_provenance_review"],
        "cleanup_route_or_baseline_with_role_provenance_review_definition": "Rows with catalog_category=CLEANUP or effective preset_tag=cleanup plus at least one positive Wiki quest/clue/log/pet/activity/recipe/tool/storage/key signal. The count requires human review; it does not prove post-quest reuse, bank desirability, or a destination.",
        "current_cleanup_tag_rows": sum(row["preset_tag"] == "cleanup" for row in rows),
        "core_positive_fact_counts": {
            "quest_association": role_counts["quest_association"], "quest_items_category": role_counts["wiki_quest_items_category"],
            "clue_requirement": role_counts["clue_step_requirement"], "treasure_trails_reward": role_counts["treasure_trails_reward"],
            "formal_collection_log_category_or_table": role_counts["formal_collection_log_membership"],
            "wiki_pet": role_counts["wiki_pet"], "slayer_activity_provenance": role_counts["slayer_activity_provenance"],
            "treasure_trails_activity_provenance": role_counts["clue_activity_provenance"],
        },
        "collection_log_page_revision": log_revision, "collection_log_structured_plink_occurrences": plink_occurrences,
        "collection_log_unique_item_titles": len(log_sources),
        "collection_log_catalog_title_matches": role_counts["activity_collection_log_provenance"],
        "collection_log_formal_activity_section_counts": dict(section_counts.most_common()),
        "priority_source_backed_case_count": len(priority), "priority_source_backed_case_ids": [case["item_id"] for case in priority],
        "personal_collectible_preference_policy": "Unknown per player; formal log membership and pet/trophy provenance do not imply personal collecting or a storage destination.",
        "quest_retained_function_policy": "Quest association or Quest items category alone does not establish post-quest reuse. Retained-function proposals require separate direct evidence, such as a repeatable recharge, Farming payment, equipment bonus, or specific tool use.",
        "slayer_scope_policy": "Collection Log activity section Slayer is provenance only. Other Slayer loot candidates need direct item-page drop/use evidence or an explicit Slayer equipment category; do not infer utility/destination from source activity alone.",
        "limitations": [
            "Wiki categories, quest properties, and Collection Log title links are page-level evidence, not proof that every ID version has the same function.",
            "Formal Collection Log membership is separate from player personal collection preference and destination.",
            "Collection Log activity section records provenance; its presence does not dictate storage placement.",
            "No absence of a category, link, or item-page fact is treated as proof of no role.",
            "Current preset routes are review candidates, not semantic proof.",
            "Rows without exact-ID facts remain when current route or cleanup scope makes them relevant.",
            "The mechanical review is not a full manual assessment of every candidate row.",
        ],
    }
    with (OUT / "coverage.json").open("w", encoding="utf-8", newline="\n") as stream:
        json.dump(summary, stream, ensure_ascii=False, indent=2)
        stream.write("\n")
    print(json.dumps({"rows": len(rows), "joins": dict(join_counts), "roles": dict(role_counts), "priority": len(priority)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
