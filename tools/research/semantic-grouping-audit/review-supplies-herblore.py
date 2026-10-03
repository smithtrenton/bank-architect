#!/usr/bin/env python3
"""Build the research-only supplies/Herblore semantic review from shared audit inputs."""
import csv
import json
import os
import re
from collections import Counter, defaultdict
from urllib.parse import quote

BASE = "tmp/semantic-audit"
OUT = f"{BASE}/reviews/supplies-herblore"
RELEVANT_SKILLS = {"Cooking", "Herblore"}
SOURCE_CATEGORIES = {
    "Food", "Edible items", "Drinks", "Potions", "Herblore",
    "Herblore secondaries", "Herbs", "Unfinished potions",
}
os.makedirs(OUT, exist_ok=True)

# Candidate generation is mechanical and deliberately broad. It includes current catalog
# supply/herb categories, exact Wiki role categories, cross-tag findings, and recipe edges.
effective = list(csv.DictReader(
    open(f"{BASE}/effective.tsv", encoding="utf-8-sig", newline=""), delimiter="\t"))
catalog_candidates = [
    r for r in effective
    if (r["itemCategory"] == "POTION" and r["subcategory"] in {
        "potion", "potion-dose-1", "potion-dose-2", "potion-dose-3", "potion-dose-4",
        "food", "drink", "pvm-utility",
    })
    or r["itemCategory"] == "HERBLORE"
    or (r["itemCategory"] == "FARMING" and r["subcategory"] == "herb-seed")
    or (r["itemCategory"] == "SKILLING" and r["subcategory"] in {"raw-food", "cooking-material"})
]
catalog_ids = {int(r["itemId"]) for r in catalog_candidates}
with open(f"{OUT}/candidate-universe.csv", "w", encoding="utf-8-sig", newline="") as f:
    fields = ["itemId", "name", "itemCategory", "subcategory", "ironmanTabKey", "workflowKey",
              "tags", "variantFamilyKey", "variantFamilyCount", "variantFlags"]
    writer = csv.DictWriter(f, fieldnames=fields)
    writer.writeheader()
    for row in catalog_candidates:
        writer.writerow({k: row.get(k, "") for k in fields})

# Parse exact-ID joined source rows and identify cross-tag supply/Herblore candidates.
selected = []
for line in open(f"{BASE}/joined.jsonl", encoding="utf-8"):
    item = json.loads(line)
    categories = {
        key[len("Category:"):]
        for page in item.get("wiki_records", [])
        for key, value in page.items()
        if key.startswith("Category:") and value is True
    }
    relevant_edges = [
        edge for edge in item.get("recipe_relations", [])
        if RELEVANT_SKILLS.intersection(edge.get("skills", []))
    ]
    reasons = []
    if item["item_id"] in catalog_ids:
        reasons.append("CURRENT_CATALOG_DOMAIN")
    if SOURCE_CATEGORIES.intersection(categories):
        reasons.append("WIKI_PAGE_CATEGORY_CANDIDATE")
    if relevant_edges:
        reasons.append("COOKING_OR_HERBLORE_RECIPE_EDGE")
    if "SECONDARY_ROLE_OUTSIDE_HERBLORE" in item.get("detectors", []):
        reasons.append("CROSS_TAG_SECONDARY_DETECTOR")
    if "EDIBLE_ROLE_IN_UNRELATED_TAG" in item.get("detectors", []):
        reasons.append("CROSS_TAG_EDIBLE_DETECTOR")
    if "RECIPE_ROLE_IN_CLEANUP" in item.get("detectors", []) and relevant_edges:
        reasons.append("CLEANUP_RECIPE_DETECTOR_RELEVANT_SKILL")
    if reasons:
        selected.append((item, categories, relevant_edges, reasons))

# Read existing exact-ID functional metadata and its source registry.
metadata = {}
for line in open("src/main/resources/com/pkoka5/ironmanbankarchitect/catalog/item-sort-metadata.tsv", encoding="utf-8-sig"):
    if not line.strip() or line.startswith("#"):
        continue
    c = line.rstrip("\n").split("\t")
    if len(c) >= 11:
        metadata[int(c[0])] = dict(zip(
            ("family", "variant_kind", "variant_value", "food_role", "heal_model", "heal_min",
             "heal_max", "secondary_heal", "area_restriction", "source_key"), c[1:11]))
