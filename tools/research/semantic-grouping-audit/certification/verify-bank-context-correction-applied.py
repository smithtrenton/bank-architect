#!/usr/bin/env python3
"""Research draft: strict conditional verifier for selected bank-context corrections.

This is not installed in CERT and cannot grant approval. Trust is supplied by
an external, root-reviewed authorization object; simulation uses an explicitly
synthetic object in a temporary CERT copy.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import importlib.util
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[4]
PACKET = ROOT / "tmp/root-review/bank-context-next-applied-verifier-draft-v8-20261003"
CERT_LIVE = ROOT / "tools/research/semantic-grouping-audit/certification"
TYPED_CACHE_AUDIT_SHA256 = "2b3d26771dc30b68762de4591c2c783cb65ea3506fadcb070e9830cf40ddd189"
REQUALIFICATION_MANIFEST_SHA256 = "472e466507399815d1ac412ed3e259ef1736d524220579d18c70bcfe9acf3e69"
TYPED_AUDIT_GENERATOR_SHA256 = "9ef00e1f200f30e98238ae9718c63144e6f1121641d26f610ee2ec703ccf49d3"
TYPED_AUDIT_SUMMARY_SHA256 = "e3eb51640e5ff11abff0e90bb23438c9b9dc9c9e8f9621c62b2b2ac0a91b5faa"
IDENTITY_DECODER_SHA256 = "b713023ff2503776dedc2e9dab24c41c76d33746cea66d52d3faa6420845de80"
IDENTITY_POLICY_SHA256 = "fda424bfabf53dcf6aa7057548536752ab3c5af343172bd3fb9d74b10c151033"
CONFIG_INDEX_SHA256 = "b0db45d77e90f2097718a92542efe21bdc7b77bbe2f4665cbb087451c977c514"
CANDIDATE_PACKET_MANIFEST_SHA256 = "05cc62f03e59b953eb16aee3a00d42e236cb742f4053263e527820cfebd2a873"
ROOT_NATIVE_REPLAY_SCRIPT_SHA256 = "147207db9bc5282e3b580e3ba9d754d3e2e545620f423c811cd2b809840ef99b"
ROOT_NATIVE_REPLAY_MANIFEST_SHA256 = "4ce902009de5a6310ab44e477187f979a3e525570ec6f32cde9484fbcf5a5e58"
ROOT_NATIVE_REPLAY_OUTPUT_SHA256 = "98285c795c82477b151b8ab7e482e1c94e6d64177ac9ecf0391a3bdd22d1786d"
LEGACY_LEDGER_SHA256 = "65203f66527d6ab5eca27fb4747eebf7b9196aff8725dc32aaaddf82cbe98cc5"
NOTE_SELECTOR_SHA256 = "78db14d57746db5f1e1c1af89a943701abff3f344505efb6cf6aa70da2b61004"

RESOLVER_MANIFEST_SHA256 = "5bf83a50fab80e85b1b29c8e4f8d402891be3d1ee4ffc92eb3399e3ec42420c5"
RESOLVER_POOL_SHA256 = "be767a798d765aa27943003eef5d943d83a930e9fd94428e148184e9bfd5a2c6"
ROOT_NOTE_READING_MANIFEST_SHA256 = "8e0dce0e077932753ee96bb172ea47bdab0c99dd510361215a9b3b6a974375b9"
RAW_EXPORT_SHA256 = "8b9a60c88580187b4a4ae407aa5566897c01151bd62b9ada3f9c649a399c7318"
PRIMARY_DECISIONS_SHA256 = "dc0929e6ca8c87f8c30aa814ff72d4e9dd077163474ec9e0d8920e668b5f0a9a"
PRIMARY_ASSIGNMENTS_SHA256 = "8edd5bd90bfae6c1a886441a02089641505792f317ebb71245daa11652482041"
PRIMARY_CANDIDATE_MANIFEST_SHA256 = "e10ec8bf8b4abdc017cad787f39fbceab3631f7a388faa0e118b2bcd9f8f32e0"
PRIMARY_MANIFEST_SHA256 = "b85110c6e76a3e4c326158cd9b71ebbf7b177bc1a842805d21036d77fe7d03cf"
PRIMARY_POLICY_APPROVALS_SHA256 = "9332b9f8fb5603d02f4d087f626d54cb6150bcffb1631dcdca4af92fc252bb3a"
IDENTITY_ARCHIVE_SHA256 = "2fdcab1851e7509818b88cc89882c095687d41e87d07a8774adb121236705c4e"
IDENTITY_INDEX_SHA256 = "f3bf20b4dbe2ea90196ccfa3d642773e78e5d683316b5a2e75e08239f7ecd677"
CACHE_ARCHIVE_SHA256 = "65f803275575a512df896ed80ff806550a174b068bea2881b5257f138d597db7"
BANK_PAGE_SHA256 = "f3ac75d1f65f9e25d973f697d873605dd4068a837c8e7be63ea246309c7c0bd5"
BANK_NOTE_PAGE_SHA256 = "b32655b2b112d5704b55efc589839b848906f0c71122b70001123b67f9a08a94"
OLD_CONTEXT_POLICY_SHA256 = "1eba5665c39e89eb723190181746c6d6a3427f7f6c588818baf1d6ae8cfc9cfc"
OLD_CONTEXT_PIN_SHA256 = "443154bfddd3a1c7722d826596b8ce909bcf74af22dd336392f89be787691253"
OLD_CONTEXT_VERIFIER_SHA256 = "664ff5e74ca329a839cc56d30ff66254c04120ac8da5f98b4d434706437682d2"
PRIOR_1490_DECISIONS_SHA256 = "2b21eff03e136f84334ff8861fdaeff127571e9f9c1dfb31379af990b1c7f252"

GENERIC_BANK_LITERAL = (
    "Storing a note in a bank, selling it to a shop, or using it on a bank booth "
    "or banker will convert the note to its item equivalent."
)
NOTE_BANK_LITERAL = (
    "Storing a note in a bank, selling it to a shop, or 'using' it on a [[bank booth]], "
    "[[bank chest]], or [[banker]] will convert the note to its item equivalent."
)
PLACEHOLDER_BANK_LITERAL = (
    "Bank placeholders allow the player to reserve bank slots for specific items, "
    "giving them the ability to create a fixed layout for their bank."
)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def canonical(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
                                    separators=(",", ":")).encode("utf-8")).hexdigest()


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8-sig").splitlines() if line.strip()]


def fail(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def verify_packet_manifest(root_authorization_path: Path) -> str:
    """Validate every frozen/draft input before any packet helper is imported."""
    manifest_path = PACKET / "packet-manifest.json"
    authorization = read_json(root_authorization_path)
    expected_hash = authorization.get("packetManifestSha256")
    fail(isinstance(expected_hash, str) and sha(manifest_path) == expected_hash,
         "external root authorization does not pin the packet manifest bytes")
    manifest = read_json(manifest_path)
    fail(manifest.get("schema") == 1 and isinstance(manifest.get("files"), dict),
         "unknown or malformed packet manifest")
    listed = manifest["files"]
    for relative, expected_hash in listed.items():
        rel = Path(relative)
        fail(not rel.is_absolute() and ".." not in rel.parts,
             f"packet manifest contains unsafe path: {relative}")
        path = (PACKET / rel).resolve()
        fail(path.is_relative_to(PACKET.resolve()) and path.is_file(),
             f"packet manifest path escapes packet or is missing: {relative}")
        fail(not (PACKET / rel).is_symlink(), f"packet manifest path is a symlink: {relative}")
        fail(sha(path) == expected_hash, f"packet manifest artifact changed: {relative}")
    actual = set()
    for path in PACKET.rglob("*"):
        if not path.is_file():
            continue
        relative = path.relative_to(PACKET).as_posix()
        if relative == "packet-manifest.json" or relative.startswith("simulation/isolated-positive-"):
            continue
        if "__pycache__" in path.parts:
            continue
        actual.add(relative)
    fail(actual == set(listed), "packet file inventory differs from the pinned manifest")
    return expected_hash


def frozen_sources() -> dict[str, Path]:
    src = PACKET / "frozen/sources"
    return {
        "identityArchive": src / "tmp/category-certification/identity-links.jsonl",
        "identityReport": src / "tmp/category-certification/identity-report.json",
        "cacheArchive": src / "tmp/category-certification/runelite-index2-item-archive10.bin",
        "bankPage": src / "tmp/category-certification/identity-policy-sources/15359494.txt",
        "bankNotePage": src / "tmp/category-certification/wiki-articles/text/15337973.txt",
        "articleIndex": src / "article-index.json",
    }


def expected_source_pins() -> dict[str, str]:
    return {
        "resolverSuccessorManifestSha256": RESOLVER_MANIFEST_SHA256,
        "resolverCandidatePoolSha256": RESOLVER_POOL_SHA256,
        "rootNoteabilityReadingManifestSha256": ROOT_NOTE_READING_MANIFEST_SHA256,
        "rawExportSha256": RAW_EXPORT_SHA256,
        "primaryDecisionsSha256": PRIMARY_DECISIONS_SHA256,
        "primaryAssignmentsSha256": PRIMARY_ASSIGNMENTS_SHA256,
        "primaryManifestSha256": PRIMARY_MANIFEST_SHA256,
        "primaryCandidateManifestSha256": PRIMARY_CANDIDATE_MANIFEST_SHA256,
        "primaryPolicyApprovalsSha256": PRIMARY_POLICY_APPROVALS_SHA256,
        "identityArchiveSha256": IDENTITY_ARCHIVE_SHA256,
        "identityIndexSha256": IDENTITY_INDEX_SHA256,
        "cacheArchiveSha256": CACHE_ARCHIVE_SHA256,
        "bankPageSha256": BANK_PAGE_SHA256,
        "bankNotePageSha256": BANK_NOTE_PAGE_SHA256,
        "priorContextPolicySha256": OLD_CONTEXT_POLICY_SHA256,
        "priorContextApprovalPinSha256": OLD_CONTEXT_PIN_SHA256,
        "priorContextVerifierSha256": OLD_CONTEXT_VERIFIER_SHA256,
        "prior1490DecisionSnapshotSha256": PRIOR_1490_DECISIONS_SHA256,
        "genericLedgerSha256": LEGACY_LEDGER_SHA256,
        "exactNoteabilitySelectorSha256": NOTE_SELECTOR_SHA256,
        "typedCacheAuditSha256": TYPED_CACHE_AUDIT_SHA256,
        "typedCacheAuditInputManifestSha256": REQUALIFICATION_MANIFEST_SHA256,
        "typedAuditGeneratorSha256": TYPED_AUDIT_GENERATOR_SHA256,
        "typedAuditSummarySha256": TYPED_AUDIT_SUMMARY_SHA256,
        "identityDecoderSha256": IDENTITY_DECODER_SHA256,
        "identityPolicySha256": IDENTITY_POLICY_SHA256,
        "cacheConfigIndexSha256": CONFIG_INDEX_SHA256,
        "candidatePacketManifestSha256": CANDIDATE_PACKET_MANIFEST_SHA256,
        "rootNativeReplayScriptSha256": ROOT_NATIVE_REPLAY_SCRIPT_SHA256,
        "rootNativeReplayManifestSha256": ROOT_NATIVE_REPLAY_MANIFEST_SHA256,
        "rootNativeReplayOutputSha256": ROOT_NATIVE_REPLAY_OUTPUT_SHA256,
        "bankSnapshotReaderSha256": "9edfa96ea08a2db058a77e969ebace96adb271e887fc6d8938560ee1f25cb0be",
        "bankSnapshotSha256": "c020757491aed2f2fd42e5d9ac2ba6a99060d96e4c549ecba7591f04e4a1f093",
        "bankItemIdsSha256": "a6a21d2f3da98cf3b451f7ee99341cb62a71f4d4ca1c50d3fa06bd678d0eec98",
        "bankItemSnapshotSha256": "66d265c39aed08d42063e5d19c322badb3e6bc608c56eff3b57a3f7bf5f0e907",
    }


def verify_packet_inputs() -> tuple[list[dict[str, Any]], dict[int, dict[str, Any]], dict[int, dict[str, Any]], dict[int, dict[str, str]]]:
    resolver = PACKET / "frozen/resolver-successor"
    primary = PACKET / "frozen/primary-snapshot"
    export = PACKET / "frozen/raw-export/after-coverage-3840.tsv"
    fail(sha(resolver / "manifest.json") == RESOLVER_MANIFEST_SHA256, "resolver manifest pin mismatch")
    fail(sha(resolver / "strict-gate-candidate-tuples-2111.jsonl") == RESOLVER_POOL_SHA256, "resolver pool pin mismatch")
    fail(sha(PACKET / "frozen/noteability-root-reading/manifest.json") == ROOT_NOTE_READING_MANIFEST_SHA256,
         "root exact-noteability reading pin mismatch")
    fail(sha(export) == RAW_EXPORT_SHA256, "full raw export hash mismatch")
    fail(sha(primary / "candidate-decisions.jsonl") == PRIMARY_DECISIONS_SHA256, "primary decision snapshot hash mismatch")
    fail(sha(primary / "candidate-assignments.tsv") == PRIMARY_ASSIGNMENTS_SHA256, "primary assignments hash mismatch")
    fail(sha(primary / "candidate-manifest.json") == PRIMARY_CANDIDATE_MANIFEST_SHA256,
         "primary candidate manifest hash mismatch")
    published_manifest = PACKET / "frozen/resolver-inputs/docs/research/category-certification/approved-assignments-manifest.json"
    fail(sha(published_manifest) == PRIMARY_MANIFEST_SHA256, "published primary manifest hash mismatch")
    fail(sha(primary / "root-policy-approvals.json") == PRIMARY_POLICY_APPROVALS_SHA256, "primary policy pin hash mismatch")
    fail(sha(PACKET / "frozen/prior-1490/root-decisions-3683.jsonl") == PRIOR_1490_DECISIONS_SHA256,
         "prior 1,490 baseline hash mismatch")
    audit_dir = PACKET / "frozen/typed-cache-audit"
    audit_path = audit_dir / "candidate-edge-audit-2116.jsonl"
    audit_manifest_path = audit_dir / "requalification-manifest.json"
    generator_path = audit_dir / "audit.py"
    artifact_hashes_path = audit_dir / "artifact-hashes.json"
    audit_summary_path = audit_dir / "independent-audit-summary.json"
    candidate_manifest_path = audit_dir / "candidate-packet-manifest.json"
    fail(sha(audit_path) == TYPED_CACHE_AUDIT_SHA256 and
         sha(audit_manifest_path) == REQUALIFICATION_MANIFEST_SHA256,
         "independent raw-cache edge audit or its requalification manifest changed")
    fail(sha(generator_path) == TYPED_AUDIT_GENERATOR_SHA256 and
         sha(audit_dir / "identity.py") == IDENTITY_DECODER_SHA256 and
         sha(audit_dir / "identity-policy.json") == IDENTITY_POLICY_SHA256 and
         sha(audit_dir / "runelite-config-index-2.bin") == CONFIG_INDEX_SHA256 and
         sha(candidate_manifest_path) == CANDIDATE_PACKET_MANIFEST_SHA256,
         "raw-cache decoder, policy, config index, generator, or candidate input manifest changed")
    artifact_hashes = read_json(artifact_hashes_path)
    fail(artifact_hashes.get("audit.py") == TYPED_AUDIT_GENERATOR_SHA256 and
         artifact_hashes.get("candidate-edge-audit-2116.jsonl") == TYPED_CACHE_AUDIT_SHA256 and
         sha(audit_summary_path) == TYPED_AUDIT_SUMMARY_SHA256,
         "independent edge audit output/generator digest record changed")
    identity_policy = read_json(audit_dir / "identity-policy.json")
    cache_inputs = identity_policy.get("inputs", {}).get("cache", {})
    fail(cache_inputs.get("frozenItemArchive", {}).get("sha256") == CACHE_ARCHIVE_SHA256 and
         cache_inputs.get("frozenConfigIndex", {}).get("sha256") == CONFIG_INDEX_SHA256 and
         cache_inputs.get("configIndexRevision") == 1790690697 and
         cache_inputs.get("itemArchiveRevision") == 1790689442,
         "identity policy does not bind the decoded cache/config bytes and revisions")
    audit_summary = read_json(audit_summary_path)
    cache_summary = audit_summary.get("cacheDecode", {})
    fail(cache_summary.get("archiveSha256") == CACHE_ARCHIVE_SHA256 and
         cache_summary.get("configIndexSha256") == CONFIG_INDEX_SHA256 and
         cache_summary.get("indexRevision") == 1790690697 and
         cache_summary.get("itemArchiveRevision") == 1790689442 and
         cache_summary.get("decodedArchiveEdgesMatchingIdentityLinks") == 14324 and
         cache_summary.get("archiveEdgesOnlyFromCurrentCoverage") == 0,
         "independent decoder summary does not reconcile cache/archive outputs")
    candidate_manifest = read_json(candidate_manifest_path)
    expected_candidate_inputs = {
        "tools/research/semantic-grouping-audit/certification/identity-policy.json": IDENTITY_POLICY_SHA256,
        "tmp/category-certification/runelite-index2-item-archive10.bin": CACHE_ARCHIVE_SHA256,
        "tmp/category-certification/identity-links.jsonl": IDENTITY_ARCHIVE_SHA256,
        "tmp/category-certification/wiki-articles/article-index.json": IDENTITY_INDEX_SHA256,
    }
    fail(all(candidate_manifest.get("inputHashes", {}).get(name) == value
             for name, value in expected_candidate_inputs.items()),
         "raw-cache audit candidate manifest does not bind all decoder inputs")
    upstream_manifest = read_json(audit_manifest_path)
    fail(upstream_manifest.get("inputPins", {}).get(
        "tmp/root-review/bank-context-next-independent-20261003/candidate-edge-audit-2116.jsonl") ==
         TYPED_CACHE_AUDIT_SHA256,
         "requalification manifest does not bind the independent raw-cache audit bytes")
    native_dir = audit_dir / "root-native-replay"
    native_script = native_dir / "replay_bank_edges_root_20261004.py"
    native_manifest_path = native_dir / "manifest.json"
    native_edges_path = native_dir / "selected-decoded-edges-2096.jsonl"
    fail(sha(native_script) == ROOT_NATIVE_REPLAY_SCRIPT_SHA256 and
         sha(native_manifest_path) == ROOT_NATIVE_REPLAY_MANIFEST_SHA256 and
         sha(native_edges_path) == ROOT_NATIVE_REPLAY_OUTPUT_SHA256,
         "root native 2,096-edge cache replay files changed")
    native_manifest = read_json(native_manifest_path)
    native_expected_inputs = {
        "tools/research/semantic-grouping-audit/certification/identity.py": IDENTITY_DECODER_SHA256,
        "tools/research/semantic-grouping-audit/certification/identity-policy.json": IDENTITY_POLICY_SHA256,
        "tmp/category-certification/runelite-index2-item-archive10.bin": CACHE_ARCHIVE_SHA256,
        "tmp/category-certification/runelite-config-index-2.bin": CONFIG_INDEX_SHA256,
        "tmp/category-certification/identity-links.jsonl": IDENTITY_ARCHIVE_SHA256,
        "tmp/root-review/bank-context-next-independent-20261003/candidate-edge-audit-2116.jsonl": TYPED_CACHE_AUDIT_SHA256,
        "tmp/root-review/bank-context-next-independent-20261003/cache-edge-difference-set.jsonl": "f32799b656b245e7986764bbde41c914a4550981c1f46a97519ed22c06bca9fd",
        "tmp/category-certification/after-coverage.tsv": RAW_EXPORT_SHA256,
        "tmp/root-review/bank-context-gear3840-noteability-resolver-successor-20261003/strict-gate-candidate-tuples-2111.jsonl": RESOLVER_POOL_SHA256,
    }
    fail(native_manifest.get("inputs") == native_expected_inputs and
         native_manifest.get("scriptSha256") == ROOT_NATIVE_REPLAY_SCRIPT_SHA256 and
         native_manifest.get("outputSha256") == ROOT_NATIVE_REPLAY_OUTPUT_SHA256 and
         native_manifest.get("selectedCorrectionRows") == 2096 and
         native_manifest.get("samePlacementRowsPreserved") == 15,
         "root native replay manifest does not bind the exact selected pool and source inputs")
    pins = expected_source_pins()
    src = frozen_sources()
    for key, path_key in (("identityArchiveSha256", "identityArchive"),
                          ("identityIndexSha256", "articleIndex"),
                          ("cacheArchiveSha256", "cacheArchive"),
                          ("bankPageSha256", "bankPage"),
                          ("bankNotePageSha256", "bankNotePage")):
        fail(sha(src[path_key]) == pins[key], f"frozen source changed: {path_key}")
    live_runtime_sources = {
        "bankSnapshotReaderSha256": ROOT / "src/main/java/com/pkoka5/ironmanbankarchitect/bank/BankSnapshotReader.java",
        "bankSnapshotSha256": ROOT / "src/main/java/com/pkoka5/ironmanbankarchitect/bank/BankSnapshot.java",
        "bankItemIdsSha256": ROOT / "src/main/java/com/pkoka5/ironmanbankarchitect/bank/BankItemIds.java",
        "bankItemSnapshotSha256": ROOT / "src/main/java/com/pkoka5/ironmanbankarchitect/bank/BankItemSnapshot.java",
    }
    for key, path in live_runtime_sources.items():
        frozen = PACKET / "frozen/runtime-sources/bank" / path.name
        fail(sha(frozen) == pins[key] and sha(path) == pins[key],
             f"observed-bank row runtime source changed: {path.name}")

    assignments: dict[int, dict[str, str]] = {}
    with (primary / "candidate-assignments.tsv").open(encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f, delimiter="\t"):
            item_id = int(row["itemId"])
            fail(item_id not in assignments, f"duplicate assignment row {item_id}")
            assignments[item_id] = row
    decisions_rows = read_jsonl(primary / "candidate-decisions.jsonl")
    decisions = {int(row["itemId"]): row for row in decisions_rows}
    fail(len(decisions_rows) == len(decisions) == 34085, "primary decisions are not a complete unique 34,085-ID snapshot")
    fail(set(assignments) == set(decisions) and len(assignments) == 34085,
         "primary decision/assignment ID universes differ")
    with export.open(encoding="utf-8-sig", newline="") as f:
        current_rows = list(csv.DictReader(f, delimiter="\t"))
    current = {int(row["itemId"]): row for row in current_rows}
    fail(len(current_rows) == len(current) == 34085, "raw export is not a complete unique 34,085-ID set")
    fail(set(current) == set(decisions), "raw export and decision ID universes differ")
    return read_jsonl(resolver / "strict-gate-candidate-tuples-2111.jsonl"), decisions, current, assignments


def verify_prior_1490(current_decisions: dict[int, dict[str, Any]]) -> None:
    old = {int(row["itemId"]): row for row in read_jsonl(PACKET / "frozen/prior-1490/root-decisions-3683.jsonl")}
    ids = {item_id for item_id, row in old.items() if "rootBankContextApproval" in row}
    new_ids = {item_id for item_id, row in current_decisions.items() if "rootBankContextApproval" in row}
    fail(len(ids) == len(new_ids) == 1490, "prior context cohort count changed")
    fail(all(old[item_id] == current_decisions[item_id] for item_id in ids),
         "one or more of the prior 1,490 decision objects changed")
    for name, expected in (("bank-context-placement-approved-policy.json", OLD_CONTEXT_POLICY_SHA256),
                           ("bank-context-placement-approvals.json", OLD_CONTEXT_PIN_SHA256),
                           ("verify-bank-context-placement.py", OLD_CONTEXT_VERIFIER_SHA256)):
        fail(sha(PACKET / "frozen/prior-1490" / name) == expected, f"frozen prior context pin changed: {name}")
        fail(sha(CERT_LIVE / name) == expected, f"live prior context pin changed before import: {name}")

    live_verifier = CERT_LIVE / "verify-bank-context-placement.py"
    live_ledger = CERT_LIVE / "ledger.py"
    frozen_ledger = PACKET / "frozen/prior-1490/ledger.py"
    fail(sha(live_verifier) == OLD_CONTEXT_VERIFIER_SHA256,
         "live legacy bank-context verifier changed before import")
    fail(sha(live_ledger) == LEGACY_LEDGER_SHA256 and sha(frozen_ledger) == LEGACY_LEDGER_SHA256,
         "live or frozen generic ledger changed before import")

    # Run the unchanged legacy verifier independently; it still owns all 1,490
    # prior conditional cases and never receives the new correction allowlist.
    spec = importlib.util.spec_from_file_location("legacy_bank_context_verifier",
        live_verifier)
    fail(spec is not None and spec.loader is not None, "cannot load prior context verifier")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    policy, cases, _, _ = module.verify()
    fail(len(cases) == len(policy["cases"]) == 1490, "legacy verifier no longer validates exactly 1,490 cases")


def case_map(pool: list[dict[str, Any]]) -> tuple[dict[int, dict[str, Any]], list[dict[str, Any]]]:
    by_id = {int(row["itemId"]): row for row in pool}
    fail(len(by_id) == len(pool) == 2111, "resolver pool does not have 2,111 unique alias IDs")
    corrections = [row for row in pool if row.get("candidateDisposition") == "route-correction-candidate"]
    same = [row for row in pool if row.get("candidateDisposition") == "same-assignment-candidate"]
    fail(len(corrections) == 2096 and len(same) == 15, "resolver route partition differs from 2,096 corrections / 15 same")
    fail(Counter(row["relation"] for row in corrections) == {"NOTE_VARIANT_OF": 778, "PLACEHOLDER_FOR": 1318},
         "correction relation counts differ")
    fail(Counter(row["relation"] for row in same) == {"NOTE_VARIANT_OF": 7, "PLACEHOLDER_FOR": 8},
         "same-placement relation counts differ")
    return by_id, corrections


def expected_cases(corrections: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [{"itemId": int(row["itemId"]), "targetItemId": int(row["targetItemId"]), "relation": row["relation"]}
            for row in sorted(corrections, key=lambda value: int(value["itemId"]))]


def load_edge_archive() -> tuple[dict[int, list[dict[str, Any]]], dict[int, set[int]]]:
    edges: dict[int, list[dict[str, Any]]] = defaultdict(list)
    graph: dict[int, set[int]] = defaultdict(set)
    for edge in read_jsonl(frozen_sources()["identityArchive"]):
        source = int(edge["fromItemId"])
        edges[source].append(edge)
        if edge.get("relation") in {"NOTE_VARIANT_OF", "PLACEHOLDER_FOR"}:
            graph[source].add(int(edge["toItemId"]))
    return edges, graph


def has_cycle(source: int, target: int, graph: dict[int, set[int]]) -> bool:
    pending = [target]
    visited: set[int] = set()
    while pending:
        node = pending.pop()
        if node == source:
            return True
        if node not in visited:
            visited.add(node)
            pending.extend(graph.get(node, ()))
    return False


def check_policy(policy_path: Path, pin_path: Path, root_authorization_path: Path, *,
                 allow_synthetic: bool = False,
                 emitted_decisions: dict[int, dict[str, Any]] | None = None) -> tuple[dict[str, Any], dict[str, Any], list[dict[str, Any]], list[dict[str, Any]]]:
    packet_manifest_hash = verify_packet_manifest(root_authorization_path)
    pool, decisions, current, assignments = verify_packet_inputs()
    verify_prior_1490(decisions)
    pool_by_id, corrections = case_map(pool)
    typed_audit_rows = read_jsonl(PACKET / "frozen/typed-cache-audit/candidate-edge-audit-2116.jsonl")
    typed_audit = {int(row["itemId"]): row for row in typed_audit_rows}
    resolved_all_rows = read_jsonl(PACKET / "frozen/resolver-successor/resolved-noteability-all-2116.jsonl")
    resolved_all = {int(row["itemId"]): row for row in resolved_all_rows}
    fail(len(typed_audit_rows) == len(typed_audit) == len(resolved_all_rows) == len(resolved_all) == 2116 and
         set(typed_audit) == set(resolved_all) and set(pool_by_id).issubset(set(typed_audit)),
         "independent raw-cache edge audit/resolver rows do not cover the exact 2,116 source cohort")
    unselected_ids = set(typed_audit) - set(pool_by_id)
    fail(len(unselected_ids) == 5 and all(resolved_all[item_id].get("relation") == "NOTE_VARIANT_OF" and
         resolved_all[item_id].get("resolvedExactSource", {}).get("state") == "unknown" for item_id in unselected_ids),
         "the five nonselectable source-unknown NOTE edges changed or entered the selectable pool")
    native_edge_rows = read_jsonl(PACKET / "frozen/typed-cache-audit/root-native-replay/selected-decoded-edges-2096.jsonl")
    native_edges = {int(row["itemId"]): row for row in native_edge_rows}
    fail(len(native_edge_rows) == len(native_edges) == 2096,
         "root native decoded-edge output is not 2,096 unique selected aliases")
    policy = read_json(policy_path)
    pin = read_json(pin_path)
    authorization = read_json(root_authorization_path)
    if allow_synthetic:
        fail(policy.get("status") == "simulation-only synthetic policy; grants no approval",
             "synthetic policy lacks explicit simulation-only status")
        fail(pin.get("status") == "simulation-only synthetic approval pin; grants no approval",
             "synthetic pin lacks explicit simulation-only status")
        fail(authorization.get("status") == "simulation-only synthetic root authorization; grants no approval",
             "synthetic root authorization lacks explicit simulation-only status")
    else:
        fail(root_authorization_path.resolve() == (CERT_LIVE / "bank-context-corrections-root-authorization.json").resolve(),
             "official verification accepts only the root-installed authorization path")
        fail(authorization.get("status") == "root-reviewed exact bank-context correction authorization",
             "external root authorization is absent or not reviewed")
        fail(policy.get("status") == "root-reviewed conditional canonical correction placement only",
             "policy is not root-approved for conditional correction placement")
        fail(pin.get("status") == "root-reviewed conditional bank-context correction pin",
             "approval pin is not root-reviewed")

    fail(policy.get("schema") == "root-approved-bank-context-corrections/v1", "unknown correction policy schema")
    fail(policy.get("axis") == "bank-context.canonical-primary-placement", "wrong policy axis")
    fail(policy.get("assignmentScope") == "conditional canonical target placement only", "wrong assignment scope")
    fail(policy.get("unassessedDimensions") == ["raw-functions", "tag-meaning", "supplemental-roles",
          "availability", "tradeability", "acquisition", "depositability", "bankability"],
         "policy widens or changes the unassessed-dimension boundary")
    expected = expected_cases(corrections)
    fail(policy.get("cases") == expected, "policy case list is not the exact frozen correction set")
    approved = pin.get("approvedPolicy", {})
    fail(approved.get("name") == policy_path.name, "approval pin policy filename mismatch")
    fail(approved.get("sha256") == sha(policy_path), "approval pin policy byte hash mismatch")
    fail(approved.get("canonicalSha256") == canonical(policy), "approval pin policy canonical hash mismatch")
    fail(approved.get("caseCount") == len(expected) == 2096, "approval pin case count mismatch")
    fail(approved.get("approvedItemIds") == sorted(case["itemId"] for case in expected),
         "approval pin exact approved ID list mismatch")
    fail(pin.get("verifierSha256") == sha(Path(__file__)), "approval pin verifier hash mismatch")
    fail(pin.get("sourcePins") == expected_source_pins(), "approval pin source hash map mismatch")
    authorized = authorization.get("authorizedBankContextCorrections")
    fail(isinstance(authorized, dict), "external root authorization payload is missing")
    expected_authorization = {
        "policyFile": policy_path.name,
        "policySha256": sha(policy_path),
        "policyCanonicalSha256": canonical(policy),
        "approvalFile": pin_path.name,
        "approvalSha256": sha(pin_path),
        "verifierSha256": sha(Path(__file__)),
        "caseCount": 2096,
        "approvedItemIds": sorted(case["itemId"] for case in expected_cases(case_map(verify_packet_inputs()[0])[1])),
        "sourcePins": expected_source_pins(),
    }
    fail(authorized == expected_authorization,
         "external root authorization does not exactly bind policy, pin, verifier, IDs and sources: " +
         repr([key for key, value in expected_authorization.items() if authorized.get(key) != value]))
    required_approval = {
        "bank-context-corrections-approved-policy.json": sha(policy_path),
        pin_path.name: sha(pin_path),
        "verify-bank-context-correction-applied.py": sha(Path(__file__)),
    }

    index = read_json(PACKET / "frozen/sources/article-index.json")
    edges, graph = load_edge_archive()
    note_selector = _load_note_selector()
    bank_page = frozen_sources()["bankPage"].read_text(encoding="utf-8-sig")
    bank_note_page = frozen_sources()["bankNotePage"].read_text(encoding="utf-8-sig")
    fail(GENERIC_BANK_LITERAL in bank_page, "pinned Bank transformation literal is missing")
    fail(NOTE_BANK_LITERAL in bank_note_page, "pinned Bank note transformation literal is missing")
    fail(PLACEHOLDER_BANK_LITERAL in bank_page, "pinned Bank placeholder literal is missing")
    fail(pin.get("prior1490DecisionCount") == 1490, "approval pin does not preserve the prior 1,490 cohort")
    fail(pin.get("currentExclusionCount") == 707, "approval pin does not preserve 707 exclusions")

    # The target map/policy route is derived from the pinned 3,840 primary
    # decision snapshot. Each target must have its own exact policy case and
    # detached policy hash, even for older policies without a serialized scope
    # marker. This correction policy contributes primary placement only.
    root_approvals = read_json(PACKET / "frozen/primary-snapshot/root-policy-approvals.json")["approvedPolicies"]
    policy_cases: dict[str, dict[int, list[dict[str, Any]]]] = {}
    verified_context_ids: set[int] = set()
    for case in expected:
        item_id, target_id, relation = case["itemId"], case["targetItemId"], case["relation"]
        row = pool_by_id[item_id]
        raw_cache_row = typed_audit[item_id]
        native_edge = native_edges.get(item_id)
        fail(raw_cache_row.get("candidateId") == row.get("candidateId") and
             int(raw_cache_row.get("targetItemId", -1)) == target_id and
             raw_cache_row.get("relation") == relation,
             f"item {item_id}: independently decoded audit edge does not match exact alias/target/relation")
        fail(isinstance(native_edge, dict) and int(native_edge.get("targetItemId", -1)) == target_id and
             native_edge.get("relation") == relation and
             int(native_edge.get("decodedEdge", {}).get("fromItemId", -1)) == item_id and
             int(native_edge.get("decodedEdge", {}).get("toItemId", -1)) == target_id and
             native_edge.get("decodedEdge", {}).get("relation") == relation and
             native_edge.get("decodedEdge", {}).get("cacheField") == row["typedCacheEvidence"]["cacheField"] and
             native_edge.get("decodedEdge", {}).get("cacheOpcode") == row["typedCacheEvidence"]["cacheOpcode"],
             f"item {item_id}: root native cache replay does not match exact selected edge")
        alias = current[item_id]
        target = current[target_id]
        alias_route = {"category": alias["itemCategory"], "subcategory": alias["subcategory"],
                       "ironmanTabKey": alias["ironmanTabKey"]}
        target_route = {"category": target["itemCategory"], "subcategory": target["subcategory"],
                        "ironmanTabKey": target["ironmanTabKey"]}
        fail(target_route == {"category": row["proposedCategory"], "subcategory": row["proposedSubcategory"],
              "ironmanTabKey": row["proposedIronmanTabKey"]}, f"item {item_id}: pool target route differs from raw export")
        fail(alias_route != target_route, f"item {item_id}: same-placement alias improperly selected as correction")
        fail(alias["auditScope"] not in {"EXCLUDED_NON_BANKABLE", "SUPPLEMENTAL"},
             f"item {item_id}: alias is excluded or supplemental")
        fail(decisions[item_id]["decision"] == "unresolved", f"item {item_id}: alias is not unresolved in pinned primary snapshot")
        fail(decisions[target_id]["decision"] in {"certify", "revise"}, f"target {target_id} lacks its own primary action")
        target_decision = decisions[target_id]
        decision_route = {"category": target_decision.get("proposedCategory"),
                          "subcategory": target_decision.get("proposedSubcategory"),
                          "ironmanTabKey": target_decision.get("proposedIronmanTabKey")}
        fail(decision_route == target_route, f"target {target_id} published action/TSV routes differ")
        approval = target_decision.get("rootApproval")
        fail(isinstance(approval, dict), f"target {target_id} has no own root primary approval record")
        policy_name = approval.get("policyFile")
        policy_pin = root_approvals.get(policy_name)
        fail(isinstance(policy_pin, dict) and policy_pin.get("sha256") == approval.get("policySha256"),
             f"target {target_id} primary policy approval pin mismatch")
        fail(target_id in {int(value) for value in policy_pin.get("approvedItemIds", [])},
             f"target {target_id} is not in the detached primary policy ID set")
        fail(approval.get("policySourceRevision") == target_decision.get("evidence", [{}])[0].get("sourceRevision") or
             approval.get("policySourceRevision") is not None,
             f"target {target_id} approval has no pinned source revision")
        policy_file = PACKET / "frozen/primary-snapshot/policies" / str(policy_name)
        fail(sha(policy_file) == approval["policySha256"], f"target {target_id} primary policy bytes changed")
        if policy_name not in policy_cases:
            body = read_json(policy_file)
            by_item: dict[int, list[dict[str, Any]]] = defaultdict(list)
            for policy_case in body.get("cases", []):
                by_item[int(policy_case["itemId"])].append(policy_case)
            policy_cases[policy_name] = by_item
        target_policy_cases = policy_cases[policy_name].get(target_id, [])
        fail(len(target_policy_cases) == 1, f"target {target_id} does not have one exact primary policy case")
        target_policy_case = target_policy_cases[0]
        for field, value in (("proposedCategory", target_route["category"]),
                             ("proposedSubcategory", target_route["subcategory"])):
            fail(target_policy_case.get(field) == value, f"target {target_id} policy route differs at {field}")
        if "proposedIronmanTabKey" in target_policy_case:
            fail(target_policy_case["proposedIronmanTabKey"] == target_route["ironmanTabKey"],
                 f"target {target_id} policy tab differs")

        target_evidence = row["targetWikiEvidence"]
        fail(int(target_evidence["itemId"]) == target_id and target_id in {int(x) for x in target_evidence["exactInfoboxItemIds"]},
             f"target {target_id} lacks exact Wiki ID membership")
        fail(target_evidence["sourceIndexHash"] == IDENTITY_INDEX_SHA256, f"target {target_id} article index hash changed")
        title = target_evidence["sourceTitle"]
        article = index.get(title)
        fail(isinstance(article, dict), f"target {target_id} source title is absent from the pinned index")
        fail(int(article["revid"]) == int(target_evidence["sourceRevision"]) and
             article["sha256"] == target_evidence["verifiedBodySha256"], f"target {target_id} page/index pins differ")
        fail(approval.get("policySourceTitle") == title and
             int(approval.get("policySourceRevision", -1)) == int(target_evidence["sourceRevision"]) and
             approval.get("policySourceSha256") == target_evidence["verifiedBodySha256"],
             f"target {target_id} primary approval does not bind its direct exact Wiki source")
        exact_fact_params = target_evidence["sourceRecord"]["params"]
        for fact in approval.get("exactVariantFacts", []):
            fail(exact_fact_params.get(fact["field"]) == fact["value"],
                 f"target {target_id} primary exact fact differs from own Wiki field {fact['field']}")
        page = PACKET / "frozen/sources/target-3840-pages" / f"{target_evidence['sourceRevision']}.txt"
        fail(sha(page) == target_evidence["verifiedBodySha256"], f"target {target_id} source page hash mismatch")
        target_page_text = page.read_text(encoding="utf-8-sig")
        quote_lines = [line for line in target_evidence.get("quote", "").splitlines() if line.strip()]
        fail(bool(quote_lines) and all(line in target_page_text for line in quote_lines),
             f"target {target_id}: exact target ID quote is absent from its pinned page")
        target_record = target_evidence.get("sourceRecord", {})
        target_params = target_record.get("params", {})
        target_suffix = str(target_record.get("suffix", ""))
        target_id_key = f"id{target_suffix}" if f"id{target_suffix}" in target_params else "id"
        target_id_value = target_params.get(target_id_key)
        target_id_fields = re.findall(rf"(?m)^[ \t]*\|[ \t]*{re.escape(target_id_key)}[ \t]*=[ \t]*(.*?)[ \t]*$",
                                      target_page_text)
        fail(isinstance(target_id_value, str) and
             [value.strip() for value in target_id_fields].count(target_id_value.strip()) == 1,
             f"target {target_id}: selected ID parameter does not match its literal page field")
        target_id_tokens = [value.strip() for value in target_id_value.split(",")]
        fail(all(value.isdigit() for value in target_id_tokens) and
             target_id_tokens.count(str(target_id)) == 1 and len(set(target_id_tokens)) == len(target_id_tokens),
             f"target {target_id}: selected ID parameter does not establish exactly one target membership")

        matching = [edge for edge in edges.get(item_id, [])
                    if edge.get("relation") in {"NOTE_VARIANT_OF", "PLACEHOLDER_FOR", "BOUGHT_VARIANT_OF"}]
        fail(len(matching) == 1, f"item {item_id}: ambiguous, bought, or extra canonical edges")
        edge = matching[0]
        fail(edge["relation"] == relation and int(edge["toItemId"]) == target_id,
             f"item {item_id}: frozen typed edge disagrees with policy case")
        fail(not has_cycle(item_id, target_id, graph), f"item {item_id}: typed identity path is cyclic")
        typed = row["typedCacheEvidence"]
        independent_edge = typed_audit[item_id].get("typedCacheEdge", {})
        actual_cache = independent_edge.get("actual", {})
        packet_cache = independent_edge.get("packet", {})
        fail(independent_edge.get("matchesFrozenArchive") is True and
             independent_edge.get("actualArchiveEdgeCount") == 1,
             f"item {item_id}: independent raw-cache decode does not establish exactly one archived edge")
        fail(all(actual_cache.get(key) == typed.get(key) for key in
                 ("fromItemId", "toItemId", "relation", "cacheField", "cacheOpcode")) and
             packet_cache == typed,
             f"item {item_id}: independent raw-cache audit does not match the exact typed packet edge")
        actual_typed = [e for e in edge.get("evidence", []) if e.get("kind") == "typed_identity"]
        fail(len(actual_typed) == 1, f"item {item_id}: exact typed cache evidence is missing or ambiguous")
        typed_fields = ("fromItemId", "toItemId", "relation", "cacheField", "cacheOpcode",
                        "sourcePath", "sourceHash", "sourceRevision", "configIndexRevision")
        fail(all(actual_typed[0].get(key) == typed.get(key) for key in typed_fields),
             f"item {item_id}: typed cache evidence differs from the frozen archive")
        fail(typed.get("identityIndexHash") == IDENTITY_ARCHIVE_SHA256,
             f"item {item_id}: identity index source pin mismatch")
        fail(int(typed["fromItemId"]) == item_id and int(typed["toItemId"]) == target_id and
             typed["relation"] == relation, f"item {item_id}: typed edge endpoint mismatch")
        if relation == "NOTE_VARIANT_OF":
            resolved = row["resolvedExactSource"]
            note_record = {"suffix": resolved["sourceRecordSuffix"], "params": resolved["sourceRecordParams"],
                           "sourceRecordIdKey": resolved["sourceRecordIdKey"]}
            note_page = PACKET / "frozen/sources/exact-noteability" / f"{resolved['sourceRevision']}.txt"
            fail(sha(note_page) == resolved["sourceSha256"], f"item {item_id}: exact noteability source hash mismatch")
            fail(resolved.get("sourceIndexHash") == IDENTITY_INDEX_SHA256 and
                 resolved.get("sourceTitle") == target_evidence["sourceTitle"] and
                 int(resolved.get("sourceRevision", -1)) == int(target_evidence["sourceRevision"]) and
                 resolved.get("sourceSha256") == target_evidence["verifiedBodySha256"],
                 f"item {item_id}: selected note source is not the target's exact indexed page")
            fail(int(resolved.get("selectedInfoboxItemId", -1)) == target_id and
                 resolved.get("exactInfoboxItemIdListMatchesTarget") is True and
                 resolved.get("selectedRecordIdMatchesTarget") is True,
                 f"item {item_id}: selected record ID state is not bound to target")
            exact_article = index.get(resolved["sourceTitle"])
            fail(isinstance(exact_article, dict) and
                 int(exact_article.get("revid", -1)) == int(resolved["sourceRevision"]) and
                 exact_article.get("sha256") == resolved["sourceSha256"] and
                 target_id in {int(value) for value in exact_article.get("requestedItemIds", [])},
                 f"item {item_id}: selected source page/index exact ID binding mismatch")
            state, field_key = note_selector.selected_noteability(target_id, note_record,
                note_page.read_text(encoding="utf-8-sig"), resolved["sourceRecordIdKey"])
            fail(state == "Yes" and state == resolved["state"] and field_key == resolved["fieldKey"],
                 f"item {item_id}: exact selected target noteability is not explicit Yes")
        else:
            fail(relation == "PLACEHOLDER_FOR", f"item {item_id}: unknown context relation")

        bank_pin = row["bankTransformationSourcePin"]
        if relation == "NOTE_VARIANT_OF":
            fail(bank_pin["title"] == "Bank note" and bank_pin["bodySha256"] == BANK_NOTE_PAGE_SHA256,
                 f"item {item_id}: Bank note conversion pin mismatch")
            source_literal = NOTE_BANK_LITERAL
        else:
            fail(bank_pin["title"] == "Bank" and bank_pin["bodySha256"] == BANK_PAGE_SHA256,
                 f"item {item_id}: Bank placeholder source pin mismatch")
            source_literal = PLACEHOLDER_BANK_LITERAL
        fail(source_literal in (bank_note_page if relation == "NOTE_VARIANT_OF" else bank_page),
             f"item {item_id}: exact generic bank operation source text missing")

        fail(emitted_decisions is not None and item_id in emitted_decisions,
             f"item {item_id}: emitted full decision output is missing")
        current_decision = emitted_decisions[item_id]
        fail(item_id not in verified_context_ids, f"duplicate context correction {item_id}")
        verified_context_ids.add(item_id)
        base_decision = decisions[item_id]
        mutable_fields = {
            "decision", "proposedCategory", "proposedSubcategory", "proposedIronmanTabKey",
            "proposedTags", "proposedRoles", "assignmentClaimScope", "rawItemFunctionClaimScope",
            "roleClaimScope", "availabilityClaimScope", "tradeabilityClaimScope", "acquisitionClaimScope",
            "depositabilityClaimScope", "bankabilityClaimScope", "rootBankContextApproval",
            "approvedCanonicalBase", "identityLinks", "evidence", "rationale", "semanticPredicate",
        }
        fail(set(current_decision) == set(base_decision) | mutable_fields,
             f"item {item_id}: decision keys differ from the exact approved field set")
        fail(all(current_decision.get(key) == value for key, value in base_decision.items()
                 if key not in mutable_fields),
             f"item {item_id}: nonmutable base decision fields changed")
        fail(current_decision.get("decision") == "revise", f"item {item_id}: correction is not marked revise")
        fail({"category": current_decision.get("proposedCategory"),
              "subcategory": current_decision.get("proposedSubcategory"),
              "ironmanTabKey": current_decision.get("proposedIronmanTabKey")} == target_route,
             f"item {item_id}: corrected route is not the exact approved target route")
        raw_tags = sorted(tag for tag in alias.get("tags", "").split(",") if tag)
        fail(sorted(current_decision.get("proposedTags", [])) == raw_tags,
             f"item {item_id}: tags were not preserved exactly from the raw alias")
        fail(current_decision.get("proposedRoles") is None, f"item {item_id}: target roles were inherited")
        fail(current_decision.get("assignmentClaimScope") == "conditional canonical target placement only",
             f"item {item_id}: assignment scope is not conditional primary placement")
        for field in ("rawItemFunctionClaimScope", "roleClaimScope", "availabilityClaimScope",
                      "tradeabilityClaimScope", "acquisitionClaimScope", "depositabilityClaimScope",
                      "bankabilityClaimScope"):
            fail(current_decision.get(field) == "unassessed", f"item {item_id}: {field} was approved or omitted")
        fail(current_decision.get("rootBankContextApproval") == required_approval,
             f"item {item_id}: detached context approval binding mismatch")
        base = current_decision.get("approvedCanonicalBase")
        fail(isinstance(base, dict) and base.get("itemId") == target_id and
             base.get("decision") == target_decision["decision"] and
             base.get("frozenSnapshotSha256") == PRIMARY_DECISIONS_SHA256 and
             base.get("frozenDecisionSha256") == canonical(target_decision) and
             base.get("route") == target_route and
             base.get("policyFile") == policy_name and base.get("policySha256") == approval["policySha256"],
             f"item {item_id}: target primary approval chain is not pinned in the case proof")
        links = current_decision.get("identityLinks", [])
        fail(len(links) == 1, f"item {item_id}: expected one exact identity proof link")
        link = links[0]
        fail(link.get("fromItemId") == item_id and link.get("itemId") == target_id and
             link.get("toItemId") == target_id and link.get("relation") == relation,
             f"item {item_id}: decision identity link has wrong endpoints or relation")
        link_evidence = link.get("evidence", [])
        fail(any(e.get("kind") == "typed_identity" and
                 all(e.get(key) == typed.get(key) for key in typed_fields) for e in link_evidence),
             f"item {item_id}: decision omits the approved exact typed edge")
        fail(any(e.get("kind") == "exact_wiki" and e.get("itemId") == target_id and
                 e.get("sourceHash") == target_evidence["verifiedBodySha256"] and
                 target_id in {int(v) for v in e.get("exactInfoboxItemIds", [])} for e in link_evidence),
             f"item {item_id}: decision omits exact target Wiki evidence")
        bank_evidence = [e for e in current_decision.get("evidence", []) if e.get("kind") == "local_source"]
        expected_revision = int(bank_pin["revision"])
        expected_source = bank_pin["title"]
        fail(any(e.get("sourceTitle") == expected_source and e.get("sourceRevision") == expected_revision and
                 e.get("sourceHash") == bank_pin["bodySha256"] and source_literal in e.get("quote", "")
                 for e in bank_evidence), f"item {item_id}: decision omits exact Bank operation evidence")

    fail(verified_context_ids == {int(row["itemId"]) for row in expected},
         "selected correction verifier did not validate the complete exact policy set")
    return policy, pin, corrections, pool


def run_generic_remainder(decision_rows: list[dict[str, Any]], corrections: list[dict[str, Any]],
                          generic_output: Path, *, expect_full_failure: bool = False) -> dict[str, Any]:
    selected_ids = {int(row["itemId"]) for row in corrections}
    fail(len(selected_ids) == 2096, "split list is not exactly the correction cohort")
    all_ids = {int(row["itemId"]) for row in decision_rows}
    fail(len(all_ids) == len(decision_rows) == 34085, "decision output is incomplete or duplicate")
    fail(selected_ids.issubset(all_ids), "selected corrections are missing from the full decision output")
    ledger_path = CERT_LIVE / "ledger.py"
    fail(sha(ledger_path) == LEGACY_LEDGER_SHA256 and
         sha(PACKET / "frozen/prior-1490/ledger.py") == LEGACY_LEDGER_SHA256,
         "generic ledger changed before import")
    spec = importlib.util.spec_from_file_location("bank_context_generic_ledger", ledger_path)
    fail(spec is not None and spec.loader is not None, "cannot load unchanged generic ledger verifier")
    ledger = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(ledger)
    raw_path = PACKET / "frozen/raw-export/after-coverage-3840.tsv"
    with raw_path.open(encoding="utf-8-sig", newline="") as f:
        raw_rows = {int(row["itemId"]): row for row in csv.DictReader(f, delimiter="\t")}
    actual_raw_mismatches: set[int] = set()
    for decision in decision_rows:
        item_id = int(decision["itemId"])
        row = raw_rows[item_id]
        proposed_tags = sorted(decision.get("proposedTags", []))
        raw_tags = sorted(tag for tag in row.get("tags", "").split(",") if tag)
        if (decision.get("decision") in {"certify", "revise"} and
                (decision.get("proposedCategory") != row.get("itemCategory") or
                 decision.get("proposedSubcategory") != row.get("subcategory") or
                 decision.get("proposedIronmanTabKey") != row.get("ironmanTabKey") or
                 proposed_tags != raw_tags)):
            actual_raw_mismatches.add(item_id)
    fail(actual_raw_mismatches == selected_ids,
         "full raw export mismatch set is not exactly the authorized correction IDs")

    full_path = generic_output.with_name(generic_output.stem + "-all.jsonl")
    if full_path.exists():
        raise ValueError(f"refusing to overwrite full-decision simulation output: {full_path}")
    if generic_output.exists():
        raise ValueError(f"refusing to overwrite generic verification output: {generic_output}")
    full_path.write_text("".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in decision_rows),
                         encoding="utf-8")
    if expect_full_failure:
        try:
            ledger.verify_applied(raw_path, [full_path])
        except ValueError as exc:
            message = str(exc)
            named_ids = {int(value) for value in __import__("re").findall(r"item (\d+):", message)}
            fail(bool(named_ids) and named_ids.issubset(selected_ids),
                 "generic full raw failure names a nonselected ID or no selected correction")
        else:
            raise ValueError("full generic applied check unexpectedly accepted raw-route corrections")

    residual = [row for row in decision_rows if int(row["itemId"]) not in selected_ids]
    fail(len(residual) == 31989, f"generic remainder has wrong denominator: {len(residual)}")
    generic_output.parent.mkdir(parents=True, exist_ok=True)
    generic_output.write_text("".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in residual),
                              encoding="utf-8")
    ledger.verify_applied(raw_path, [generic_output])
    return {"fullDecisionRows": len(decision_rows), "conditionallyVerifiedCorrectionRows": len(selected_ids),
            "genericRows": len(residual), "genericCheck": "PASS", "fullRawCheck": "EXPECTED_FAIL_ON_SELECTED_CORRECTIONS"}


def verify(policy_path: Path, pin_path: Path, decision_path: Path, generic_output: Path, *,
           root_authorization_path: Path, allow_synthetic: bool = False) -> dict[str, Any]:
    verify_packet_manifest(root_authorization_path)
    decision_rows = read_jsonl(decision_path)
    decision_map = {int(row["itemId"]): row for row in decision_rows}
    pool, base_snapshot, raw, _ = verify_packet_inputs()
    fail(set(decision_map) == set(base_snapshot) == set(raw) and len(decision_map) == len(decision_rows) == 34085,
         "supplied final decision output is not the exact frozen 34,085-ID universe")
    policy, pin, corrections, pool = check_policy(policy_path, pin_path, root_authorization_path,
        allow_synthetic=allow_synthetic,
        emitted_decisions=decision_map)
    prior = {int(row["itemId"]): row for row in read_jsonl(PACKET / "frozen/prior-1490/root-decisions-3683.jsonl")}
    prior_context_ids = {item_id for item_id, row in prior.items() if "rootBankContextApproval" in row}
    fail(all(decision_map[item_id] == prior[item_id] for item_id in prior_context_ids),
         "supplied output changed an existing bank-context decision")
    selected_ids = {int(row["itemId"]) for row in corrections}
    fail(all(decision_map[item_id] == base_snapshot[item_id] for item_id in set(base_snapshot) - selected_ids),
         "a nonselected decision object changed from the frozen primary snapshot")
    exclusion_ids = {item_id for item_id, row in base_snapshot.items() if row.get("decision") == "exclude"}
    fail(len(exclusion_ids) == 707, "frozen base no longer has 707 exclusions")
    fail(all(decision_map[item_id] == base_snapshot[item_id] for item_id in exclusion_ids),
         "supplied output changed a preserved exclusion")
    held_edges = {(int(row["itemId"]), int(row["targetItemId"]), row["relation"])
                  for row in read_jsonl(PACKET / "frozen/requalification/preserved-holds-49.jsonl")}
    selected_edges = {(int(row["itemId"]), int(row["targetItemId"]), row["relation"])
                      for row in expected_cases(corrections)}
    fail(not held_edges.intersection(selected_edges), "selected policy contains a preserved held edge")
    fail(not ({edge[0] for edge in held_edges} & {edge[0] for edge in selected_edges}),
         "selected policy suppresses a preserved held alias")
    generic = run_generic_remainder(decision_rows, corrections, generic_output,
                                    expect_full_failure=allow_synthetic)
    return {"status": "PASS_SIMULATION_ONLY_CONDITIONAL_CANONICAL_TARGET_CHECK" if allow_synthetic
            else "PASS_ROOT_APPROVED_CONDITIONAL_CANONICAL_TARGET_CHECK",
            "policyCases": len(policy["cases"]), "candidatePoolRows": len(pool),
            "samePlacementRowsRemainGeneric": 15, "previousConditionalCasesPreserved": 1490,
            "priorExclusionsPreserved": 707,
            "interpretation": "conditionally verified against approved canonical target; not applied to runtime export",
            **generic}


def _load_note_selector() -> Any:
    selector_path = PACKET / "draft/exact-noteability-selector.py"
    fail(sha(selector_path) == NOTE_SELECTOR_SHA256, "exact noteability selector changed before import")
    selector_spec = importlib.util.spec_from_file_location("exact_noteability_selector",
        selector_path)
    fail(selector_spec is not None and selector_spec.loader is not None, "cannot load exact noteability selector")
    selector = importlib.util.module_from_spec(selector_spec)
    selector_spec.loader.exec_module(selector)
    return selector


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cert-dir", type=Path, required=True)
    parser.add_argument("--decisions", type=Path, required=True)
    parser.add_argument("--generic-output", type=Path, required=True)
    parser.add_argument("--root-authorization", type=Path, required=True)
    parser.add_argument("--simulation", action="store_true",
                        help="allow only a temporary synthetic root authorization; grants no approval")
    args = parser.parse_args()
    if not args.generic_output.resolve().is_relative_to((PACKET / "simulation").resolve()):
        raise SystemExit("research draft writes only to a direct simulation artifact path")
    policy_path = args.cert_dir / "bank-context-corrections-approved-policy.json"
    pin_path = args.cert_dir / "bank-context-corrections-approvals.json"
    result = verify(policy_path, pin_path, args.decisions, args.generic_output,
                    root_authorization_path=args.root_authorization,
                    allow_synthetic=args.simulation)
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"FAIL_CLOSED: {exc}", file=sys.stderr)
        raise SystemExit(2)
