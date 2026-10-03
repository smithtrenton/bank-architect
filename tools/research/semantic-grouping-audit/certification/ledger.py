#!/usr/bin/env python3
"""Build deterministic, exact-ID certification packets from compiled catalog exports."""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Iterable


ROOT = Path(__file__).resolve().parents[4]
DEFAULT_COVERAGE = ROOT / "tmp/category-certification/current-coverage.tsv"
DEFAULT_JOINED = ROOT / "tmp/semantic-audit/joined.jsonl"
DEFAULT_ARTICLE_INDEX = ROOT / "tmp/category-certification/wiki-articles/article-index.json"
DEFAULT_IDENTITY_LINKS = ROOT / "tmp/category-certification/identity-links.jsonl"
DEFAULT_IDENTITY_REPORT = ROOT / "tmp/category-certification/identity-report.json"
PACKET_OUTPUT_BASE = ROOT / "tmp/category-certification/reviewer-packets"
SHARDS = {
    "gear": {"GEAR"},
    "skilling-farming": {"SKILLING", "FARMING"},
    "supplies-herblore": {"POTION", "HERBLORE"},
    "tools": {"TOOL"},
    "clue-unique": {"CLUE", "UNIQUE"},
    "currency-runes-teleport": {"CURRENCY", "RUNE", "TELEPORT"},
    "cleanup-quest": {"CLEANUP"},
    "cleanup-other": {"CLEANUP"},
}
EVIDENCE_KINDS = {"exact_wiki", "typed_identity", "local_source", "direct_variant"}
DECISIONS = {"certify", "revise", "exclude", "unresolved"}
EDGE_SEMANTICS = {
    "NOTE_VARIANT_OF": ("notedID/notedTemplate", "97/98"),
    "BOUGHT_VARIANT_OF": ("boughtId/boughtTemplateId", "139/140"),
    "PLACEHOLDER_FOR": ("placeholderID/placeholderTemplateID", "148/149"),
}


def tag_set(value: Any) -> set[str]:
    if not isinstance(value, list) or any(not isinstance(tag, str) for tag in value):
        raise ValueError("tags must be supplied as a list of strings")
    return {tag for tag in value if tag}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_tsv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream, delimiter="\t"))


def strict_id(value: Any) -> int | None:
    text = str(value).strip()
    return int(text) if re.fullmatch(r"[0-9]+", text) else None


def exact_record_ids(record: dict[str, Any]) -> set[int]:
    raw = record.get("item_id", [])
    if not isinstance(raw, list):
        raw = [raw]
    return {parsed for value in raw if (parsed := strict_id(value)) is not None}


def read_joined(path: Path) -> dict[int, dict[str, Any]]:
    by_id: dict[int, dict[str, Any]] = {}
    with path.open(encoding="utf-8-sig") as stream:
        for line_number, line in enumerate(stream, 1):
            if not line.strip():
                continue
            entry = json.loads(line)
            item_id = strict_id(entry.get("item_id"))
            if item_id is None:
                raise ValueError(f"Non-numeric joined key at {path}:{line_number}")
            if item_id in by_id:
                raise ValueError(f"Duplicate joined key {item_id}")
            exact_records = [r for r in entry.get("wiki_records", [])
                             if item_id in exact_record_ids(r)]
            by_id[item_id] = {
                "wikiJoinStatus": entry.get("wiki_join_status", ""),
                "wikiRecords": exact_records,
                "wikiUrls": entry.get("wiki_urls", []),
                "wikiLookupStatus": entry.get("wiki_lookup_status", ""),
                "wikiLookupLinks": entry.get("wiki_lookup_links", []),
                "wikiLookupWarnings": entry.get("wiki_lookup_warnings", []),
                "baselineRoles": entry.get("roles", []),
                "baselinePresetTag": entry.get("preset_tag", ""),
                "recipeRelations": entry.get("recipe_relations", []),
                "variantFlags": entry.get("variant_flags", []),
            }
    return by_id


def shard_for(row: dict[str, str]) -> str:
    category = row.get("itemCategory", "")
    if category == "CLEANUP":
        return "cleanup-other" if row.get("subcategory", "") == "cleanup" else "cleanup-quest"
    for shard, categories in SHARDS.items():
        if category in categories:
            return shard
    raise ValueError(f"No reviewer shard for category {category!r}, item {row.get('itemId')}")