sources = {}
for line in open("src/main/resources/com/pkoka5/ironmanbankarchitect/catalog/item-sort-metadata-sources.tsv", encoding="utf-8-sig"):
    if not line.strip() or line.startswith("#"):
        continue
    c = line.rstrip("\n").split("\t")
    if len(c) >= 5:
        sources[c[0]] = {"url": c[1], "retrieved": c[2], "revision": c[3]}

# Exact potion dose families are sourced and cross-checked against DOSE metadata.
dose_groups = []
for line in open("src/main/resources/com/pkoka5/ironmanbankarchitect/catalog/potion-layout-families.tsv", encoding="utf-8-sig"):
    if not line.strip() or line.startswith("#"):
        continue
    key, values = line.rstrip("\n").split("\t")[:2]
    members = [int(value) for value in values.split(",")]
    valid = all(
        member in metadata
        and metadata[member]["family"] == key
        and metadata[member]["variant_kind"] == "DOSE"
        and int(metadata[member]["variant_value"]) == 4 - index
        for index, member in enumerate(members)
    )
    source = sources.get("osrs-wiki-potions-15243625", {})
    dose_groups.append({
        "group_key": key, "group_type": "potion_dose_family", "member_ids": members,
        "variant_order": "4,3,2,1", "confidence": "HIGH" if valid else "UNRESOLVED_METADATA_MISMATCH",
        "evidence_url": source.get("url"), "evidence_revision": source.get("revision"),
        "basis": "Exact-ID family resource validated against sourced DOSE metadata.",
    })

# Additional source-labeled dose families: exact item IDs share a Wiki article and its
# explicit version_anchor (for example, "3 dose"). These remain distinct families by article,
# preserving minigame/quest/workflow copies as their own IDs and reporting their categories.
known_dose_ids = {member for group in dose_groups for member in group["member_ids"]}
wiki_dose_rows = defaultdict(lambda: {"doses": defaultdict(list), "categories": set(), "urls": set()})
for item, categories, edges, reasons in selected:
    if item["catalog_category"] != "POTION" or item.get("wiki_join_status") not in {"EXACT_ID_SINGLE", "EXACT_ID_MULTIPLE"}:
        continue
    for page in item.get("wiki_records", []):
        anchor = re.fullmatch(r"\s*([1-4])\s*dose\s*", str(page.get("version_anchor", "")), re.I)
        if not anchor or not page.get("Category:Potions") or not page.get("page_name"):
            continue
        article = page["page_name"]
        bucket = wiki_dose_rows[article]
        state = {"item_id": item["item_id"], "name": item["name"],
                 "dose": int(anchor.group(1)), "page_name_sub": page.get("page_name_sub"),
                 "catalog_category": item["catalog_category"], "subcategory": item["subcategory"],
                 "quest": page.get("quest"),
                 "source_item_url": (item.get("wiki_urls") or [""])[0]}
        bucket["doses"][int(anchor.group(1))].append(state)
        bucket["categories"].update(key[len("Category:"):] for key, value in page.items()
                                    if key.startswith("Category:") and value is True)
        bucket["urls"].update(item.get("wiki_urls", []))
wiki_dose_groups = []
for article, bucket in sorted(wiki_dose_rows.items()):
    dose_map = bucket["doses"]
    member_ids = {row["item_id"] for dose_rows in dose_map.values() for row in dose_rows}
    if len(dose_map) < 2 or member_ids.issubset(known_dose_ids):
        continue
    wiki_dose_groups.append({
        "group_key": "wiki-dose:" + re.sub(r"[^a-z0-9]+", "-", article.lower()).strip("-"),
        "group_type": "exact_id_wiki_dose_state_family", "wiki_article": article,
        "dose_states": {str(dose): sorted(rows, key=lambda row: row["item_id"])
                        for dose, rows in sorted(dose_map.items(), reverse=True)},
        "member_ids": sorted(member_ids), "dose_order": sorted(dose_map, reverse=True),
        "special_categories": sorted(bucket["categories"] & {"Quest items", "Minigame items", "Unobtainable items"}),
        "confidence": "HIGH_SOURCE_DOSE_VARIANTS",
        "evidence_urls": sorted(bucket["urls"]),
        "evidence_revision": "unavailable_in_joined_api_snapshot",
        "basis": "Each exact-ID Wiki item row is explicitly anchored as an N-dose version on the same article; special item IDs/categories stay distinct.",
    })
wiki_dose_by_id = {member: group["group_key"] for group in wiki_dose_groups for member in group["member_ids"]}

