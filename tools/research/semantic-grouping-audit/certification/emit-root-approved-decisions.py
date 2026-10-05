#!/usr/bin/env python3
"""Emit exact-ID decisions from the pinned root-approved policy files.

This read-only builder verifies pinned candidate evidence without accepting
candidate decisions as approvals. It never changes plugin sources or the frozen
reviewer packets; approvals come from the separate root policy pins.
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
PACKET_NAMES = tuple(name + '.jsonl' for name in (
    'gear', 'skilling-farming', 'supplies-herblore', 'tools', 'clue-unique',
    'currency-runes-teleport', 'cleanup-quest', 'cleanup-other'))
POLICY_NAMES = (
    "cleanup-other-policy.json",
    "materials-approved-policy.json",
    "gear-approved-policy.json",
    "utility-approved-policy.json",
    "cleanup-gear-approved-policy.json",
    "gear-slot-approved-policy.json",
    "gear-primary-approved-policy.json",
    "food-primary-approved-policy.json",
    "raw-food-primary-approved-policy.json",
    "teleport-primary-approved-policy.json",
    "rune-primary-approved-policy.json",
    "tool-subcategory-approved-policy.json",
    "tool-primary-approved-policy.json",
    "farming-primary-approved-policy.json",
    "farming-supplemental-approved-policy.json",
    "prayer-bone-subcategory-approved-policy.json",
    "clue-residual44-primary-approved-policy.json",
    "clue-cosmetic-primary-approved-policy.json",
    "clue-cosmetic-corrections-approved-policy.json",
    "cooking-stage-primary-approved-policy.json",
    "cooking-stage-corrections-approved-policy.json",
    "potion-primary-approved-policy.json",
    "potion-corrections-approved-policy.json",
    "materials-v15-primary-approved-policy.json",
    "materials-v15-corrections-approved-policy.json",
    "materials-v15-g101-340-primary-approved-policy.json",
    "materials-v15-g101-340-corrections-approved-policy.json",
    "materials-v15-g341-493-corrections-approved-policy.json",
    "gear-primary-through246-same-approved-policy.json",
    "gear-primary-through246-corrections-approved-policy.json",
    "gear-primary-next157-same-approved-policy.json",
    "gear-primary-next157-corrections-approved-policy.json",
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
    for path in sorted(PACKET_DIR / name for name in PACKET_NAMES):
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
    approval_record = json.loads((CERT / "root-policy-approvals.json").read_text(encoding="utf-8-sig"))
    if approval_record.get("schema") != 1 or approval_record.get("status") != "root-reviewed exact policy pins":
        raise ValueError("Invalid detached root-policy approval record")
    approved_policies = approval_record["approvedPolicies"]
    if set(approved_policies) != set(POLICY_NAMES):
        raise ValueError("Approval record does not exactly name the whitelisted root policies")
    for name in POLICY_NAMES:
        path = CERT / name
        hashes[name] = sha256(path)
        policy = json.loads(path.read_text(encoding="utf-8-sig"))
        approved = approved_policies[name]
        if hashes[name] != approved["sha256"]:
            raise ValueError(f"Root policy bytes differ from the separate approval pin: {name}")
        canonical = hashlib.sha256(json.dumps(policy, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
        if canonical != approved["canonicalSha256"] or sorted(case["itemId"] for case in policy["cases"]) != approved["approvedItemIds"] or len(policy["cases"]) != approved["caseCount"]:
            raise ValueError(f"Root policy contents or exact ID set differ from the separate approval pin: {name}")
        primary_verifiers = {
            "gear-primary-through246-same-approved-policy.json": ("verify-gear-primary-through246-policy.py", 115),
            "gear-primary-through246-corrections-approved-policy.json": ("verify-gear-primary-through246-policy.py", 110),
            "gear-primary-next157-same-approved-policy.json": ("verify-gear-primary-next157-policy.py", 88),
            "gear-primary-next157-corrections-approved-policy.json": ("verify-gear-primary-next157-policy.py", 69),
            "gear-primary-approved-policy.json": ("verify-gear-primary-policy.py", 939),
            "food-primary-approved-policy.json": ("verify-food-primary-policy.py", 40),
            "teleport-primary-approved-policy.json": ("verify-teleport-primary-policy.py", 72),
            "rune-primary-approved-policy.json": ("verify-rune-primary-policy.py", 23),
            "tool-primary-approved-policy.json": ("verify-tool-primary-policy.py", 151),
            "farming-primary-approved-policy.json": ("verify-farming-primary-policy.py", 51),
            "farming-supplemental-approved-policy.json": ("verify-farming-supplemental-policy.py", 66),
            "clue-residual44-primary-approved-policy.json": ("verify-cosmetic-cooking-policies.py", 44),
            "clue-cosmetic-primary-approved-policy.json": ("verify-cosmetic-cooking-policies.py", 230),
            "clue-cosmetic-corrections-approved-policy.json": ("verify-cosmetic-cooking-policies.py", 10),
            "cooking-stage-primary-approved-policy.json": ("verify-cosmetic-cooking-policies.py", 4),
            "cooking-stage-corrections-approved-policy.json": ("verify-cosmetic-cooking-policies.py", 5),
            "potion-primary-approved-policy.json": ("verify-potion-primary-policies.py", 347),
            "potion-corrections-approved-policy.json": ("verify-potion-primary-policies.py", 40),
            "materials-v15-primary-approved-policy.json": ("verify-materials-v15-first100.py", 7),
            "materials-v15-corrections-approved-policy.json": ("verify-materials-v15-first100.py", 75),
            "materials-v15-g101-340-primary-approved-policy.json": ("verify-materials-v15-g101-340.py", 37),
            "materials-v15-g101-340-corrections-approved-policy.json": ("verify-materials-v15-g101-340.py", 152),
            "materials-v15-g341-493-corrections-approved-policy.json": ("verify-materials-v15-g341-493.py", 255),
        }
        if name in primary_verifiers:
            script, expected_count = primary_verifiers[name]
            spec = importlib.util.spec_from_file_location("root_primary_verifier", CERT / script)
            if spec is None or spec.loader is None:
                raise ValueError("Cannot load the approved primary provenance verifier: " + script)
            verifier = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(verifier)
            if name in {"gear-primary-through246-same-approved-policy.json", "gear-primary-through246-corrections-approved-policy.json", "gear-primary-next157-same-approved-policy.json", "gear-primary-next157-corrections-approved-policy.json"}:
                verifier.verify_policy(policy, expected_policy_name=name)
            else:
                verifier.verify_policy(policy)
            if len(policy["cases"]) != expected_count:
                raise ValueError(f"Expected exactly {expected_count} approved cases in {name}")
        if name == "raw-food-primary-approved-policy.json":
            raw_inputs = {
                "articleIndex": ARTICLE_INDEX,
                "materialsPacket": PACKET_DIR / "skilling-farming.jsonl",
                "rawFishReview": BASE / "reviews/materials-positive-cohorts/20261003-raw-fish-cooking-inputs/root-review-packet.json",
            }
            if any(sha256(path) != policy["sourceHashes"][key] for key, path in raw_inputs.items()):
                raise ValueError("Raw-food frozen review inputs changed")
            raw_review = json.loads(raw_inputs["rawFishReview"].read_text(encoding="utf-8-sig"))
            if (policy.get("status") != "root-reviewed primary assignments only" or
                    (len(policy["cases"]) != 21 or policy.get("expectedCaseCount") != 21) or
                    {case["itemId"] for case in policy["cases"]} != {row["itemId"] for row in raw_review["included"]}):
                raise ValueError("Raw-food approved exact review cohort changed")
        for case in policy["cases"]:
            item_id = int(case["itemId"])
            if item_id in cases:
                prior = cases[item_id][1]
                raise ValueError(f"Root policy ID {item_id} overlaps {prior} and {name}")
            cases[item_id] = (case, name)
    if len(cases) != 3203:
        raise ValueError(f"Expected exactly 3,203 disjoint approved policy cases, found {len(cases)}")
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
    # Exact mapper-qualified achievement rewards stay on the default gather tab.
    if category == "GEAR" and item_id in {11136, 13103, 13113, 13118, 13123, 13125, 13128, 13129, 13132}:
        return "currency-utilities"
    if item_id in {7936, 24704, 32083, 32085}:
        return "resources"
    if item_id in {5509, 5510, 5511, 5512, 5513, 5514, 5515, 26784, 26786, 5521, 19634, 13392, 25781}:
        return "skilling-tools"
    if item_id in {762, 1588}:
        return "storage-cleanup"
    if category not in STANDARD_TABS:
        raise ValueError(f"item {item_id}: no preset tab route for category {category!r}")
    if item_id in {952, 1755}:
        return "currency-utilities"
    if category == "FARMING" and subcategory == "herb-seed":
        return "herblore"
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
    if policy_name == "raw-food-primary-approved-policy.json":
        raw = (ROOT / source["path"]).read_text(encoding="utf-8")
        subject = re.search(r"[']{3}([^\n]*?)[']{3}", raw)
        if subject is None or excerpt != raw[subject.start():].split("\n\n", 1)[0].strip():
            raise ValueError(f"item {item_id}: raw-food evidence must be the full literal own-subject lead")
        cooking = case.get("secondaryExcerpts", [])
        if not cooking or any(not re.search(r"cook", quote, re.I) for quote in cooking):
            raise ValueError(f"item {item_id}: missing direct literal Cooking-input clause")
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

    direct_function_policies = {
        "clue-residual44-primary-approved-policy.json", "clue-cosmetic-primary-approved-policy.json",
        "clue-cosmetic-corrections-approved-policy.json", "cooking-stage-primary-approved-policy.json",
        "cooking-stage-corrections-approved-policy.json",
        "potion-primary-approved-policy.json", "potion-corrections-approved-policy.json",
        "materials-v15-primary-approved-policy.json", "materials-v15-corrections-approved-policy.json",
        "materials-v15-g101-340-primary-approved-policy.json", "materials-v15-g101-340-corrections-approved-policy.json",
        "materials-v15-g341-493-corrections-approved-policy.json",
    }
    positive_quote = None
    if policy_name in direct_function_policies:
        positive_quote = verify_quote(source, item_id, case["positiveFunctionExcerpt"], "positiveFunctionExcerpt")
        if positive_quote not in [excerpt] + secondary_quotes:
            evidence.append(citation(title, source, item_id, positive_quote))

    if case.get("contextEvidence"):
        if policy_name != "materials-v15-g341-493-corrections-approved-policy.json" or item_id != 30975:
            raise ValueError("Unexpected generic ritual context")
        # The pinned policy verifier checks these literal generic passages.
        # They provide ritual context, without an Alan-specific XP claim.
        evidence.extend(case["contextEvidence"])

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
    if policy_name in {"potion-primary-approved-policy.json", "potion-corrections-approved-policy.json"}:
        # The provenance verifier independently recomputes this from the exact
        # sort/dose-family metadata; targets are never copied from after-coverage.
        tab = case["proposedIronmanTabKey"]
    changed = (category != current["category"] or subcategory != current["subcategory"] or
               proposed_tags != sorted(current["tags"]) or tab != current["ironmanTabKey"])
    decision = "revise" if changed else "certify"
    primary_only = policy_name in {"gear-primary-approved-policy.json", "gear-primary-through246-same-approved-policy.json", "gear-primary-next157-same-approved-policy.json", "food-primary-approved-policy.json", "raw-food-primary-approved-policy.json", "teleport-primary-approved-policy.json", "rune-primary-approved-policy.json", "tool-primary-approved-policy.json", "farming-primary-approved-policy.json", "farming-supplemental-approved-policy.json", "clue-residual44-primary-approved-policy.json", "clue-cosmetic-primary-approved-policy.json", "cooking-stage-primary-approved-policy.json"}
    expected = "certify" if primary_only else "revise"
    if policy_name in {"potion-primary-approved-policy.json", "materials-v15-primary-approved-policy.json", "materials-v15-g101-340-primary-approved-policy.json"}:
        expected = "certify"
    primary_scope_only = primary_only or policy_name in direct_function_policies or policy_name in {"gear-primary-through246-same-approved-policy.json", "gear-primary-through246-corrections-approved-policy.json", "gear-primary-next157-same-approved-policy.json", "gear-primary-next157-corrections-approved-policy.json"}
    if primary_scope_only and (roles or case.get("proposedTags") or tag_evidence):
        raise ValueError(f"item {item_id}: primary-only policy cannot add tag or supplemental-role claims")
    if decision != expected:
        raise ValueError(f"item {item_id}: {policy_name} produced {decision}, expected {expected}")
    rationale = str(case.get("rationale") or normalized(excerpt))
    predicate_excerpt = case["positiveFunctionExcerpt"] if policy_name == "tool-primary-approved-policy.json" else excerpt
    if positive_quote is not None:
        predicate_excerpt = positive_quote
    predicate = f"Exact-ID evidence: {normalized(predicate_excerpt)}"
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
            **({"bonusSourceProof": case["bonusSourceProof"]} if case.get("bonusSourceProof") else {}),
            **({"variantFunctionProof": case["variantFunctionProof"]} if case.get("variantFunctionProof") else {}),
            **({"stateScopeNotes": case["stateScopeNotes"]} if case.get("stateScopeNotes") else {}),
            **({"approvalScope": "primary category, subcategory and tab only; tags retained and supplemental roles unassessed"}
               if primary_scope_only else {}),
        },
    }


def load_bank_policy() -> tuple[dict[int, dict[str, Any]], dict[str, str]]:
    spec = importlib.util.spec_from_file_location('root_bank_verifier', CERT / 'verify-bank-ignore-policy.py')
    if spec is None or spec.loader is None:
        raise ValueError('Cannot load detached bank policy verifier')
    verifier = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(verifier)
    verifier.verify_policy()
    policy = json.loads((CERT / 'bank-ignore-approved-policy.json').read_text(encoding='utf-8'))
    return ({case['itemId']: case for case in policy['cases']}, {
        'policy': sha256(CERT / 'bank-ignore-approved-policy.json'),
        'approvalPin': sha256(CERT / 'bankability-policy-approvals.json'),
        'verifier': sha256(CERT / 'verify-bank-ignore-policy.py'),
        'runtimeResource': policy['runtimeResourceSha256'],
    })


def make_bank_exclusion(case: dict[str, Any], packet: dict[str, Any], hashes: dict[str, str],
                        sources: dict[str, dict[str, Any]]) -> dict[str, Any]:
    item_id = case['itemId']; title = case['sourceTitle']; source = sources[title]
    if source['sha256'] != case['sourceSha256'] or source['revid'] != case['sourceRevision']:
        raise ValueError(f'#{item_id}: bank exclusion source differs from exact indexed article')
    facts = []
    for field in case['exactIdField'] + case['bankabilityField']:
        if isinstance(field, str):
            match = re.fullmatch(r'\|\s*(\w+)\s*=\s*(.*?)\s*', field)
            if match is None:
                raise ValueError(f'#{item_id}: bank field is not a literal assignment')
            facts.append({'field': match[1], 'value': match[2]})
        else:
            facts.append(field)
    quote = 'This item cannot be deposited into a bank.' if item_id in {13183, 13184} else ''
    current = packet['current']
    return {
        'itemId': item_id, 'shard': packet['shard'], 'decision': 'exclude',
        'exclusionReason': 'NON_BANKABLE', 'proposedCategory': current['category'],
        'proposedSubcategory': current['subcategory'], 'proposedIronmanTabKey': current['ironmanTabKey'],
        'proposedTags': sorted(current['tags']), 'proposedRoles': None, 'roleClaimScope': 'unassessed',
        'semanticPredicate': 'Exact own selected bankable=No or direct no-deposit prose; excluded only from unobserved bank-deposit candidates.',
        'rationale': 'Root-approved deposit prohibition. Retain this ID in the audit denominator and preserve every observed live row; reference category and tags are not certified by this exclusion.',
        'evidence': [citation(title, source, item_id, quote, facts)], 'identityLinks': [],
        'reviewer': 'root-approved-bank-policy-emitter', 'rootBankabilityApproval': hashes,
    }


def load_bank_supplement():
    spec = importlib.util.spec_from_file_location('root_bank_supplement', CERT / 'verify-bank-ignore-supplemental.py')
    if spec is None or spec.loader is None:
        raise ValueError('Cannot load supplemental bank verifier')
    verifier = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(verifier)
    verifier.verify()
    policy = json.loads((CERT / 'bank-ignore-supplemental-approved-policy.json').read_text(encoding='utf-8'))
    return ({case['itemId']: case for case in policy['cases']}, {
        'policy': sha256(CERT / 'bank-ignore-supplemental-approved-policy.json'),
        'approvalPin': sha256(CERT / 'bankability-supplemental-approvals.json'),
        'verifier': sha256(CERT / 'verify-bank-ignore-supplemental.py'),
        'runtimePolicy': policy['sourceHashes']['src/main/java/com/pkoka5/ironmanbankarchitect/catalog/BankabilityPolicy.java'],
    })


def make_bank_supplemental_exclusion(case, packet, hashes, sources):
    row = make_bank_exclusion(case, packet, hashes, sources)
    source = sources[case['sourceTitle']]
    row['evidence'] = [citation(case['sourceTitle'], source, case['itemId'], case['quote'],
                                [{'field': 'id', 'value': '13532'}])]
    row['semanticPredicate'] = 'Exact own current article records an unconditional bank deposit prohibition for ID 13532; exclude only unobserved deposit candidates.'
    row['rationale'] = 'Root reviewed the full own article and separately approved the direct dated deposit prohibition. Missing bankable remains unknown. Preserve every observed bank row; category, tags, availability and other roles remain unassessed.'
    return row


def load_bank_context(packets: dict[int, dict[str, Any]], occupied: set[int]):
    spec = importlib.util.spec_from_file_location('root_bank_context', CERT / 'verify-bank-context-placement.py')
    if spec is None or spec.loader is None:
        raise ValueError('Cannot load conditional bank-context verifier')
    verifier = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(verifier)
    policy, candidates, snapshot, pins = verifier.verify()
    hashes = {name: sha256(CERT / name) for name in (
        'bank-context-placement-approved-policy.json', 'bank-context-placement-approvals.json',
        'verify-bank-context-placement.py')}
    result = {}
    snapshot_hash = sha256(verifier.SNAPSHOT)
    for candidate in candidates:
        item_id, target = candidate['itemId'], candidate['targetItemId']
        if item_id in occupied:
            raise ValueError(f'Conditional bank-context case overlaps another approval: {item_id}')
        packet, base = packets[item_id], snapshot[target]
        current = packet['current']
        if (current['category'], current['subcategory'], current['ironmanTabKey']) != (
                base['proposedCategory'], base['proposedSubcategory'], base['proposedIronmanTabKey']):
            raise ValueError(f'Conditional bank placement changes frozen assignment: {item_id}')
        relation = candidate['relation']
        condition = policy['conditions'][relation]
        own_evidence = [e for e in base['evidence'] if e.get('itemId') == target
                        and e['kind'] in {'exact_wiki', 'direct_variant'}]
        transformation = [{
            'kind': 'local_source', 'source': pin['url'], 'sourceTitle': pin['title'],
            'sourceRevision': pin['revision'], 'sourceHash': pin['sha256'],
            'sourcePath': pin['localPath'], 'quote': passage['text'],
            'claimScope': 'generic bank transformation or restriction; not exact raw-item semantics',
        } for pin in pins['pins'] for passage in pin['passages']]
        result[item_id] = {
            'itemId': item_id, 'shard': packet['shard'], 'decision': 'certify',
            'proposedCategory': current['category'], 'proposedSubcategory': current['subcategory'],
            'proposedIronmanTabKey': current['ironmanTabKey'], 'proposedTags': sorted(current['tags']),
            'proposedRoles': None, 'roleClaimScope': 'unassessed',
            'assignmentClaimScope': 'bank-context canonical placement only',
            'rawItemFunctionClaimScope': 'unassessed', 'availabilityClaimScope': 'unassessed',
            'semanticPredicate': candidate['semanticPredicate'],
            'rationale': f'Root approves only conditional bank-context placement for exact {relation} '
                         f'edge {item_id} -> {target}. {condition} The exact target primary placement '
                         'was separately approved before this integration. Raw functions, tags, '
                         'availability and broad item equivalence remain unassessed.',
            'evidence': transformation,
            'identityLinks': [{'itemId': target, 'fromItemId': item_id, 'toItemId': target,
                               'relation': relation, 'evidence': [candidate['typedCacheEvidence']] + own_evidence}],
            'reviewer': 'root-approved-bank-context-rule', 'rootBankContextApproval': hashes,
            'approvedCanonicalBase': {'itemId': target, 'decision': base['decision'],
                                      'frozenDecisionSha256': verifier.canonical(base),
                                      'frozenSnapshotSha256': snapshot_hash},
        }
    return result, hashes


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
    bank_cases, bank_hashes = load_bank_policy()
    bank_supplement, bank_supplement_hashes = load_bank_supplement()
    if set(bank_supplement) & (set(cases) | set(optional_certifications) | set(bank_cases)):
        raise ValueError('Supplemental bank case overlaps a prior primary or bank policy')
    bank_context, bank_context_hashes = load_bank_context(
        packets, set(cases) | set(optional_certifications) | set(bank_cases) | set(bank_supplement))
    for item_id in sorted(packets):
        packet = packets[item_id]
        if item_id in cases:
            case, policy_name = cases[item_id]
            output_rows.append(make_actionable(case, policy_name, policy_hashes[policy_name],
                                               packet, article_index, article_index_hash))
        elif item_id in optional_certifications:
            output_rows.append(optional_certifications[item_id])
        elif item_id in bank_cases:
            output_rows.append(make_bank_exclusion(bank_cases[item_id], packet, bank_hashes, article_index))
        elif item_id in bank_supplement:
            output_rows.append(make_bank_supplemental_exclusion(bank_supplement[item_id], packet,
                                                               bank_supplement_hashes, article_index))
        elif item_id in bank_context:
            output_rows.append(bank_context[item_id])
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
                     for path in sorted(PACKET_DIR / name for name in PACKET_NAMES)}
    coverage_path = BASE / "current-coverage.tsv"
    manifest = {
        "schema": "root-approved-category-decisions/v1",
        "policyCaseCount": len(cases),
        "optionalRootCertificationCount": len(optional_certifications),
        "bankContextPlacementCount": len(bank_context),
        "ownPrimaryApprovalCount": sum(row['decision'] in {'certify', 'revise'} and
                                       row.get('assignmentClaimScope') != 'bank-context canonical placement only'
                                       for row in output_rows),
        "decisionRows": len(output_rows),
        "actionableRows": sum(row["decision"] in {"certify", "revise", "exclude"} for row in output_rows),
        "unresolvedRows": sum(row["decision"] == "unresolved" for row in output_rows),
        "actionCounts": dict(sorted(Counter(row["decision"] for row in output_rows).items())),
        "replayScriptHashes": {name: sha256(CERT / name) for name in
                               ("emit-root-approved-decisions.py", "review-approved-clue-scrolls.py", "ledger.py",
                                "verify-gear-primary-policy.py", "verify-gear-primary-through246-policy.py", "verify-gear-primary-next157-policy.py", "verify-gear-bonus-sources.py", "verify-food-primary-policy.py", "verify-teleport-primary-policy.py", "verify-rune-primary-policy.py", "verify-tool-primary-policy.py", "verify-farming-primary-policy.py", "verify-farming-supplemental-policy.py", "verify-cosmetic-cooking-policies.py", "verify-potion-primary-policies.py", "verify-bank-context-placement.py", "verify-materials-v15-first100.py", "verify-materials-v15-g101-340.py", "verify-materials-v15-g341-493.py", "verify-bank-ignore-supplemental.py")},
        "sourceHashes": {
            "bankabilityPolicy": bank_hashes,
            "bankabilitySupplementalPolicy": bank_supplement_hashes,
            "bankContextPlacement": bank_context_hashes,
            "policies": policy_hashes,
            "rootPolicyApprovals": sha256(CERT / "root-policy-approvals.json"),
            "optionalCertifications": certification_hashes,
            "articleIndex": sha256(ARTICLE_INDEX),
            "frozenCoverage": sha256(coverage_path),
            "gearBonusSourceProof": sha256(BASE / "reviews/gear-v2/bonus-source-proof.json"),
            "foodCandidatePacket": sha256(BASE / "reviews/supplies-food-positive-v8-root-replay/food-positive-rule-candidates.jsonl"),
            "rawFishReview": sha256(BASE / "reviews/materials-positive-cohorts/20261003-raw-fish-cooking-inputs/root-review-packet.json"),
            "teleportCandidatePacket": sha256(BASE / "reviews/transport-v16/ordinary-teleport-consumables-review.json"),
            "runeCandidatePacket": sha256(BASE / "reviews/transport-v17/ordinary-spellcasting-runes-review.json"),
            "toolCandidatePacket": sha256(BASE / "reviews/proposed-unchanged-primary-tools-e8745b79b5f2d3d5/candidate-policy.json"),
            "farmingCandidatePacket": sha256(BASE / "reviews/materials-positive-cohorts/20261003-farming-seed-literal-v2/root-review-packet.json"),
            "frozenPackets": packet_hashes,
        },
        "output": (str(args.output.relative_to(ROOT)) if args.output.is_relative_to(ROOT) else str(args.output)).replace("\\", "/"),
        "outputSha256": sha256(args.output),
        "summaryTsv": (str(args.summary_tsv.relative_to(ROOT)) if args.summary_tsv.is_relative_to(ROOT) else str(args.summary_tsv)).replace("\\", "/"),
        "summaryTsvSha256": sha256(args.summary_tsv),
        "tabPolicy": "Standard target tabs are computed from the approved target category using the current preset mapper's category routes, plus explicit ID routes listed in this emitter. after-coverage is never read by the emitter.",
    }
    args.manifest.parent.mkdir(parents=True, exist_ok=True)
    args.manifest.write_text(json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    print(f"Wrote {len(output_rows)} exact-ID decisions ({manifest['actionableRows']} actionable; {manifest['unresolvedRows']} unresolved)")
    print(f"Decisions: {args.output}")
    print(f"Manifest: {args.manifest}")


if __name__ == "__main__":
    main()
