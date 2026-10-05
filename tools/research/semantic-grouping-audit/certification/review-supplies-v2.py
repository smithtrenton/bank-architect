#!/usr/bin/env python3
"""Versioned evidence-first supplies/Herblore certification.

Reads the frozen supplies packet, pinned exact-ID Wiki article index, current coverage,
the prior supplies ledger, and the detached typed-cache identity graph. The prior ledger
is input only; this script writes to a separate v2 output directory.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
from collections import defaultdict, Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
DEFAULT_PACKET = ROOT / "tmp/category-certification/reviewer-packets/supplies-herblore.jsonl"
DEFAULT_INDEX = ROOT / "tmp/category-certification/wiki-articles/article-index.json"
DEFAULT_COVERAGE = ROOT / "tmp/category-certification/current-coverage.tsv"
DEFAULT_V1 = ROOT / "tmp/category-certification/reviews/supplies/decisions.jsonl"
DEFAULT_IDENTITY = ROOT / "tmp/category-certification/identity-links.jsonl"
DEFAULT_IDENTITY_POLICY = Path(__file__).with_name("identity-policy.json")
DEFAULT_POLICY = Path(__file__).with_name("supplies-policy-v2.json")
DEFAULT_OUT = ROOT / "tmp/category-certification/reviews/supplies-v2"

DOSE_RE = re.compile(r"\b([1-4])\s*[- ]?doses?\b", re.I)
HP_RE = re.compile(r"\b(?:heals?|restores?)\s+(?:up to\s+)?(\d+(?:\.\d+)?%?)\s+(?:hit ?points?|hp)\b", re.I)
ENERGY_RE = re.compile(r"\b(?:restores?|restore|regains?)\s+(?:up to\s+)?(\d+(?:\.\d+)?%?)\s+(?:run )?energy\b", re.I)
ACTIVITY_RE = re.compile(r"\b(?:Nightmare Zone|Barbarian Assault|Tithe Farm|Wintertodt|Tempoross|Guardians of the Rift|Pest Control|the Wilderness|Neypotzli|the Gauntlet|the Inferno|a raid)\b", re.I)
RESTRICT_RE = re.compile(
    r"\b(?:can|may)\s+only\s+be\s+used\b.{0,120}\b(?:in|within|during|at)\b.{0,100}\b(?:Wilderness|arena|raid|minigame|quest|area|activity|Neypotzli)\b"
    r"|\b(?:can|may)\s+be\s+used\s+only\b.{0,120}\b(?:in|within|during|at)\b.{0,100}\b(?:Wilderness|arena|raid|minigame|quest|area|activity|Neypotzli)\b"
    r"|\bonly\s+usable\b.{0,100}\b(?:in|within|during|at)\b.{0,100}\b(?:Wilderness|arena|raid|minigame|quest|area|activity|Neypotzli)\b"
    r"|\b(?:cannot|can't)\s+be\s+used\b.{0,100}\b(?:outside|in|within|during)\b.{0,100}\b(?:Wilderness|arena|raid|minigame|quest|area|activity|Neypotzli)\b",
    re.I,
)


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def clean_wiki(text: str) -> str:
    text = re.sub(r"<ref.*?</ref>|<ref[^>]*/?>", " ", text, flags=re.S | re.I)
    text = re.sub(r"\{\{.*?\}\}", " ", text, flags=re.S)
    text = re.sub(r"\[\[(?:[^\]|]*\|)?([^\]]+)\]\]", r"\1", text)
    text = re.sub(r"'''?", "", text)
    return " ".join(text.split())


def body_paragraphs(raw: str) -> list[tuple[str, str]]:
    raw = re.sub(r"\{\{Infobox Item.*?\n\}\}", "\n", raw, count=1, flags=re.S | re.I)
    paragraphs = []
    for para in re.split(r"\n\s*\n", raw):
        literal = para.strip()
        if not literal or literal.startswith("==") or literal.startswith("{{") or literal.startswith("|{"):
            continue
        literal = re.sub(r"^\[\[File:[^\]]*\]\]\s*", "", literal, count=1, flags=re.I)
        plain = clean_wiki(literal)
        if plain and not plain.startswith("=="):
            paragraphs.append((literal, plain))
    return paragraphs


def load_exact_index(path: Path) -> tuple[dict[int, list[tuple[str, dict]]], dict[str, dict]]:
    index = json.loads(path.read_text(encoding="utf-8"))
    by_id: dict[int, list[tuple[str, dict]]] = defaultdict(list)
    for title, meta in index.items():
        for raw_id in meta.get("exactInfoboxItemIds", []):
            if str(raw_id).isdigit():
                by_id[int(raw_id)].append((title, meta))
    return by_id, index


def exact_record_categories(row: dict, item_id: int, extra_records: list[dict] | None = None) -> tuple[set[str], list[dict]]:
    records = list(row.get("sourceEvidence", {}).get("wikiRecords", []))
    records.extend(extra_records or [])
    matching = []
    for record in records:
        raw_ids = record.get("item_id", [])
        if isinstance(raw_ids, (str, int)):
            raw_ids = [raw_ids]
        if item_id in {int(x) for x in raw_ids if str(x).isdigit()}:
            matching.append(record)
    cats = {key[9:] for record in matching for key, value in record.items()
            if key.startswith("Category:") and value is True}
    return cats, matching


def exact_variant(meta: dict, item_id: int) -> tuple[dict, dict, str]:
    variant = meta.get("variants", {}).get(str(item_id), {})
    params = variant.get("params", {})
    suffix = str(variant.get("suffix", ""))
    return variant, params, suffix


def variant_value(params: dict, suffix: str, field: str) -> tuple[str, str]:
    if suffix and f"{field}{suffix}" in params:
        key = f"{field}{suffix}"
        return key, str(params[key])
    if field in params:
        return field, str(params[field])
    return "", ""


def item_evidence(meta: dict, item_id: int, quote: str = "", fields: list[str] | None = None) -> dict:
    variant, params, suffix = exact_variant(meta, item_id)
    structured = []
    for field in fields or []:
        key, value = variant_value(params, suffix, field)
        if key:
            structured.append({"field": key, "value": value})
    evidence = {
        "kind": "exact_wiki", "source": meta["sourceUrl"], "sourceTitle": meta["title"],
        "sourceRevision": int(meta["revid"]), "sourceHash": "sha256:" + meta["sha256"],
        "rawPacketPath": meta.get("packetPath", ""),
        "rawPacketHash": "sha256:" + meta.get("packetSha256", ""), "itemId": item_id,
    }
    if quote:
        normalized_quote = " ".join(quote.split())[:500]
        raw_text = (ROOT / meta["path"]).read_text(encoding="utf-8", errors="replace")
        if normalized_quote in " ".join(raw_text.split()):
            evidence["quote"] = normalized_quote
    if structured:
        evidence["structuredFacts"] = structured
    if not evidence.get("quote") and not structured:
        for field in ("id", "name", "examine", "options", "version"):
            key, value = variant_value(params, suffix, field)
            if key:
                evidence.setdefault("structuredFacts", []).append({"field": key, "value": value})
                break
    return evidence


def assignment(row: dict) -> dict:
    if "current" in row:
        return row["current"]
    tags = [x for x in row.get("tags", "").split(",") if x]
    return {"category": row.get("itemCategory", ""), "subcategory": row.get("subcategory", ""),
            "ironmanTabKey": row.get("ironmanTabKey", ""), "tags": tags}


def matching_paragraph(paras: list[tuple[str, str]], patterns: list[re.Pattern]) -> tuple[str, str]:
    for literal, plain in paras:
        if any(pattern.search(plain) for pattern in patterns):
            return literal, plain
    return "", ""


def direct_review(row: dict, current_by_id: dict[int, dict], by_id: dict[int, list[tuple[str, dict]]],
                  text_cache: dict[str, tuple[str, list[tuple[str, str]]]],
                  policy: dict, extra_records: list[dict] | None = None) -> dict:
    item_id = int(row["itemId"])
    current = assignment(row)
    found = by_id.get(item_id, [])
    if len(found) != 1:
        return {"supported": False, "roles": [], "evidence": [],
                "rationale": "No unique pinned exact-ID article record is available for this numeric item ID."}
    title, meta = found[0]
    variant, params, suffix = exact_variant(meta, item_id)
    text_path = ROOT / meta["path"]
    if str(text_path) not in text_cache:
        text_cache[str(text_path)] = (text_path.read_text(encoding="utf-8"), [])
    raw, paras = text_cache[str(text_path)]
    if not paras:
        paras = body_paragraphs(raw)
        text_cache[str(text_path)] = (raw, paras)
    categories, records = exact_record_categories(row, item_id, extra_records)
    exact_examine = variant_value(params, suffix, "examine")[1]
    exact_name = variant_value(params, suffix, "name")[1] or variant.get("name", "")
    exact_version = variant_value(params, suffix, "version")[1] or variant.get("variant", "")
    exact_options = variant_value(params, suffix, "options")[1]
    full_exact_text = " ".join(x for x in (exact_name, exact_version, exact_examine, exact_options) if x)
    plain_body = " ".join(plain for _, plain in paras[:12])
    context = " ".join(x for x in (full_exact_text, plain_body) if x)
    roles: list[str] = []
    role_quotes: list[tuple[str, list[str]]] = []
    effects: list[str] = []
    workflow_intermediate = False
    structured_fields: list[str] = ["id", "version", "name", "examine", "options", "quest", "heal", "healing", "hitpoints", "hp", "energy", "effect"]
    dose_match = DOSE_RE.search(exact_version) or DOSE_RE.search(exact_examine)
    bucket_dose = next((str(record.get("version_anchor", "")) for record in records
                        if record.get("version_anchor")), "")
    dose_match = dose_match or DOSE_RE.search(bucket_dose)
    heal_num = HP_RE.search(context)
    energy_num = ENERGY_RE.search(context)
    if heal_num:
        effects.append("healing_hp:" + heal_num.group(1))
        lit, _ = matching_paragraph(paras, [HP_RE])
        if lit:
            role_quotes.append((lit, ["examine", "heal", "healing", "hitpoints", "hp"]))
    if energy_num:
        effects.append("run_energy:" + energy_num.group(1))
        lit, _ = matching_paragraph(paras, [ENERGY_RE])
        if lit:
            role_quotes.append((lit, ["examine", "energy", "effect"]))
    if dose_match:
        roles.append("dose_state:" + dose_match.group(1))

    # Quest association is a secondary context role. It never decides the item category.
    quest = variant_value(params, suffix, "quest")[1]
    if quest and quest.lower() != "no":
        roles.append("quest-associated")
        structured_fields.append("quest")
    if "Quest items" in categories:
        roles.append("quest-associated-page-facet")

    options = {x.strip().lower() for x in exact_options.split(",")}
    action_evidence = []
    for field in ("options", "examine", "version", "name", "heal", "healing", "hitpoints", "energy", "effect"):
        key, value = variant_value(params, suffix, field)
        if key:
            action_evidence.append({"field": key, "value": value})

    category = current.get("category", "")
    subcat = current.get("subcategory", "")
    policy_predicate = policy.get("assignment_policy", {}).get(category, {}).get(subcat, "")
    proposition = ""
    assignment_role = ""
    unresolved = []
    article_role_quote, article_role_plain = matching_paragraph(
        paras, [re.compile(r"\bis (?:an? )?(?:unfinished )?potion\b", re.I),
                re.compile(r"\bused (?:to make|in making|as an ingredient|to create)\b", re.I),
                re.compile(r"\bherblore\b", re.I), re.compile(r"\bis eaten\b", re.I),
                re.compile(r"\bwhen eaten\b", re.I), re.compile(r"\bdrink(?:n|ing)?\b", re.I)])

    if category == "POTION":
        if "cargo crate" in exact_examine.lower() and "potion" in exact_examine.lower() and not (options & {"drink", "sip", "quaff", "eat", "bite"}):
            roles.append("courier-cargo-container")
            unresolved.append("The exact variant examine describes a cargo crate carrying potions, and its exact options do not provide a drink/eat action. The taxonomy has no cargo-container destination, so this is not certified as a usable potion.")
        food_action = "eat" in options or "bite" in options or re.search(r"\b(?:eaten|edible|heals|healing)\b", exact_examine, re.I)
        food_effect = bool(heal_num or "Food" in categories or "Edible items" in categories)
        drink_action = bool(options & {"drink", "sip", "quaff"}) or re.search(r"\b(?:drink|sip|quaff)\b", exact_examine, re.I)
        potion_facet = "Potions" in categories
        potion_text = bool(re.search(r"\bpotion\b", exact_examine, re.I) or re.search(r"\bpotion\b", article_role_plain, re.I))
        if food_action and food_effect:
            roles.append("edible_food")
            assignment_role = "food"
        if drink_action and (potion_facet or "Drinks" in categories or energy_num or re.search(r"\bdrink\b", article_role_plain, re.I)):
            roles.append("drinkable")
            if energy_num:
                roles.append("energy-restoring-drink")
            if "Drinks" in categories:
                if assignment_role not in {"food"}:
                    assignment_role = "drink"
        if potion_facet and drink_action and (dose_match or potion_text or energy_num or heal_num):
            roles.append("consumable_potion")
            if not assignment_role:
                assignment_role = "potion"
        if (potion_facet and (dose_match or potion_text) and
                (drink_action or "Drink" in exact_options or "Sip" in exact_options)):
            roles.append("potion-use")
        # Exact activity/restriction text is mandatory for activity-specific buckets.
        restriction_match = next((RESTRICT_RE.search(text) for text in (exact_examine, article_role_plain)
                                 if RESTRICT_RE.search(text)), None)
        activity_text = " ".join((exact_examine, article_role_plain))
        activity_match = ACTIVITY_RE.search(activity_text)
        activity_association = bool(activity_match and re.search(
            r"\b(?:used|usable|can be used|works|active|effect|restores?|drank|drinking)\b.{0,120}\b" +
            re.escape(activity_match.group(0)) + r"\b|\b" + re.escape(activity_match.group(0)) +
            r"\b.{0,120}\b(?:used|usable|works|active|effect|restores?)\b", activity_text, re.I))
        if restriction_match:
            roles.append("potion-use-restriction")
            if subcat == "restricted-potion":
                assignment_role = "restricted-potion"
                role_quotes.append((article_role_quote if RESTRICT_RE.search(article_role_plain) else exact_examine,
                                    ["examine", "version"]))
        elif activity_association and potion_facet and (drink_action or dose_match):
            roles.append("activity-associated-potion:" + activity_match.group(0))
            if subcat == "activity-potion":
                assignment_role = "activity-potion"
                role_quotes.append((article_role_quote, ["examine", "version", "options"]))
        if heal_num and assignment_role == "food":
            role_quotes.append((next((lit for lit, plain in paras if HP_RE.search(plain)), ""),
                                ["examine", "heal", "healing", "hitpoints", "hp"]))
        if energy_num and assignment_role == "drink":
            role_quotes.append((next((lit for lit, plain in paras if ENERGY_RE.search(plain)), ""),
                                ["examine", "energy", "effect"]))
        if subcat in {"potion-dose-1", "potion-dose-2", "potion-dose-3", "potion-dose-4", "dose-1", "dose-2", "dose-3"}:
            expected = int(subcat[-1])
            if dose_match and int(dose_match.group(1)) == expected and "consumable_potion" in roles:
                assignment_role = subcat
            elif dose_match:
                unresolved.append(f"The exact source states a {dose_match.group(1)}-dose potion while the current subcategory is {subcat}.")
            else:
                unresolved.append("The exact current dose state is not stated for this item ID.")
        if subcat == "potion" and "consumable_potion" in roles:
            if assignment_role not in {"food", "drink", "activity-potion", "restricted-potion"}:
                assignment_role = "potion"
        if subcat == "food" and "edible_food" not in roles:
            unresolved.append("No exact Eat/edible action and food effect supports the current food subcategory.")
        if subcat == "drink" and "drinkable" not in roles:
            unresolved.append("No exact Drink/Sip action and effect supports the current drink subcategory.")
        if subcat == "activity-potion" and assignment_role != "activity-potion":
            unresolved.append("The exact item state has no explicit source statement tying its potion use to an activity.")
        if subcat == "restricted-potion" and assignment_role != "restricted-potion":
            unresolved.append("The exact item state has no explicit use/area restriction.")
        if subcat == "pvm-utility":
            if re.search(r"\b(?:PvM|combat|boss|monster|damage|attack|defence|strength)\b", context, re.I):
                roles.append("pvm-combat-utility")
                assignment_role = "pvm-utility"
            else:
                unresolved.append("The exact item source does not document a PvM/combat effect for the current utility bucket.")
        workflow_intermediate = bool(
            "Herblore" in categories and re.search(r"\bintermediate item\b", article_role_plain, re.I) and
            re.search(r"\brequiring?\b.{0,60}\bHerblore\b", article_role_plain, re.I) and
            not (options & {"drink", "sip", "quaff", "eat", "bite"}))
        if workflow_intermediate:
            roles.append("herblore_workflow_intermediate")
            assignment_role = "herblore-supply"
            role_quotes.append((article_role_quote, ["examine", "options", "name", "version"]))
    elif category == "HERBLORE":
        unfinished = bool("Unfinished potions" in categories and re.search(r"need another ingredient|unfinished potion", exact_examine + " " + article_role_plain, re.I))
        secondary = bool("Herblore secondaries" in categories and re.search(r"herblore|potion|ingredient", exact_examine + " " + article_role_plain, re.I))
        herb_facet = "Herbs" in categories
        herblore_text = bool(re.search(r"herblore", exact_examine + " " + article_role_plain, re.I))
        # Variant state must be attached to this exact ID; generic prose about cleaning
        # herbs cannot turn another variant into a clean/grimy item.
        state_name = (exact_name + " " + exact_version + " " + exact_examine).lower()
        if unfinished:
            roles.append("unfinished_potion_stage")
            assignment_role = "unfinished-potion"
            role_quotes.append((article_role_quote or exact_examine, ["examine", "version", "options"]))
        if secondary:
            roles.append("herblore_secondary_ingredient")
            if subcat == "secondary":
                assignment_role = "secondary"
            role_quotes.append((article_role_quote or exact_examine, ["examine", "version", "options"]))
        if herb_facet and herblore_text:
            state = "grimy-herb" if re.search(r"\bgrimy\b", state_name, re.I) else "clean-herb" if re.search(r"\bclean\b", state_name, re.I) else "herb"
            roles.append(state.replace("-", "_") + ":exact-item-state")
            if subcat == state or subcat == "herb" and state == "herb":
                assignment_role = subcat
            role_quotes.append((article_role_quote or exact_examine, ["name", "version", "examine", "options"]))
        if "Herblore" in categories and herblore_text:
            roles.append("herblore_material_or_workflow_input")
            if subcat in {"herblore", "herblore-supply", "herblore-base"} and not assignment_role:
                assignment_role = subcat
                role_quotes.append((article_role_quote or exact_examine, ["examine", "version", "options"]))
        if subcat == "unfinished-potion" and not unfinished:
            unresolved.append("The exact item ID has no unfinished-potion stage/examine evidence.")
        if subcat == "secondary" and not secondary:
            unresolved.append("The exact item ID has no direct secondary-ingredient role evidence.")
        if subcat in {"herb", "clean-herb", "grimy-herb"} and not any(r.endswith("exact-item-state") for r in roles):
            unresolved.append("The exact item ID has no direct herb-state and Herblore-role evidence.")
        if subcat in {"herblore", "herblore-supply", "herblore-base"} and not assignment_role:
            unresolved.append("The exact article does not document a Herblore material/base/supply role for this ID.")

    # Normalize primary-role candidates and avoid certifying overlapping placement claims.
    if assignment_role:
        expected_subcat = assignment_role
        if category == "POTION" and assignment_role in {"food", "drink", "potion", "activity-potion", "restricted-potion", "pvm-utility"}:
            if subcat == expected_subcat:
                pass
        elif category == "HERBLORE" and subcat == expected_subcat:
            pass
        elif assignment_role in {"potion-dose-1", "potion-dose-2", "potion-dose-3", "potion-dose-4", "dose-1", "dose-2", "dose-3"} and subcat == expected_subcat:
            pass
    role_candidates = {r for r in roles if r in {"edible_food", "drinkable", "consumable_potion", "potion-use-restriction", "pvm-combat-utility", "herblore_secondary_ingredient", "unfinished_potion_stage", "herblore_material_or_workflow_input"} or r.startswith(("activity-associated-potion:", "clean_herb:", "grimy_herb:", "herb:"))}
    primary_overlaps = ("edible_food" in role_candidates and "consumable_potion" in role_candidates) or ("drinkable" in role_candidates and "edible_food" in role_candidates)
    current_matches = bool(assignment_role) and (
        assignment_role == subcat or
        assignment_role == "potion" and subcat == "potion" or
        assignment_role == "herblore" and subcat == "herblore"
    )
    correction = None
    correction_policy = policy.get("correction_targets", {}).get(category, {}).get(assignment_role)
    if correction_policy and assignment_role != subcat:
        direct_primary_support = False
        if category == "POTION" and assignment_role == "food":
            direct_primary_support = food_action and food_effect and not drink_action and not potion_facet
        elif category == "POTION" and assignment_role == "drink":
            direct_primary_support = drink_action and ("Drinks" in categories or bool(energy_num)) and not food_action and not potion_facet
        elif category == "HERBLORE" and assignment_role == "unfinished-potion":
            direct_primary_support = unfinished
        elif category == "HERBLORE" and assignment_role == "secondary":
            direct_primary_support = secondary
        elif category == "HERBLORE" and assignment_role in {"clean-herb", "grimy-herb"}:
            direct_primary_support = herb_facet and herblore_text and assignment_role.split("-")[0] in state_name
        elif category == "POTION" and assignment_role == "herblore-supply":
            direct_primary_support = workflow_intermediate
        if direct_primary_support:
            correction = correction_policy
    evidence = []
    quote, fields = next(((q, f) for q, f in role_quotes if q), ("", []))
    if not quote and records:
        quote = next((str(record.get("examine", "")) for record in records if record.get("examine")), "")
        fields = ["examine", "options", "version"]
    if quote or action_evidence:
        evidence.append(item_evidence(meta, item_id, quote, fields or ["options", "examine", "version", "quest"]))
    else:
        evidence.append(item_evidence(meta, item_id, "", ["id", "name", "examine", "options", "version"]))
    effects.extend(r for r in roles if r.startswith("dose_state:"))
    if not roles:
        reason = "The pinned exact-ID item record is present, but the item-specific article text/variant fields do not establish a positive functional role."
        return {"supported": False, "roles": [], "effects": effects, "evidence": evidence, "rationale": reason,
                "sourceTitle": title, "primaryRole": "", "assignmentRole": "", "currentMatches": False}
    if current_matches and not primary_overlaps and not unresolved:
        return {"supported": True, "roles": sorted(set(roles)), "effects": sorted(set(effects)), "evidence": evidence,
                "rationale": "Exact-ID article prose and the selected variant's own structured options/examine support the current functional placement; dose, healing, energy, restrictions, and quest association are represented as separate roles where present. Applied assignment policy: " + policy_predicate,
                "sourceTitle": title, "primaryRole": assignment_role, "assignmentRole": assignment_role, "currentMatches": True}
    rationale = "; ".join(unresolved)
    if primary_overlaps and not rationale:
        rationale = "The exact item has overlapping consumable roles; primary placement needs an explicit policy decision while dose/effect roles remain separate."
    elif not rationale:
        rationale = f"Exact source supports role(s) {', '.join(sorted(role_candidates or set(roles)))}, but those roles do not fully establish the current {category}/{subcat} placement."
    if correction:
        rationale = f"Exact item evidence supports {correction['category']}/{correction['subcategory']}: {correction['predicate']} Current source facts show options={exact_options!r}, examine={exact_examine!r}, and exact Wiki facets={sorted(categories)!r}."
    return {"supported": False, "roles": sorted(set(roles)), "effects": sorted(set(effects)), "evidence": evidence,
            "rationale": rationale, "sourceTitle": title, "primaryRole": assignment_role,
            "assignmentRole": assignment_role, "currentMatches": current_matches,
            "correction": correction}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--packet", type=Path, default=DEFAULT_PACKET)
    ap.add_argument("--index", type=Path, default=DEFAULT_INDEX)
    ap.add_argument("--coverage", type=Path, default=DEFAULT_COVERAGE)
    ap.add_argument("--v1", type=Path, default=DEFAULT_V1)
    ap.add_argument("--identity", type=Path, default=DEFAULT_IDENTITY)
    ap.add_argument("--identity-policy", type=Path, default=DEFAULT_IDENTITY_POLICY)
    ap.add_argument("--policy", type=Path, default=DEFAULT_POLICY)
    ap.add_argument("--output", type=Path, default=DEFAULT_OUT)
    args = ap.parse_args()

    policy = json.loads(args.policy.read_text(encoding="utf-8"))
    identity_policy = json.loads(args.identity_policy.read_text(encoding="utf-8"))
    rows = [json.loads(line) for line in args.packet.read_text(encoding="utf-8-sig").splitlines() if line.strip()]
    old_decisions = {int(r["itemId"]): r for r in (json.loads(line) for line in args.v1.read_text(encoding="utf-8").splitlines() if line.strip())}
    current_by_id = {}
    with args.coverage.open(encoding="utf-8-sig", newline="") as stream:
        for r in csv.DictReader(stream, delimiter="\t"):
            if str(r.get("itemId", "")).isdigit():
                current_by_id[int(r["itemId"])] = r
    by_id, index = load_exact_index(args.index)
    edges_by_from: dict[int, list[dict]] = defaultdict(list)
    with args.identity.open(encoding="utf-8") as stream:
        for line in stream:
            edge = json.loads(line)
            edges_by_from[int(edge["fromItemId"])].append(edge)

    text_cache: dict[str, tuple[str, list[tuple[str, str]]]] = {}
    direct_cache: dict[int, dict] = {}
    packet_by_id = {int(r["itemId"]): r for r in rows}
    for row in rows:
        item_id = int(row["itemId"])
        direct_cache[item_id] = direct_review(row, current_by_id, by_id, text_cache, policy)

    output = []
    inherited_counts = Counter()
    status_counts = Counter()
    source_review_counts = Counter()
    for row in rows:
        item_id = int(row["itemId"])
        current = row["current"]
        base = dict(old_decisions[item_id])
        # Earlier reviewer actions are candidates, not approvals. Re-evaluate every
        # assigned ID from exact source and typed identity evidence while preserving
        # the frozen v1 ledger as a separate input artifact.
        base.update({"decision": "unresolved", "proposedCategory": current["category"],
                     "proposedSubcategory": current["subcategory"],
                     "proposedTags": sorted(current.get("tags", [])),
                     "proposedRoles": None, "proposedIronmanTabKey": current["ironmanTabKey"],
                     "semanticPredicate": "Evaluate this exact item's primary function, state, and tab independently from its pinned exact-ID source; preserve overlap as separate roles.",
                     "rationale": "The exact item source does not yet establish an actionable classification.",
                     "evidence": [], "identityLinks": []})

        direct = direct_cache[item_id]
        if direct.get("supported"):
            base.update({"decision": "certify", "proposedCategory": current["category"],
                         "proposedSubcategory": current["subcategory"], "proposedTags": sorted(current.get("tags", [])),
                         "proposedRoles": direct["roles"], "proposedIronmanTabKey": current["ironmanTabKey"],
                         "rationale": direct["rationale"], "evidence": direct["evidence"], "identityLinks": []})
            source_review_counts["direct_certify"] += 1
            output.append(base)
            status_counts["certify"] += 1
            continue
        if direct.get("correction"):
            target = direct["correction"]
            base.update({"decision": "revise", "proposedCategory": target["category"],
                         "proposedSubcategory": target["subcategory"],
                         "proposedTags": sorted(current.get("tags", [])),
                         "proposedRoles": direct["roles"],
                         "proposedIronmanTabKey": target["ironmanTabKey"],
                         "semanticPredicate": target["predicate"],
                         "rationale": direct["rationale"], "evidence": direct["evidence"],
                         "identityLinks": []})
            source_review_counts["direct_revise"] += 1
            output.append(base)
            status_counts["revise"] += 1
            continue
        if direct.get("roles"):
            base["proposedRoles"] = direct["roles"]
            base["evidence"] = direct["evidence"]
            base["rationale"] = direct["rationale"]
            source_review_counts["direct_role_but_unresolved"] += 1

        inherited = False
        allowed = identity_policy.get("classificationPolicy", {})
        for edge in edges_by_from.get(item_id, []):
            relation = edge.get("relation")
            if relation not in {"NOTE_VARIANT_OF", "PLACEHOLDER_FOR"}:
                continue
            rule = allowed.get(relation, {}).get("inheritCanonicalBankGrouping", "no")
            if rule not in {"conditional for bank-storage grouping only", "yes in the current runtime bank snapshot when RuneLite exposes a valid placeholder template and target ID"}:
                continue
            target_id = int(edge["toItemId"])
            target_row = packet_by_id.get(target_id)
            if target_row is None:
                coverage_target = current_by_id.get(target_id)
                if not coverage_target:
                    continue
                target_row = {"itemId": target_id,
                              "current": {"category": coverage_target.get("itemCategory", ""),
                                          "subcategory": coverage_target.get("subcategory", ""),
                                          "ironmanTabKey": coverage_target.get("ironmanTabKey", ""),
                                          "tags": [x for x in coverage_target.get("tags", "").split(",") if x]},
                              "sourceEvidence": {}}
            support = []
            for bucket in edge.get("wikiBucketSupport", []):
                support.extend(bucket.get("sourceRecords", []))
            target_review = direct_review(target_row, current_by_id, by_id, text_cache, policy, support)
            if not target_review.get("supported"):
                continue
            target_assignment = assignment(target_row)
            identity_hash = identity_policy.get("inputs", {}).get("typedIdentityEdges", {}).get("sha256", "")
            typed = next((dict(e, identityIndexHash=identity_hash)
                          for e in edge.get("evidence", []) if e.get("kind") == "typed_identity"), None)
            if not typed:
                continue
            semantic = next((e for e in target_review.get("evidence", []) if e.get("kind") == "exact_wiki"), None)
            if not semantic:
                continue
            state_role = "note-form-bank-grouping" if relation == "NOTE_VARIANT_OF" else "placeholder-bank-slot"
            # Neither a note nor an empty placeholder inherits the target's use, dose,
            # effect, or state. The target's role only supports bank grouping.
            inherited_roles = [state_role] + [
                "bank-grouped-with-exact-target:" + role for role in target_review["roles"]
                if role in {"herblore_material_or_workflow_input", "unfinished_potion_stage",
                            "herblore_secondary_ingredient", "edible_food", "consumable_potion",
                            "drinkable", "potion-use-restriction", "pvm-combat-utility"}
                or role.startswith(("dose_state:", "activity-associated-potion:", "clean_herb:", "grimy_herb:", "herb:"))]
            base.update({"proposedCategory": target_assignment["category"],
                         "proposedSubcategory": target_assignment["subcategory"],
                         "proposedTags": sorted(current.get("tags", [])),
                         "proposedIronmanTabKey": target_assignment["ironmanTabKey"],
                         "proposedRoles": inherited_roles,
                         "rationale": f"Typed {relation} cache edge identifies exact target ID {target_id}; that target independently has exact source-backed roles {', '.join(target_review['roles'])}. The supplied identity policy permits this relation to inherit bank grouping while retaining this item's {('note-form' if relation == 'NOTE_VARIANT_OF' else 'placeholder-slot')} state; item usability is not inherited.",
                         "evidence": [],
                         "identityLinks": [{"itemId": target_id, "fromItemId": item_id, "toItemId": target_id, "relation": relation,
                                            "evidence": [typed, semantic]}]})
            same = (base["proposedCategory"] == current["category"] and
                    base["proposedSubcategory"] == current["subcategory"] and
                    base["proposedIronmanTabKey"] == current["ironmanTabKey"] and
                    set(base["proposedTags"]) == set(current.get("tags", [])))
            base["decision"] = "certify" if same else "revise"
            inherited_counts[relation] += 1
            inherited = True
            break
        if inherited:
            output.append(base)
            status_counts[base["decision"]] += 1
            continue

        # Exact source IDs receive a concrete role/effect account even when the taxonomy
        # or role priority remains unsettled. Identity provenance alone stays unresolved.
        if direct.get("evidence"):
            base["evidence"] = direct["evidence"]
        if direct.get("roles"):
            base["proposedRoles"] = direct["roles"]
        else:
            base["proposedRoles"] = None
        if direct.get("rationale"):
            base["rationale"] = direct["rationale"]
        if not direct.get("sourceTitle"):
            base["rationale"] = "No unique pinned exact-ID item article variant is indexed for this numeric ID; no category or role is inferred from its title, family, or unrelated page facts."
        base["decision"] = "unresolved"
        output.append(base)
        status_counts["unresolved"] += 1

    args.output.mkdir(parents=True, exist_ok=True)
    decisions_path = args.output / "decisions.jsonl"
    with decisions_path.open("w", encoding="utf-8", newline="\n") as stream:
        for item in output:
            stream.write(json.dumps(item, ensure_ascii=False, separators=(",", ":")) + "\n")
    roles_path = args.output / "role-evidence.jsonl"
    with roles_path.open("w", encoding="utf-8", newline="\n") as stream:
        for item_id, review in direct_cache.items():
            stream.write(json.dumps({"itemId": item_id, **review}, ensure_ascii=False, separators=(",", ":")) + "\n")
    summary = {
        "version": "supplies-herblore-certification-v2",
        "reviewedIds": len(output), "decisionCounts": dict(status_counts),
        "directExactIndexedIds": sum(bool(by_id.get(int(r["itemId"]))) for r in rows),
        "directRoleCounts": dict(source_review_counts), "typedInheritedCounts": dict(inherited_counts),
        "unresolvedIds": status_counts.get("unresolved", 0),
        "inputs": {
            "packet": {"path": str(args.packet), "sha256": sha256(args.packet)},
            "articleIndex": {"path": str(args.index), "sha256": sha256(args.index)},
            "coverage": {"path": str(args.coverage), "sha256": sha256(args.coverage)},
            "priorLedger": {"path": str(args.v1), "sha256": sha256(args.v1)},
            "identityLinks": {"path": str(args.identity), "sha256": sha256(args.identity)},
            "identityPolicy": {"path": str(args.identity_policy), "sha256": sha256(args.identity_policy)},
            "suppliesPolicy": {"path": str(args.policy), "sha256": sha256(args.policy)},
        },
        "semanticLimits": [
            "Pinned revision/hash audit validates provenance, not whether an exact textual fact supports a role.",
            "NOTE_VARIANT_OF and PLACEHOLDER_FOR inherit bank grouping only under the supplied identity policy and only from an independently source-supported target.",
            "BOUGHT_VARIANT_OF has no inheritance. Quest association, dose, edible/drink overlap, activity restrictions, and item state remain separate roles.",
            "Rows without a direct or permitted inherited role remain unresolved with a specific evidence gap.",
        ],
    }
    (args.output / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"reviewedIds": len(output), "decisionCounts": dict(status_counts),
                      "directRoleCounts": dict(source_review_counts), "typedInheritedCounts": dict(inherited_counts)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