food_members = defaultdict(list)
for item_id, facts in metadata.items():
    if facts["food_role"] != "NONE":
        food_members[facts["family"]].append({"item_id": item_id, **facts})
food_groups = []
for key, members in sorted(food_members.items()):
    if len(members) < 2:
        continue
    urls = sorted({sources[m["source_key"]]["url"] for m in members if m["source_key"] in sources})
    revisions = sorted({sources[m["source_key"]]["revision"] for m in members if m["source_key"] in sources})
    food_groups.append({
        "group_key": key, "group_type": "food_serving_or_restriction_family", "members": members,
        "confidence": "HIGH", "evidence_urls": urls, "evidence_revisions": revisions,
        "basis": "Exact-ID metadata preserves serving/healing/area-restriction dimensions from cited source.",
    })

fields = [
    "item_id", "name", "current_category", "current_subcategory", "preset_category", "preset_tag",
    "preset_tag_by_family", "candidate_families", "candidate_roles", "wiki_join_status", "wiki_pages",
    "wiki_categories", "wiki_version_states", "wiki_quest", "wiki_examine", "relevant_recipe_edges",
    "candidate_scope_reasons", "existing_metadata", "confidence", "source_urls", "source_revisions",
    "assessment", "unresolved",
]
review = []
for item, categories, edges, reasons in selected:
    pages, states, examines, quests = [], [], [], []
    for page in item.get("wiki_records", []):
        title = page.get("page_name_sub") or page.get("page_name")
        if title and title not in pages:
            pages.append(title)
        state = {key: page[key] for key in ("version_anchor", "default_version", "item_name") if key in page}
        if state and state not in states:
            states.append(state)
        if page.get("examine") and page["examine"] not in examines:
            examines.append(page["examine"])
        if page.get("quest") and page["quest"] != "No" and page["quest"] not in quests:
            quests.append(page["quest"])
    roles = []
    for category, role in [
        ("Herblore secondaries", "herblore_secondary"), ("Herbs", "herb"), ("Seeds", "seed"),
        ("Farming", "farming"), ("Potions", "potion_page"), ("Unfinished potions", "unfinished_potion_page"),
        ("Food", "food_page"), ("Edible items", "edible_page"), ("Drinks", "drink_page"),
        ("Cooking", "cooking_page"),
    ]:
        if category in categories:
            roles.append(role)
    if any("Herblore" in edge.get("skills", []) for edge in edges):
        roles.append("herblore_recipe_input_candidate")
    if any("Cooking" in edge.get("skills", []) for edge in edges):
        roles.append("cooking_recipe_input_candidate")

    facts = metadata.get(item["item_id"])
    urls = list(item.get("wiki_urls", []))
    revisions = ["unavailable_in_joined_api_snapshot"] if urls else []
    if facts:
        source = sources.get(facts["source_key"], {})
        if source.get("url") and source["url"] not in urls:
            urls.append(source["url"])
        if source.get("revision"):
            revisions.append(source["revision"])
    for edge in edges:
        title = edge.get("page_sub") or edge.get("page")
        if title:
            url = "https://oldschool.runescape.wiki/w/" + quote(title.replace(" ", "_"), safe="()_%#")
            if url not in urls:
                urls.append(url)

    exact = item.get("wiki_join_status") in {"EXACT_ID_SINGLE", "EXACT_ID_MULTIPLE"}
    direct_role = bool(SOURCE_CATEGORIES.intersection(categories))
    if exact and direct_role:
        confidence = "HIGH_ROLE_MEDIUM_LINKAGE"
        assessment = "Exact-ID Wiki row supports page categories and item-page state; family needs an exact-ID relation, recipe title edges remain candidate-only."
    elif exact and edges:
        confidence = "MEDIUM_RECIPE_CANDIDATE"
        assessment = "Exact-ID Wiki row plus Cooking/Herblore recipe title relation supports candidate input role; edge does not prove output item-ID variant."
    elif exact:
        confidence = "LOW_REVIEW"
        assessment = "Exact-ID item page exists, but available facts do not directly establish supplies/Herblore function."
    else:
        confidence = "UNRESOLVED_NO_EXACT_ID_FACT"
        assessment = "Catalog/category/title trigger only; do not infer function or family from missing Wiki data."
    unresolved = []
    if not exact:
        unresolved.append("No exact-ID Wiki infobox row in joined snapshot; retrieve exact item page or corroborating source.")
    if edges:
        unresolved.append("Recipe edges are Wiki-title links and do not prove a particular output dose or serving ID.")
    if "Seeds" in categories and not any("Farming" in edge.get("skills", []) for edge in edges):
        unresolved.append("Seed category does not provide exact seed-to-harvest output relation in this snapshot.")
    if facts and facts["food_role"] != "NONE":
        unresolved.append("Food metadata is from its cited older snapshot; joined infobox lacks healing or attack-delay fields.")
    families = []
    if facts:
        families.append(facts["family"])
    elif item.get("family_hint"):
        families.append(item["family_hint"] + " [catalog hint; unverified]")
    dose = next((group for group in dose_groups if item["item_id"] in group["member_ids"]), None)
    if dose and dose["group_key"] not in families:
        families.append(dose["group_key"])
    if item["item_id"] in wiki_dose_by_id:
        families.append(wiki_dose_by_id[item["item_id"]])
    review.append({
        "item_id": item["item_id"], "name": item["name"], "current_category": item["catalog_category"],
        "current_subcategory": item["subcategory"], "preset_category": item.get("preset_category", ""),
        "preset_tag": item.get("preset_tag", ""), "preset_tag_by_family": item.get("preset_tag_by_family", ""),
        "candidate_families": " | ".join(families),
        "candidate_roles": " | ".join(sorted(set(roles + [r for r in item.get("roles", []) if r.startswith("wiki_category:")]))),
        "wiki_join_status": item.get("wiki_join_status", ""), "wiki_pages": " | ".join(pages),
        "wiki_categories": " | ".join(sorted(categories)),
        "wiki_version_states": json.dumps(states, ensure_ascii=False, separators=(",", ":")),
        "wiki_quest": " | ".join(quests), "wiki_examine": " | ".join(examines),
        "relevant_recipe_edges": json.dumps([
            {key: edge.get(key) for key in ("page", "page_sub", "skills", "role", "join_scope")}
            for edge in edges
        ], ensure_ascii=False, separators=(",", ":")),
        "candidate_scope_reasons": " | ".join(reasons),
        "existing_metadata": json.dumps(facts, ensure_ascii=False, separators=(",", ":")) if facts else "",
        "confidence": confidence, "source_urls": " | ".join(urls),
        "source_revisions": " | ".join(sorted(set(revisions))), "assessment": assessment,
        "unresolved": " | ".join(unresolved),
    })
