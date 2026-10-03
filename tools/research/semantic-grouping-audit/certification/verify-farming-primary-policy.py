#!/usr/bin/env python3
"""Read-only verifier for the separately root-approved 51 ordinary seed cases.

Draft mode checks the frozen root review. Policy mode fails closed unless the
complete policy is canonically pinned by the detached root approvals file.
This helper never writes policy or ledger decisions.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[4]
CERT = ROOT / "tools/research/semantic-grouping-audit/certification"
BASE = ROOT / "tmp/category-certification"
DRAFT_PATH = BASE / "root-review/farming-primary-root-reviewed-draft.json"
AUDIT_PATH = ROOT / "tmp/root-review/farming-primary-draft-independent-audit.json"
APPROVALS_PATH = CERT / "root-policy-approvals.json"
PACKET_V2 = BASE / "reviews/materials-positive-cohorts/20261003-farming-seed-literal-v2/root-review-packet.json"

EXPECTED = {
    "articleIndex": (BASE / "wiki-articles/article-index.json", "f3bf20b4dbe2ea90196ccfa3d642773e78e5d683316b5a2e75e08239f7ecd677"),
    "materialsPacket": (BASE / "reviewer-packets/skilling-farming.jsonl", "415b1b0ecc9ea35cad7d1b0eb7476110472dc113231ebe61294ef94120345ddb"),
    "literalPacket": (PACKET_V2, "88734dda247ec388b7186d7cffc610662bdb3f2eafe09ba4c75604e547c4a8cf"),
    "independentReview": (BASE / "reviews/materials-positive-cohorts/20261003-farming-seeds-corrected/root-review/independent-semantic-review.json", "d12bb24d56cd8dbe9190594a62672253d6b3d9ec83508aa0a37ac2abe4a5c65f"),
    "rootReadRecord": (BASE / "root-review/farming-51-main-thread-source-review-v1.json", "27e5a23a5374a6aa8639540369339eb46afd1950689ea5e6562a79a52263948f"),
    "immutableRootDraft": (DRAFT_PATH, "bdb8d147281ef26a3cc8c5849910dde1d1a38b1c910e1c23fac647f97a4c9eb6"),
    "draftIndependentAudit": (AUDIT_PATH, "f6c726c528e5de5cdf1a5097ac92ed0c92f7b0d6c0257591cc9d373a833a025c"),
}
TARGET = {"category": "FARMING", "subcategory": "farming", "ironmanTabKey": "seeds-farming"}
FACT_FIELDS = ("id", "name", "options", "examine", "equipable", "stackable", "quest", "tradeable", "noteable")
EXACT_IDS = {
    5096, 5097, 5098, 5099, 5101, 5102, 5103, 5104, 5105, 5106,
    5280, 5281, 5283, 5284, 5285, 5286, 5287, 5288, 5289, 5290,
    5305, 5306, 5307, 5308, 5309, 5310, 5311, 5313, 5314, 5315,
    5316, 5318, 5319, 5320, 5321, 5322, 5323, 5324,
    21486, 21488, 22869, 22871, 22873, 22877, 22887,
    31541, 31543, 31545, 31547, 31549, 31551,
}


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8-sig").splitlines() if line.strip()]


def norm(text: str) -> str:
    return " ".join(text.split())


def check(ok: bool, message: str, errors: list[str]) -> None:
    if not ok:
        errors.append(message)


def source_objects(errors: list[str]) -> dict[str, Any]:
    objects: dict[str, Any] = {}
    for key, (path, expected_hash) in EXPECTED.items():
        check(path.is_file(), f"missing fixed source artifact {key}: {path.relative_to(ROOT)}", errors)
        if not path.is_file():
            continue
        actual = digest(path)
        check(actual == expected_hash, f"fixed source hash mismatch for {key}: {actual}", errors)
        if key == "articleIndex":
            objects[key] = load_json(path)
        elif key == "materialsPacket":
            objects[key] = load_jsonl(path)
        else:
            objects[key] = load_json(path)
    return objects


def compare_pin_maps(policy: dict[str, Any], errors: list[str]) -> None:
    expected_hashes = {key: value[1] for key, value in EXPECTED.items()}
    expected_paths = {key: value[0].relative_to(ROOT).as_posix() for key, value in EXPECTED.items()}
    check(policy.get("sourceHashes") == expected_hashes, "policy sourceHashes differ from the seven fixed source pins", errors)
    check(policy.get("sourceInputPaths") == expected_paths, "policy sourceInputPaths differ from the seven fixed source paths", errors)


def _verify_policy_report(policy: dict[str, Any], policy_path: Path) -> dict[str, Any]:
    """Require detached approval bytes, exact fixed inputs, and exact 51 cases."""
    errors: list[str] = []
    policy_path = policy_path.resolve()
    if not policy_path.is_file():
        raise ValueError(f"policy file does not exist: {policy_path}")
    check(policy.get("schema") == 1, "policy schema is not 1", errors)
    check(policy.get("status") == "root-reviewed primary assignments only", "policy lacks root-reviewed primary-only status", errors)
    check(policy.get("expectedCaseCount") == 51, "policy expectedCaseCount is not 51", errors)
    check(policy_path.parent == CERT.resolve(), f"policy must live at the fixed certification directory {CERT}", errors)
    if not APPROVALS_PATH.is_file():
        check(False, "detached root-policy-approvals.json is missing", errors)
    else:
        approvals = load_json(APPROVALS_PATH)
        check(approvals.get("schema") == 1 and approvals.get("status") == "root-reviewed exact policy pins", "detached root approval record is invalid", errors)
        approval = approvals.get("approvedPolicies", {}).get(policy_path.name)
        check(isinstance(approval, dict), "policy filename is absent from detached approvedPolicies", errors)
        if isinstance(approval, dict):
            canonical = hashlib.sha256(json.dumps(policy, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()
            check(canonical == approval.get("canonicalSha256"), "policy canonical bytes differ from detached approval", errors)
            cases = policy.get("cases", [])
            ids = [case.get("itemId") for case in cases]
            check(ids == approval.get("approvedItemIds") and len(ids) == 51, "policy case IDs/order differ from the detached approved exact set", errors)
            check(approval.get("caseCount") == 51 and approval.get("decision") == "certify", "detached approval is not certify/51", errors)

    compare_pin_maps(policy, errors)
    objects = source_objects(errors)
    if errors:
        return {"status": "FAIL", "mode": "approved_policy", "errors": errors}
    errors.extend(verify_cases(policy.get("cases", []), objects))
    return {"status": "PASS" if not errors else "FAIL", "mode": "approved_policy", "recordedRootApproval": not errors, "verifiedIds": len(policy.get("cases", [])), "errors": errors}


def verify_cases(cases: list[dict[str, Any]], objects: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    check(len(cases) == 51, f"policy has {len(cases)} cases, expected 51", errors)
    ids = [case.get("itemId") for case in cases]
    check(len(set(ids)) == 51 and set(ids) == EXACT_IDS, "policy IDs are not the exact frozen 51-case set", errors)
    index = objects["articleIndex"]
    literal = objects["literalPacket"]
    materials = {row["itemId"]: row for row in objects["materialsPacket"]}
    packet_rows = {row["itemId"]: row for row in literal.get("rows", [])}
    draft = objects["immutableRootDraft"]
    independent = objects["independentReview"]
    read_record = objects["rootReadRecord"]
    audit = objects["draftIndependentAudit"]

    check(draft.get("expectedCaseCount") == 51 and {c.get("itemId") for c in draft.get("cases", [])} == EXACT_IDS, "immutable root draft membership changed", errors)
    check(cases == draft.get("cases"), "approved policy cases differ from the immutable root-reviewed 51 cases", errors)
    check(set(read_record.get("reviewedItemIds", [])) == EXACT_IDS, "root read record exact ID set changed", errors)
    check({r.get("itemId") for r in independent.get("candidateRows", [])} == EXACT_IDS, "independent semantic review exact ID set changed", errors)
    check(audit.get("status") == "SOURCE_SET_AND_PRIMARY_SCOPE_CHECKS_PASSED_SEMANTIC_APPROVAL_NOT_GRANTED", "independent 51-case audit status changed", errors)
    check(audit.get("validation", {}).get("all126SecondaryQuotesLiteralAndPacketBacked") is True, "independent audit no longer verifies all 126 secondary quotes", errors)
    audit_rows = {r.get("itemId"): r for r in audit.get("perItem", [])}
    check(set(audit_rows) == EXACT_IDS, "independent audit row set differs from exact 51 IDs", errors)
    check(literal.get("approvalStatus") == "NOT_APPROVED_PROPOSAL_ONLY", "literal source packet is not proposal-only", errors)
    check(literal.get("accounting", {}).get("exactBoundRows") == 150 and literal.get("accounting", {}).get("uniqueExactIds") == 150, "v2 literal packet is not exact 150-row scope", errors)
    check(literal.get("accounting", {}).get("unchangedOrdinaryPrimaryCandidatesPreserved") == 51 and literal.get("accounting", {}).get("previousHoldsPreserved") == 99, "v2 candidate/hold scope changed", errors)
    check(literal.get("accounting", {}).get("rejectedImageOnlySyncedFieldCandidates") == 2, "v2 does not explicitly reject the two image-only Synced field candidates", errors)
    check(not literal.get("validationFailures"), "v2 literal packet reports validation failures", errors)
    check(len(packet_rows) == len(literal.get("rows", [])) == 150, "v2 literal packet contains duplicate or missing IDs", errors)
    packet_candidates = {r["itemId"] for r in literal["rows"] if r.get("semanticReviewStatus") == "candidate_for_root_review_unchanged_primary"}
    check(packet_candidates == EXACT_IDS, "v2 unchanged-primary candidate set differs from exact approved set", errors)

    secondary_total = 0
    for case in cases:
        item_id = case["itemId"]
        try:
            candidate = packet_rows[item_id]
            route_row = materials[item_id]
            title = case["title"]
            article = index[title]
        except (KeyError, TypeError):
            errors.append(f"item {item_id}: missing exact source/material row")
            continue
        exact = candidate.get("exactOwnVariantBinding", {})
        source = candidate.get("source", {})
        variant = article.get("variants", {}).get(str(item_id), {})
        params = variant.get("params", {})
        suffix = str(variant.get("suffix") or "")
        actual_title = candidate.get("sourceTitle")
        p = (case.get("proposedCategory"), case.get("proposedSubcategory"), case.get("proposedIronmanTabKey"))
        raw_route = route_row.get("current", {})
        check(actual_title == title == article.get("title"), f"item {item_id}: title binding differs across policy, literal packet, and index", errors)
        check(candidate.get("semanticReviewStatus") == "candidate_for_root_review_unchanged_primary", f"item {item_id}: not the exact unchanged-primary candidate", errors)
        check(p == (TARGET["category"], TARGET["subcategory"], TARGET["ironmanTabKey"]), f"item {item_id}: proposed target changed", errors)
        check(all(raw_route.get(k) == TARGET[k] for k in TARGET), f"item {item_id}: frozen current primary route changed", errors)
        check(not case.get("proposedTags") and not case.get("addedRoles") and not case.get("tagEvidence"), f"item {item_id}: policy makes an unapproved tag or role claim", errors)
        check((case.get("sourceRevision"), case.get("sourceSha256")) == (article.get("revid"), article.get("sha256")) == (source.get("sourceRevision"), source.get("sourceHash")), f"item {item_id}: exact Wiki source revision/hash differs", errors)
        check(article.get("path", "").replace("\\", "/") == source.get("sourceTextPath", "").replace("\\", "/"), f"item {item_id}: indexed article path differs from packet path", errors)
        check(source.get("articleIndexHash") == EXPECTED["articleIndex"][1], f"item {item_id}: article-index hash is not pinned", errors)
        check(item_id in article.get("exactInfoboxItemIds", []) and str(item_id) in article.get("variants", {}), f"item {item_id}: article index lacks exact ID binding", errors)
        check(exact.get("variantKey") == str(item_id) and str(exact.get("variantSuffix") or "") == suffix, f"item {item_id}: exact variant key/suffix differs", errors)
        selected_id_field = "id" + suffix if suffix else "id"
        selected_name_field = "name" + suffix if suffix else "name"
        selected_examine_field = "examine" + suffix if suffix else "examine"
        check(exact.get("selectedRawIdField") == selected_id_field and params.get(selected_id_field) == str(item_id), f"item {item_id}: selected own numeric ID does not bind", errors)
        check(exact.get("variantName") == variant.get("name") == params.get(selected_name_field), f"item {item_id}: exact variant name differs", errors)
        check(exact.get("selectedRawName") == {"field": selected_name_field, "value": params.get(selected_name_field)}, f"item {item_id}: selected raw name field differs", errors)
        check(exact.get("selectedRawVersion") == {"field": ("version" + suffix if suffix else None), "value": (params.get("version" + suffix) if suffix else None)}, f"item {item_id}: selected version field differs", errors)
        check(exact.get("selectedRawExamine") == {"field": selected_examine_field, "value": params.get(selected_examine_field)}, f"item {item_id}: selected examine field differs", errors)
        check(exact.get("selectedRawOptions") == {"field": "options", "value": params.get("options")}, f"item {item_id}: selected options field differs", errors)
        check(exact.get("numericIdsBoundBySameExactVariantState") == [item_id] and exact.get("thisItemIdPresentInRawNumericField") is True, f"item {item_id}: exact raw state binding is not singleton", errors)
        check(case.get("exactVariantFacts") == [{"field": f, "value": params.get(f)} for f in FACT_FIELDS], f"item {item_id}: all nine exact variant facts differ", errors)
        for field, expected in (("options", "Drop"), ("quest", "No"), ("tradeable", "Yes"), ("equipable", "No"), ("stackable", "Yes"), ("noteable", "No")):
            own_field = field + suffix if suffix and field + suffix in params else field
            check(params.get(own_field) == expected, f"item {item_id}: selected own {field} state is not {expected}", errors)
        check(case.get("semanticExcerpt") == case.get("positiveFunctionExcerpt"), f"item {item_id}: positive function is not the exact reviewed own lead", errors)
        excerpts = candidate.get("literalOwnSubjectAndMechanicExcerpts", [])
        own = next((e for e in excerpts if e.get("kind") == "own_subject_definition_paragraph"), None)
        check(own is not None, f"item {item_id}: no own-subject paragraph in v2 packet", errors)
        if own:
            check(norm(own.get("text", "")) == norm(case.get("semanticExcerpt", "")), f"item {item_id}: policy lead differs from v2 own-subject source", errors)
            low = own.get("text", "").lower()
            check(any(s in low for s in ("farming", "flower patch", "allotment patch", "tree patch", "fruit tree patch", "plant pot", "herb patch", "hops patch", "special patch")) and any(s in low for s in ("plant", "planted", "planting", "sow", "sown", "grow", "growing", "grown")), f"item {item_id}: own lead lacks direct planting/growing signal", errors)
        own_text_path = (ROOT / source.get("sourceTextPath", "").replace("\\", "/")).resolve()
        if not own_text_path.is_file() or digest(own_text_path) != source.get("sourceHash"):
            errors.append(f"item {item_id}: source bytes absent or do not match pinned raw-source SHA-256")
            continue
        raw = own_text_path.read_bytes().decode("utf-8")
        field_lines = exact.get("selectedRawFieldLines", {})
        check(exact.get("rawExactIdLine") in raw and f"|{selected_id_field} = {item_id}" in raw, f"item {item_id}: selected raw exact ID line absent", errors)
        check(field_lines.get("name") in raw and field_lines.get("examine") in raw and field_lines.get("options") in raw, f"item {item_id}: selected raw name/examine/options lines absent", errors)
        for ex in excerpts:
            start, end = ex.get("sourceStartChar"), ex.get("sourceEndChar")
            check(isinstance(start, int) and isinstance(end, int) and raw[start:end] == ex.get("text"), f"item {item_id}: literal excerpt offset is not exact raw source", errors)
        secondary = case.get("secondaryExcerpts", [])
        secondary_total += len(secondary)
        packet_context = [e.get("text", "") for e in excerpts if e.get("kind") in ("positive_or_competing_mechanic_context", "raw_farming_or_recipe_mechanic_template")]
        for quote in secondary:
            check(any(norm(quote) == norm(raw_ex) for raw_ex in packet_context), f"item {item_id}: secondary quote is not a literal v2 packet citation", errors)
            check(norm(quote) in norm(raw), f"item {item_id}: secondary quote is not in the pinned raw source", errors)
        audit_row = audit_rows.get(item_id, {})
        check(audit_row.get("title") == title and audit_row.get("sourceRevision") == article.get("revid") and audit_row.get("sourceSha256") == article.get("sha256"), f"item {item_id}: independent audit source binding differs", errors)
        check(audit_row.get("currentRoute") == audit_row.get("proposedRoute") == TARGET, f"item {item_id}: independent audit route differs", errors)
        check(audit_row.get("secondaryContextCitationCount") == len(secondary), f"item {item_id}: independent secondary count differs", errors)
    check(secondary_total == 126, f"case secondary excerpts total {secondary_total}, expected 126", errors)
    return errors


def verify_policy(policy: dict[str, Any], policy_path: Path | None = None) -> dict[str, Any]:
    """Fail closed for the emitter; technical integrity does not grant approval."""
    fixed_path = CERT / "farming-primary-approved-policy.json"
    actual_path = fixed_path if policy_path is None else policy_path.resolve()
    if actual_path.resolve() != fixed_path.resolve():
        raise ValueError("Farming policy must use its exact fixed approved filename")
    if not actual_path.is_file() or load_json(actual_path) != policy:
        raise ValueError("Farming policy argument differs from the saved approved policy")
    approvals = load_json(APPROVALS_PATH)
    approval = approvals.get("approvedPolicies", {}).get(fixed_path.name)
    if not isinstance(approval, dict) or digest(actual_path) != approval.get("sha256"):
        raise ValueError("Farming policy bytes differ from the detached root approval pin")
    result = _verify_policy_report(policy, actual_path)
    if result.get("status") != "PASS" or not result.get("recordedRootApproval"):
        raise ValueError("Farming primary verification failed: " + "; ".join(result.get("errors", [])))
    return {**result, "technicalGate": "passed", "exactIdsVerified": 51,
            "scope": "unchanged primary category/subcategory/tab only; tags and secondary roles unassessed"}


def verify_draft() -> dict[str, Any]:
    errors: list[str] = []
    objects = source_objects(errors)
    draft = objects.get("immutableRootDraft")
    if draft is not None:
        compare_pin_maps({"sourceHashes": {k: h for k, (_, h) in EXPECTED.items()}, "sourceInputPaths": {k: p.relative_to(ROOT).as_posix() for k, (p, _) in EXPECTED.items()}}, errors)
        errors.extend(verify_cases(draft.get("cases", []), objects))
    return {"status": "PASS" if not errors else "FAIL", "mode": "draft_only_read_only", "draftSha256": digest(DRAFT_PATH) if DRAFT_PATH.is_file() else None, "verifiedIds": 51 if not errors else None, "errors": errors, "approval": "not attempted; draft mode cannot approve"}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--draft", action="store_true", help="verify frozen sources and root draft only")
    parser.add_argument("policy", nargs="?", type=Path, help="approved policy path (must be under the fixed CERT directory)")
    args = parser.parse_args()
    if args.draft:
        result = verify_draft()
    elif args.policy:
        result = verify_policy(load_json(args.policy), args.policy)
    else:
        parser.error("provide --draft or an approved policy path")
    print(json.dumps(result, sort_keys=True, ensure_ascii=False, indent=2))
    return 0 if result.get("status") == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
