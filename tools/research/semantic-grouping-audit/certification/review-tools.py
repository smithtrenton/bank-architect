#!/usr/bin/env python3
"""Review TOOL and quest-associated CLEANUP rows against exact pinned Wiki pages."""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[4]
DEFAULT_COVERAGE = ROOT / "tmp/category-certification/current-coverage.tsv"
DEFAULT_INDEX = ROOT / "tmp/category-certification/wiki-articles/article-index.json"
DEFAULT_POLICY = Path(__file__).with_name("tools-policy.json")
DEFAULT_OUTPUT = ROOT / "tmp/category-certification/reviews"
SHARDS = {"tools": ("TOOL", None), "cleanup-quest": ("CLEANUP", "cleanup")}


def read_tsv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream, delimiter="\t"))


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def contains_any(text: str, phrases: list[str]) -> list[str]:
    folded = text.casefold()
    return [phrase for phrase in phrases if phrase.casefold() in folded]


def excerpt(text: str, phrase: str, limit: int, item_name: str = "") -> str:
    folded = text.casefold()
    start = folded.find(phrase.casefold())
    if start < 0:
        return ""
    anchor = text.casefold().find(("'''" + item_name + "'''" if item_name else "").casefold())
    if anchor < 0 and item_name:
        anchor = text.casefold().find(item_name.casefold())
    sentence_start = anchor if 0 <= anchor <= start else start
    left_candidates = [text.rfind("\n", 0, sentence_start), text.rfind(". ", 0, sentence_start), text.rfind("! ", 0, sentence_start), text.rfind("? ", 0, sentence_start)]
    left = max(left_candidates)
    left = 0 if left < 0 else left + (2 if text[left:left + 2] in {". ", "! ", "? "} else 1)
    right_candidates = [pos for pos in (text.find("\n", start), text.find(". ", start), text.find("! ", start), text.find("? ", start)) if pos >= 0]
    right = min(right_candidates) if right_candidates else len(text)
    quote = re.sub(r"\s+", " ", text[left:right]).strip()
    if len(quote) <= limit:
        return quote
    separators = [pos for pos in (text.rfind(", ", left, start), text.rfind("; ", left, start)) if pos >= 0]
    clause_left = max(separators) + 2 if separators else left
    clause_right_candidates = [pos for pos in (text.find(", ", start + len(phrase), right), text.find("; ", start + len(phrase), right)) if pos >= 0]
    clause_right = min(clause_right_candidates) if clause_right_candidates else right
    clause = re.sub(r"\s+", " ", text[clause_left:clause_right]).strip()
    if len(clause) <= limit and phrase.casefold() in clause.casefold():
        return clause
    # Preserve a literal source span when a sentence exceeds the preferred
    # quote length; synthetic ellipses would fail source-integrity verification.
    return re.sub(r"\s+", " ", text[left:right]).strip()


def item_claim_text(text: str, exact_params: dict[str, str], item_name: str) -> str:
    """Exact infobox facts plus lead sentences that explicitly name this item."""
    body = text.split("\n}}", 1)[1] if "\n}}" in text else ""
    body = re.sub(r"\[\[(?:File|Image):[^\]]+\]\]", "", body, flags=re.IGNORECASE)
    body = re.split(r"\n==", body, maxsplit=1)[0][:5000]
    name = item_name.strip().casefold()
    chunks = re.split(r"(?<=[.!?])\s+|\n+", body)
    prose = " ".join(chunk for chunk in chunks if name and name in chunk.casefold())
    ignored = {"name", "image", "id", "value", "weight"}
    params = "\n".join(f"{key} = {value}" for key, value in exact_params.items() if key not in ignored)
    return params + ("\n" + prose if prose else "")


def exact_article_map(index: dict[str, Any]) -> dict[int, list[tuple[str, dict[str, Any]]]]:
    reverse: dict[int, list[tuple[str, dict[str, Any]]]] = defaultdict(list)
    for title, record in index.items():
        for raw_id in record.get("exactInfoboxItemIds", []):
            if str(raw_id).isdigit():
                reverse[int(raw_id)].append((title, record))
    return reverse


def category_tab(category: str, policy: dict[str, Any]) -> str:
    explicit = policy.get("tabs", {}).get(category)
    if explicit:
        return explicit
    return {
        "TELEPORT": "currency-utilities", "GEAR": "combat-gear",
        "SKILLING": "resources", "RUNE": "currency-utilities",
        "CURRENCY": "currency-utilities", "FARMING": "seeds-farming",
    }.get(category, "storage-cleanup")