def build(coverage_path: Path, joined_path: Path, article_index_path: Path,
         identity_links_path: Path, identity_report_path: Path, output: Path | None) -> None:
    rows = read_tsv(coverage_path)
    if not rows:
        raise ValueError(f"Empty coverage input: {coverage_path}")
    required = {"itemId", "registryName", "constantName", "auditScope", "catalogName",
                "itemCategory", "ironmanTabKey", "subcategory", "tags"}
    missing = required - set(rows[0])
    if missing:
        raise ValueError(f"Coverage input is missing columns: {sorted(missing)}")
    ids = [strict_id(row["itemId"]) for row in rows]
    if any(item_id is None for item_id in ids):
        raise ValueError("Coverage contains a non-numeric or non-strict itemId")
    if len(ids) != len(set(ids)):
        raise ValueError("Coverage contains duplicate item IDs")
    joined = read_joined(joined_path) if joined_path.is_file() else {}
    article_index = json.loads(article_index_path.read_text(encoding="utf-8-sig")) if article_index_path.is_file() else {}
    article_sources: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for title, source in article_index.items():
        for raw_id in source.get("exactInfoboxItemIds", []):
            item_id = strict_id(raw_id)
            if item_id is not None:
                article_sources[item_id].append(source)
    identity_candidates: dict[int, list[dict[str, Any]]] = defaultdict(list)
    if identity_links_path.is_file():
        with identity_links_path.open(encoding="utf-8-sig") as stream:
            for line in stream:
                if not line.strip():
                    continue
                edge = json.loads(line)
                for raw_id in (edge.get("fromItemId"), edge.get("toItemId")):
                    item_id = strict_id(raw_id)
                    if item_id is not None:
                        identity_candidates[item_id].append(edge)
    identity_index_hash = sha256(identity_links_path) if identity_links_path.is_file() else None
    output = output or PACKET_OUTPUT_BASE.with_name(
        PACKET_OUTPUT_BASE.name + "-" + sha256(coverage_path)[:8] + "-" +
        (sha256(joined_path)[:8] if joined_path.is_file() else "no-joined") + "-" +
        (sha256(article_index_path)[:8] if article_index_path.is_file() else "no-articles") + "-" +
        (identity_index_hash[:8] if identity_index_hash else "no-identities"))

    output.mkdir(parents=True, exist_ok=True)
    shards: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row, item_id in zip(rows, ids):
        assert item_id is not None
        shard = shard_for(row)
        source = joined.get(item_id, {})
        if source or item_id in article_sources:
            source["wikiArticleSources"] = sorted(
                article_sources.get(item_id, []), key=lambda entry: entry.get("title", ""))
        packet = {
            "itemId": item_id,
            "registryName": row["registryName"],
            "constantName": row["constantName"],
            "auditScope": row["auditScope"],
            "catalogName": row["catalogName"],
            "current": {
                "category": row["itemCategory"],
                "subcategory": row["subcategory"],
                "ironmanTabKey": row["ironmanTabKey"],
                "tags": [tag for tag in row["tags"].split(",") if tag],
            },
            "shard": shard,
            "sourceEvidence": source,
            "typedIdentityEvidenceCandidates": identity_candidates.get(item_id, []),
            "review": {
                "decision": "",
                "proposedCategory": "",
                "proposedSubcategory": "",
                "proposedTags": [],
                "proposedRoles": [],
                "proposedIronmanTabKey": "",
                "semanticPredicate": "",
                "rationale": "",
                "evidence": [],
                "identityLinks": [],
                "reviewer": "",
            },
        }
        shards[shard].append(packet)

    if sum(map(len, shards.values())) != len(rows):
        raise AssertionError("Shard partition does not cover the current export")
    shard_ids: set[int] = set()
    summary: dict[str, Any] = {
        "inputs": {
            str(coverage_path): sha256(coverage_path),
            str(joined_path): sha256(joined_path) if joined_path.is_file() else None,
            str(article_index_path): sha256(article_index_path) if article_index_path.is_file() else None,
            str(identity_links_path): identity_index_hash,
            str(identity_report_path): sha256(identity_report_path) if identity_report_path.is_file() else None,
        },
        "recordCount": len(rows),
        "scopes": dict(sorted(Counter(r["auditScope"] for r in rows).items())),
        "categories": dict(sorted(Counter(r["itemCategory"] for r in rows).items())),
        "shards": {},
        "wikiExactRecordCounts": {"joinedRows": len(joined), "directExactMatches": 0,
                                  "unmatchedCurrentIds": 0},
        "articleIndexPages": len(article_index),
        "typedIdentityEdgeCount": sum(len(edges) for edges in identity_candidates.values()) // 2,
        "limitations": [
            "The current assignment is a snapshot, not certification evidence.",
            "Only numeric exact item_id values from joined.jsonl are attached; alternate lookup links remain visibly separate.",
            "Missing Wiki records, absent fields, and false category values do not establish absence of a role.",
            "Bulk item-infobox rows can lack page revision IDs; source packet/hash provenance must be cited by reviewers.",
        ],
    }
    for shard, packets in sorted(shards.items()):
        packet_path = output / f"{shard}.jsonl"
        with packet_path.open("w", encoding="utf-8", newline="\n") as stream:
            for packet in packets:
                stream.write(json.dumps(packet, ensure_ascii=False, sort_keys=True) + "\n")
                item_id = packet["itemId"]
                if item_id in shard_ids:
                    raise AssertionError(f"ID occurs in more than one shard: {item_id}")
                shard_ids.add(item_id)
                if packet["sourceEvidence"].get("wikiArticleSources"):
                    summary["wikiExactRecordCounts"]["directExactMatches"] += 1
                else:
                    summary["wikiExactRecordCounts"]["unmatchedCurrentIds"] += 1
        summary["shards"][shard] = {
            "count": len(packets),
            "sha256": sha256(packet_path),
            "scopes": dict(sorted(Counter(p["auditScope"] for p in packets).items())),
            "categories": dict(sorted(Counter(p["current"]["category"] for p in packets).items())),
            "packet": packet_path.name,
        }
    if shard_ids != set(ids):
        raise AssertionError("Shard IDs do not equal current coverage IDs")
    summary_path = output / "evidence-summary.json"
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
                            encoding="utf-8")
    print(f"Wrote {len(rows)} rows in {len(shards)} disjoint shards to {output}")


