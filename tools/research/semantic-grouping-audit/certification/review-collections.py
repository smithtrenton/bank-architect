#!/usr/bin/env python3
"""Build per-ID, source-backed reviews for the CLUE and UNIQUE shards."""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[4]
DEFAULT_PACKET = ROOT / "tmp/category-certification/reviewer-packets/clue-unique.jsonl"
DEFAULT_INDEX = ROOT / "tmp/category-certification/wiki-articles/article-index.json"
DEFAULT_POLICY = ROOT / "tools/research/semantic-grouping-audit/policies/collections-policy.json"
DEFAULT_OUTPUT = ROOT / "tmp/category-certification/reviews/collections/clue-unique.jsonl"

CLUE_TERMS = re.compile(r"\b(clue scroll|treasure trail|emote clue|cryptic clue|challenge scroll)\b", re.I)
CLUE_FUNCTION = re.compile(r"\b(requires?|required|must (?:be|wear|use)|used to|used for|item needed|wearing|to complete).{0,100}\b(clue|treasure trail|emote)\b|\b(clue|treasure trail|emote).{0,100}\b(requires?|required|must|wear|use|complete|solve)\b", re.I)
STYLE_TERMS = re.compile(r"\b(cosmetic|appearance|decorative|decoration|fashion|colour|color)\b|no (?:stat )?bonuses|purely for (?:cosmetic|decoration)|worn purely", re.I)
PET_TERMS = re.compile(r"\b(pet|follower|companion)\b", re.I)
TROPHY_TERMS = re.compile(r"\b(trophy|trophies|display(?:ed|ing)? (?:in|on|inside)|mount(?:ed|ing)? (?:in|on|inside))\b", re.I)
CONTAINER_TERMS = re.compile(r"\b(open(?:s|ed|ing)?|contains?|contents|loot)\b", re.I)
KEY_TERMS = re.compile(r"\b(key|passage|door|chest|lair|boss|access)\b", re.I)
UPGRADE_TERMS = re.compile(r"\b(upgrad(?:e|ed|es|ing)|enhanc(?:e|ed|es|ing)|combine(?:d|s)?|infus(?:e|ed|es|ing)|attach(?:ed|es)?)\b", re.I)
CHARGE_TERMS = re.compile(r"\b(charg(?:e|es|ed|ing)|recharg(?:e|es|ed|ing)|deplet(?:e|es|ed|ing))\b", re.I)
RELIC_TERMS = re.compile(r"\b(salvag(?:e|es|ed|ing)|repair|restore|rebuild|reconstruct)\b", re.I)
BONUS_BLOCK = re.compile(r"\{\{Infobox Bonuses\b(.*?)\}\}", re.I | re.S)
NUMBER = re.compile(r"\|\s*([a-z]+)\s*=\s*(-?\d+(?:\.\d+)?)", re.I)
CLUE_SCROLL_TITLE = re.compile(r"^clue scroll(?:\s*\(|$)", re.I)
QUEST_ONLY = re.compile(r"\b(?:used only in|only used in|only use in)\b.{0,120}\bquest\b|\b(?:quest|quest completion).{0,120}\b(?:cannot be obtained|cannot be reclaimed|cannot be reobtained|no longer available|used only)\b", re.I)
QUEST_CONTEXT = re.compile(r"\bquest item\b|\bused in the .{0,80}quest\b", re.I)
DOG_PET_TITLE = re.compile(r"\b(labrador|chihuahua|border collie|corgi|greyhound|husky|pug|samoyed|bernese mountain dog|shiba|spaniel|yorkie)\b", re.I)


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def short_quote(text: str, pattern: re.Pattern[str]) -> str | None:
    for raw in text.splitlines():
        line = re.sub(r"\s+", " ", raw).strip()
        if (len(line) > 25 and pattern.search(line)
                and not line.startswith(("|", "{{", "}}", "{|", "[[File:", "!"))):
            return line[:200]
    return None


