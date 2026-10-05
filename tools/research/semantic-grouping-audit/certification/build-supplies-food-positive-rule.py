#!/usr/bin/env python3
"""Build an immutable root-review cohort for strictly evidenced POTION/food rows.

This packet is a candidate set for policy review, not a certification or approval.
It only considers the direct exact-source certify rows in supplies-herblore v2.
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
DEFAULT_DECISIONS = ROOT / "tmp/category-certification/reviews/supplies-v2/decisions.jsonl"
DEFAULT_ROLE_EVIDENCE = ROOT / "tmp/category-certification/reviews/supplies-v2/role-evidence.jsonl"
DEFAULT_PACKET = ROOT / "tmp/category-certification/reviewer-packets/supplies-herblore.jsonl"
DEFAULT_INDEX = ROOT / "tmp/category-certification/wiki-articles/article-index.json"
DEFAULT_OUT = ROOT / "tmp/category-certification/reviews/supplies-food-positive-v6"

EFFECT_RE = re.compile(
    r"\b(?:heal(?:s|ed)?|restores?|restore|recovers?|regains?)\b[^.!?\n]{0,120}"
    r"(?:\b\d+(?:\s*(?:-|–|to)\s*\d+)?%?\b[^.!?\n]{0,45})?"
    r"\b(?:hit ?points?|hp|health|(?:run )?energy|stamina)\b"
    r"|\b\d+(?:\s*(?:-|–|to)\s*\d+)?%?\s*(?:hit ?points?|hp|health|(?:run )?energy|stamina)"
    r"[^.!?\n]{0,90}\b(?:heal(?:s|ed)?|restores?|restore|recovers?|regains?)\b",
    re.I,
)
EFFECT_NUM_RE = re.compile(r"\d", re.I)
EAT_CONTEXT_RE = re.compile(r"\b(?:when eaten|if eaten|eaten when|eating (?:the|this) (?:food|fish|item)|upon eating|after eating)\b", re.I)
MULTIBITE_RE = re.compile(
    r"\b(?:two|three|four|multiple|several|\d+)\s+(?:separate\s+)?bites\b",
    re.I,
)
ACTIVITY_RE = re.compile(
    r"\b(?:can|may)\s+only\s+be\s+(?:eaten|used)\b.{0,120}\b(?:in|within|during|at)\b.{0,100}"
    r"|\b(?:can|may)\s+be\s+(?:eaten|used)\s+only\b.{0,120}\b(?:in|within|during|at)\b.{0,100}"
    r"\b(?:Wilderness|Barbarian Assault|Tithe Farm|Wintertodt|Tempoross|Nightmare Zone|Pest Control|arena|raid|minigame|activity)\b",
    re.I,
)
INGREDIENT_RE = re.compile(
    r"\b(?:is|are|used as|serves as)\b.{0,70}\b(?:an? )?(?:cooking )?ingredient\b"
    r"|\bused to (?:make|create|prepare|cook)\b.{0,100}\b(?:food|meal|dish|pie|pizza|cake)\b"
    r"|\bused in cooking\b",
    re.I,
)
STAGE_RE = re.compile(r"\b(?:uncooked|raw|unprepared|incomplete|unfinished|half[- ]eaten|partly eaten|unbaked|unfried|uncut|slice of|piece of|half (?:a|an|of)|\d+/\d+)\b", re.I)
UNPLEASANT_RE = re.compile(r"\b(?:poison|poisoned|poisonous|rotten|putrid|inedible|bad food|bad kebab|burnt|burned|disgusting|slimy|unappetising|unappetizing)\b|(?:not|does not|doesn't)\s+(?:look\s+)?(?:too\s+)?appetising|tastes better than it looks", re.I)
DISGUISE_RE = re.compile(r"\b(?:disguise|disguised|costume food|food disguise)\b", re.I)
INTERFACE_RE = re.compile(r"\b(?:cargo crate|crate of|cargo|package of|construction|furniture|interface|display item|model of)\b", re.I)
QUEST_RE = re.compile(r"\b(?:quest item|used in (?:the )?[A-Z][A-Za-z' -]+ quest|needed for (?:the )?[A-Z][A-Za-z' -]+ quest)\b")
HOLIDAY_CATEGORIES = {"Holiday items", "Holiday event items", "Items from holiday events"}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def compact(text: str) -> str:
    return " ".join(str(text).split())


def plain_wiki(text: str) -> str:
    text = re.sub(r"<ref.*?</ref>|<ref[^>]*/?>", " ", text, flags=re.S | re.I)
    text = re.sub(r"\[\[(?:[^\]|]*\|)?([^\]]+)\]\]", r"\1", text)
    text = re.sub(r"<[^>]+>", " ", text)
    return compact(re.sub(r"'''?", "", text))


def strip_templates(text: str) -> str:
    """Drop balanced transclusion markup while retaining surrounding article prose."""
    out = []
    depth = 0
    i = 0
    while i < len(text):
        if text.startswith("{{", i):
            depth += 1
            i += 2
            continue
        if depth and text.startswith("}}", i):
            depth -= 1
            i += 2
            continue
        if depth:
            i += 1
            continue
        out.append(text[i])
        i += 1
    return "".join(out)


def paragraphs(raw: str) -> list[tuple[str, str]]:
    body = re.sub(r"\{\{Infobox Item.*?\n\}\}", "\n", raw, count=1, flags=re.S | re.I)
    body = strip_templates(body)
    out = []
    for block in re.split(r"\n\s*\n", body):
        literal = block.strip()
        if not literal or literal.startswith(("==", "{{", "|{")):
            continue
        literal = re.sub(r"^\[\[File:[^\]]*\]\]\s*", "", literal, count=1, flags=re.I)
        plain = plain_wiki(literal)
        if plain and not plain.startswith("=="):
            out.append((literal, plain))
    return out


def sentence_pairs(literal: str, plain: str) -> list[tuple[str, str]]:
    # Keep literal and readable forms paired by splitting on likely sentence breaks.
    raw_sentences = re.split(r"(?<=[.!?])\s+(?=[A-Z\[]|''')", literal)
    plain_sentences = re.split(r"(?<=[.!?])\s+(?=[A-Z])", plain)
    if len(raw_sentences) == len(plain_sentences):
        return [(compact(raw), compact(readable)) for raw, readable in zip(raw_sentences, plain_sentences)]
    return [(compact(literal), compact(plain))]


def exact_params(meta: dict, item_id: int) -> tuple[dict, str]:
    variant = meta.get("variants", {}).get(str(item_id), {})
    return variant.get("params", {}), str(variant.get("suffix", ""))


def variant_fact(params: dict, suffix: str, field: str) -> tuple[str, str]:
    key = f"{field}{suffix}" if suffix and f"{field}{suffix}" in params else field if field in params else ""
    return (key, str(params[key])) if key else ("", "")


def exact_categories(packet_row: dict, item_id: int) -> set[str]:
    categories = set()
    for record in packet_row.get("sourceEvidence", {}).get("wikiRecords", []):
        raw_ids = record.get("item_id", [])
        if isinstance(raw_ids, (str, int)):
            raw_ids = [raw_ids]
        if item_id not in {int(value) for value in raw_ids if str(value).isdigit()}:
            continue
        categories.update(key[9:] for key, value in record.items()
                          if key.startswith("Category:") and value is True)
    return categories


def source_evidence(meta: dict, item_id: int, params: dict, suffix: str, quote: str = "") -> dict:
    fields = []
    for name in ("id", "name", "version", "examine", "options", "quest"):
        key, value = variant_fact(params, suffix, name)
        if key:
            fields.append({"field": key, "value": value})
    evidence = {
        "kind": "exact_wiki", "source": meta["sourceUrl"], "sourceTitle": meta["title"],
        "sourceRevision": int(meta["revid"]), "sourceHash": "sha256:" + meta["sha256"],
        "rawPacketPath": meta.get("packetPath", ""),
        "rawPacketHash": "sha256:" + meta.get("packetSha256", ""), "itemId": item_id,
        "structuredFacts": fields,
    }
    if quote:
        evidence["quote"] = compact(quote)
    return evidence


def literal_effect(paras: list[tuple[str, str]], exact_name: str) -> tuple[str, str]:
    for literal, plain in paras:
        for raw_sentence, sentence in sentence_pairs(literal, plain):
            # Split clauses so an effect attached to a neighboring recipe product
            # cannot be attributed to the reviewed item merely because both names
            # occur in one sentence (for example, poisoned and cooked variants).
            clauses = re.split(r"[,;]\s+", sentence)
            for clause in clauses:
                if not EFFECT_RE.search(clause) or not EFFECT_NUM_RE.search(clause):
                    continue
                subject_specific = bool(
                    (exact_name and exact_name.casefold() in clause.casefold()) or
                    EAT_CONTEXT_RE.search(clause) or
                    re.search(r"\b(?:when|if) eaten\b[^.!?]{0,55}\b(?:it|this (?:food|fish|item)|the (?:food|fish|item))\b", clause, re.I)
                )
                if subject_specific and raw_sentence and len(raw_sentence) <= 900:
                    return raw_sentence, clause
    return "", ""


def reason_evidence(quote: str, params: dict, suffix: str) -> dict:
    evidence = {}
    if quote:
        evidence["literalQuote"] = compact(quote)
    for field in ("name", "version", "examine", "options", "quest"):
        key, value = variant_fact(params, suffix, field)
        if key:
            evidence.setdefault("structuredFacts", []).append({"field": key, "value": value})
    return evidence


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--decisions", type=Path, default=DEFAULT_DECISIONS)
    parser.add_argument("--role-evidence", type=Path, default=DEFAULT_ROLE_EVIDENCE)
    parser.add_argument("--packet", type=Path, default=DEFAULT_PACKET)
    parser.add_argument("--index", type=Path, default=DEFAULT_INDEX)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError(f"Refusing to overwrite immutable output: {args.output}")

    decisions = [json.loads(line) for line in args.decisions.read_text(encoding="utf-8").splitlines() if line.strip()]
    packet_rows = {int(row["itemId"]): row for row in
                   (json.loads(line) for line in args.packet.read_text(encoding="utf-8-sig").splitlines() if line.strip())}
    index = json.loads(args.index.read_text(encoding="utf-8"))
    by_id = defaultdict(list)
    for title, meta in index.items():
        for raw_id in meta.get("exactInfoboxItemIds", []):
            if str(raw_id).isdigit():
                by_id[int(raw_id)].append((title, meta))

    all_direct_certs = [decision for decision in decisions
                        if decision.get("decision") == "certify" and not decision.get("identityLinks") and
                        any(e.get("kind") == "exact_wiki" and int(e.get("itemId", -1)) == int(decision["itemId"])
                            for e in decision.get("evidence", []))]
    if len(all_direct_certs) != 519:
        raise ValueError(f"Expected 519 directly sourced certify rows from the frozen v2 output; found {len(all_direct_certs)}")

    root_rows = []
    candidate_clusters: dict[str, dict] = {}
    counts = Counter()
    for decision in all_direct_certs:
        item_id = int(decision["itemId"])
        packet_row = packet_rows[item_id]
        current = packet_row["current"]
        item_evidence = next(e for e in decision["evidence"]
                             if e.get("kind") == "exact_wiki" and int(e.get("itemId", -1)) == item_id)
        indexed_matches = by_id.get(item_id, [])
        if len(indexed_matches) != 1:
            counts["separate_no_unique_exact_article"] += 1
            root_rows.append({"itemId": item_id, "reviewStatus": "separate", "reasonCodes": ["no_unique_exact_article"],
                              "current": current, "proposed": {k: decision.get(k) for k in
                                  ("proposedCategory", "proposedSubcategory", "proposedIronmanTabKey")},
                              "evidence": [item_evidence], "rationale": "Direct certify input does not resolve to exactly one pinned exact-ID article."})
            continue
        title, meta = indexed_matches[0]
        params, suffix = exact_params(meta, item_id)
        option_key, exact_options = variant_fact(params, suffix, "options")
        examine_key, exact_examine = variant_fact(params, suffix, "examine")
        name_key, exact_name = variant_fact(params, suffix, "name")
        version_key, exact_version = variant_fact(params, suffix, "version")
        categories = exact_categories(packet_row, item_id)
        raw_text = (ROOT / meta["path"]).read_text(encoding="utf-8", errors="replace")
        paras = paragraphs(raw_text)
        lead_literal, lead_plain = paras[0] if paras else ("", "")
        lead_first = re.split(r"(?<=[.!?])\s+", lead_plain, maxsplit=1)[0] if lead_plain else ""
        effect_quote, effect_plain = literal_effect(paras, exact_name)
        exact_tokens = {token.strip().casefold() for token in exact_options.split(",") if token.strip()}
        reasons = []
        separation_reasons = []
        if (current.get("category"), current.get("subcategory"), current.get("ironmanTabKey")) != ("POTION", "food", "potions-food"):
            reasons.append("not_current_potion_food_tab")
        if "eat" not in exact_tokens:
            reasons.append("exact_variant_has_no_Eat_option")
        if not effect_quote:
            reasons.append("no_literal_subject_specific_numeric_healing_or_nourishment_clause")

        identity_text = " ".join((exact_name, exact_version, exact_examine, lead_plain))
        exact_state_text = " ".join((exact_name, exact_version, exact_examine))
        all_plain = " ".join(plain for _, plain in paras)
        bite_clause = next((plain for _, plain in paras if MULTIBITE_RE.search(plain) and
                            (exact_name.casefold() in plain.casefold() or
                             re.search(r"\b(?:this|the) (?:food|fish|item|cake|pie|pizza)\b", plain, re.I))), "")
        if bite_clause or re.search(r"\bEat (?:one|a) bite\b", exact_options, re.I):
            separation_reasons.append("multi_bite_mechanic")
        if DISGUISE_RE.search(" ".join((exact_state_text, lead_first))) or "Disguises" in categories:
            separation_reasons.append("disguise_or_costume_role")
        if STAGE_RE.search(exact_state_text) or re.search(r"\b(?:must|needs? to|cannot be eaten until|before it can be eaten)\b.{0,70}\b(?:cook|prepare|bake|fry)\w*", lead_first, re.I):
            separation_reasons.append("staged_or_unprepared_variant")
        quest_value = variant_fact(params, suffix, "quest")[1]
        if quest_value.casefold() == "yes" or "Quest items" in categories or QUEST_RE.search(lead_plain):
            separation_reasons.append("quest_food_or_quest_item")
        if INGREDIENT_RE.search(lead_plain) or re.search(r"\b(?:cooking|food) ingredient\b", exact_examine, re.I):
            separation_reasons.append("food_or_cooking_ingredient")
        if ACTIVITY_RE.search(" ".join((exact_name, exact_version, exact_examine, all_plain))):
            separation_reasons.append("explicit_activity_only_restriction")
        negative_lead = re.search(r"\b(?:poisoned|poisonous|rotten|putrid|inedible|bad food|bad kebab|burnt|burned|disgusting)\b", lead_first, re.I)
        if UNPLEASANT_RE.search(exact_state_text) or negative_lead:
            separation_reasons.append("unpleasant_poisoned_rotten_or_burnt_state")
        if re.search(r"\bpremade\b", exact_name, re.I) or INTERFACE_RE.search(" ".join((exact_name, exact_version, exact_examine, lead_first))):
            separation_reasons.append("construction_cargo_or_interface_object")
        if "Holiday items" in categories or "Holiday event items" in categories or "Items from holiday events" in categories:
            separation_reasons.append("holiday_or_event_collectible")

        target = (current.get("category"), current.get("subcategory"), current.get("ironmanTabKey")) == ("POTION", "food", "potions-food")
        included = target and "eat" in exact_tokens and bool(effect_quote) and not separation_reasons
        reasons.extend(separation_reasons)
        status = "candidate_positive_rule" if included else "separate"
        if included:
            counts["candidate_positive_rule"] += 1
            mechanic_template = plain_wiki(effect_quote).casefold()
            if exact_name:
                mechanic_template = re.sub(re.escape(exact_name.casefold()), "<item>", mechanic_template, flags=re.I)
            mechanic_template = re.sub(r"\b\d+(?:\s*(?:-|–|to)\s*\d+)?%?\b", "<n>", mechanic_template)
            lead_template = plain_wiki(lead_first).casefold()
            if exact_name:
                lead_template = re.sub(re.escape(exact_name.casefold()), "<item>", lead_template, flags=re.I)
            lead_template = re.sub(r"\b\d+(?:\s*(?:-|–|to)\s*\d+)?%?\b", "<n>", lead_template)
            cluster_key = hashlib.sha256((lead_template + " || " + mechanic_template).encode("utf-8")).hexdigest()[:16]
            cluster = candidate_clusters.setdefault(cluster_key, {
                "clusterId": cluster_key, "leadTemplate": lead_template, "mechanicTemplate": mechanic_template,
                "members": [],
            })
            cluster["members"].append({"itemId": item_id, "sourceTitle": title,
                                       "sourceRevision": int(meta["revid"]), "sourceHash": "sha256:" + meta["sha256"],
                                       "literalLead": compact(lead_literal)[:1000],
                                       "literalClause": compact(effect_quote), "readableClause": effect_plain})
        else:
            counts["separate_noncandidate"] += 1

        evidence = source_evidence(meta, item_id, params, suffix, effect_quote)
        root_rows.append({
            "itemId": item_id, "reviewStatus": status, "rootApproval": "not_approved_candidate_only",
            "reasonCodes": reasons, "current": current,
            "proposed": {"category": decision.get("proposedCategory"),
                         "subcategory": decision.get("proposedSubcategory"),
                         "ironmanTabKey": decision.get("proposedIronmanTabKey")},
            "secondaryRolesAndTags": {"status": "unassessed",
                                      "currentTags": list(current.get("tags", [])),
                                      "reportedRolesUnassessed": list(decision.get("proposedRoles") or [])},
            "exactVariant": {"suffix": suffix, "nameField": name_key, "name": exact_name,
                             "versionField": version_key, "version": exact_version,
                             "examineField": examine_key, "examine": exact_examine,
                             "optionsField": option_key, "options": exact_options,
                             "exactEatOption": "eat" in exact_tokens},
            "source": {"title": title, "revision": int(meta["revid"]), "revisionTimestamp": meta.get("revisionTimestamp"),
                       "url": meta["sourceUrl"], "articleTextPath": meta["path"],
                       "articleTextHash": "sha256:" + meta["sha256"],
                       "rawPacketPath": meta.get("packetPath"),
                       "rawPacketHash": "sha256:" + meta.get("packetSha256", "")},
            "exactWikiCategories": sorted(categories), "literalEffectClause": compact(effect_quote),
            "readableEffectClause": effect_plain, "lead": compact(lead_literal)[:1000],
            "mechanicClusterId": cluster_key if included else None,
            "evidence": [evidence],
            "rationale": ("Exact ID variant has its own Eat option and a literal item-specific numeric healing/nourishment clause; current placement is POTION/food/potions-food, and no explicit separation signal matched. Candidate only for root review."
                          if included else "Separated from the positive-rule cohort because: " + ", ".join(reasons or ["no required explicit exclusion; item does not meet all inclusion facts"]) + "."),
        })

    args.output.mkdir(parents=True, exist_ok=False)
    packet_path = args.output / "food-positive-rule-candidates.jsonl"
    clusters_path = args.output / "lead-mechanic-clusters.json"
    with packet_path.open("x", encoding="utf-8", newline="\n") as stream:
        for row in sorted(root_rows, key=lambda item: item["itemId"]):
            stream.write(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n")
    with clusters_path.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump({"clusterCount": len(candidate_clusters),
                   "clusters": sorted(candidate_clusters.values(), key=lambda item: item["clusterId"])},
                  stream, ensure_ascii=False, indent=2)
        stream.write("\n")
    summary = {
        "schema": "ironman-bank-architect.supplies-food-positive-root-review.v6",
        "status": "candidate packet only; no root approval or policy decision",
        "directSourceCertifyRows": len(all_direct_certs),
        "candidateCounts": dict(counts),
        "clusterCount": len(candidate_clusters),
        "inputs": {"decisions": {"path": str(args.decisions), "sha256": sha256(args.decisions)},
                   "roleEvidence": {"path": str(args.role_evidence), "sha256": sha256(args.role_evidence)},
                   "packet": {"path": str(args.packet), "sha256": sha256(args.packet)},
                   "articleIndex": {"path": str(args.index), "sha256": sha256(args.index)}},
        "outputs": {"perIdPacket": {"path": str(packet_path), "sha256": sha256(packet_path), "rows": len(root_rows)},
                    "clusters": {"path": str(clusters_path), "sha256": sha256(clusters_path)}},
        "rules": ["Own exact variant options must include Eat.",
                  "Require a literal, subject-specific, numeric HP/health/energy effect in the pinned exact item article.",
                  "Only current POTION/food/potions-food rows can enter the candidate cohort.",
                  "Multi-bite, staged, quest, ingredient, activity-only, disguise, holiday, unpleasant, and container/interface cases are separately identified.",
                  "Exact source integrity and candidate inclusion do not constitute semantic approval."],
    }
    summary_path = args.output / "summary.json"
    with summary_path.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(summary, stream, ensure_ascii=False, indent=2)
        stream.write("\n")
    print(json.dumps({"directSourceCertifyRows": len(all_direct_certs),
                      "candidateCounts": dict(counts), "clusterCount": len(candidate_clusters),
                      "packetSha256": sha256(packet_path), "clusterSha256": sha256(clusters_path)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