def validate_decisions(packet_dir: Path, decision_paths: Iterable[Path],
                       shard_names: set[str] | None = None) -> None:
    universe: dict[int, dict[str, Any]] = {}
    for packet_path in sorted(packet_dir.glob("*.jsonl")):
        if packet_path.name.startswith("decisions-"):
            continue
        with packet_path.open(encoding="utf-8") as stream:
            for line in stream:
                packet = json.loads(line)
                universe[packet["itemId"]] = packet
    expected = {item_id: packet for item_id, packet in universe.items()
                if shard_names is None or packet["shard"] in shard_names}
    seen: dict[int, dict[str, Any]] = {}
    errors: list[str] = []
    for path in decision_paths:
        with path.open(encoding="utf-8-sig") as stream:
            for line_number, line in enumerate(stream, 1):
                if not line.strip():
                    continue
                decision = json.loads(line)
                item_id = strict_id(decision.get("itemId"))
                loc = f"{path}:{line_number}"
                if item_id is None or item_id not in expected:
                    errors.append(f"{loc}: unknown/non-numeric exact itemId")
                    continue
                if item_id in seen:
                    errors.append(f"{loc}: duplicate/conflicting decision for {item_id}")
                    continue
                seen[item_id] = decision
                baseline = expected[item_id]
                if decision.get("shard") != baseline["shard"]:
                    errors.append(f"{loc}: item {item_id} belongs to {baseline['shard']}")
                action = decision.get("decision")
                if action not in DECISIONS:
                    errors.append(f"{loc}: decision must be one of {sorted(DECISIONS)}")
                if not str(decision.get("rationale", "")).strip():
                    errors.append(f"{loc}: rationale is required")
                if not str(decision.get("semanticPredicate", "")).strip():
                    errors.append(f"{loc}: semanticPredicate is required")
                roles = decision.get("proposedRoles")
                if roles is not None and not isinstance(roles, list):
                    errors.append(f"{loc}: proposedRoles must be a list or null")
                role_scope = decision.get("roleClaimScope")
                if role_scope not in {None, "supplemental_only", "unassessed"}:
                    errors.append(f"{loc}: roleClaimScope must be supplemental_only or unassessed")
                if action in {"certify", "revise", "exclude"} and roles is None and role_scope != "unassessed":
                    errors.append(f"{loc}: actionable null roles require roleClaimScope=unassessed")
                if role_scope == "supplemental_only" and not isinstance(roles, list):
                    errors.append(f"{loc}: supplemental_only role claims must be a list")
                if not isinstance(decision.get("proposedTags"), list):
                    errors.append(f"{loc}: proposedTags must be explicitly supplied as a list")
                evidence = decision.get("evidence", [])
                links = decision.get("identityLinks", [])
                if action in {"certify", "revise", "exclude"} and not evidence and not links:
                    errors.append(f"{loc}: actionable decisions require positive evidence or a typed identity chain")
                if action in {"certify", "revise"}:
                    current = baseline["current"]
                    expected_fields = {
                        "proposedCategory": current["category"],
                        "proposedSubcategory": current["subcategory"],
                        "proposedTags": set(current["tags"]),
                        "proposedIronmanTabKey": current["ironmanTabKey"],
                    }
                    for field, current_value in expected_fields.items():
                        if field not in decision:
                            errors.append(f"{loc}: {field} must be explicitly supplied")
                        elif field == "proposedTags" and action == "certify" and tag_set(decision[field]) != current_value:
                            errors.append(f"{loc}: certify proposal differs from current {field}; mark revise")
                        elif field != "proposedTags" and action == "certify" and decision[field] != current_value:
                            errors.append(f"{loc}: certify proposal differs from current {field}; mark revise")
                    if action == "revise" and all((tag_set(decision.get(field, [])) == value
                                                    if field == "proposedTags" else decision.get(field) == value)
                                                   for field, value in expected_fields.items()):
                        errors.append(f"{loc}: revise must identify a current category/subcategory/tab change")
                for evidence_row in evidence:
                    if evidence_row.get("kind") not in EVIDENCE_KINDS:
                        errors.append(f"{loc}: unsupported evidence kind {evidence_row.get('kind')!r}")
                    if not evidence_row.get("source"):
                        errors.append(f"{loc}: evidence source is required")
                    if evidence_row.get("kind") in {"exact_wiki", "direct_variant"}:
                        source_id = strict_id(evidence_row.get("itemId"))
                        link_targets = {strict_id(link.get("itemId")) for link in links}
                        if source_id != item_id and source_id not in link_targets:
                            errors.append(f"{loc}: Wiki evidence must name reviewed item or a typed-link endpoint")
                        source_hash = str(evidence_row.get("sourceHash", ""))
                        valid_hash = bool(re.fullmatch(r"(?:sha256:)?[0-9a-fA-F]{64}", source_hash))
                        revision = evidence_row.get("sourceRevision")
                        if not (revision or valid_hash):
                            errors.append(f"{loc}: Wiki evidence needs sourceRevision or sourceHash")
                        if not str(evidence_row.get("quote", "")).strip() and not evidence_row.get("structuredFacts"):
                            errors.append(f"{loc}: Wiki evidence needs an excerpt or exact structured variant facts")
                    elif evidence_row.get("kind") == "typed_identity" and not evidence_row.get("relation"):
                        errors.append(f"{loc}: typed_identity evidence must name its relation")
                evidenced_chain = False
                direct_wiki = any(e.get("kind") in {"exact_wiki", "direct_variant"} and
                                  strict_id(e.get("itemId")) == item_id for e in evidence)
                for link in links:
                    linked_id = strict_id(link.get("itemId"))
                    source_id = strict_id(link.get("fromItemId"))
                    target_id = strict_id(link.get("toItemId"))
                    if (linked_id is None or linked_id not in universe or not link.get("relation") or
                            not link.get("evidence") or {source_id, target_id} != {item_id, linked_id}):
                        errors.append(f"{loc}: identity links need exact endpoints, directed typed relation, and evidence")
                    else:
                        nested = link["evidence"]
                        typed_edge = any(e.get("kind") == "typed_identity" and
                                         strict_id(e.get("fromItemId")) == source_id and
                                         strict_id(e.get("toItemId")) == target_id and
                                         e.get("relation") == link.get("relation") and bool(e.get("source")) and
                                         bool(e.get("identityIndexHash")) and
                                         bool(re.fullmatch(r"(?:sha256:)?[0-9a-fA-F]{64}", str(e.get("sourceHash", ""))))
                                         for e in nested)
                        semantic_endpoint = any(e.get("kind") in {"exact_wiki", "direct_variant"} and
                                                strict_id(e.get("itemId")) == target_id and
                                                (e.get("sourceRevision") or re.fullmatch(
                                                    r"(?:sha256:)?[0-9a-fA-F]{64}", str(e.get("sourceHash", "")))) and
                                                (str(e.get("quote", "")).strip() or bool(e.get("structuredFacts")))
                                                for e in nested)
                        if not typed_edge:
                            errors.append(f"{loc}: identity edge needs hashed typed cache/archive evidence with matching endpoints")
                        if not semantic_endpoint:
                            errors.append(f"{loc}: identity edge needs exact Wiki semantic evidence for its target ID")
                        if source_id == item_id and typed_edge and semantic_endpoint:
                            evidenced_chain = True
                if action in {"certify", "revise", "exclude"} and not (direct_wiki or evidenced_chain):
                    errors.append(f"{loc}: action needs direct exact Wiki evidence or an evidenced typed-cache-to-Wiki chain")
                if action == "unresolved" and not str(decision.get("rationale", "")).strip():
                    errors.append(f"{loc}: unresolved decision needs an explicit evidence gap")
    missing = set(expected) - set(seen)
    if missing:
        errors.append(f"missing decisions for {len(missing)} IDs; first IDs: {sorted(missing)[:20]}")
    if errors:
        raise ValueError("Decision validation failed:\n" + "\n".join(errors[:100]))
    print(f"Validated {len(seen)} unique decisions; all packet IDs covered and evidence schema is valid")