def descriptive_quote(article: dict[str, Any]) -> str:
    """Return an item-specific article sentence for evidence gaps as well as positive findings."""
    params = article["params"]
    examine = str(params.get("examine", "")).strip()
    if examine and not examine.startswith("{{"):
        return examine[:170]
    for raw in article["text"].splitlines():
        line = re.sub(r"\s+", " ", raw).strip()
        if len(line) > 40 and not line.startswith(("|", "{{", "}}", "{|", "[[File:", "!")):
            return line[:200]
    return ""


def direct_item_evidence(item_id: int, index: dict[str, Any]) -> tuple[dict[str, Any] | None, dict[str, Any] | None, str | None]:
    matches = [(title, entry) for title, entry in index.items()
               if item_id in entry.get("exactInfoboxItemIds", [])
               and str(item_id) in entry.get("variants", {})]
    if len(matches) != 1:
        return None, None, f"Expected one exact parsed Wiki item variant for ID {item_id}; found {len(matches)}."
    title, entry = matches[0]
    path = ROOT / entry["path"]
    if not path.is_file():
        return None, None, f"Pinned article text is missing for exact ID {item_id}."
    text = path.read_text(encoding="utf-8")
    variant = entry["variants"][str(item_id)]
    params = variant.get("params", {})
    exact = str(params.get("id", params.get(f"id{variant.get('suffix', '')}", ""))).strip() == str(item_id)
    # The index's typed parser is the source of the per-variant item ID when IDn is used.
    if item_id not in entry.get("exactInfoboxItemIds", []) or not variant:
        return None, None, f"The parsed article variant does not independently identify exact ID {item_id}."
    source = {
        "kind": "exact_wiki",
        "source": entry.get("sourceUrl", ""),
        "sourceTitle": title,
        "sourceRevision": entry.get("revid"),
        "sourceHash": "sha256:" + entry.get("sha256", sha256(path)),
        "itemId": item_id,
    }
    return {"title": title, "text": text, "params": params, "variant": variant,
            "source": source, "exact": exact}, variant, None


