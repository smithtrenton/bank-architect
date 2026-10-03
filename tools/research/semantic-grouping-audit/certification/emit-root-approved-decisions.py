#!/usr/bin/env python3
"""Emit exact-ID decisions from the six pinned root-approved policy files.

This is a read-only certification artifact builder. It does not read candidate
review outputs and never changes plugin sources or the frozen reviewer packets.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import importlib.util
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[4]
CERT = ROOT / "tools/research/semantic-grouping-audit/certification"
BASE = ROOT / "tmp/category-certification"
PACKET_DIR = BASE / "reviewer-packets"
ARTICLE_INDEX = BASE / "wiki-articles/article-index.json"
POLICY_NAMES = (
    "cleanup-other-policy.json",
    "materials-approved-policy.json",
    "gear-approved-policy.json",
    "utility-approved-policy.json",
    "cleanup-gear-approved-policy.json",
    "gear-slot-approved-policy.json",
)
DEFAULT_OUTPUT = BASE / "root-approved-decisions.jsonl"
CLUE_RULE = CERT / "clue-scroll-approved-rule.json"

# These are the standard category-to-tab routes in the current preset mapper.
# IDs with dedicated routes are listed explicitly below, so targets are derived
# from the approved category semantics and mapper rules, never from after-coverage.
STANDARD_TABS = {
    "CLEANUP": "storage-cleanup",
    "CLUE": "clues-cosmetics",
    "CURRENCY": "currency-utilities",
    "FARMING": "seeds-farming",
    "GEAR": "combat-gear",
    "HERBLORE": "herblore",
    "POTION": "potions-food",
    "RUNE": "currency-utilities",
    "SKILLING": "resources",
    "TELEPORT": "currency-utilities",
    "TOOL": "skilling-tools",
    "UNIQUE": "slayer-boss-loot",
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def normalized(value: Any) -> str:
    return " ".join(str(value).split())


def load_packets() -> dict[int, dict[str, Any]]:
    packets: dict[int, dict[str, Any]] = {}
    for path in sorted(PACKET_DIR.glob("*.jsonl")):
        if path.name.startswith("decisions-"):
            continue
        for line_number, line in enumerate(path.read_text(encoding="utf-8-sig").splitlines(), 1):
            if not line.strip():
                continue
            record = json.loads(line)
            item_id = int(record["itemId"])
            if item_id in packets:
                raise ValueError(f"Duplicate frozen packet ID {item_id} ({path}:{line_number})")
            packets[item_id] = record
    if len(packets) != 34085:
        raise ValueError(f"Expected 34,085 frozen packet IDs, found {len(packets)}")
    coverage_path = BASE / "current-coverage.tsv"
    with coverage_path.open(encoding="utf-8-sig", newline="") as stream:
        coverage_ids = {int(row["itemId"]) for row in csv.DictReader(stream, delimiter="\t")}
    if set(packets) != coverage_ids:
        raise ValueError("Frozen reviewer packet IDs do not exactly match frozen current-coverage.tsv")
    return packets


def load_policy_cases() -> tuple[dict[int, tuple[dict[str, Any], str]], dict[str, str]]:
    cases: dict[int, tuple[dict[str, Any], str]] = {}
    hashes: dict[str, str] = {}
    for name in POLICY_NAMES:
        path = CERT / name
        hashes[name] = sha256(path)
        policy = json.loads(path.read_text(encoding="utf-8-sig"))
        for case in policy["cases"]:
            item_id = int(case["itemId"])
            if item_id in cases:
                prior = cases[item_id][1]
                raise ValueError(f"Root policy ID {item_id} overlaps {prior} and {name}")
            cases[item_id] = (case, name)
    if len(cases) != 230:
        raise ValueError(f"Expected exactly 230 disjoint approved cases, found {len(cases)}")
    return cases, hashes


def load_article_sources() -> dict[str, dict[str, Any]]:
    index = json.loads(ARTICLE_INDEX.read_text(encoding="utf-8-sig"))
    for title, source in index.items():
        raw_path = str(source.get("path", "")).replace("\\", "/")
        text_path = ROOT / raw_path
        if not text_path.is_file() or sha256(text_path) != source.get("sha256"):
            raise ValueError(f"Pinned article text missing or changed: {title} ({raw_path})")
    return index


def citation(source_title: str, source: dict[str, Any], item_id: int,
             quote: str = "", facts: list[dict[str, str]] | None = None) -> dict[str, Any]:
    return {
        "kind": "exact_wiki",
        "sourceTitle": source_title,
        "source": source["sourceUrl"],
        "sourceRevision": source["revid"],
        "sourceHash": source["sha256"],
        "itemId": item_id,
        "quote": quote,
        **({"structuredFacts": facts} if facts else {}),
    }


def verify_quote(source: dict[str, Any], item_id: int, quote: str, label: str) -> str:
    if not isinstance(quote, str) or not quote.strip():
        raise ValueError(f"item {item_id}: {label} must be a non-empty literal excerpt")
    text_path = ROOT / str(source["path"]).replace("\\", "/")
    text = normalized(text_path.read_text(encoding="utf-8", errors="replace"))
    if normalized(quote) not in text:
        raise ValueError(f"item {item_id}: {label} is not literal text in pinned {source['title']} revision {source['revid']}")
    return quote


def exact_facts(case: dict[str, Any], source: dict[str, Any], item_id: int) -> list[dict[str, str]]:
    facts = case.get("exactVariantFacts", [])
    if not facts:
        return []
    if str(item_id) not in source.get("variants", {}):
        raise ValueError(f"item {item_id}: no exact variant in {source['title']}")
    variant = source["variants"][str(item_id)]
    params = variant.get("params", {})
    suffix = str(variant.get("suffix", ""))
    checked: list[dict[str, str]] = []
    for fact in facts:
        field = str(fact["field"])
        value = str(fact["value"])
        raw_field = field
        if raw_field not in params or str(params.get(raw_field)) != value:
            if suffix and field + suffix in params:
                raw_field = field + suffix
        if raw_field not in params or str(params[raw_field]) != value:
            raise ValueError(f"item {item_id}: policy fact {field}={value!r} does not match exact raw field {raw_field!r}")
        checked.append({"field": raw_field, "value": value})
    return checked


def tab_for(category: str, subcategory: str, item_id: int) -> str:
    # Keep item-specific routes from PresetCategoryMapper explicit and fail closed.
    if item_id in {7936, 24704, 32083, 32085}:
        return "resources"
    if item_id in {5509, 5510, 5511, 5512, 5513, 5514, 5515, 26784, 26786, 5521, 19634, 13392, 25781}:
        return "skilling-tools"
    if item_id == 1201:
        return "slayer-boss-loot"
    if item_id in {762, 1588}:
        return "storage-cleanup"
    if category not in STANDARD_TABS:
        raise ValueError(f"item {item_id}: no preset tab route for category {category!r}")
    # Seed-like Farming subcategories share the normal seeds-farming tab.
    return STANDARD_TABS[category]


def make_actionable(case: dict[str, Any], policy_name: str, policy_hash: str,
                    packet: dict[str, Any], source_index: dict[str, dict[str, Any]],
                    article_index_hash: str) -> dict[str, Any]:
    item_id = int(case["itemId"])
    title = str(case["title"])
    source = source_index.get(title)
    if source is None:
        raise ValueError(f"item {item_id}: exact policy title {title!r} is absent from article index")
    if int(case["sourceRevision"]) != int(source["revid"]):
        raise ValueError(f"item {item_id}: policy revision differs from pinned article index")
    if case["sourceSha256"].lower() != str(source["sha256"]).lower():
        raise ValueError(f"item {item_id}: policy source hash differs from pinned article index")
    exact_ids = {int(value) for value in source.get("exactInfoboxItemIds", [])}
    if item_id not in exact_ids or str(item_id) not in source.get("variants", {}):
        raise ValueError(f"item {item_id}: title does not contain an exact pinned Infobox Item variant")

    excerpt = verify_quote(source, item_id, case.get("semanticExcerpt", ""), "semanticExcerpt")
    evidence = [citation(title, source, item_id, excerpt)]
    secondary = case.get("secondaryExcerpts", [])
    if isinstance(secondary, dict):
        secondary = list(secondary.values())
    secondary_quotes: list[str] = []
    for index, secondary_quote in enumerate(secondary):
        if isinstance(secondary_quote, dict):
            secondary_quote = secondary_quote.get("quote", secondary_quote.get("excerpt", ""))
        quote = verify_quote(source, item_id, secondary_quote, f"secondaryExcerpts[{index}]")
        secondary_quotes.append(quote)
        evidence.append(citation(title, source, item_id, quote))

    tag_evidence = case.get("tagEvidence", {}) or {}
    if not isinstance(tag_evidence, dict):
        raise ValueError(f"item {item_id}: tagEvidence must be a mapping")
    for tag, quote in sorted(tag_evidence.items()):
        quote = verify_quote(source, item_id, quote, f"tagEvidence[{tag}]")
        evidence.append(citation(title, source, item_id, quote))

    facts = exact_facts(case, source, item_id)
    if facts:
        evidence.append(citation(title, source, item_id, facts=facts))

    current = packet["current"]
    category = str(case["proposedCategory"])
    subcategory = str(case["proposedSubcategory"])
    roles = case.get("addedRoles")
    if roles is None:
        roles = []
    if not isinstance(roles, list) or any(not isinstance(role, str) for role in roles):
        raise ValueError(f"item {item_id}: addedRoles must be a list of supplemental claims")
    tags = set(current["tags"])
    tags.update(case.get("proposedTags", []))
    tags.update(roles)
    proposed_tags = sorted(tags)
    tab = tab_for(category, subcategory, item_id)
    changed = (category != current["category"] or subcategory != current["subcategory"] or
               proposed_tags != sorted(current["tags"]) or tab != current["ironmanTabKey"])
    decision = "revise" if changed else "certify"
    rationale = str(case.get("rationale") or normalized(excerpt))
    predicate = f"Exact-ID evidence: {normalized(excerpt)}"
    return {
        "itemId": item_id,
        "shard": packet["shard"],
        "decision": decision,
        "proposedCategory": category,
        "proposedSubcategory": subcategory,
        "proposedTags": proposed_tags,
        "proposedRoles": roles if roles else None,
        "roleClaimScope": "supplemental_only" if roles else "unassessed",
        "proposedIronmanTabKey": tab,
        "semanticPredicate": predicate,
        "rationale": rationale,
        "evidence": evidence,
        "identityLinks": [],
        "reviewer": "root-approved-policy-emitter",
        "rootApproval": {
            "policyFile": policy_name,
            "policySha256": policy_hash,
            "policySourceTitle": title,
            "policySourceRevision": int(case["sourceRevision"]),
            "policySourceSha256": case["sourceSha256"],
            "articleIndexSha256": article_index_hash,
            "secondaryExcerpts": secondary_quotes,
            "exactVariantFacts": facts,
            "tagEvidence": tag_evidence,
        },
    }


def load_root_certifications(path: Path, packets: dict[int, dict[str, Any]],
                             already_approved: set[int], article_index_hash: str) -> tuple[dict[int, dict[str, Any]], str, str]:
    rule = json.loads(CLUE_RULE.read_text(encoding="utf-8-sig"))
    rule_hash = sha256(CLUE_RULE)
    if rule.get("articleIndexSha256") != article_index_hash:
        raise ValueError("clue-scroll rule does not pin the current article index")
    if rule.get("schema") != 1 or rule.get("status") != "root-reviewed rule for primary assignment only":
        raise ValueError("clue-scroll rule has an unexpected schema or approval status")
    approved_ids = {int(item_id) for item_id in rule.get("approvedItemIds", [])}
    clue_packet = PACKET_DIR / "clue-unique.jsonl"
    if not clue_packet.is_file() or sha256(clue_packet) != rule.get("packetSha256"):
        raise ValueError("clue-scroll rule does not pin the current immutable clue-unique packet")
    # Recompute the approved positive rule from raw pinned pages. A literal
    # citation from the right item page is insufficient if it does not support
    # this exact predicate, selected state, or primary-role claim.
    rule_script = CERT / "review-approved-clue-scrolls.py"
    spec = importlib.util.spec_from_file_location("root_clue_scroll_rule", rule_script)
    if spec is None or spec.loader is None:
        raise ValueError("Cannot load the root-approved clue rule verifier")
    verifier = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(verifier)
    expected_rows, selected_ids, _ = verifier.candidates()
    if set(selected_ids) != approved_ids:
        raise ValueError("Recomputed raw clue predicate differs from the approved exact ID set")
    expected_by_id = {row["itemId"]: row for row in expected_rows if row["decision"] == "certify"}
    proof_fields = ("itemId", "shard", "decision", "proposedCategory", "proposedSubcategory",
                    "proposedTags", "proposedRoles", "roleClaimScope", "semanticPredicate",
                    "rationale", "evidence", "identityLinks")
    merged: dict[int, dict[str, Any]] = {}
    for line_number, line in enumerate(path.read_text(encoding="utf-8-sig").splitlines(), 1):
        if not line.strip():
            continue
        row = json.loads(line)
        item_id = int(row["itemId"])
        if row.get("decision") == "unresolved" and item_id not in approved_ids:
            continue
        if item_id in merged or item_id in already_approved:
            raise ValueError(f"Optional certification overlaps another root policy at ID {item_id}")
        if item_id not in approved_ids or item_id not in packets or row.get("decision") != "certify":
            raise ValueError(f"Certification row {line_number} is not a root-rule-approved exact-ID certify decision")
        if (row.get("proposedCategory"), row.get("proposedSubcategory"), row.get("proposedIronmanTabKey")) != (
                "CLUE", "treasure-trail", "clues-cosmetics"):
            raise ValueError(f"Clue certification {item_id} differs from the root-approved primary target")
        expected = expected_by_id[item_id]
        if any(row.get(field) != expected.get(field) for field in proof_fields):
            raise ValueError(f"Clue certification {item_id} differs from the recomputed root-approved raw predicate proof")
        evidence = row.get("evidence", [])
        if not evidence or any(e.get("kind") not in {"exact_wiki", "direct_variant"} for e in evidence):
            raise ValueError(f"Clue certification {item_id} lacks direct exact Wiki evidence")
        # This rule approves only primary assignment. Retain packet tags without
        # claiming the rule independently re-proved them or inferring extra roles.
        row["proposedTags"] = list(packets[item_id]["current"]["tags"])
        if row.get("proposedRoles") != ["treasure_trail_step"]:
            raise ValueError(f"Clue certification {item_id} does not carry the exact root-reviewed primary role")
        row["shard"] = packets[item_id]["shard"]
        row["reviewer"] = "root-approved-clue-scroll-rule"
        row["rootApproval"] = {
            "policyFile": (str(path.relative_to(ROOT)) if path.is_relative_to(ROOT) else str(path)).replace("\\", "/"),
            "policySha256": sha256(path),
            "ruleFile": str(CLUE_RULE.relative_to(ROOT)).replace("\\", "/"),
            "ruleSha256": rule_hash,
            "articleIndexSha256": article_index_hash,
            "approvalScope": "primary category, subcategory, and tab only; packet tags retained without new tag claims",
        }
        merged[item_id] = row
    if len(merged) != len(approved_ids):
        raise ValueError(f"Certification file must contain every approved rule ID: expected {len(approved_ids)}, found {len(merged)}")
    return merged, rule_hash, sha256(path)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--manifest", type=Path)
    parser.add_argument("--summary-tsv", type=Path)
    parser.add_argument("--certifications", type=Path,
                        help="optional root-approved exact-ID certification JSONL with a pinned rule")
    args = parser.parse_args()
    if args.manifest is None:
        args.manifest = args.output.with_name(args.output.stem + "-manifest.json")
    if args.summary_tsv is None:
        args.summary_tsv = args.output.with_suffix(".tsv")

    packets = load_packets()
    cases, policy_hashes = load_policy_cases()
    article_index = load_article_sources()
    article_index_hash = sha256(ARTICLE_INDEX)
    optional_certifications: dict[int, dict[str, Any]] = {}
    certification_hashes: dict[str, str] = {}
    if args.certifications:
        optional_certifications, rule_hash, decisions_hash = load_root_certifications(
            args.certifications, packets, set(cases), article_index_hash)
        certification_hashes = {
            "rule": rule_hash,
            "decisions": decisions_hash,
        }
    output_rows: list[dict[str, Any]] = []
    for item_id in sorted(packets):
        packet = packets[item_id]
        if item_id in cases:
            case, policy_name = cases[item_id]
            output_rows.append(make_actionable(case, policy_name, policy_hashes[policy_name],
                                               packet, article_index, article_index_hash))
        elif item_id in optional_certifications:
            output_rows.append(optional_certifications[item_id])
        else:
            current = packet["current"]
            output_rows.append({
                "itemId": item_id,
                "shard": packet["shard"],
                "decision": "unresolved",
                "proposedCategory": current["category"],
                "proposedSubcategory": current["subcategory"],
                "proposedTags": [],
                "proposedRoles": None,
                "roleClaimScope": "unassessed",
                "proposedIronmanTabKey": current["ironmanTabKey"],
                "semanticPredicate": "No root-approved semantic predicate is recorded for this exact ID.",
                "rationale": "No case in the pinned root-approved policy set addresses this exact ID; category certification remains unresolved.",
                "evidence": [],
                "identityLinks": [],
                "reviewer": "root-approved-policy-emitter",
            })

    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8", newline="\n") as stream:
        for row in output_rows:
            stream.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
    args.summary_tsv.parent.mkdir(parents=True, exist_ok=True)
    with args.summary_tsv.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.writer(stream, delimiter="\t", lineterminator="\n")
        writer.writerow(["itemId", "ownerShard", "decision", "proposedCategory", "proposedSubcategory",
                         "proposedIronmanTabKey", "sourceRevisions"])
        for row in output_rows:
            revisions = sorted({str(e.get("sourceRevision")) for e in row.get("evidence", [])
                                if e.get("sourceRevision")})
            writer.writerow([row["itemId"], row["shard"], row["decision"],
                             row.get("proposedCategory", ""), row.get("proposedSubcategory", ""),
                             row.get("proposedIronmanTabKey", ""), ",".join(revisions) or "-"])
    packet_hashes = {str(path.relative_to(ROOT)).replace("\\", "/"): sha256(path)
                     for path in sorted(PACKET_DIR.glob("*.jsonl")) if not path.name.startswith("decisions-")}
    coverage_path = BASE / "current-coverage.tsv"
    manifest = {
        "schema": "root-approved-category-decisions/v1",
        "policyCaseCount": len(cases),
        "optionalRootCertificationCount": len(optional_certifications),
        "decisionRows": len(output_rows),
        "actionableRows": sum(row["decision"] in {"certify", "revise", "exclude"} for row in output_rows),
        "unresolvedRows": sum(row["decision"] == "unresolved" for row in output_rows),
        "actionCounts": dict(sorted(Counter(row["decision"] for row in output_rows).items())),
        "replayScriptHashes": {name: sha256(CERT / name) for name in
                               ("emit-root-approved-decisions.py", "review-approved-clue-scrolls.py", "ledger.py")},
        "sourceHashes": {
            "policies": policy_hashes,
            "optionalCertifications": certification_hashes,
            "articleIndex": sha256(ARTICLE_INDEX),
            "frozenCoverage": sha256(coverage_path),
            "frozenPackets": packet_hashes,
        },
        "output": (str(args.output.relative_to(ROOT)) if args.output.is_relative_to(ROOT) else str(args.output)).replace("\\", "/"),
        "outputSha256": sha256(args.output),
        "summaryTsv": (str(args.summary_tsv.relative_to(ROOT)) if args.summary_tsv.is_relative_to(ROOT) else str(args.summary_tsv)).replace("\\", "/"),
        "summaryTsvSha256": sha256(args.summary_tsv),
        "tabPolicy": "Standard target tabs are computed from the approved target category using the current preset mapper's category routes, plus explicit ID routes listed in this emitter. after-coverage is never read by the emitter.",
    }
    args.manifest.parent.mkdir(parents=True, exist_ok=True)
    args.manifest.write_text(json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"Wrote {len(output_rows)} exact-ID decisions ({manifest['actionableRows']} actionable; {manifest['unresolvedRows']} unresolved)")
    print(f"Decisions: {args.output}")
    print(f"Manifest: {args.manifest}")


if __name__ == "__main__":
    main()
