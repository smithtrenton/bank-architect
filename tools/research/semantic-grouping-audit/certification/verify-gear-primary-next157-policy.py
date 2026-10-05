from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import sys
from pathlib import Path
from pathlib import PurePosixPath, PureWindowsPath
from typing import Any

ROOT = Path(__file__).resolve().parents[4]
PACKET = ROOT / "tmp/root-review/gear-primary-through411-approved-integration-draft-v5-20261003"
UPSTREAM = ROOT / "tmp/root-review/gear-primary-through411-formal-integration-draft-20261003"
AUDIT = ROOT / "tmp/root-review/gear-primary-through411-final-independent-audit-20261003/assessment.md"
CERT = ROOT / "tools/research/semantic-grouping-audit/certification"
UPSTREAM_MANIFEST_SHA256 = "6540f8e46dd59008c592ce09b0f9b35fd5f84506470300b85602e7cedc515209"
AUDIT_SHA256 = "7cb4e36c53a4eef4f4ed9ac1a6c7eee36452a059be9edb1e4ed3a3259c779929"
CURRENT_PINS = {
    "approved-assignments-3683.tsv": "f9ed56e77b56a4166430bf3f2d04926a4313ad144b27a6b26c8449b91f10fe22",
    "approved-assignments-manifest-3683.json": "1e0d8361a2a7beaf73aee7a039bed8a1eed37f035828023ce55e95ce83a3ff31",
    "root-decisions-3683.jsonl": "2b21eff03e136f84334ff8861fdaeff127571e9f9c1dfb31379af990b1c7f252",
    "compiled-coverage-1385.tsv": "1385fb1aac491a1865cc71e9144ca2ad466b684d43529dbe9187bf7371e2e14c",
    "root-policy-approvals-3683.json": "91807553454d29a8a48efd85183cf3bec9066b8b9437b641547bb29e60c34b9a",
}
POLICIES = {
    "gear-primary-next157-same-approved-policy.json": ("gear-primary-next157-same-candidate-policy.json", 88, "certify", "a4477e60913df420c7b0daca255716ce489ca8e78856925fa30f3ceac6e1bcec"),
    "gear-primary-next157-corrections-approved-policy.json": ("gear-primary-next157-corrections-candidate-policy.json", 69, "revise", "890b930c7f98d6c2c66fef76ad39eb0ffbcb11ab48d528b019c5e9c71e5e5e57"),
}


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def canonical_sha(value: Any) -> str:
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def contained_path(base: Path, relative: Any, label: str) -> Path:
    if not isinstance(relative, str) or not relative or "\x00" in relative:
        raise ValueError(f"invalid {label} relative path")
    normalized = relative.replace("\\", "/")
    posix = PurePosixPath(normalized)
    windows = PureWindowsPath(relative)
    if posix.is_absolute() or windows.is_absolute() or windows.drive or any(part in {"", ".", ".."} for part in posix.parts):
        raise ValueError(f"unsafe {label} relative path: {relative!r}")
    base_real = base.resolve()
    candidate = (base_real / Path(*posix.parts)).resolve()
    try:
        candidate.relative_to(base_real)
    except ValueError as error:
        raise ValueError(f"{label} path escapes its allowed directory: {relative!r}") from error
    return candidate


def packet_path(relative: Any, label: str = "packet") -> Path:
    return contained_path(PACKET, relative, label)


def upstream_path(relative: Any, label: str = "upstream packet") -> Path:
    return contained_path(UPSTREAM, relative, label)