def semantic_roles(category: str, subcategory: str, article: dict[str, Any]) -> tuple[list[str], list[tuple[str, re.Pattern[str]]]]:
    text, params = article["text"], article["params"]
    roles: set[str] = set()
    proof: list[tuple[str, re.Pattern[str]]] = []
    equipable = str(params.get("equipable", "")).strip().casefold() == "yes"
    if equipable:
        roles.add("equipable")
    if re.search(r"\[\[Category:Collection log items\]\]", text, re.I):
        roles.add("collection_log_member")
    for block in BONUS_BLOCK.findall(text):
        vals = {k.casefold(): float(v) for k, v in NUMBER.findall(block)}
        if any(v != 0 for k, v in vals.items() if k not in {"slot", "weight"}):
            roles.add("combat_equipment")
            proof.append(("Combat bonuses", re.compile(r"\{\{Infobox Bonuses", re.I)))
            break

    clue = CLUE_TERMS.search(text) is not None
    clue_use = CLUE_FUNCTION.search(text) is not None
    if re.search(r"\b(?:reward|obtained) from.{0,100}\b(?:clue scroll|treasure trail)s?\b", text, re.I):
        roles.add("clue_reward_provenance")
        proof.append(("Clue-reward provenance", re.compile(r"\b(?:reward|obtained) from.{0,100}\b(?:clue scroll|treasure trail)s?\b", re.I)))
    if clue_use:
        roles.add("functional_clue_utility")
        proof.append(("Clue-use mechanics", CLUE_FUNCTION))

    if category == "CLUE" and subcategory == "treasure-trail":
        return sorted(roles), proof
    if category == "CLUE" and subcategory == "cosmetic":
        style = STYLE_TERMS.search(text) is not None
        if style:
            roles.add("cosmetic_or_style_retention")
            proof.append(("Appearance or wearability", STYLE_TERMS if STYLE_TERMS.search(text) else re.compile(r"\|equipable\s*=\s*Yes", re.I)))
        if PET_TERMS.search(text):
            roles.add("pet_companion")
            if DOG_PET_TITLE.search(article["title"]):
                roles.add("pet_stage_puppy" if "puppy" in article["title"].casefold() else "pet_stage_adult")
            proof.append(("Pet or follower identity", PET_TERMS))
        if QUEST_CONTEXT.search(text):
            roles.add("quest_required_item")
            proof.append(("Quest function", QUEST_CONTEXT))
        return sorted(roles), proof
    if category == "CLUE" and subcategory == "collection-pet":
        if PET_TERMS.search(text):
            roles.add("pet_companion")
            if DOG_PET_TITLE.search(article["title"]):
                roles.add("pet_stage_puppy" if "puppy" in article["title"].casefold() else "pet_stage_adult")
            proof.append(("Pet or follower identity", PET_TERMS))
        return sorted(roles), proof
    if category == "CLUE" and subcategory == "collection-trophy":
        if TROPHY_TERMS.search(text):
            roles.add("display_trophy")
            proof.append(("Display or trophy mechanics", TROPHY_TERMS))
        return sorted(roles), proof

    if subcategory in {"reward-container", "reward-drop"}:
        if CONTAINER_TERMS.search(text):
            roles.add("reward_container_or_drop")
            proof.append(("Opening or reward contents", CONTAINER_TERMS))
    elif subcategory in {"boss-access-key", "reward-key"}:
        if KEY_TERMS.search(text):
            roles.add("access_or_reward_key")
            proof.append(("Key and access mechanics", KEY_TERMS))
    elif subcategory == "key-material":
        if UPGRADE_TERMS.search(text) and KEY_TERMS.search(text):
            roles.add("key_crafting_material")
            proof.extend([("Key mechanics", KEY_TERMS), ("Combination mechanics", UPGRADE_TERMS)])
    elif subcategory in {"equipment-upgrade", "weapon-upgrade"}:
        if UPGRADE_TERMS.search(text):
            roles.add("equipment_upgrade_material")
            proof.append(("Upgrade mechanics", UPGRADE_TERMS))
    elif subcategory == "equipment-charge":
        if CHARGE_TERMS.search(text):
            roles.add("equipment_charge_resource")
            proof.append(("Charge mechanics", CHARGE_TERMS))
    elif subcategory == "salvaging-relic":
        if RELIC_TERMS.search(text):
            roles.add("salvaging_or_recovery_relic")
            proof.append(("Salvage or recovery mechanics", RELIC_TERMS))
    return sorted(roles), proof