with open(f"{OUT}/item-review.csv", "w", encoding="utf-8-sig", newline="") as f:
    writer = csv.DictWriter(f, fieldnames=fields)
    writer.writeheader()
    writer.writerows(review)
with open(f"{OUT}/unresolved-items.csv", "w", encoding="utf-8-sig", newline="") as f:
    writer = csv.DictWriter(f, fieldnames=fields)
    writer.writeheader()
    writer.writerows(row for row in review if row["confidence"] == "UNRESOLVED_NO_EXACT_ID_FACT")

# Recipe edges are retained as workflow candidates only; they are not variant-specific proof.
workflows = defaultdict(lambda: {"inputs": {}, "skills": set(), "urls": set()})
for item, categories, edges, reasons in selected:
    for edge in edges:
        title = edge.get("page_sub") or edge.get("page")
        if not title:
            continue
        group = workflows[title]
        group["inputs"][item["item_id"]] = {
            "item_id": item["item_id"], "name": item["name"],
            "source_item_url": (item.get("wiki_urls") or [""])[0],
            "edge_role": edge.get("role"), "join_scope": edge.get("join_scope"),
        }
        group["skills"].update(edge.get("skills", []))
        group["urls"].add("https://oldschool.runescape.wiki/w/" + quote(title.replace(" ", "_"), safe="()_%#"))
recipe_groups = []
for title, group in sorted(workflows.items()):
    if len(group["inputs"]) < 2:
        continue
    recipe_groups.append({
        "group_key": "recipe:" + re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-"),
        "group_type": "wiki_recipe_input_candidates", "recipe_title": title,
        "skills": sorted(group["skills"]),
        "candidate_input_ids": sorted(group["inputs"].values(), key=lambda row: row["item_id"]),
        "confidence": "MEDIUM_TITLE_RELATION_VARIANT_UNRESOLVED",
        "evidence_urls": sorted(group["urls"]),
        "basis": "At least two exact-ID rows carry this recipe title edge; output variant ID remains unproven.",
    })