def verify_packet_manifest() -> None:
    manifest_path = packet_path("packet-files-manifest.json", "packet manifest")
    sidecar_path = packet_path("packet-files-manifest.sha256", "packet manifest sidecar")
    if not manifest_path.is_file() or not sidecar_path.is_file():
        raise ValueError("integration packet has not been sealed")
    manifest_sha = sha(manifest_path)
    if sidecar_path.read_text(encoding="ascii").split()[0] != manifest_sha:
        raise ValueError("integration packet manifest sidecar differs")
    files = load(manifest_path).get("files", {})
    actual = {p.relative_to(PACKET).as_posix() for p in PACKET.rglob("*") if p.is_file() and p.name not in {"packet-files-manifest.json", "packet-files-manifest.sha256"} and "__pycache__" not in p.parts}
    if actual != set(files):
        raise ValueError("integration packet file set differs from its immutable manifest")
    for relative, record in files.items():
        path = packet_path(relative, "manifest")
        if sha(path) != record["sha256"] or path.stat().st_size != record["bytes"]:
            raise ValueError(f"integration packet file changed: {relative}")


def assert_source_pins() -> dict[str, str]:
    manifest = UPSTREAM / "packet-files-manifest.json"
    if sha(manifest) != UPSTREAM_MANIFEST_SHA256:
        raise ValueError("frozen formal candidate packet manifest changed")
    sidecar = (UPSTREAM / "packet-files-manifest.sha256").read_text(encoding="ascii").split()[0]
    if sidecar != UPSTREAM_MANIFEST_SHA256:
        raise ValueError("formal candidate packet sidecar changed")
    for rel, record in load(manifest)["files"].items():
        path = upstream_path(rel, "upstream manifest")
        if not path.is_file() or sha(path) != record["sha256"] or path.stat().st_size != record["bytes"]:
            raise ValueError(f"frozen candidate evidence differs: {rel}")
    if sha(AUDIT) != AUDIT_SHA256:
        raise ValueError("independent audit bytes changed")
    pins = {}
    for name, expected in CURRENT_PINS.items():
        path = packet_path(f"frozen-current/{name}", "frozen current input")
        actual = sha(path)
        if expected and actual != expected:
            raise ValueError(f"frozen current source differs: {name}")
        pins[name] = actual
    return pins


def load_builder():
    path = packet_path("build-integration-draft.py", "policy builder")
    spec = importlib.util.spec_from_file_location("gear157_integration_builder", path)
    if spec is None or spec.loader is None:
        raise ValueError("cannot load frozen deterministic policy derivation")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def expected_approved_objects() -> dict[str, dict[str, Any]]:
    verify_packet_manifest()
    assert_source_pins()
    builder = load_builder()
    result = {}
    plan = upstream_path("frozen-plan/through411-plan", "frozen plan directory")
    for official_name, (candidate_name, count, decision, expected_sha) in POLICIES.items():
        candidate_path = packet_path(f"frozen-candidate/{candidate_name}", "candidate policy")
        candidate_sha = sha(candidate_path)
        candidate = load(candidate_path)
        if candidate_sha != load(packet_path("approval-proposals/official-policy-object-proposals.json", "policy proposal envelope"))["policies"][official_name]["sourceHashes"]["candidatePolicyFile"]:
            raise ValueError(f"proposal candidate hash differs for {official_name}")
        if candidate.get("expectedCaseCount") != count or candidate.get("expectedDecision") != decision or len(candidate.get("cases", [])) != count:
            raise ValueError(f"candidate scope/count changed for {official_name}")
        for case in candidate["cases"]:
            provenance = case.get("evidenceProvenance", {})
            page_rel = provenance.get("sourcePage")
            note_rel = provenance.get("sourceNotePath")
            page = contained_path(plan, page_rel, "source page")
            note = contained_path(plan, note_rel, "root note")
            if not page.is_file() or sha(page) != case.get("sourceSha256"):
                raise ValueError(f"exact source page path/hash differs for item {case.get('itemId')}")
            if not note.is_file() or sha(note) != provenance.get("sourceNoteSha256"):
                raise ValueError(f"root-note path/hash differs for item {case.get('itemId')}")
        policy = builder.official_policy(candidate, official_name, candidate_sha)
        raw = json.dumps(policy, ensure_ascii=False, indent=2) + "\n"
        if hashlib.sha256(raw.encode("utf-8")).hexdigest() != expected_sha:
            raise ValueError(f"proposed policy canonical bytes differ for {official_name}")
        if policy.get("primaryOnly") is not True or policy.get("addedRoles") != [] or policy.get("proposedTags") != []:
            raise ValueError(f"policy scope widened for {official_name}")
        ids = [int(case["itemId"]) for case in policy["cases"]]
        if ids != sorted(ids) or len(set(ids)) != count:
            raise ValueError(f"case IDs are duplicated or unordered for {official_name}")
        if any(case.get("expectedDecision") != decision for case in policy["cases"]):
            raise ValueError(f"decision differs in {official_name}")
        result[official_name] = policy
    same = set(int(c["itemId"]) for c in result["gear-primary-next157-same-approved-policy.json"]["cases"])
    corr = set(int(c["itemId"]) for c in result["gear-primary-next157-corrections-approved-policy.json"]["cases"])
    if len(same | corr) != 157 or same & corr:
        raise ValueError("same/correction policies do not partition the exact 157 candidates")
    return result