def verify_applied(coverage_path: Path, decision_paths: Iterable[Path]) -> None:
    current_rows = read_tsv(coverage_path)
    current: dict[int, dict[str, str]] = {}
    for row in current_rows:
        item_id = strict_id(row.get("itemId"))
        if item_id is None or item_id in current:
            raise ValueError(f"Invalid or duplicate current item ID: {row.get('itemId')!r}")
        current[item_id] = row
    checked: set[int] = set()
    actionable_checked = 0
    unresolved_skipped = 0
    exclusions_checked = 0
    mismatches: list[str] = []
    for path in decision_paths:
        with path.open(encoding="utf-8-sig") as stream:
            for line_number, line in enumerate(stream, 1):
                if not line.strip():
                    continue
                decision = json.loads(line)
                item_id = strict_id(decision.get("itemId"))
                if item_id is None or item_id not in current:
                    mismatches.append(f"{path}:{line_number}: item is absent from new export")
                    continue
                if item_id in checked:
                    mismatches.append(f"{path}:{line_number}: duplicate decision for {item_id}")
                    continue
                checked.add(item_id)
                row = current[item_id]
                if decision.get("decision") == "exclude":
                    exclusions_checked += 1
                    if row.get("auditScope") in {"NAMED_EFFECTIVE", "SUPPLEMENTAL"}:
                        mismatches.append(f"item {item_id}: exclusion is not reflected in the new export scope")
                    continue
                if decision.get("decision") not in {"certify", "revise"}:
                    if decision.get("decision") == "unresolved":
                        unresolved_skipped += 1
                    continue
                actionable_checked += 1
                checks = {
                    "category": (decision.get("proposedCategory"), row.get("itemCategory", "")),
                    "subcategory": (decision.get("proposedSubcategory"), row.get("subcategory", "")),
                    "tab": (decision.get("proposedIronmanTabKey"), row.get("ironmanTabKey", "")),
                    "tags": (sorted(decision.get("proposedTags", [])),
                             sorted(tag for tag in row.get("tags", "").split(",") if tag)),
                }
                for field, (proposed, actual) in checks.items():
                    if proposed != actual:
                        mismatches.append(f"item {item_id}: proposed {field} {proposed!r} != new export {actual!r}")
    if mismatches:
        raise ValueError("Applied-decision check failed:\n" + "\n".join(mismatches[:100]))
    print(f"Applied-decision coverage passed: decisionRows={len(checked)}, actionableTargetsVerified={actionable_checked}, "
          f"exclusionsChecked={exclusions_checked}, unresolvedRowsSkipped={unresolved_skipped}, export={coverage_path}")


