#!/usr/bin/env python3
"""Build a focused, source-bound proposal for 12 wearable CLUE/cosmetic rows."""
import hashlib
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
REVIEW = ROOT / "tmp/category-certification/reviews/collections/cosmetic-strict-review.json"
INDEX = ROOT / "tmp/category-certification/wiki-articles/article-index.json"
OUT = ROOT / "tmp/category-certification/reviews/collections/gear-primary-function-12-proposal.json"
IDS = [3759, 3761, 3763, 3765, 3777, 3779, 3781, 3783, 3785, 3787, 3789, 12271]
ITEM_FIELDS = ("name", "id", "options", "equipable", "tradeable")
BONUS_FIELDS = ("slot", "dslash", "dcrush", "drange", "amagic", "dmagic", "prayer")


def sha(path):
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def params_in_block(text, template):
    match = re.search(r"\{\{" + re.escape(template) + r"([^\n]*(?:\n(?!\}\})[^\n]*)*)\n\}\}", text, re.I)
    if not match:
        raise ValueError(f"missing {template} block")
    return {k.strip().lower(): v.strip() for k, v in re.findall(r"(?m)^\|\s*([A-Za-z]+)\s*=\s*([^\r\n]*)", match.group(1))}


def main():
    report = json.loads(REVIEW.read_text(encoding="utf-8"))
    index = json.loads(INDEX.read_text(encoding="utf-8"))
    source_rows = {int(r["itemId"]): r for r in report["perItemReviews"]}
    pages = {title: art for title, art in index.items()}
    results = []
    for item_id in IDS:
        current = source_rows[item_id]
        ev = current["sourceEvidence"]
        art = pages[ev["sourceTitle"]]
        text_path = ROOT / art["path"]
        text = text_path.read_text(encoding="utf-8")
        variant = art["variants"][str(item_id)]["params"]
        item = {k: variant[k] for k in ITEM_FIELDS if k in variant}
        item["id"] = str(item_id)
        bonuses = params_in_block(text, "Infobox Bonuses")
        bonus_facts = {k: bonuses[k] for k in BONUS_FIELDS if k in bonuses and bonuses[k]}
        if str(bonuses.get("slot", "")).lower() not in {"cape", "head"}:
            raise ValueError(f"unexpected exact slot for {item_id}: {bonuses.get('slot')}")
        if not item.get("id") == str(item_id) or not re.search(r"(?i)\bWear\b", item.get("options", "")):
            raise ValueError(f"exact item identity / active Wear proof failed for {item_id}")
        if variant.get("equipable") != "Yes":
            raise ValueError(f"item is not marked equipable: {item_id}")

        if item_id == 12271:
            functional_quote = (
                "Alongside the other god mitres, it yields the second highest possible "
                "[[prayer bonus]] for a head slot item whilst having a "
                "[[magic attack bonus|magic attack]] and [[defence bonus]] identical to "
                "[[mystic hat]]s."
            )
            other_quotes = [
                "To wear a [[mitre]], the player needs at least 40 [[Prayer]] and 40 [[Magic]].",
                "{{Costume storage|treasure chest|tier=easy<ref>Despite being a reward from medium treasure trails, the item is stored with the easy rewards of the treasure chest.</ref>|[[Bandos vestment set]]|set=true}}",
                "==Used in recommended equipment==",
                "{{EmoteClue}}",
                "[[Category:Collection log items]]",
            ]
            subcategory = "head"
            rationale = (
                "The exact wearable variant has explicit Prayer, Magic attack, and defence use, "
                "with a +5 prayer bonus and +4 magic attack/defence in its pinned bonus table. "
                "Medium clue reward and collection-log facts are secondary provenance; the page "
                "also marks an emote-clue use and costume-room storage."
            )
            roles = ["equipable", "combat_equipment", "clue_reward_provenance", "collection_log_member", "functional_clue_utility"]
            tags = []
        else:
            functional_quote = next(
                line.strip()
                for line in text.splitlines()
                if "These capes have the same bonuses as" in line
            )
            other_quotes = [line.strip() for line in text.splitlines() if "quest" in line.lower()]
            subcategory = "gear"
            rationale = (
                "The exact Wear-enabled cape page says these capes carry the same bonuses as a normal "
                "cape (for the blue variant, the coloured Black-cape variants); its unique bonus "
                "table binds this ID to cape slot and +1 slash defence, +1 crush defence, and +2 "
                "ranged defence. Quest references describe acquisition restrictions/context, not an "
                "ongoing quest-only function."
            )
            roles = ["equipable", "combat_equipment"]
            tags = []

        cite = {
            "kind": "exact_wiki",
            "sourceTitle": ev["sourceTitle"],
            "itemId": item_id,
            "sourceRevision": art["revid"],
            "source": art["sourceUrl"],
            "sourceHash": "sha256:" + art["sha256"],
            "claim": "The uniquely ID-bound, active wearable exact item has an equipment slot and positive combat/prayer function.",
            "structuredFacts": [{"template": "Infobox Item", "field": k, "value": v} for k, v in item.items()]
                + [{"template": "Infobox Bonuses", "field": k, "value": v} for k, v in bonus_facts.items()],
            "quote": functional_quote,
            "otherFullPageFacts": other_quotes,
        }
        results.append({
            "itemId": item_id,
            "decision": "revise",
            "currentCategory": current["currentCategory"],
            "currentSubcategory": current["currentSubcategory"],
            "currentIronmanTabKey": current["currentTab"],
            "currentRoles": current["currentRoles"],
            "currentTags": current["currentTags"],
            "proposedCategory": "GEAR",
            "proposedSubcategory": subcategory,
            "proposedIronmanTabKey": "combat-gear",
            "equipmentSlot": bonus_facts["slot"],
            "proposedRoles": roles,
            "proposedTags": tags,
            "semanticPredicate": "Exact pinned article has the exact numeric item ID and Wear/equipable state; the same unique article binds that variant to an equipment slot and explicitly documents positive exact-slot combat/prayer bonuses or their equivalent subject-specific function. Acquisition source, collection-log membership, and flavor text do not establish placement.",
            "rationale": rationale,
            "evidence": [cite],
            "reviewer": "codex-collections",
            "shard": "gear-primary-function-12",
        })

    packet = {
        "schema": 1,
        "status": "source-bound proposal; awaiting independent root review",
        "sourceInputs": {
            "cosmeticReview": {"path": str(REVIEW.relative_to(ROOT)), "sha256": sha(REVIEW)},
            "articleIndex": {"path": str(INDEX.relative_to(ROOT)), "sha256": sha(INDEX)},
        },
        "counts": {"total": len(results), "capeSlot": sum(r["equipmentSlot"] == "cape" for r in results), "headSlot": sum(r["equipmentSlot"] == "head" for r in results)},
        "decisions": results,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(packet, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(OUT), **packet["counts"]}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