def verify_policy(policy: dict[str, Any], expected_policy_name: str, *, allow_draft: bool = False) -> dict[str, Any]:
    expected = expected_approved_objects()
    policy_name = expected_policy_name
    if policy_name not in expected:
        raise ValueError("unexpected policy filename")
    if policy == expected[policy_name]:
        verify_detached_approval(expected)
        verify_runtime_route_authorization()
        return {"status": "PASS", "policy": policy_name, "caseCount": len(policy["cases"]), "metadata": "root-reviewed"}
    if allow_draft:
        builder = load_builder()
        candidate_name = POLICIES[policy_name][0]
        candidate_path = packet_path(f"frozen-candidate/{candidate_name}", "draft policy")
        draft = load(candidate_path)
        if policy == draft:
            return {"status": "PASS", "policy": policy_name, "caseCount": len(policy["cases"]), "metadata": "research-candidate"}
    raise ValueError("policy is not the exact approved derivation; draft status is rejected unless explicit draft mode")


def verify_detached_approval(expected: dict[str, dict[str, Any]]) -> None:
    current = load(CERT / "root-policy-approvals.json")
    baseline = load(packet_path("frozen-current/root-policy-approvals-3683.json", "prior detached approval pins"))
    if current.get("status") != "root-reviewed exact policy pins" or current.get("reviewer") != "root":
        raise ValueError("detached root approvals do not have the required root-reviewed status")
    baseline_pins = baseline.get("approvedPolicies", {})
    current_pins = current.get("approvedPolicies", {})
    if set(current_pins) != set(baseline_pins) | set(POLICIES):
        raise ValueError("detached approval key set is not exactly predecessor pins plus these two policies")
    current_old = {k: v for k, v in current_pins.items() if k not in POLICIES}
    if current_old != baseline_pins:
        raise ValueError("an existing detached approval pin changed")
    additions = current.get("approvedPolicies", {})
    for name, policy in expected.items():
        pin = additions.get(name)
        if not isinstance(pin, dict):
            raise ValueError(f"missing detached authorization for {name}")
        raw = (CERT / name).read_bytes()
        ids = sorted(int(c["itemId"]) for c in policy["cases"])
        if pin != {"sha256": hashlib.sha256(raw).hexdigest(), "canonicalSha256": canonical_sha(policy), "approvedItemIds": ids, "caseCount": len(ids), "decision": policy["expectedDecision"]}:
            raise ValueError(f"detached authorization does not pin the exact complete policy: {name}")