def audit_sources(packet_dir: Path, article_index_path: Path, identity_links_path: Path,
                 identity_report_path: Path, decision_paths: list[Path],
                 shard_names: set[str] | None = None) -> list[dict[str, Any]]:
    """Audit actionable source claims even while other IDs remain unresolved."""
    validate_decisions(packet_dir, decision_paths, shard_names)
    decisions = [json.loads(line) for path in decision_paths
                 for line in path.read_text(encoding="utf-8-sig").splitlines() if line.strip()]
    article_index = json.loads(article_index_path.read_text(encoding="utf-8-sig"))
    identity_rows: dict[tuple[int, int, str], list[dict[str, Any]]] = defaultdict(list)
    needs_identity = any(e.get("kind") == "typed_identity"
                         for decision in decisions for link in decision.get("identityLinks", [])
                         for e in link.get("evidence", []))
    identity_report: dict[str, Any] = {}
    identity_index_hash: str | None = None
    frozen_cache_hashes: dict[str, str] = {}
    if needs_identity:
        identity_report = json.loads(identity_report_path.read_text(encoding="utf-8-sig"))
        identity_index_hash = sha256(identity_links_path)
        if identity_report.get("identity_links_sha256") != identity_index_hash:
            raise ValueError("identity-report.json does not pin the current identity-links.jsonl hash")
        with identity_links_path.open(encoding="utf-8-sig") as stream:
            for line in stream:
                if not line.strip():
                    continue
                edge = json.loads(line)
                from_id, to_id = strict_id(edge.get("fromItemId")), strict_id(edge.get("toItemId"))
                relation = edge.get("relation")
                if from_id is not None and to_id is not None and relation:
                    identity_rows[(from_id, to_id, relation)].append(edge)
        frozen_cache_hashes = identity_report.get("cache", {}).get("frozen_containers", {})
    verified_text: dict[str, str] = {}
    errors: list[str] = []
    wiki_evidence_verified = 0
    typed_edges_verified = 0
    actionable_rows = sum(d.get("decision") in {"certify", "revise", "exclude"} for d in decisions)
    unresolved_rows_skipped = sum(d.get("decision") == "unresolved" and not d.get("evidence") and
                                  not d.get("identityLinks") for d in decisions)

    def verify_wiki(evidence: dict[str, Any], loc: str) -> None:
        nonlocal wiki_evidence_verified
        title = evidence.get("sourceTitle")
        indexed = article_index.get(title) if title else None
        if not indexed:
            errors.append(f"{loc}: sourceTitle is absent from the pinned article index")
            return
        if evidence.get("sourceRevision") != indexed.get("revid"):
            errors.append(f"{loc}: sourceRevision does not match article index")
        supplied_hash = str(evidence.get("sourceHash", "")).removeprefix("sha256:")
        if supplied_hash.lower() != str(indexed.get("sha256", "")).lower():
            errors.append(f"{loc}: sourceHash does not match article index")
        if evidence.get("source") != indexed.get("sourceUrl"):
            errors.append(f"{loc}: source URL does not match article index")
        raw_path = str(indexed.get("path", "")).replace("\\", "/")
        article_path = ROOT / raw_path
        if not article_path.is_file() or sha256(article_path) != indexed.get("sha256"):
            errors.append(f"{loc}: pinned article text file is missing or its hash changed")
            return
        if raw_path not in verified_text:
            verified_text[raw_path] = article_path.read_text(encoding="utf-8", errors="replace")
        quote = " ".join(str(evidence.get("quote", "")).split())
        body = " ".join(verified_text[raw_path].split())
        if quote and quote not in body:
            errors.append(f"{loc}: supporting excerpt is absent from the pinned article text")
        item_id = strict_id(evidence.get("itemId"))
        variant = indexed.get("variants", {}).get(str(item_id), {}) if item_id is not None else {}
        if item_id not in {strict_id(x) for x in indexed.get("exactInfoboxItemIds", [])}:
            errors.append(f"{loc}: cited exact item ID is absent from article's infobox ID set")
        facts = evidence.get("structuredFacts", [])
        if facts and not variant:
            errors.append(f"{loc}: exact variant parameters are absent for the cited ID")
        for fact in facts:
            field = fact.get("field")
            if field not in variant.get("params", {}) or str(variant["params"][field]) != str(fact.get("value")):
                errors.append(f"{loc}: structured fact {field!r} does not match exact variant parameters")
        if not quote and not facts:
            errors.append(f"{loc}: Wiki evidence needs an exact excerpt or structured variant facts")
        wiki_evidence_verified += 1

    for decision in decisions:
        item_id = decision["itemId"]
        for evidence in decision.get("evidence", []):
            if evidence.get("kind") in {"exact_wiki", "direct_variant"}:
                verify_wiki(evidence, f"item {item_id}")
        for link in decision.get("identityLinks", []):
            for evidence in link.get("evidence", []):
                if evidence.get("kind") in {"exact_wiki", "direct_variant"}:
                    if strict_id(evidence.get("itemId")) != strict_id(link.get("toItemId")):
                        errors.append(f"item {item_id}: linked Wiki evidence must name toItemId")
                    verify_wiki(evidence, f"item {item_id} identity {link.get('relation')}")
                elif evidence.get("kind") == "typed_identity":
                    raw_path = str(evidence.get("sourcePath", "")).replace("\\", "/")
                    identity_path = ROOT / raw_path
                    expected_hash = str(evidence.get("sourceHash", "")).removeprefix("sha256:")
                    if not raw_path or not identity_path.is_file() or sha256(identity_path).lower() != expected_hash.lower():
                        errors.append(f"item {item_id}: typed identity artifact is absent or hash-mismatched")
                    edge_from = strict_id(evidence.get("fromItemId"))
                    edge_to = strict_id(evidence.get("toItemId"))
                    relation = evidence.get("relation")
                    semantics = EDGE_SEMANTICS.get(relation)
                    if evidence.get("identityIndexHash") != identity_index_hash:
                        errors.append(f"item {item_id}: typed identity cites a different identity-links index hash")
                    if not semantics or (evidence.get("cacheField"), evidence.get("cacheOpcode")) != semantics:
                        errors.append(f"item {item_id}: relation does not match supported cache field/opcode semantics")
                    edge_matches = []
                    if edge_from is not None and edge_to is not None and relation:
                        for edge in identity_rows.get((edge_from, edge_to, relation), []):
                            if (edge.get("cacheField"), edge.get("cacheOpcode")) != (evidence.get("cacheField"), evidence.get("cacheOpcode")):
                                continue
                            if strict_id(edge.get("targetId")) != edge_to or strict_id(edge.get("itemId")) != edge_to:
                                continue
                            if not any(
                                fact.get("kind") == "typed_identity" and
                                strict_id(fact.get("fromItemId")) == edge_from and
                                strict_id(fact.get("toItemId")) == edge_to and
                                fact.get("relation") == relation and
                                fact.get("sourcePath") == evidence.get("sourcePath") and
                                fact.get("sourceHash") == evidence.get("sourceHash") and
                                fact.get("sourceRevision") == evidence.get("sourceRevision") and
                                fact.get("configIndexRevision") == evidence.get("configIndexRevision")
                                for fact in edge.get("evidence", [])):
                                continue
                            target_wiki = False
                            for fact in edge.get("evidence", []):
                                if fact.get("kind") != "exact_wiki" or strict_id(fact.get("itemId")) != edge_to:
                                    continue
                                title = fact.get("sourceTitle")
                                indexed = article_index.get(title) if title else None
                                params = fact.get("sourceRecord", {}).get("params", {})
                                variant_ids = [value for key, value in params.items()
                                               if key == "id" or re.fullmatch(r"id[0-9]+", key)]
                                exact_index_ids = {strict_id(value) for value in
                                                   (indexed or {}).get("exactInfoboxItemIds", [])}
                                if (indexed and edge_to in exact_index_ids and
                                        fact.get("sourceRevision") == indexed.get("revid") and
                                        fact.get("sourceUrl") == indexed.get("sourceUrl") and
                                        edge_to in {strict_id(value) for value in variant_ids}):
                                    target_wiki = True
                                    break
                            if target_wiki and int(edge.get("targetWikiFactCount", 0)) > 0:
                                edge_matches.append(edge)
                    if not edge_matches:
                        errors.append(f"item {item_id}: claimed typed identity edge is absent from identity-links.jsonl")
                    else:
                        typed_edges_verified += 1
                    frozen = frozen_cache_hashes.get(Path(raw_path).name)
                    if not frozen or frozen.lower() != expected_hash.lower():
                        errors.append(f"item {item_id}: cache artifact hash is not in the frozen cache manifest")
                    report_cache = identity_report.get("cache", {})
                    if evidence.get("sourceRevision") != report_cache.get("config_archive_revision"):
                        errors.append(f"item {item_id}: cache archive revision differs from identity report")
                    if evidence.get("configIndexRevision") != report_cache.get("index_revision"):
                        errors.append(f"item {item_id}: config index revision differs from identity report")
    if errors:
        raise ValueError("Certification source-integrity gate failed:\n" + "\n".join(errors[:100]))
    print("Source integrity passed: "
          f"decisionRows={len(decisions)}, actionableRows={actionable_rows}, "
          f"wikiEvidenceRecordsVerified={wiki_evidence_verified}, "
          f"typedIdentityEdgesVerified={typed_edges_verified}, "
          f"unresolvedRowsSkipped={unresolved_rows_skipped}")
    return decisions