def in_shard(row: dict[str, str], shard: str) -> bool:
    category, excluded_subcategory = SHARDS[shard]
    return row["itemCategory"] == category and (
        excluded_subcategory is None or row["subcategory"] != excluded_subcategory
    )


def review_row(row: dict[str, str], shard: str, reverse: dict[int, list[tuple[str, dict[str, Any]]]],
               policy: dict[str, Any]) -> dict[str, Any]:
    item_id = int(row["itemId"])
    category = row["itemCategory"]
    subcategory = row["subcategory"]
    current_tab = row["ironmanTabKey"]
    current_tags = [tag for tag in row.get("tags", "").split(",") if tag]
    proposed = {
        "category": category,
        "subcategory": subcategory,
        "tab": current_tab,
        "roles": [],
        "tags": current_tags,
        "predicate": "",
    }
    evidence: list[dict[str, Any]] = []
    sources = reverse.get(item_id, [])
    reasons: list[str] = []
    source_text = ""
    exact_params: dict[str, str] = {}
    chosen: tuple[str, dict[str, Any]] | None = None

    if len(sources) == 1:
        title, record = sources[0]
        path = ROOT / Path(record["path"])
        chosen = (title, record)
        if path.is_file():
            source_text = path.read_text(encoding="utf-8")
        variant = record.get("variants", {}).get(str(item_id), {})
        exact_params = {str(k): str(v) for k, v in variant.get("params", {}).items()}
        exact_params_text = "\n".join(f"{k} = {v}" for k, v in exact_params.items())
        item_name = exact_params.get("name", title)
        evidence_text = item_claim_text(source_text, exact_params, item_name)
        evidence_source = record.get("sourceUrl", "")
        evidence_row = {
            "kind": "exact_wiki", "source": evidence_source,
            "sourceTitle": title,
            "sourceRevision": record.get("revid"),
            "sourceHash": "sha256:" + record.get("sha256", ""),
            "itemId": item_id,
        }

        support_by_subcategory = policy.get("supportCues", {}).get(category, {})
        support = contains_any(evidence_text, support_by_subcategory.get(subcategory, []))
        if category == "CLEANUP" and subcategory == "burnt-food":
            # Require the item's exact lead to explain that it results from
            # accidentally burning food; its name or examine alone is not proof.
            burnt_cues = support_by_subcategory.get(subcategory, [])
            support = contains_any(evidence_text, burnt_cues)
        if category == "CLEANUP" and subcategory == "quest-item":
            # A quest parameter is association only; require explicit prose that identifies this as a quest item.
            support = contains_any(evidence_text, ["quest item", "quest items"])

        curated = policy.get("curatedCorrections", {}).get(str(item_id))
        if curated:
            quotes = curated.get("quotes", [])
            if not quotes:
                cue = curated.get("cue", "")
                quote = excerpt(source_text, cue, int(policy["evidencePolicy"]["quoteLimit"])) if cue else ""
                quotes = [quote] if quote else []
            if quotes and all(quote in source_text for quote in quotes):
                proposed.update(
                    category=curated["category"],
                    subcategory=curated["subcategory"],
                    tab=curated["tab"],
                    roles=list(curated["roles"]),
                    tags=list(curated.get("tags", [])),
                    predicate=curated["reason"],
                )
                evidence.extend({**evidence_row, "quote": quote} for quote in quotes)
                for variant_case in curated.get("variantFacts", []):
                    facts = variant_case.get("facts", [])
                    if facts:
                        variant_evidence = {
                            **evidence_row,
                            "kind": "direct_variant",
                            "structuredFacts": facts,
                            "claim": variant_case.get("claim", "Exact infobox facts bind this item ID to its own variant."),
                        }
                        if variant_case.get("quote"):
                            variant_evidence["quote"] = variant_case["quote"]
                        evidence.append(variant_evidence)
                reasons.append(curated["reason"])
                support = []
            elif quotes:
                reasons.append("The curated exact-source excerpt did not match the acquired revision; decision remains unresolved.")

        tag_support = {
            tag: contains_any(evidence_text, policy.get("tagCues", {}).get(tag, []))
            for tag in current_tags
        }
        unsupported_tags = [tag for tag, matches in tag_support.items() if not matches]
        if support and unsupported_tags:
            reasons.append("The current auxiliary tag(s) lack direct exact-ID support: " + ", ".join(unsupported_tags) + ".")
            support = []
            evidence.clear()
            proposed["roles"] = []
            proposed["predicate"] = ""

        if support:
            cue = support[0]
            # Emit a literal span from the pinned page itself. `evidence_text` is a
            # convenient matching view that concatenates infobox fields and prose;
            # quotes from that synthetic view may not exist contiguously in source.
            quote = excerpt(source_text, cue, int(policy["evidencePolicy"]["quoteLimit"]), item_name)
            if quote:
                evidence_row["quote"] = quote
                evidence.append(evidence_row)
                if category == "CLEANUP" and subcategory == "burnt-food":
                    # Preserve a direct no-use statement when the exact page has
                    # one; burnt-state evidence alone never implies unusability.
                    if "no use whatsoever" in evidence_text.casefold():
                        no_use_quote = excerpt(source_text, "no use whatsoever", int(policy["evidencePolicy"]["quoteLimit"]), item_name)
                        if no_use_quote:
                            evidence.append({**evidence_row, "quote": no_use_quote})
                            proposed["roles"].append("explicit_no_documented_use")
                    if "some players collect them or resell them" in source_text.casefold():
                        collect_quote = excerpt(source_text, "some players collect them or resell them", int(policy["evidencePolicy"]["quoteLimit"]), item_name)
                        if collect_quote:
                            evidence.append({**evidence_row, "quote": collect_quote})
                            proposed["roles"].append("player_collectible_resalable")
                proposed["roles"].append({
                    "TOOL": "skilling_tool_or_utility",
                    "CLEANUP": {
                        "quest-item": "quest_item",
                        "burnt-food": "burnt_food_state",
                        "readable-lore": "readable_lore",
                    }.get(subcategory, "cleanup_review"),
                }[category])
                proposed["predicate"] = (
                    f"Exact Wiki item {item_id} has source wording supporting the {subcategory} role; "
                    f"the current {category} assignment and its bank-tab destination are appropriate."
                )
                if category == "CLEANUP" and subcategory == "burnt-food":
                    details = ["the exact item-named lead says it results from accidentally burning food"]
                    if "explicit_no_documented_use" in proposed["roles"]:
                        details.append("the page explicitly says it has no use whatsoever")
                    if "player_collectible_resalable" in proposed["roles"]:
                        details.append("the page also documents player collection and resale")
                    proposed["predicate"] = (
                        f"Exact item {item_id}: " + "; ".join(details) +
                        ". Retain the burnt-food classification and documented roles."
                    )
                reasons.append(f"Exact item {item_id} source wording directly supports {subcategory!r} (cue: {cue!r}).")
            else:
                support = []

        if not support and not curated and category == "CLEANUP" and subcategory == "quest-item":
            # Only exact infobox facts or lead sentences naming this item can expose another role.
            # Competing-role changes are curated per exact ID below; broad keyword routes are intentionally disabled.
            routes = {}
            for target_category, rule in routes.items():
                matched = contains_any(evidence_text, rule.get("cues", []))
                if matched:
                    proposed["category"] = target_category
                    proposed["subcategory"] = rule["subcategory"]
                    proposed["tab"] = category_tab(target_category, policy)
                    proposed["roles"] = ["quest_associated", {
                        "TELEPORT": "transport_access", "TOOL": "tool_or_skill_utility",
                        "GEAR": "combat_equipment", "SKILLING": "skilling_resource_or_material",
                    }[target_category]]
                    cue = matched[0]
                    quote = excerpt(evidence_text, cue, int(policy["evidencePolicy"]["quoteLimit"]))
                    if quote:
                        evidence_row["quote"] = quote
                        evidence.append(evidence_row)
                        reasons.append(
                            f"The exact quest-associated item page documents independent {target_category} use (cue: {cue!r}); "
                            "quest association does not explain that function."
                        )
                    else:
                        proposed.update(category=category, subcategory=subcategory, tab=current_tab, roles=[], predicate="")
                    break

    assignment_changed = (
        proposed["category"] != category
        or proposed["subcategory"] != subcategory
        or proposed["tab"] != current_tab
        or proposed["tags"] != current_tags
    )
    if evidence and assignment_changed:
        decision = "revise"
        if not proposed["predicate"]:
            proposed["predicate"] = (
                f"Exact item {item_id} has both a quest association and a separately documented "
                f"{proposed['category']} role; place it by that independent function."
            )
    elif evidence:
        decision = "certify"
    else:
        decision = "unresolved"
        if not sources:
            reasons.append("No acquired pinned item page has this exact numeric ID in its infobox; name or family evidence cannot substitute.")
        elif len(sources) > 1:
            reasons.append("More than one pinned page directly contains this exact ID; the page-to-variant semantics are ambiguous without typed identity/direct-variant evidence.")
        elif not source_text:
            reasons.append("The exact-ID article text file is missing from the acquired source index.")
        else:
            reasons.append(
                f"The pinned exact-ID source does not positively establish all of {category}/{subcategory}/{current_tab}; "
                "the current assignment and absent/false facets cannot certify it."
            )
        proposed["predicate"] = "Unresolved: exact source evidence is insufficient to certify or correct this row."

    if chosen:
        title, record = chosen
        # Preserve source identity in the rationale even when a rule did not find a supporting excerpt.
        reasons.insert(0, f"Reviewed exact page {title!r} (revision {record.get('revid')}).")
    return {
        "itemId": item_id,
        "shard": shard,
        "decision": decision,
        "reviewStatus": {"certify": "CERTIFIED", "revise": "CORRECTION", "unresolved": "UNRESOLVED"}[decision],
        "proposedCategory": proposed["category"],
        "proposedSubcategory": proposed["subcategory"],
        "proposedRoles": proposed["roles"],
        "proposedTags": proposed["tags"],
        "proposedIronmanTabKey": proposed["tab"],
        "semanticPredicate": proposed["predicate"],
        "rationale": " ".join(reasons),
        "evidence": evidence,
        "identityLinks": [],
        "reviewer": policy.get("reviewer", "tools-and-quest-cleanup"),
    }