def verify_runtime_route_authorization() -> None:
    route = CERT / "gear-primary-next157-runtime-route-approval.json"
    if not route.is_file():
        raise ValueError("missing detached runtime route approval; 1201 correction is not applied")
    value = load(route)
    required_path = packet_path("approval-proposals/runtime-route-approval-proposal.json", "route proposal")
    manifest_path = packet_path("packet-files-manifest.json", "packet manifest")
    required = load(required_path)
    expected = {
        "schema": 1,
        "status": "root-approved exact runtime route change",
        "reviewer": "root",
        "approvedPacketManifestSha256": sha(manifest_path),
        "approvedRouteProposalSha256": sha(required_path),
        "approvedRuntimeRouteProposal": required,
    }
    if value != expected:
        raise ValueError("runtime route approval differs from the exact paired mapper/emitter/resource/test proposal")
    if value.get("status") != "root-approved exact runtime route change":
        raise ValueError("runtime route approval is not root-approved")
    approved_proposal = value.get("approvedRuntimeRouteProposal")
    if not isinstance(approved_proposal, dict):
        raise ValueError("root runtime authorization lacks the approved route proposal object")
    proof = approved_proposal.get("compiledApplicationProof", {})
    proof_path = packet_path(proof.get("path"), "compiled proof")
    if not proof_path.is_file() or sha(proof_path) != proof.get("sha256"):
        raise ValueError("compiled application/preservation proof is missing or changed")
    verify_compiled_proof(proof_path)
    verify_runtime_application_manifest(approved_proposal)
    verify_runtime_postimages(approved_proposal)


def verify_compiled_proof(proof_path: Path) -> None:
    report = load(proof_path)
    if report.get("status") != "PASS; full compiled application and preservation" or report.get("universe") != 34085 or report.get("supportedTargetsVerified") != 157 or report.get("unchangedTargetCount") != 88 or report.get("changedAssignmentRows") != 69 or report.get("otherRowsIdentical") != 34016 or report.get("allTagsPreserved") is not True or report.get("bankReaderAndFixtureUnchanged") is not True or report.get("primaryLedgerNotYetAdvanced") is not True:
        raise ValueError("compiled runtime proof does not establish the exact scoped change/preservation")


def verify_runtime_application_manifest(value: dict[str, Any]) -> None:
    binding = value.get("runtimeApplicationManifest", {})
    path = packet_path(binding.get("path"), "runtime manifest")
    if not path.is_file() or sha(path) != binding.get("sha256"):
        raise ValueError("runtime application source manifest is missing or changed")
    runtime = load(path)
    changed = runtime.get("changedFiles", {})
    expected = {
        "src/main/java/com/pkoka5/ironmanbankarchitect/organize/PresetCategoryMapper.java": "PresetCategoryMapper.java",
        "src/main/resources/com/pkoka5/ironmanbankarchitect/catalog/canonical-item-classification-overrides.tsv": "canonical-item-classification-overrides.tsv",
        "src/test/java/com/pkoka5/ironmanbankarchitect/organize/PresetCategoryMapperTest.java": "PresetCategoryMapperTest.java",
        "src/test/java/com/pkoka5/ironmanbankarchitect/catalog/ResourceItemRegistryTest.java": "ResourceItemRegistryTest.java",
        "src/test/java/com/pkoka5/ironmanbankarchitect/organize/layout/ItemSetCategoryConsistencyTest.java": "ItemSetCategoryConsistencyTest.java",
    }
    if set(changed) != set(expected):
        raise ValueError("compiled runtime application changed-file allowlist differs")
    for path_key, name in expected.items():
        record = changed[path_key]
        if record.get("beforeSha256") != value["beforeAfter"][name]["beforeSha256"] or record.get("afterSha256") != value["beforeAfter"][name]["afterSha256"]:
            raise ValueError(f"compiled runtime before/after binding differs: {path_key}")
    emitter_name = "tools/research/semantic-grouping-audit/certification/emit-root-approved-decisions.py"
    lineage = value.get("emitterLineage", {})
    historical_emitter = packet_path("frozen-runtime/emit-root-approved-decisions.py", "historical compiled-proof emitter")
    v4_emitter = packet_path("frozen-runtime/v4-staged-emit-root-approved-decisions.py", "installed V4 emitter before V5")
    if (sha(historical_emitter) != lineage.get("compiledJavaProofUnchangedEmitterSha256") or
            runtime.get("unchangedFiles", {}).get(emitter_name) != lineage.get("compiledJavaProofUnchangedEmitterSha256")):
        raise ValueError("historical compiled runtime proof does not pin its unchanged pre-V4 emitter")
    if (sha(v4_emitter) != lineage.get("v4InstalledEmitterBeforeV5Sha256") or
            lineage.get("v4InstalledEmitterBeforeV5Sha256") != value["beforeAfter"]["emit-root-approved-decisions.py"]["beforeSha256"] or
            lineage.get("v5Change") != "Only the exact disjoint load_policy_cases count guard/message changes from 3046 / 3,046 to 3203 / 3,203."):
        raise ValueError("V5 emitter does not preserve the exact V4-to-V5 count-guard lineage")
    if runtime.get("status") != "Runtime candidate applied for compiled verification; formal157 ledger approval still pending" or runtime.get("counts") != {"resourceChanges": 69, "adds": 66, "replaces": 3} or runtime.get("primaryLedgerUnchanged") is not True or runtime.get("bankRowsAndTagsUnchanged") is not True or runtime.get("noNewTestMethods") is not True:
        raise ValueError("runtime application manifest does not establish the pending-only, preserved ledger state")