def complete_decisions(packet_dir: Path, coverage_path: Path, article_index_path: Path,
                       identity_links_path: Path, identity_report_path: Path,
                       decision_paths: list[Path]) -> None:
    decisions = audit_sources(packet_dir, article_index_path, identity_links_path,
                              identity_report_path, decision_paths)
    unresolved = [d["itemId"] for d in decisions if d.get("decision") == "unresolved"]
    if unresolved:
        raise ValueError(f"Certification incomplete: {len(unresolved)} unresolved IDs; first IDs: {unresolved[:20]}")
    verify_applied(coverage_path, decision_paths)
    print(f"Technical completeness gates passed: {len(decisions)} decisions, zero unresolved, runtime targets applied, cited source artifacts verified; independent semantic approval is required separately")


def write_gap_report(packet_dir: Path, coverage_path: Path, article_index_path: Path,
                     identity_links_path: Path, identity_report_path: Path,
                     decision_paths: list[Path], output_path: Path) -> None:
    """Write a deterministic per-ID view of unresolved work and verified audit gates."""
    packet_by_id: dict[int, dict[str, Any]] = {}
    for packet_path in sorted(packet_dir.glob("*.jsonl")):
        if packet_path.name.startswith("decisions-"):
            continue
        with packet_path.open(encoding="utf-8") as stream:
            for line in stream:
                packet = json.loads(line)
                packet_by_id[packet["itemId"]] = packet

    coverage_by_id: dict[int, dict[str, str]] = {}
    for row in read_tsv(coverage_path):
        item_id = strict_id(row.get("itemId"))
        if item_id is None or item_id in coverage_by_id:
            raise ValueError(f"Invalid or duplicate coverage item ID: {row.get('itemId')!r}")
        coverage_by_id[item_id] = row
    if set(coverage_by_id) != set(packet_by_id):
        raise ValueError("Coverage IDs do not equal reviewer packet IDs")

    decisions_by_id: dict[int, dict[str, Any]] = {}
    decision_paths_by_shard: dict[str, list[Path]] = defaultdict(list)
    decision_counts_by_shard: dict[str, Counter[str]] = defaultdict(Counter)
    for path in decision_paths:
        seen_shards: set[str] = set()
        with path.open(encoding="utf-8-sig") as stream:
            for line_number, line in enumerate(stream, 1):
                if not line.strip():
                    continue
                decision = json.loads(line)
                item_id = strict_id(decision.get("itemId"))
                if item_id is None or item_id not in packet_by_id:
                    raise ValueError(f"{path}:{line_number}: unknown/non-numeric exact itemId")
                if item_id in decisions_by_id:
                    raise ValueError(f"{path}:{line_number}: duplicate decision for {item_id}")
                decisions_by_id[item_id] = decision
                seen_shards.add(decision.get("shard", ""))
                decision_counts_by_shard[decision.get("shard", "")][decision.get("decision", "missing")] += 1
        for shard in seen_shards:
            decision_paths_by_shard[shard].append(path)
    if set(decisions_by_id) != set(packet_by_id):
        missing = sorted(set(packet_by_id) - set(decisions_by_id))
        extra = sorted(set(decisions_by_id) - set(packet_by_id))
        raise ValueError(f"Decision IDs do not equal packet IDs; missing={missing[:20]} extra={extra[:20]}")

    article_index = json.loads(article_index_path.read_text(encoding="utf-8"))
    direct_pages: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for title, record in article_index.items():
        for raw_id in record.get("exactInfoboxItemIds", []):
            item_id = strict_id(raw_id)
            if item_id is not None:
                direct_pages[item_id].append({"title": title, "revision": record.get("revid")})

    identity_candidates: dict[int, list[dict[str, Any]]] = defaultdict(list)
    with identity_links_path.open(encoding="utf-8") as stream:
        for line in stream:
            if not line.strip():
                continue
            edge = json.loads(line)
            from_id = strict_id(edge.get("fromItemId"))
            to_id = strict_id(edge.get("toItemId"))
            if from_id is not None and to_id is not None and edge.get("targetWikiFactCount", 0) > 0:
                identity_candidates[from_id].append({"toItemId": to_id, "relation": edge.get("relation")})

    schema_audits: dict[str, dict[str, Any]] = {}
    source_audits: dict[str, dict[str, Any]] = {}
    for shard, paths in sorted(decision_paths_by_shard.items()):
        try:
            validate_decisions(packet_dir, paths, {shard})
            schema_audits[shard] = {"status": "pass"}
        except (OSError, ValueError, json.JSONDecodeError) as error:
            schema_audits[shard] = {"status": "fail", "errors": str(error).splitlines()[:20]}
        try:
            audit_sources(packet_dir, article_index_path, identity_links_path, identity_report_path,
                          paths, {shard})
            source_audits[shard] = {"status": "pass"}
        except (OSError, ValueError, json.JSONDecodeError) as error:
            source_audits[shard] = {"status": "fail", "errors": str(error).splitlines()[:20]}

    shard_summary: dict[str, dict[str, Any]] = {}
    scope_counts: dict[str, Counter[str]] = defaultdict(Counter)
    overall_counts: Counter[str] = Counter()
    assignments: list[dict[str, Any]] = []
    for item_id, baseline in sorted(coverage_by_id.items()):
        decision = decisions_by_id[item_id]
        shard = decision["shard"]
        action = decision.get("decision", "missing")
        pages = direct_pages.get(item_id, [])
        candidates = identity_candidates.get(item_id, [])
        unresolved = action == "unresolved"
        if unresolved:
            gap = ("unresolved-with-exact-wiki" if pages else
                   "unresolved-with-typed-wiki-candidate" if candidates else
                   "unresolved-no-exact-source-path")
        elif action in {"certify", "revise", "exclude"}:
            gap = f"actionable-source-audit-{source_audits.get(shard, {}).get('status', 'missing')}"
        else:
            gap = "unknown-decision"

        summary = shard_summary.setdefault(shard, {
            "total": 0, "decisionCounts": Counter(), "scopeCounts": defaultdict(Counter),
            "directExactWiki": 0, "typedWikiCandidate": 0, "actionable": 0,
            "unresolvedDirectWiki": 0, "unresolvedTypedWikiCandidate": 0,
            "unresolvedNoExactSource": 0,
        })
        scope = baseline.get("auditScope", "")
        summary["total"] += 1
        summary["decisionCounts"][action] += 1
        summary["scopeCounts"][scope][action] += 1
        summary["directExactWiki"] += bool(pages)
        summary["typedWikiCandidate"] += bool(candidates)
        summary["actionable"] += action in {"certify", "revise", "exclude"}
        if unresolved:
            summary["unresolvedDirectWiki"] += bool(pages)
            summary["unresolvedTypedWikiCandidate"] += not pages and bool(candidates)
            summary["unresolvedNoExactSource"] += not pages and not candidates
        scope_counts[scope][action] += 1
        overall_counts[action] += 1
        assignments.append({
            "itemId": item_id,
            "shard": shard,
            "auditScope": scope,
            "currentCategory": baseline.get("itemCategory", ""),
            "currentSubcategory": baseline.get("subcategory", ""),
            "currentTab": baseline.get("ironmanTabKey", ""),
            "decision": action,
            "proposedCategory": decision.get("proposedCategory"),
            "proposedSubcategory": decision.get("proposedSubcategory"),
            "proposedTab": decision.get("proposedIronmanTabKey"),
            "gap": gap,
            "exactWikiPages": [page["title"] for page in pages],
            "typedWikiCandidateCount": len(candidates),
            "evidenceCount": len(decision.get("evidence", [])),
            "identityLinkCount": len(decision.get("identityLinks", [])),
        })

    for shard, summary in shard_summary.items():
        summary["decisionCounts"] = dict(sorted(summary["decisionCounts"].items()))
        summary["scopeCounts"] = {
            scope: dict(sorted(counts.items()))
            for scope, counts in sorted(summary["scopeCounts"].items())
        }
        summary["schemaAudit"] = schema_audits.get(shard, {"status": "missing"})
        summary["sourceAudit"] = source_audits.get(shard, {"status": "missing"})

    priority = []
    for shard, summary in sorted(shard_summary.items(),
                                 key=lambda pair: (pair[1]["decisionCounts"].get("unresolved", 0), pair[0]),
                                 reverse=True):
        priority.append({
            "shard": shard,
            "unresolved": summary["decisionCounts"].get("unresolved", 0),
            "unresolvedWithExactWiki": summary["unresolvedDirectWiki"],
            "unresolvedWithTypedWikiCandidate": summary["unresolvedTypedWikiCandidate"],
            "unresolvedWithoutExactSourcePath": summary["unresolvedNoExactSource"],
            "schemaAudit": summary["schemaAudit"]["status"],
            "sourceAudit": summary["sourceAudit"]["status"],
        })
    report = {
        "status": "coverage gap report; schema/source integrity is not semantic certification",
        "universeCount": len(assignments),
        "hashes": {
            "currentCoverageSha256": sha256(coverage_path),
            "afterCoverageSha256": sha256(coverage_path.with_name("after-coverage.tsv")),
            "articleIndexSha256": sha256(article_index_path),
            "identityLinksSha256": sha256(identity_links_path),
            "decisionFilesSha256": {str(path): sha256(path) for path in sorted(set(decision_paths))},
        },
        "decisionCounts": dict(sorted(overall_counts.items())),
        "scopeDecisionCounts": {
            scope: dict(sorted(counts.items())) for scope, counts in sorted(scope_counts.items())
        },
        "shards": dict(sorted(shard_summary.items())),
        "priorityOrder": priority,
        "assignments": assignments,
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
                           encoding="utf-8")
    print(f"Wrote coverage gap report for {len(assignments)} exact IDs to {output_path}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    build_parser = sub.add_parser("build", help="write eight deterministic reviewer packets")
    build_parser.add_argument("--coverage", type=Path, default=DEFAULT_COVERAGE)
    build_parser.add_argument("--joined", type=Path, default=DEFAULT_JOINED)
    build_parser.add_argument("--output", type=Path, help="output path; default is a deterministic hash-versioned directory")
    validate_parser = sub.add_parser("validate", help="check packet accounting and decision schema; unresolved decisions are allowed")
    validate_parser.add_argument("--packets", type=Path, default=PACKET_OUTPUT_BASE)
    validate_parser.add_argument("--shard", choices=sorted(SHARDS), action="append", help="validate only these assigned shards")
    validate_parser.add_argument("decisions", nargs="+", type=Path)
    applied_parser = sub.add_parser("verify-applied", help="compare proposed classifications with a fresh compiled export")
    applied_parser.add_argument("--coverage", type=Path, required=True)
    applied_parser.add_argument("decisions", nargs="+", type=Path)
    complete_parser = sub.add_parser("complete", help="strictly require zero unresolved IDs, applied targets, and intact cited sources")
    complete_parser.add_argument("--packets", type=Path, default=PACKET_OUTPUT_BASE)
    complete_parser.add_argument("--coverage", type=Path, required=True)
    complete_parser.add_argument("--article-index", type=Path, default=DEFAULT_ARTICLE_INDEX)
    complete_parser.add_argument("--identity-links", type=Path, default=DEFAULT_IDENTITY_LINKS)
    complete_parser.add_argument("--identity-report", type=Path, default=DEFAULT_IDENTITY_REPORT)
    complete_parser.add_argument("decisions", nargs="+", type=Path)
    source_parser = sub.add_parser("audit-sources", help="verify source claims while unresolved rows remain")
    source_parser.add_argument("--packets", type=Path, default=PACKET_OUTPUT_BASE)
    source_parser.add_argument("--article-index", type=Path, default=DEFAULT_ARTICLE_INDEX)
    source_parser.add_argument("--identity-links", type=Path, default=DEFAULT_IDENTITY_LINKS)
    source_parser.add_argument("--identity-report", type=Path, default=DEFAULT_IDENTITY_REPORT)
    source_parser.add_argument("--shard", choices=sorted(SHARDS), action="append", help="audit only these assigned shards")
    source_parser.add_argument("decisions", nargs="+", type=Path)
    gaps_parser = sub.add_parser("gap-report", help="write a complete per-ID unresolved-work and audit report")
    gaps_parser.add_argument("--packets", type=Path, default=PACKET_OUTPUT_BASE)
    gaps_parser.add_argument("--coverage", type=Path, default=DEFAULT_COVERAGE)
    gaps_parser.add_argument("--article-index", type=Path, default=DEFAULT_ARTICLE_INDEX)
    gaps_parser.add_argument("--identity-links", type=Path, default=DEFAULT_IDENTITY_LINKS)
    gaps_parser.add_argument("--identity-report", type=Path, default=DEFAULT_IDENTITY_REPORT)
    gaps_parser.add_argument("--output", type=Path, required=True)
    gaps_parser.add_argument("decisions", nargs="+", type=Path)
    build_parser.add_argument("--article-index", type=Path, default=DEFAULT_ARTICLE_INDEX)
    build_parser.add_argument("--identity-links", type=Path, default=DEFAULT_IDENTITY_LINKS)
    build_parser.add_argument("--identity-report", type=Path, default=DEFAULT_IDENTITY_REPORT)
    args = parser.parse_args()
    if args.command == "build":
        build(args.coverage, args.joined, args.article_index, args.identity_links,
              args.identity_report, args.output)
    elif args.command == "validate":
        validate_decisions(args.packets, args.decisions, set(args.shard) if args.shard else None)
    elif args.command == "complete":
        complete_decisions(args.packets, args.coverage, args.article_index, args.identity_links,
                           args.identity_report, args.decisions)
    elif args.command == "audit-sources":
        audit_sources(args.packets, args.article_index, args.identity_links, args.identity_report,
                      args.decisions, set(args.shard) if args.shard else None)
    elif args.command == "gap-report":
        write_gap_report(args.packets, args.coverage, args.article_index, args.identity_links,
                         args.identity_report, args.decisions, args.output)
    else:
        verify_applied(args.coverage, args.decisions)


if __name__ == "__main__":
    main()
