#!/usr/bin/env python3
"""Create a corrected report for the frozen 0f20ae6 alias proposal packet.

The original proposal, endpoint manifest, and compact TSV remain untouched.
This correction pins the policy approval snapshot and clarifies the 1,806-only
scope and runtime-vs-raw-catalog verification boundary.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import json
import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[4]
OUT = ROOT / "tmp/category-certification/root-review"
SOURCE_REPORT = OUT / "root-confirmed-typed-alias-report-1806.json"
OUTPUT_REPORT = OUT / "root-confirmed-typed-alias-report-1806-corrected.json"
FROZEN_POLICY_PINS = OUT / "root-policy-approvals-0f20ae6.json"
EXPECTED_SOURCE_REPORT_HASH = "247adc3969b846bd0f78d64ef4394cd55fbcd2d0c6a26b7f2b91d86c22d0875f"
EXPECTED_POLICY_PIN_HASH = "6125ef0850d960902d01536e1afb3c68d91cf3e74ba477178f2d03d79881e8af"
CHECKPOINT_COMMIT = "0f20ae6da0c46221edce9d90a41c4e436adaf9f5"


def sha(path: pathlib.Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def rel(path: pathlib.Path) -> str:
    return path.relative_to(ROOT).as_posix()


def line_evidence(path: pathlib.Path, tokens: tuple[str, ...]) -> list[dict]:
    rows = []
    for number, text in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if any(token in text for token in tokens):
            rows.append({"line": number, "text": text.strip()})
    return rows


def main() -> None:
    if sha(SOURCE_REPORT) != EXPECTED_SOURCE_REPORT_HASH:
        raise ValueError("frozen source report hash changed; refusing to rewrite its corrected copy")
    if sha(FROZEN_POLICY_PINS) != EXPECTED_POLICY_PIN_HASH:
        raise ValueError("frozen 0f20ae6 policy approval snapshot hash mismatch")
    report = json.loads(SOURCE_REPORT.read_text(encoding="utf-8"))
    pins = json.loads(FROZEN_POLICY_PINS.read_text(encoding="utf-8"))
    if len(pins.get("approvedPolicies", {})) != 7:
        raise ValueError("expected exactly seven policy pins in the 0f20ae6 approval snapshot")

    universe = report["approvedEndpointUniverse"]
    if (universe.get("count") != 1806
            or universe.get("rootApprovedDecisionsSha256") != "b643b10ceeba41f92747921a505c52f70c1b049bace51ad432574b8d6e7e4000"):
        raise ValueError("report does not describe the frozen 1,806-endpoint checkpoint")
    for source in universe["selectedSevenPolicySources"]:
        pin = pins["approvedPolicies"].get(pathlib.PurePosixPath(source["path"]).name)
        if not pin or pin.get("sha256") != source.get("sha256"):
            raise ValueError("selected policy source does not match frozen root policy pin")
        policy_path = ROOT / source["path"]
        if sha(policy_path) != source["sha256"]:
            raise ValueError(f"selected policy bytes changed: {source['path']}")

    # Verify the previously frozen proposal artifacts before creating a new report.
    for path_key, hash_key in (("proposalLedgerPath", "proposalLedgerSha256"),
                               ("endpointSourceManifestPath", "endpointSourceManifestSha256"),
                               ("compactReviewPath", "compactReviewSha256")):
        path = ROOT / (report.get(path_key) or universe.get(path_key))
        expected = report.get(hash_key) or universe.get(hash_key)
        if not path.exists() or sha(path) != expected:
            raise ValueError(f"frozen proposal artifact hash mismatch: {path}")

    report["schema"] = "ironman-bank-architect.root-confirmed-typed-alias-proposals.v3"
    report["correction"] = {
        "kind": "source metadata and scope wording correction; proposal rows unchanged",
        "sourceReportPath": rel(SOURCE_REPORT),
        "sourceReportSha256": EXPECTED_SOURCE_REPORT_HASH,
        "policyApprovalSnapshotPath": rel(FROZEN_POLICY_PINS),
        "policyApprovalSnapshotSha256": EXPECTED_POLICY_PIN_HASH,
        "policyApprovalSnapshotCommit": CHECKPOINT_COMMIT,
        "priorProposalLedgerSha256": report["proposalLedgerSha256"],
        "priorEndpointManifestSha256": report["endpointSourceManifestSha256"],
        "priorCompactReviewSha256": report["compactReviewSha256"],
    }
    universe["rootPolicyApprovalsPath"] = rel(FROZEN_POLICY_PINS)
    universe["rootPolicyApprovalsSha256"] = EXPECTED_POLICY_PIN_HASH
    universe["rootPolicyApprovalsSourceRevision"] = CHECKPOINT_COMMIT
    universe["rootPolicyApprovalScope"] = "The seven exact policy files listed in selectedSevenPolicySources; later food policy pins and endpoint rows are outside this frozen 0f20ae6 cohort."
    universe["approvalBoundary"] = (
        "Exactly the 1,806 endpoint IDs in checkpoint 0f20ae6 are in scope: 230 root-pinned policy revisions, "
        "939 gear-primary certifications, and 637 clue certifications. The later 61 food/raw-food endpoints "
        "and all other rows are excluded from this packet. Only category/subcategory and a tab explicitly present "
        "in a selected root policy case or clue approval scope are treated as reviewed. Endpoint roles and tags "
        "remain endpoint-specific and are never inherited through these typed edges."
    )

    root = ROOT
    runtime_paths = [
        "src/main/java/com/pkoka5/ironmanbankarchitect/bank/BankSnapshotReader.java",
        "src/main/java/com/pkoka5/ironmanbankarchitect/bank/BankItemIds.java",
        "src/main/java/com/pkoka5/ironmanbankarchitect/overlay/BankCategoryOverlay.java",
        "src/main/java/com/pkoka5/ironmanbankarchitect/overlay/BankGuideOverlay.java",
    ]
    runtime_evidence = {
        "BankSnapshotReader.java": ("InventoryID.BANK", "getPlaceholderTemplateId", "getPlaceholderId",
                                    "BankItemIds.canonical", "new BankItemSnapshot(canonicalItemId, 0"),
        "BankItemIds.java": ("public static int canonical", "return placeholderTemplateId != -1"),
        "BankCategoryOverlay.java": ("categoryIndexFor(canonicalItemId(child.getItemId()))",
                                     "BankItemIds.canonical"),
        "BankGuideOverlay.java": ("itemIds[slot] = canonicalItemId", "BankItemIds.canonical"),
    }
    runtime_rows = []
    for path in runtime_paths:
        file = root / path
        runtime_rows.append({"path": path, "sha256": sha(file),
                             "lineEvidence": line_evidence(file, runtime_evidence[file.name])})
    report["mechanics"]["runtimeCode"] = runtime_rows

    ledger_path = root / "tools/research/semantic-grouping-audit/certification/ledger.py"
    ledger_lines = line_evidence(ledger_path, ("def verify_applied", "item_id = strict_id(decision.get(\"itemId\"))",
                                               "checks = {", '"category":', '"subcategory":', '"tab":', '"tags":'))
    report["verifyAppliedScopeRecommendation"] = {
        "sourcePath": rel(ledger_path),
        "sourceSha256": sha(ledger_path),
        "currentBehavior": "verify_applied keys actionable decisions by decision.itemId and compares proposed category, subcategory, tab, and tags to the fresh export row with that same ID. That is a raw catalog-row check; it does not model the bank UI's placeholder canonicalization.",
        "lineEvidence": ledger_lines,
        "placeholderRecommendation": "Keep the raw catalog ID and bank lookup ID as separate identities. When a live bank slot's ItemComposition has placeholderTemplateId != -1 and placeholderId > 0, the current BankSnapshotReader/BankItemIds path looks up the canonical parent ID and retains placeholder=true/quantity=0. Verify the reviewed primary against that parent row for bank lookup. Do not fail that bank-lookup check because the placeholder alias's raw catalog row retains a different category; report and verify raw alias fields separately.",
        "noteRecommendation": "The Wiki Bank source supports conversion when depositing a note; the current plugin canonicalizes placeholders only and otherwise preserves the observed item ID. Keep NOTE_VARIANT_OF as storage-conversion provenance, not a plugin grouping override. If a note ID is ever observed by the plugin, its own raw assignment applies unless an explicit feature and exact evidence establish otherwise.",
        "propertyBoundary": "A typed cache edge does not transfer Wear, Eat, held-use, equipment action, stats, effects, roles, or tags. Do not certify these properties through note/placeholder identity.",
        "suggestedScopes": ["raw_catalog_item", "placeholder_bank_parent_lookup", "bank_storage_conversion_only"],
        "approvalStatus": "research recommendation only; no production or decision-ledger changes"
    }

    report["limitations"] = [
        "This packet covers exactly the frozen 1,806 endpoint IDs from checkpoint 0f20ae6: 230 root-pinned policy revisions, 939 gear-primary certifications, and 637 clue certifications. The later 61 food/raw-food approvals are excluded.",
        "All 1,627 incoming typed alias links in this packet target the 1,169 policy endpoints; none targets a clue endpoint. No selected policy endpoint has an explicitly reviewed tab, so tab inheritance/comparison is omitted for all proposal rows.",
        "No source, role, tag, action, stat, or effect context is inherited from endpoint to alias.",
        "Raw current-vs-reviewed category/subcategory mismatches are mechanical comparison deltas, not accepted catalog edits or semantic certifications of the alias IDs.",
        "A cache edge proves the directed relation at the pinned cache revision; it does not prove which item ID a live bank slot presents. Placeholder canonicalization must be verified through the runtime composition fields and code path."
    ]
    report["correctedAtUtc"] = dt.datetime.now(dt.timezone.utc).isoformat()
    OUTPUT_REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"output": rel(OUTPUT_REPORT), "sha256": sha(OUTPUT_REPORT),
                      "endpointCount": universe["count"], "typedLinks": report["incomingTypedEdges"]["proposalRows"],
                      "policyApprovalSnapshotSha256": EXPECTED_POLICY_PIN_HASH,
                      "sourceReportUnchanged": sha(SOURCE_REPORT) == EXPECTED_SOURCE_REPORT_HASH}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