def verify_staged_postimages(value: dict[str, Any]) -> None:
    staged = {
        "PresetCategoryMapper.java": packet_path("staged/postimages/PresetCategoryMapper.java", "staged mapper postimage"),
        "emit-root-approved-decisions.py": packet_path("staged/emit-root-approved-decisions.py", "staged emitter postimage"),
        "canonical-item-classification-overrides.tsv": packet_path("staged/postimages/canonical-item-classification-overrides.tsv", "staged catalog postimage"),
        "PresetCategoryMapperTest.java": packet_path("staged/postimages/PresetCategoryMapperTest.java", "staged mapper test postimage"),
        "ResourceItemRegistryTest.java": packet_path("staged/postimages/ResourceItemRegistryTest.java", "staged resource test postimage"),
        "ItemSetCategoryConsistencyTest.java": packet_path("staged/postimages/ItemSetCategoryConsistencyTest.java", "staged set test postimage"),
    }
    for name, path in staged.items():
        expected_after = value["beforeAfter"][name]["afterSha256"]
        if not path.is_file() or sha(path) != expected_after:
            raise ValueError(f"staged exact postimage does not match the route proposal: {name}")
    emitter_source = CERT / "emit-root-approved-decisions.py"
    expected_before = value["beforeAfter"]["emit-root-approved-decisions.py"]["beforeSha256"]
    if sha(packet_path("frozen-runtime/v4-staged-emit-root-approved-decisions.py", "frozen V4 emitter preimage")) != expected_before or sha(emitter_source) != expected_before:
        raise ValueError("staged emitter patch preimage does not match the frozen and currently installed emitter")


def verify_runtime_postimages(value: dict[str, Any]) -> None:
    actual_paths = {
        "PresetCategoryMapper.java": ROOT / "src/main/java/com/pkoka5/ironmanbankarchitect/organize/PresetCategoryMapper.java",
        "emit-root-approved-decisions.py": CERT / "emit-root-approved-decisions.py",
        "canonical-item-classification-overrides.tsv": ROOT / "src/main/resources/com/pkoka5/ironmanbankarchitect/catalog/canonical-item-classification-overrides.tsv",
        "PresetCategoryMapperTest.java": ROOT / "src/test/java/com/pkoka5/ironmanbankarchitect/organize/PresetCategoryMapperTest.java",
        "ResourceItemRegistryTest.java": ROOT / "src/test/java/com/pkoka5/ironmanbankarchitect/catalog/ResourceItemRegistryTest.java",
        "ItemSetCategoryConsistencyTest.java": ROOT / "src/test/java/com/pkoka5/ironmanbankarchitect/organize/layout/ItemSetCategoryConsistencyTest.java",
    }
    for name, path in actual_paths.items():
        expected_after = value["beforeAfter"][name]["afterSha256"]
        if not path.is_file() or sha(path) != expected_after:
            raise ValueError(f"installed runtime source is not the exact reviewed postimage: {name}")


