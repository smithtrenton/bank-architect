#!/usr/bin/env python3
"""Narrowly repair unsupported cosmetic certifications in the frozen CLUE shard."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
DECISIONS = ROOT / "tmp/category-certification/reviews/collections/clue-unique.jsonl"
CORRECTIONS = ROOT / "tmp/category-certification/reviews/collections/clue-unique-corrected-delta.jsonl"
CORRECTED = ROOT / "tmp/category-certification/reviews/collections/clue-unique-corrected.jsonl"
INDEX_PATH = ROOT / "tmp/category-certification/wiki-articles/article-index.json"
PACKET = ROOT / "tmp/category-certification/reviewer-packets/clue-unique.jsonl"
index = json.loads(INDEX_PATH.read_text(encoding="utf-8"))
packet = {r["itemId"]: r for r in (json.loads(x) for x in PACKET.read_text(encoding="utf-8").splitlines())}
by_id = {i: (title, article) for title, article in index.items() for i in article.get("exactInfoboxItemIds", [])}
decisions = [json.loads(x) for x in DECISIONS.read_text(encoding="utf-8").splitlines()]


def evidence(item_id: int, quote: str) -> dict:
    title, article = by_id[item_id]
    if quote not in (ROOT / article["path"].replace("\\", "/")).read_text(encoding="utf-8"):
        raise ValueError(f"evidence quote does not match pinned source for {item_id}")
    return {
        "itemId": item_id,
        "kind": "exact_wiki",
        "sourceTitle": title,
        "source": article["sourceUrl"],
        "sourceRevision": article["revid"],
        "sourceHash": "sha256:" + article["sha256"],
        "quote": quote,
    }


def article_line(item_id: int, include: tuple[str, ...]) -> str:
    title, article = by_id[item_id]
    text = (ROOT / article["path"].replace("\\", "/")).read_text(encoding="utf-8")
    for line in text.splitlines():
        if all(term.casefold() in line.casefold() for term in include):
            return line.strip()
    raise ValueError(f"could not find {include!r} on exact page {title}")


CHANGES = {
    # These exact pages document equipment or minigame functions, but the old
    # certification cited only a flavor/examine line as evidence of cosmetics.
    6786: {
        "quote": article_line(6786, ("required in the", "quest")),
        "roles": ["equipable", "quest_required_item", "desert_heat_protection"],
        "rationale": "The pinned exact page documents quest-required wear to enter Water Ravine Dungeon and a desert-heat delay. The cited examine text does not establish cosmetic retention, so primary placement remains unresolved pending policy for this functional quest garment.",
    },
    6070: {
        "quote": article_line(6070, ("They give no bonuses.",)),
        "roles": ["equipable", "quest_required_item"],
        "rationale": "The exact page establishes that this garment belongs to the Mourner set and gives no bonuses, but does not establish cosmetic retention as its primary role. It remains unresolved pending the product policy for zero-stat quest garments.",
    },
    12273: {
        "quote": article_line(12273, ("Bandosian item", "God Wars Dungeon")),
        "roles": ["clue_reward_provenance", "collection_log_member", "combat_equipment", "equipable", "functional_clue_utility"],
        "rationale": "The exact article documents a God Wars Dungeon Bandosian-item function and a master clue-step requirement. The old generic rationale claimed appearance retention without support; this functional overlap needs a primary-category decision, so the row is unresolved.",
    },
    11891: {
        "quote": article_line(11891, ("standard of Team", "Castle Wars")),
        "roles": ["collection_log_member", "equipable", "minigame_object"],
        "rationale": "The exact article identifies this as a Castle Wars team standard used in the minigame objective. The prior cited examine line does not establish cosmetic retention, and this minigame function needs a primary-category decision.",
    },
    11892: {
        "quote": article_line(11892, ("standard of Team", "Castle Wars")),
        "roles": ["collection_log_member", "equipable", "minigame_object"],
        "rationale": "The exact article identifies this as a Castle Wars team standard used in the minigame objective. The prior cited examine line does not establish cosmetic retention, and this minigame function needs a primary-category decision.",
    },
}

corrections = []
for row in decisions:
    i = row["itemId"]
    if i in CHANGES:
        facts = CHANGES[i]
        row["decision"] = "unresolved"
        row["proposedRoles"] = facts["roles"]
        row["proposedTags"] = []
        row["evidence"] = [evidence(i, facts["quote"])]
        row["rationale"] = facts["rationale"]
        row["semanticPredicate"] = "Certify CLUE/cosmetic only when the exact item's article supports appearance retention as a primary retained role; record any independent functional roles and leave contested placement unresolved."
        corrections.append(row)
        continue
    if row.get("decision") != "certify" or row.get("proposedCategory") != "CLUE" or row.get("proposedSubcategory") != "cosmetic":
        continue
    # Repair citations that selected an examine/reward line even though the
    # exact item article has a direct cosmetic statement. Pet growth stages are
    # retained as their distinct exact item IDs in the infobox.
    if i in {2633, 2635, 2637}:
        quote = article_line(i, ("worn purely for cosmetic purposes",))
        row["evidence"] = [evidence(i, quote)]
        corrections.append(row)
    elif i in {2639, 2641, 2643}:
        quote = article_line(i, ("piece of headwear", "wearing this cavalier"))
        row["evidence"] = [evidence(i, quote)]
        corrections.append(row)
    elif i in {34503, 34505, 34507, 34509, 34511, 34513, 34515, 34517, 34519,
               34521, 34523, 34525, 34527, 34529, 34531, 34533, 34535, 34537,
               34539, 34541, 34543, 34545, 34547, 34549, 34551, 34553, 34555,
               34557, 34559, 34561, 34563, 34566, 34567, 34569, 34571, 34573}:
        title, article = by_id[i]
        text = (ROOT / article["path"].replace("\\", "/")).read_text(encoding="utf-8")
        quote = next((line.strip() for line in text.splitlines() if "are a breed of" in line and "can follow the player" in line), None)
        if quote:
            row["evidence"] = [evidence(i, quote)]
            corrections.append(row)

CORRECTED.write_text("\n".join(json.dumps(row, ensure_ascii=False, sort_keys=True) for row in decisions) + "\n", encoding="utf-8")
CORRECTIONS.write_text("\n".join(json.dumps(row, ensure_ascii=False, sort_keys=True) for row in corrections) + "\n", encoding="utf-8")
print(json.dumps({"originalRowsReadOnly": len(decisions), "correctionRows": len(corrections), "unresolvedCorrections": len(CHANGES), "evidenceRepairs": len(corrections) - len(CHANGES), "correctedLedger": str(CORRECTED.relative_to(ROOT)), "delta": str(CORRECTIONS.relative_to(ROOT))}))