def review(packet: dict[str, Any], index: dict[str, Any], policy: dict[str, Any]) -> dict[str, Any]:
    item_id = int(packet["itemId"])
    current = packet["current"]
    article, _, error = direct_item_evidence(item_id, index)
    row = {"itemId": item_id, "shard": "clue-unique", "decision": "unresolved",
           "proposedCategory": current["category"], "proposedSubcategory": current["subcategory"],
           "proposedRoles": [], "proposedIronmanTabKey": current["ironmanTabKey"],
           "semanticPredicate": "", "rationale": "", "evidence": [], "identityLinks": [],
           "proposedTags": list(current["tags"]),
           "reviewer": "collections"}
    if not article:
        row["proposedRoles"] = None
        row["semanticPredicate"] = "Direct exact-ID article identity plus mechanics required to assess primary bank placement."
        row["rationale"] = error or "No direct exact-ID article evidence was available."
        return row

    category, subcategory = current["category"], current["subcategory"]
    roles, proofs = semantic_roles(category, subcategory, article)
    if item_id in set(policy.get("pendingProductPolicyIds", [])):
        if QUEST_CONTEXT.search(article["text"]):
            roles.append("quest_required_item")
        row["proposedRoles"] = sorted(set(roles))
        row["semanticPredicate"] = "Resolve primary placement for zero-stat wearable quest items after the product policy chooses whether appearance retention or quest workflow controls the primary category."
        row["rationale"] = f"The exact '{article['title']}' article documents quest use and a wearable/appearance role. Primary category and subcategory remain unresolved pending the product policy for wearable zero-stat quest items; their documented roles remain separately recorded."
        quote = short_quote(article["text"], QUEST_CONTEXT)
        ev = dict(article["source"]); ev["quote"] = quote or descriptive_quote(article); row["evidence"].append(ev)
        return row
    row["proposedRoles"] = roles
    row["evidence"] = []
    page = article["title"]
    if category == "CLUE" and subcategory == "treasure-trail":
        clue_scroll = bool(CLUE_SCROLL_TITLE.match(page))
        if clue_scroll:
            roles.append("clue_scroll_item")
            proofs.append(("Clue-scroll item identity", CLUE_TERMS))
        supported = "functional_clue_utility" in roles or clue_scroll
        predicate = "Place this exact retained item with clue tools, clue steps, or clue-specific gear only when its article documents a treasure-trail function or context."
        semantic_reason = "The exact article identifies a clue scroll or documents a functional clue use" if supported else "The exact page did not establish a clue-solving function; reward origin or Collection Log association alone cannot certify this placement."
        if not supported and "clue_reward_provenance" in roles and "cosmetic_or_style_retention" in roles:
            row["decision"] = "revise"
            row["proposedSubcategory"] = "cosmetic"
            row["semanticPredicate"] = "Place clue-reward items by their retained role; reward provenance alone does not make them clue tools."
            row["rationale"] = f"ID {item_id} is an exact item variant on pinned '{page}'. Its article establishes cosmetic/style retention and clue-reward provenance but no clue-solving use, so revise the subcategory from treasure-trail to cosmetic while keeping CLUE and its tab."
            for _, pattern in proofs[:2]:
                quote = short_quote(article["text"], pattern)
                if quote:
                    ev = dict(article["source"]); ev["quote"] = quote; row["evidence"].append(ev)
            if not row["evidence"]:
                ev = dict(article["source"]); ev["quote"] = descriptive_quote(article); row["evidence"].append(ev)
            return row
    elif category == "CLUE" and subcategory == "cosmetic":
        supported = "cosmetic_or_style_retention" in roles or "pet_companion" in roles
        predicate = "Place this exact retained item with cosmetic styles or collectible companions when its own article identifies wearability, appearance, or pet identity."
        semantic_reason = "The pinned page identifies an appearance-bearing wearable or companion" if supported else "The exact page did not establish cosmetic or companion identity; clue reward or Collection Log membership alone is insufficient."
        if QUEST_ONLY.search(article["text"]) and "functional_clue_utility" not in roles:
            row["decision"] = "revise"
            row["proposedCategory"], row["proposedSubcategory"], row["proposedIronmanTabKey"] = "CLEANUP", "quest-item", "storage-cleanup"
            row["proposedRoles"] = sorted(set(roles + ["quest_required_item"]))
            row["proposedTags"] = []
            row["semanticPredicate"] = "Place this exact item with quest-retained items when its article documents quest-only use without clue or cosmetic function."
            row["rationale"] = f"ID {item_id} is an exact item variant on pinned '{page}'. Its article documents quest-only use and does not establish clue or cosmetic function; revise to CLEANUP/quest-item/storage-cleanup."
            quote = short_quote(article["text"], QUEST_ONLY)
            if quote:
                ev = dict(article["source"]); ev["quote"] = quote; row["evidence"].append(ev)
            if not row["evidence"]:
                ev = dict(article["source"]); ev["quote"] = descriptive_quote(article); row["evidence"].append(ev)
            return row
    elif category == "CLUE" and subcategory == "collection-pet":
        supported = "pet_companion" in roles
        predicate = "Place the exact ID with clue-associated pets only when its page identifies a pet, follower, or companion."
        semantic_reason = "The pinned page identifies this item as a pet or follower" if supported else "The exact page does not identify this item as a pet or follower."
    elif category == "CLUE" and subcategory == "collection-trophy":
        supported = "display_trophy" in roles
        predicate = "Place a trophy here only when the exact item's article documents an actual display or trophy use; Collection Log membership alone is not sufficient."
        semantic_reason = "The pinned page documents a trophy or display function" if supported else "The exact page did not establish an actual trophy/display function; Collection Log membership alone is not sufficient."
        if not supported and "cosmetic_or_style_retention" in roles:
            row["decision"] = "revise"
            row["proposedSubcategory"] = "cosmetic"
            row["semanticPredicate"] = "Place wearable style items by their documented appearance role; collection progress does not make them display trophies."
            row["rationale"] = f"ID {item_id} is an exact item variant on pinned '{page}'. Its article establishes cosmetic appearance but no display/trophy mechanic; revise the subcategory to cosmetic. Collection Log membership is not evidence."
            for _, pattern in proofs[:2]:
                quote = short_quote(article["text"], pattern)
                if quote:
                    ev = dict(article["source"]); ev["quote"] = quote; row["evidence"].append(ev)
            if not row["evidence"]:
                ev = dict(article["source"]); ev["quote"] = descriptive_quote(article); row["evidence"].append(ev)
            return row
    else:
        supported = bool(roles and proofs)
        predicate = policy["uniquePredicateBySubcategory"].get(subcategory, "Retain the exact item according to a directly documented boss/reward workflow.")
        semantic_reason = f"The pinned page supplies direct mechanics for {subcategory}" if supported else f"The exact page did not substantiate the {subcategory} function."

    row["semanticPredicate"] = predicate
    if supported:
        row["decision"] = "certify"
        row["rationale"] = f"ID {item_id} is an exact item variant on the pinned '{page}' page. {semantic_reason}; the current category, subcategory, and tab are consistent with that retained role."
        # Add a short article excerpt documenting the semantic claim. Infobox identity is already pinned by the revision and hash.
        for label, pattern in proofs[:2]:
            quote = short_quote(article["text"], pattern)
            if quote:
                ev = dict(article["source"])
                ev["quote"] = quote
                row["evidence"].append(ev)
    else:
        row["rationale"] = f"ID {item_id} is an exact item variant on the pinned '{page}' page, but {semantic_reason}"
    if not row["evidence"]:
        ev = dict(article["source"])
        quote = descriptive_quote(article)
        if quote:
            ev["quote"] = quote
        else:
            params = article["params"]
            id_field = next((key for key, value in params.items()
                             if key.casefold().startswith("id") and str(value).strip() == str(item_id)), None)
            facts = []
            if id_field:
                facts.append({"field": id_field, "value": params[id_field]})
            name_field = "name" if params.get("name") else None
            if name_field:
                facts.append({"field": name_field, "value": params[name_field]})
            if facts:
                ev["structuredFacts"] = facts
        row["evidence"].append(ev)
    if row["decision"] == "unresolved" and not roles:
        row["proposedRoles"] = None
    return row


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--packet", type=Path, default=DEFAULT_PACKET)
    ap.add_argument("--index", type=Path, default=DEFAULT_INDEX)
    ap.add_argument("--policy", type=Path, default=DEFAULT_POLICY)
    ap.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = ap.parse_args()
    packets = [json.loads(line) for line in args.packet.read_text(encoding="utf-8").splitlines() if line.strip()]
    index = json.loads(args.index.read_text(encoding="utf-8"))
    policy = json.loads(args.policy.read_text(encoding="utf-8"))
    ids = [int(p["itemId"]) for p in packets]
    if len(ids) != len(set(ids)) or any(p["shard"] != "clue-unique" for p in packets):
        raise ValueError("Packet IDs must be unique and belong to clue-unique")
    decisions = [review(p, index, policy) for p in packets]
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8", newline="\n") as stream:
        for decision in decisions:
            stream.write(json.dumps(decision, ensure_ascii=False, sort_keys=True) + "\n")
    counts: dict[str, int] = {}
    for d in decisions:
        counts[d["decision"]] = counts.get(d["decision"], 0) + 1
    print(json.dumps({"records": len(decisions), "decisions": counts,
                      "packetSha256": sha256(args.packet), "articleIndexSha256": sha256(args.index),
                      "output": str(args.output)}, indent=2))


if __name__ == "__main__":
    main()