def build(coverage_path: Path, index_path: Path, policy_path: Path, output_root: Path,
          shards: list[str]) -> None:
    rows = read_tsv(coverage_path)
    index = json.loads(index_path.read_text(encoding="utf-8"))
    policy = json.loads(policy_path.read_text(encoding="utf-8"))
    reverse = exact_article_map(index)
    for shard in shards:
        owned = [row for row in rows if in_shard(row, shard)]
        reviewed = [review_row(row, shard, reverse, policy) for row in owned]
        output_dir = output_root / shard
        output_dir.mkdir(parents=True, exist_ok=True)
        decisions_path = output_dir / "decisions.jsonl"
        with decisions_path.open("w", encoding="utf-8", newline="\n") as stream:
            for item in reviewed:
                stream.write(json.dumps(item, ensure_ascii=False, sort_keys=True) + "\n")
        counts = Counter(row["decision"] for row in reviewed)
        summary = {
            "shard": shard,
            "rowCount": len(reviewed),
            "decisions": dict(sorted(counts.items())),
            "uniqueExactArticleCount": sum(len(reverse.get(int(row["itemId"]), [])) == 1 for row in owned),
            "noExactArticleCount": sum(not reverse.get(int(row["itemId"])) for row in owned),
            "multipleExactPagesCount": sum(len(reverse.get(int(row["itemId"]), [])) > 1 for row in owned),
            "coverageSha256": sha256(coverage_path),
            "articleIndexSha256": sha256(index_path),
            "policySha256": sha256(policy_path),
            "decisionsSha256": sha256(decisions_path),
            "limitations": [
                "This is a conservative policy-driven review; unresolved means the pinned exact source does not positively support the full assignment.",
                "Direct variant prose is not propagated from another ID. Typed identity relationships remain a separate evidence requirement.",
                "An item quest parameter establishes association only. It is not evidence that the item is quest-only or lacks another role.",
            ],
        }
        (output_dir / "summary.json").write_text(
            json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        print(f"{shard}: {len(reviewed)} rows; {dict(counts)} -> {output_dir}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--coverage", type=Path, default=DEFAULT_COVERAGE)
    parser.add_argument("--index", type=Path, default=DEFAULT_INDEX)
    parser.add_argument("--policy", type=Path, default=DEFAULT_POLICY)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--shard", choices=sorted(SHARDS), action="append")
    args = parser.parse_args()
    build(args.coverage, args.index, args.policy, args.output, args.shard or list(SHARDS))


if __name__ == "__main__":
    main()