with open(f"{OUT}/group-candidates.json", "w", encoding="utf-8") as f:
    json.dump({
        "method": "Exact-ID DOSE and sourced food metadata groups are high-confidence candidates; Wiki recipe edges are title-level candidates; catalog family hints remain unverified.",
        "potion_dose_families": dose_groups, "additional_wiki_dose_families": wiki_dose_groups,
        "food_families": food_groups, "recipe_workflow_candidates": recipe_groups,
    }, f, ensure_ascii=False, indent=2)

confidence_counts = Counter(row["confidence"] for row in review)
category_counts = Counter(f"{row['current_category']}/{row['current_subcategory']}" for row in review)
wiki_category_counts = Counter()
join_counts = Counter(row["wiki_join_status"] for row in review)
for row in review:
    for category in row["wiki_categories"].split(" | "):
        if category:
            wiki_category_counts[category] += 1
summary = {
    "domain": "supplies and Herblore semantic review",
    "source": "Root joined OSRS Wiki exact-ID dataset generated 2026-10-02; local curated metadata/source files are listed separately.",
    "candidate_ids": len(review),
    "exact_id_wiki_rows": sum(row["wiki_join_status"] in {"EXACT_ID_SINGLE", "EXACT_ID_MULTIPLE"} for row in review),
    "no_exact_id_wiki_rows": sum(row["wiki_join_status"] == "NO_EXACT_ID_FACT" for row in review),
    "confidence_counts": dict(confidence_counts),
    "join_status_counts": dict(join_counts),
    "wiki_category_page_role_counts": dict(wiki_category_counts.most_common()),
    "category_subcategory_counts": dict(category_counts.most_common()),
    "existing_metadata_dose_family_count": len(dose_groups),
    "existing_metadata_dose_family_member_count": sum(len(group["member_ids"]) for group in dose_groups),
    "additional_exact_wiki_dose_family_count": len(wiki_dose_groups),
    "additional_exact_wiki_dose_member_count": sum(len(group["member_ids"]) for group in wiki_dose_groups),
    "total_source_backed_dose_candidate_families": len(dose_groups) + len(wiki_dose_groups),
    "total_source_backed_dose_candidate_ids": sum(len(group["member_ids"]) for group in dose_groups) + sum(len(group["member_ids"]) for group in wiki_dose_groups),
    "food_multi_member_family_count": len(food_groups),
    "food_multi_member_id_count": sum(len(group["members"]) for group in food_groups),
    "recipe_workflow_candidates_with_2plus_inputs": len(recipe_groups),
    "findings": [
        "Exact-ID page categories support page roles such as potions, unfinished potions, secondaries, herbs, food and drinks; they do not alone establish family or variant links.",
        f"The existing 22 four-dose families (88 IDs) agree with sourced DOSE metadata; another {len(wiki_dose_groups)} exact-ID Wiki page families expose dose anchors for {sum(len(group['member_ids']) for group in wiki_dose_groups)} additional IDs. Preserve dose state and any quest/minigame categories.",
        "Six food families have multiple exact-ID metadata members with source-backed serving or restriction dimensions; preserve each ID and its attributes.",
        f"{len(recipe_groups)} recipe groups are title-level material-to-product candidates only; exact output dose or serving IDs remain unresolved.",
        "Every catalog item without an exact-ID Wiki row is individually listed in unresolved-items.csv; no function is inferred from absent facts.",
    ],
    "limits": [
        "Joined item/category rows have exact IDs, but categories apply at page/variant scope. False category flags are not negative evidence.",
        "Joined recipe relations are page-title/name edges and do not prove exact output variant IDs.",
        "Joined infobox lacks healing, attack-delay and serving-depletion fields; existing food metadata retains older exact source revisions.",
        "The joined snapshot omits per-page revision IDs; report retrieval date and mark unavailable rather than inventing oldids.",
    ],
    "candidate_scope": "Current catalog domain plus exact Wiki supply/Herblore categories, cross-tag secondary/edible detections, and cleanup records with Cooking/Herblore recipe edges.",
}
with open(f"{OUT}/summary.json", "w", encoding="utf-8") as f:
    json.dump(summary, f, ensure_ascii=False, indent=2)
print(json.dumps({
    "review_ids": len(review), "exact": summary["exact_id_wiki_rows"],
    "unresolved": summary["no_exact_id_wiki_rows"], "confidence": dict(confidence_counts),
    "existing_dose_families": len(dose_groups), "additional_wiki_dose_families": len(wiki_dose_groups),
    "food_families": len(food_groups),
    "recipe_groups": len(recipe_groups),
}, ensure_ascii=False))
