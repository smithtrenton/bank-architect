#!/usr/bin/env python3
"""Research-only writer for the separately authorized bank-context tranche.

The only output accepted is a fresh ignored research directory. The command
does not edit official decisions, policies, approvals, bank rows, or runtime
sources. Its conditional semantics are enforced by the pinned V8 verifier.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import importlib.util
import json
import os
import shutil
import tempfile
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[4]
PACKET = ROOT / "tmp/root-review/bank-context-correction-emitter-draft-20261004"
VERIFIER_PACKET = ROOT / "tmp/root-review/bank-context-next-applied-verifier-draft-v8-20261003"
VERIFIER_PATH = VERIFIER_PACKET / "draft/verify-bank-context-correction-applied.py"
PRIMARY = VERIFIER_PACKET / "frozen/primary-snapshot"
BASE_DECISIONS = PRIMARY / "candidate-decisions.jsonl"
BASE_DECISIONS_SHA256 = "dc0929e6ca8c87f8c30aa814ff72d4e9dd077163474ec9e0d8920e668b5f0a9a"
VERIFIER_PACKET_MANIFEST_SHA256 = "c8be349197eb8f6efa3389a07fd4a0a02953b1c7b5ee8cdb0f17bad99e44162c"
VERIFIER_SHA256 = "796bebb64193bf255df4ec278878ee6b340f5fac962ffad6d3d7ec83f5dc135d"
POLICY_NAME = "bank-context-corrections-approved-policy.json"
PIN_NAME = "bank-context-corrections-approvals.json"
AUTH_NAME = "bank-context-corrections-root-authorization.json"
SIM_CERT = VERIFIER_PACKET / "simulation/isolated-positive-1isle5on/CERT"
OUTPUT_PARENT = PACKET / "simulation/output-runs"


def fail(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8-sig").splitlines() if line.strip()]


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.write_text("".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows),
                    encoding="utf-8")


def load_verifier() -> Any:
    manifest_path = VERIFIER_PACKET / "packet-manifest.json"
    fail(sha(manifest_path) == VERIFIER_PACKET_MANIFEST_SHA256, "conditional verifier packet manifest changed")
    fail(sha(VERIFIER_PATH) == VERIFIER_SHA256, "conditional verifier source changed")
    spec = importlib.util.spec_from_file_location("bank_context_correction_verifier_v8", VERIFIER_PATH)
    fail(spec is not None and spec.loader is not None, "cannot load the pinned conditional verifier")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def safe_output_path(destination: Path) -> Path:
    resolved_parent = destination.parent.resolve()
    allowed = OUTPUT_PARENT.resolve()
    fail(resolved_parent == allowed or allowed in resolved_parent.parents,
         "writer output must be inside this packet's ignored simulation/output-runs directory")
    fail(not destination.exists(), "writer refuses to overwrite any existing output")
    fail(not destination.is_symlink(), "writer refuses a symlink output")
    return destination


def construct_rows(verifier: Any, policy_path: Path, pin_path: Path, auth_path: Path,
                   *, synthetic: bool) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    # Run the complete verifier against the frozen base inputs before deriving
    # any output. This checks installed authorization, all exact cases, target
    # approval chains, current cache replay, and preservation gates.
    verifier.verify_packet_manifest(auth_path)
    pool, decisions_by_id, raw_rows, _assignments = verifier.verify_packet_inputs()
    verifier.verify_prior_1490(decisions_by_id)
    pool_by_id, corrections = verifier.case_map(pool)
    fail(len(pool) == 2111, "frozen candidate pool is not the exact 2,111-row cohort")
    fail(len(decisions_by_id) == 34085, "frozen primary snapshot is not 34,085 decisions")
    fail(len(pool_by_id) == 2111, "frozen pool is not unique by alias ID")
    raw_by_id = {int(item_id): row for item_id, row in raw_rows.items()}
    primary_approvals = read_json(VERIFIER_PACKET / "frozen/primary-snapshot/root-policy-approvals.json")["approvedPolicies"]
    output_by_id = {item_id: dict(row) for item_id, row in decisions_by_id.items()}

    for candidate in corrections:
        item_id = int(candidate["itemId"])
        target_id = int(candidate["targetItemId"])
        relation = candidate["relation"]
        row = raw_by_id[item_id]
        target = decisions_by_id[target_id]
        route = {"category": target["proposedCategory"],
                 "subcategory": target["proposedSubcategory"],
                 "ironmanTabKey": target["proposedIronmanTabKey"]}
        primary_approval = target["rootApproval"]
        policy_name = primary_approval["policyFile"]
        fail(policy_name in primary_approvals and
             primary_approvals[policy_name].get("sha256") == primary_approval["policySha256"],
             f"target {target_id}: primary approval pin changed")
        bank_pin = candidate["bankTransformationSourcePin"]
        source_literal = verifier.NOTE_BANK_LITERAL if relation == "NOTE_VARIANT_OF" else verifier.PLACEHOLDER_BANK_LITERAL
        local_source = {
            "kind": "local_source", "claimScope": "generic bank operation; no alias semantic fact",
            "sourceTitle": bank_pin["title"], "sourceRevision": bank_pin["revision"],
            "sourceHash": bank_pin["bodySha256"], "sourcePath": bank_pin["localPath"],
            "source": f"https://oldschool.runescape.wiki/w/Special:Redirect/revision/{bank_pin['revision']}",
            "quote": source_literal,
        }
        target_wiki = candidate["targetWikiEvidence"]
        links = [dict(candidate["typedCacheEvidence"]), {
            "kind": "exact_wiki", "itemId": target_id,
            "sourceTitle": target_wiki["sourceTitle"], "sourceRevision": target_wiki["sourceRevision"],
            "sourceHash": target_wiki["verifiedBodySha256"],
            "exactInfoboxItemIds": target_wiki["exactInfoboxItemIds"],
        }]
        out = output_by_id[item_id]
        out.update({
            "decision": "revise",
            "proposedCategory": route["category"],
            "proposedSubcategory": route["subcategory"],
            "proposedIronmanTabKey": route["ironmanTabKey"],
            "proposedTags": sorted(tag for tag in row["tags"].split(",") if tag),
            "proposedRoles": None,
            "assignmentClaimScope": "conditional canonical target placement only",
            "rawItemFunctionClaimScope": "unassessed", "roleClaimScope": "unassessed",
            "availabilityClaimScope": "unassessed", "tradeabilityClaimScope": "unassessed",
            "acquisitionClaimScope": "unassessed", "depositabilityClaimScope": "unassessed",
            "bankabilityClaimScope": "unassessed",
            "rootBankContextApproval": {
                POLICY_NAME: sha(policy_path), PIN_NAME: sha(pin_path),
                "verify-bank-context-correction-applied.py": sha(VERIFIER_PATH),
            },
            "approvedCanonicalBase": {
                "itemId": target_id, "decision": target["decision"],
                "frozenSnapshotSha256": verifier.PRIMARY_DECISIONS_SHA256,
                "frozenDecisionSha256": verifier.canonical(target), "route": route,
                "policyFile": policy_name, "policySha256": primary_approval["policySha256"],
            },
            "identityLinks": [{"fromItemId": item_id, "itemId": target_id, "toItemId": target_id,
                               "relation": relation, "evidence": links}],
            "evidence": [local_source],
            "rationale": "Conditional canonical target placement; source semantics remain unassessed.",
            "semanticPredicate": "bank-context.canonical-target-placement-only",
        })
    result = list(output_by_id.values())
    fail(len(result) == 34085 and len({int(row["itemId"]) for row in result}) == 34085,
         "emitter changed the exact full decision universe")
    changed = {int(row["itemId"]) for row in result
               if row != decisions_by_id[int(row["itemId"])]}
    fail(changed == {int(row["itemId"]) for row in corrections} and len(changed) == 2096,
         "emitter changed a nonselected decision or omitted a correction")
    return result, corrections


def run(cert_dir: Path, auth_path: Path, destination: Path, *, synthetic: bool = False) -> dict[str, Any]:
    verifier = load_verifier()
    if synthetic:
        fail(cert_dir.resolve() == SIM_CERT.resolve() and auth_path.resolve() == (SIM_CERT / AUTH_NAME).resolve(),
             "synthetic mode accepts only the frozen no-approval simulation fixture")
        fail("simulation-only synthetic" in read_json(auth_path).get("status", ""),
             "synthetic fixture unexpectedly appears to authorize approval")
    else:
        official_cert = ROOT / "tools/research/semantic-grouping-audit/certification"
        fail(cert_dir.resolve() == official_cert.resolve(), "official mode requires the installed CERT directory")
        fail(auth_path.resolve() == (official_cert / AUTH_NAME).resolve(),
             "official mode requires the installed root authorization file")
    policy_path = cert_dir / POLICY_NAME
    pin_path = cert_dir / PIN_NAME
    fail(sha(BASE_DECISIONS) == BASE_DECISIONS_SHA256, "frozen primary decision snapshot changed")
    final_dir = safe_output_path(destination)
    final_dir.parent.mkdir(parents=True, exist_ok=True)
    stage = Path(tempfile.mkdtemp(prefix=".bank-context-stage-", dir=final_dir.parent))
    try:
        decisions, corrections = construct_rows(verifier, policy_path, pin_path, auth_path, synthetic=synthetic)
        decisions_path = stage / "candidate-decisions.jsonl"
        generic_path = stage / "generic-remainder.jsonl"
        write_jsonl(decisions_path, decisions)
        proof = verifier.verify(policy_path, pin_path, decisions_path, generic_path,
                                root_authorization_path=auth_path, allow_synthetic=synthetic)
        fail(proof["policyCases"] == 2096 and proof["genericRows"] == 31989 and
             proof["genericCheck"] == "PASS" and
             proof["fullRawCheck"] == "EXPECTED_FAIL_ON_SELECTED_CORRECTIONS",
             "emitted output failed the full conditional/generic integration gates")
        report = {
            "status": "SIMULATION_ONLY_NO_APPROVAL" if synthetic else "ROOT_AUTHORIZED_RESEARCH_OUTPUT",
            "policyCases": len(corrections), "samePlacementCasesRemainGeneric": 15,
            "decisionRows": len(decisions), "genericRows": proof["genericRows"],
            "preservedPriorConditionalCases": proof["previousConditionalCasesPreserved"],
            "preservedExclusions": proof["priorExclusionsPreserved"],
            "fullRawCheck": (proof["fullRawCheck"] if synthetic else
                             "EXACT_2096_MISMATCH_SET_PROVED; GENERIC_FULL_INVOCATION_NOT_RUN"),
            "genericCheck": proof["genericCheck"],
            "fullRawGenericExecution": ("EXECUTED_EXPECTED_FAILURE" if synthetic else
                "NOT_EXECUTED_ROOT_MUST_RUN_UNCHANGED_GENERIC_CLI"),
            "policySha256": sha(policy_path), "approvalPinSha256": sha(pin_path),
            "verifierSha256": sha(VERIFIER_PATH),
            "outputPurpose": "research review only; never an official publication path",
        }
        (stage / "emitter-report.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        # The destination is required not to exist. Rename only after every
        # verifier and generic-ledger gate succeeds; never replace a directory.
        fail(not final_dir.exists(), "output destination appeared during validation")
        os.rename(stage, final_dir)
        return report
    except Exception:
        shutil.rmtree(stage, ignore_errors=True)
        raise


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cert-dir", type=Path, required=True)
    parser.add_argument("--root-authorization", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--simulation", action="store_true",
                        help="use only the frozen isolated authorization that grants no approval")
    args = parser.parse_args()
    report = run(args.cert_dir, args.root_authorization, args.output_dir, synthetic=args.simulation)
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