def verify_pending_proposals(expected: dict[str, dict[str, Any]]) -> None:
    envelope = load(packet_path("approval-proposals/official-policy-object-proposals.json", "policy proposal envelope"))
    pins = load(packet_path("approval-proposals/root-policy-approvals-additions.json", "pin proposal"))
    if pins.get("status") != "pending root authorization; not accepted by emitter":
        raise ValueError("detached pin proposal is no longer pending")
    if pins.get("preserveExistingApprovalRecordSha256") != sha(packet_path("frozen-current/root-policy-approvals-3683.json", "frozen approval pin source")):
        raise ValueError("detached pin proposal is not bound to the frozen prior approvals")
    if set(pins.get("addOnlyThesePins", {})) != set(POLICIES):
        raise ValueError("detached pin proposal contains an unexpected policy set")
    if envelope.get("status") != "PROPOSAL ONLY — no root approval or installation":
        raise ValueError("policy proposal status is not pending")
    for name, policy in expected.items():
        path = packet_path(f"approval-proposals/{name}.proposal.json", "approved-policy proposal")
        raw = path.read_bytes()
        ids = sorted(int(case["itemId"]) for case in policy["cases"])
        expected_pin = {"sha256": hashlib.sha256(raw).hexdigest(), "canonicalSha256": canonical_sha(policy), "approvedItemIds": ids, "caseCount": len(ids), "decision": policy["expectedDecision"]}
        if pins["addOnlyThesePins"].get(name) != expected_pin or envelope["policies"].get(name) != policy:
            raise ValueError(f"pending policy object/pin proposal differs: {name}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Fail-closed integration verifier for the 157-case primary Gear tranche.")
    parser.add_argument("--drafts", action="store_true", help="validate only staged research proposals; grants no approval")
    args = parser.parse_args()
    verify_packet_manifest()
    expected = expected_approved_objects()
    if args.drafts:
        verify_pending_proposals(expected)
        proposal = load(packet_path("approval-proposals/official-policy-object-proposals.json", "policy proposal envelope"))
        if proposal.get("status") != "PROPOSAL ONLY — no root approval or installation":
            raise ValueError("draft proposal status changed")
        for name, policy in expected.items():
            if proposal["policies"].get(name) != policy:
                raise ValueError(f"staged exact proposal differs: {name}")
            verify_policy(load(packet_path(f"frozen-candidate/{POLICIES[name][0]}", "draft policy")), name, allow_draft=True)
        route = load(packet_path("approval-proposals/runtime-route-approval-proposal.json", "route proposal"))
        if route.get("status") != "PENDING ROOT APPROVAL; NOT APPLIED":
            raise ValueError("runtime route proposal is not explicitly pending")
        proof = route.get("compiledApplicationProof", {})
        proof_path = packet_path(proof.get("path"), "compiled proof")
        if not proof_path.is_file() or sha(proof_path) != proof.get("sha256"):
            raise ValueError("the later compiled application proof is not sealed into this packet")
        verify_compiled_proof(proof_path)
        verify_runtime_application_manifest(route)
        verify_staged_postimages(route)
        print(json.dumps({"status": "PASS_DRAFT_ONLY", "policies": {name: len(policy["cases"]) for name, policy in expected.items()}, "route1201": "staged emitter postimage and compiled Java/catalog preservation proof pass; detached root authorization pending", "productionEdits": False}, indent=2))
        return 0
    for name in expected:
        policy_path = CERT / name
        if not policy_path.is_file():
            raise ValueError(f"missing installed official policy; refusing to treat draft as approval: {name}")
        verify_policy(load(policy_path), name, allow_draft=False)
    verify_detached_approval(expected)
    verify_runtime_route_authorization()
    print(json.dumps({"status": "PASS_OFFICIAL", "policies": {name: len(policy["cases"]) for name, policy in expected.items()}, "route1201": "approved and pinned"}, indent=2))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (ValueError, FileNotFoundError, KeyError) as error:
        print(f"FAIL_CLOSED: {error}", file=sys.stderr)
        raise SystemExit(2)
