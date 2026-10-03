#!/usr/bin/env python3
"""Development-only provenance gate for the separately root-approved 151-case Tool primary policy.

The report verifies exact-set/source/state bindings. It does not infer or grant
semantic approval; root review remains a separate decision.
"""
from __future__ import annotations

import argparse
import collections
import hashlib
import json
import re
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[4]
BASE = ROOT / "tmp/category-certification"
DEFAULT_ROOT_DRAFT = BASE / "root-review/tool-primary-root-reviewed-draft.json"
DEFAULT_POLICY = ROOT / "tools/research/semantic-grouping-audit/certification/tool-primary-approved-policy.json"
DEFAULT_CANDIDATE = BASE / "reviews/proposed-unchanged-primary-tools-e8745b79b5f2d3d5/candidate-policy.json"
DEFAULT_FROZEN_PACKET = BASE / "reviewer-packets/tools.jsonl"
DEFAULT_SOURCE_PACKET = BASE / "reviews/root-review-tools-639fb22ed1344ca4/root-review-groups.jsonl"
DEFAULT_MAIN_REVIEW = BASE / "root-review/tools-165-main-thread-source-review-v1.json"
DEFAULT_INDEPENDENT = BASE / "root-review/tools-151-root-draft-adversarial-v1.json"
DEFAULT_ARTICLE_INDEX = BASE / "wiki-articles/article-index.json"
DEFAULT_APPROVALS = ROOT / "tools/research/semantic-grouping-audit/certification/root-policy-approvals.json"
DEFAULT_OUTPUT = BASE / "root-review/tool-primary-provenance-verification-approved.json"
TOOL_TARGET = {"category": "TOOL", "subcategory": None, "ironmanTabKey": "skilling-tools"}
EXCEPTION_ID = 21754
ORIGINAL_HOLDS = {723, 724, 725, 726, 2162, 7449, 9681, 11024, 12800, 28628, 28813, 31985, 34030}
POUCH_IDS = set(range(5509, 5516)) | {26784, 26786}
DEGRADED_POUCH_IDS = {5511, 5513, 5515, 26786}


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def digest_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def path_for(value: str | Path) -> Path:
    path = Path(value)
    return path if path.is_absolute() else ROOT / path


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8-sig").splitlines() if line.strip()]


def plain(text: str) -> str:
    # Only MediaWiki links/emphasis are normalized; wording and template markup
    # stay literal and must come from the pinned source bytes.
    text = re.sub(r"\[\[([^]|]+)\|([^]]+)\]\]", r"\2", text)
    text = re.sub(r"\[\[([^]]+)\]\]", r"\1", text)
    return " ".join(text.replace("'''", "").replace("''", "").split())


def collapsed(text: str) -> str:
    return " ".join(text.split())


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def normalize_hash(value: Any) -> str:
    return str(value or "").removeprefix("sha256:").lower()


def map_facts(case: dict[str, Any]) -> dict[str, str]:
    facts = case.get("exactVariantStateFacts")
    if isinstance(facts, dict):
        return {str(k): str(v) for k, v in facts.items()}
    facts = case.get("exactVariantFacts")
    if isinstance(facts, list):
        return {str(row["field"]): str(row["value"]) for row in facts}
    return {}


def quote_values(case: dict[str, Any]) -> tuple[str, list[str], str]:
    own_lead = case.get("ownSubjectLeadLiteral", case.get("semanticExcerpt", ""))
    positive = case.get("positiveFunctionExcerpt", case.get("positiveFunctionLiteral", ""))
    if not positive:
        positive = case.get("positiveFunctionQuote", "")
    secondary = case.get("secondaryExcerpts", case.get("secondaryFunctionExcerpts", []))
    if isinstance(secondary, str):
        secondary = [secondary]
    return str(own_lead), [str(x) for x in secondary], str(positive)


def exact_page(index: dict[str, Any], title: str, item_id: int) -> dict[str, Any]:
    page = index.get(title)
    require(isinstance(page, dict), f"ID {item_id}: exact source title is absent from article index")
    require(item_id in [int(x) for x in page.get("exactInfoboxItemIds", [])],
            f"ID {item_id}: exact numeric ID is not bound to its own page")
    require(str(item_id) in page.get("variants", {}), f"ID {item_id}: exact own variant facts are absent")
    return page


def verify(args: argparse.Namespace) -> dict[str, Any]:
    policy_path = path_for(args.policy)
    draft_path = path_for(args.root_draft)
    candidate_path = path_for(args.candidate_policy)
    frozen_path = path_for(args.frozen_packet)
    source_path = path_for(args.source_packet)
    main_review_path = path_for(args.main_review)
    independent_path = path_for(args.independent_review)
    index_path = path_for(args.article_index)
    approvals_path = path_for(args.approvals)

    # A missing root draft or independent report is reported as pending input,
    # allowing the technical design to be reviewed before those files land.
    pending: list[str] = []
    required = [policy_path, draft_path, candidate_path, frozen_path, source_path, main_review_path, index_path]
    missing = [str(p) for p in required if not p.is_file()]
    if missing:
        return {"schema": "tool-primary-provenance-verification/v1",
                "status": "PENDING_REQUIRED_INPUTS", "missingInputs": missing,
                "semanticApproval": "not asserted"}

    policy = load_json(policy_path)
    draft_policy = load_json(draft_path)
    candidate_policy = load_json(candidate_path)
    main_review = load_json(main_review_path)
    index = load_json(index_path)

    frozen_rows = {int(r["itemId"]): r for r in load_jsonl(frozen_path)}
    require(len(frozen_rows) == 1237 and all(r.get("shard") == "tools" for r in frozen_rows.values()),
            "frozen Tool packet is not the expected 1,237-ID shard")
    source_groups = load_jsonl(source_path)
    source_rows: dict[int, tuple[dict[str, Any], dict[str, Any]]] = {}
    for group in source_groups:
        for row in group.get("items", []):
            ident = int(row["itemId"])
            require(ident not in source_rows, f"corrected source packet duplicates exact ID {ident}")
            source_rows[ident] = (group, row)
    candidate_records = {int(r["itemId"]): r for r in candidate_policy.get("records", [])}
    require(len(candidate_records) == 165 and set(candidate_records) == set(source_rows),
            "candidate policy and corrected own-source packet do not share the frozen 165-ID set")
    require(len(source_rows) == 165, "corrected own-source packet is not the full 165-ID source-read cohort")

    source_candidate_ids = {i for i, r in candidate_records.items()
                             if r.get("disposition") == "proposed_unchanged_primary"}
    source_held_ids = {i for i, r in candidate_records.items()
                       if r.get("disposition") == "hold_from_unchanged_primary_cohort"}
    require(len(source_candidate_ids) == 152 and source_held_ids == ORIGINAL_HOLDS,
            "original candidate cohort or its 13 source-read holds changed")
    require(set(int(i) for i in main_review.get("pendingPositivePrimaryCandidates", [])) == source_candidate_ids,
            "main-thread source-read pending candidate IDs differ from candidate policy")
    require({int(r["itemId"]) for r in main_review.get("heldExactIds", [])} == ORIGINAL_HOLDS,
            "main-thread source-read held IDs differ from the 13 frozen source holds")
    require(main_review.get("approvalCount") == 0 and main_review.get("reviewedExactItemCount") == 165,
            "main-thread source-read record is not the unapproved full exact cohort")
    require(main_review.get("sourcePacketSha256") == digest_file(source_path),
            "main-thread source-read record does not pin corrected source packet")

    policy_cases = policy.get("cases", [])
    case_map = {int(c["itemId"]): c for c in policy_cases}
    require(len(case_map) == len(policy_cases), "root-reviewed draft repeats an item ID")
    expected_ids = source_candidate_ids - {EXCEPTION_ID}
    require(EXCEPTION_ID in source_candidate_ids and set(case_map) == expected_ids and len(case_map) == 151,
            "root-reviewed draft must contain exactly the 151 candidates after holding only ID 21754")
    require(policy.get("expectedCaseCount") == 151, "draft expectedCaseCount is not 151")
    draft_case_map = {int(c["itemId"]): c for c in draft_policy.get("cases", [])}
    require(len(draft_case_map) == 151 and case_map == draft_case_map,
            "final policy cases differ from the immutable root-reviewed 151-case draft")
    declared_holds = {int(x["itemId"]) for x in policy.get("heldCases", policy.get("explicitAdditionalHolds", []))}
    require(declared_holds == ORIGINAL_HOLDS | {EXCEPTION_ID},
            "draft does not declare exactly the 13 original holds plus the 21754 exception")
    status = str(policy.get("status", "")).casefold()
    require(("root source reviewed" in status or "root-reviewed primary assignments only" in status) and
            "primary" in str(policy.get("scope", "")).casefold(),
            "draft lacks explicit root-reviewed primary-only scope")

    source_paths = {
        "articleIndex": index_path,
        "toolsPacket": frozen_path,
        "sourceReviewPacket": source_path,
        "candidatePacket": candidate_path,
        "rootReadRecord": main_review_path,
    }
    input_hashes = {
        "frozenToolPacket": digest_file(frozen_path),
        "candidatePolicy": digest_file(candidate_path),
        "correctedOwnSourcePacket": digest_file(source_path),
        "mainThreadSourceReview": digest_file(main_review_path),
        "articleIndex": digest_file(index_path),
    }
    hash_key_map = {
        "articleIndex": "articleIndex",
        "toolsPacket": "frozenToolPacket",
        "sourceReviewPacket": "correctedOwnSourcePacket",
        "candidatePacket": "candidatePolicy",
        "rootReadRecord": "mainThreadSourceReview",
    }
    for declared_key, actual_key in hash_key_map.items():
        require(normalize_hash(policy.get("sourceHashes", {}).get(declared_key)) == input_hashes[actual_key],
                f"policy sourceHashes does not pin exact {declared_key} bytes")
    declared_paths = policy.get("sourcePaths", {})
    for key, path in source_paths.items():
        require(path.resolve() == path_for(declared_paths.get(key, "")).resolve(),
                f"draft sourcePaths does not pin the exact {key} artifact")

    independent: dict[str, Any] | None = None
    if independent_path.is_file():
        independent = load_json(independent_path)
        reviewed_ids = set(int(i) for i in independent.get("examinedIds", []))
        exception_rows = independent.get("confirmedPrimaryExceptions", [])
        exception_ids = {int(row["itemId"]) for row in exception_rows}
        require(reviewed_ids == expected_ids and len(reviewed_ids) == 151 and
                exception_ids == {EXCEPTION_ID} and reviewed_ids.isdisjoint(exception_ids) and
                reviewed_ids | exception_ids == source_candidate_ids,
                "independent review must cover 151 positives plus the one exact 21754 exception")
        require(not independent.get("unresolvedPrimaryCases") and
                int(independent.get("counts", {}).get("positiveCases", -1)) == 151 and
                int(independent.get("counts", {}).get("heldCases", -1)) == 14 and
                not independent.get("counts", {}).get("checkFailures"),
                "independent review reports unresolved positive cases or source failures")
        require(normalize_hash(independent.get("draftSha256")) == digest_file(draft_path),
                "independent review is not bound to the immutable root-reviewed draft")
        for field, source_key in (("candidatePacketSha256", "candidatePacket"),
                                  ("sourcePacketSha256", "sourceReviewPacket"),
                                  ("toolsPacketSha256", "toolsPacket"),
                                  ("articleIndexSha256", "articleIndex"),
                                  ("rootReadRecordSha256", "rootReadRecord")):
            require(normalize_hash(independent.get(field)) == normalize_hash(policy["sourceHashes"][source_key]),
                    f"independent review source binding differs: {field}")
        exception = exception_rows[0]
        require(exception.get("status", "").startswith("held as pending") and
                exception.get("recommendedCorrection", {}).get("subcategory") == "slayer-tool" and
                exception.get("currentAssignment", {}).get("subcategory") == "tool",
                "21754 exception does not preserve the pending Slayer-tool correction boundary")
    else:
        pending.append("independent final-151 adversarial report is not present")
    if policy.get("sourceHashes", {}).get("independentReview"):
        require(normalize_hash(policy["sourceHashes"]["independentReview"]) ==
                (digest_file(independent_path) if independent_path.is_file() else ""),
                "policy independentReview hash differs from final adversarial report")
    elif str(policy.get("status", "")) == "root-reviewed primary assignments only":
        raise ValueError("final approved policy must explicitly pin independentReview source hash")

    if policy.get("status") == "root-reviewed primary assignments only":
        require(policy["sourceHashes"].get("immutableRootDraft") == digest_file(draft_path), "approved policy does not pin immutable root draft")
        require(path_for(policy["sourcePaths"].get("immutableRootDraft", "")).resolve() == draft_path.resolve(), "immutable draft path changed")
        require(path_for(policy["sourcePaths"].get("independentReview", "")).resolve() == independent_path.resolve(), "independent report path changed")

    validated_case_checks = 0
    pouch_rows_validated = 0
    tab_counts: collections.Counter[str] = collections.Counter()
    article_bytes_cache: dict[str, str] = {}
    for ident, case in case_map.items():
        candidate = candidate_records[ident]
        group, corrected = source_rows[ident]
        require(ident in frozen_rows, f"ID {ident}: not in immutable frozen Tool packet")
        frozen_current = frozen_rows[ident].get("current", {})
        candidate_current = candidate.get("currentAssignment", {})
        require({k: frozen_current.get(k) for k in ("category", "subcategory", "ironmanTabKey")} ==
                {k: candidate_current.get(k) for k in ("category", "subcategory", "ironmanTabKey")},
                f"ID {ident}: candidate route differs from frozen packet")
        route = candidate.get("proposedAssignment") or candidate.get("currentAssignment")
        expected_tab = "currency-utilities" if ident in {952, 1755} else "skilling-tools"
        expected_current = {"category": "TOOL", "subcategory": candidate["currentAssignment"]["subcategory"],
                            "ironmanTabKey": expected_tab}
        require(candidate["currentAssignment"] == expected_current and route == expected_current,
                f"ID {ident}: candidate does not preserve exact TOOL/subcategory/skilling-tools target")
        case_route = {
            "category": case.get("proposedCategory", case.get("category")),
            "subcategory": case.get("proposedSubcategory", case.get("subcategory")),
            "ironmanTabKey": case.get("proposedIronmanTabKey", case.get("ironmanTabKey")),
        }
        require(case_route == expected_current, f"ID {ident}: approved target is not its unchanged Tool route")
        tab_counts[expected_tab] += 1
        require(candidate.get("source", {}).get("reviewedIdIsExact") is True and
                corrected.get("source", {}).get("reviewedIdIsExact") is True,
                f"ID {ident}: source packet does not affirm exact numeric-ID review")

        source_info = case.get("source", {})
        title = str(case.get("title", source_info.get("title", candidate["source"]["title"])))
        page = exact_page(index, title, ident)
        require(title == candidate["source"]["title"] == corrected["source"]["title"],
                f"ID {ident}: own source title differs across policy/candidate/source packet")
        source_sha = normalize_hash(case.get("sourceSha256", case.get("sourceHash", source_info.get("sha256"))))
        revision = int(case.get("sourceRevision", source_info.get("revision", -1)))
        require(revision == int(page["revid"]) == int(candidate["source"]["revision"]) == int(corrected["source"]["revision"]),
                f"ID {ident}: own article revision mismatch")
        require(source_sha == page["sha256"] == normalize_hash(candidate["source"]["sha256"]) ==
                normalize_hash(corrected["source"]["sha256"]), f"ID {ident}: own article source hash mismatch")
        raw_path = path_for(page["path"])
        require(digest_file(raw_path) == source_sha, f"ID {ident}: pinned own article bytes changed")
        raw = raw_path.read_text(encoding="utf-8")
        article_bytes_cache[title] = raw
        require(ident in [int(i) for i in page["exactInfoboxItemIds"]], f"ID {ident}: article index no longer binds ID")
        require(ident in [int(i) for i in source_info.get("exactInfoboxItemIds", candidate["source"]["exactInfoboxItemIds"])],
                f"ID {ident}: root policy source record omits exact ID")

        own_lead, secondary, positive = quote_values(case)
        expected_lead = str(corrected["firstOwnBoldSubjectLeadLiteral"])
        require(collapsed(own_lead) == collapsed(expected_lead),
                f"ID {ident}: lead differs from corrected own-subject packet")
        candidate_lead = str(candidate.get("ownSubjectLeadLiteral", ""))
        require(collapsed(candidate_lead) == collapsed(expected_lead),
                f"ID {ident}: candidate lead differs from corrected own-subject packet")
        require(collapsed(own_lead) in collapsed(raw), f"ID {ident}: exact own-subject lead is not in pinned article bytes")
        require(bool(positive.strip()) and collapsed(positive) in collapsed(raw),
                f"ID {ident}: positive function excerpt is not literal pinned own-page text")
        corrected_paragraphs = [str(x.get("literalParagraph", ""))
                                for x in corrected.get("allMaterialFunctionAndCompetingUseParagraphs", [])]
        require(collapsed(positive) in collapsed(expected_lead) or
                any(collapsed(positive) == collapsed(x) for x in secondary) or
                any(collapsed(positive) == collapsed(x) for x in corrected_paragraphs),
                f"ID {ident}: positive quote is absent from corrected source-read excerpts")
        for excerpt in secondary:
            require(bool(excerpt.strip()) and collapsed(excerpt) in collapsed(raw),
                    f"ID {ident}: secondary excerpt is not literal pinned own-page text")

        variant = page["variants"][str(ident)]
        params = variant["params"]
        facts = map_facts(case)
        corrected_facts = {str(k): str(v) for k, v in corrected["exactVariantStateFields"].items()}
        require(facts, f"ID {ident}: draft lacks exact variant state facts")
        critical = {k: v for k, v in corrected_facts.items()
                    if k.startswith("id") or k.startswith("name") or k.startswith("options") or
                    k in {"equipable", "stackable", "noteable", "quest", "tradeable"} or
                    k.startswith("version") or k.startswith("destroy")}
        for key, value in critical.items():
            require(facts.get(key) == value, f"ID {ident}: draft omits or changes critical own state fact {key}")
        for key, value in facts.items():
            require(str(params.get(key, "")) == value, f"ID {ident}: own variant fact changed: {key}")
        own_id_fields = [k for k, v in facts.items() if re.fullmatch(r"id\d*", k) and v == str(ident)]
        require(bool(own_id_fields) and all(str(params.get(k, "")) == str(ident) for k in own_id_fields),
                f"ID {ident}: selected variant's own numeric ID changed")

        # An unchanged-primary-only policy must never add roles or tags.
        for field in ("proposedTags", "addedTags", "proposedRoles", "addedRoles", "tagEvidence", "roleEvidence"):
            value = case.get(field)
            require(value in (None, [], {}), f"ID {ident}: draft adds or asserts {field}")

        # Preserve the reviewed own preparation facts and state-specific reduced
        # capacity evidence for essence pouch IDs; no other variant may supply it.
        if ident in POUCH_IDS:
            # The exact selected variant state (New/Degraded, exact ID and
            # options) is checked above. The own functional excerpt must also
            # state its capacity/preparation use, and the degraded variants
            # need their own reduced-capacity paragraph in the case packet.
            require("essence" in plain(positive).casefold() and "hold" in plain(positive).casefold() and
                    any(ch.isdigit() for ch in positive),
                    f"ID {ident}: own preparation/capacity function is missing")
            if ident in DEGRADED_POUCH_IDS:
                reduced = [q for q in secondary if "degrad" in plain(q).casefold() and
                           ("hold" in plain(q).casefold() or "essence" in plain(q).casefold())]
                require(bool(reduced), f"ID {ident}: degraded pouch reduced-capacity excerpt is missing")
                require(all(collapsed(str(q)) in collapsed(raw) and "degrad" in plain(str(q)).casefold() and
                               ("hold" in plain(str(q)).casefold() or "essence" in plain(str(q)).casefold())
                               for q in reduced),
                        f"ID {ident}: reduced-capacity quote is not a literal degraded-state passage")
            pouch_rows_validated += 1

        if ident == 23677:
            proof = case.get("variantFunctionProof")
            require(isinstance(proof, dict), "ID 23677: explicit cosmetic-only variant proof is missing")
            require(int(proof.get("baseItemId", -1)) == 11920 and ident == 23677,
                    "ID 23677: variant proof does not bind Dragon pickaxe 11920 to exact (or) ID 23677")
            require(proof.get("relation") == "finished appearance-only physical variant",
                    "ID 23677: variant proof does not state exact cosmetic-only relationship")
            base_title = str(proof.get("baseTitle", "Dragon pickaxe"))
            base_page = exact_page(index, base_title, 11920)
            base_sha = normalize_hash(proof.get("baseSha256"))
            require(int(proof.get("baseRevision", -1)) == int(base_page["revid"]) and
                    base_sha == base_page["sha256"], "ID 23677: base source revision/hash is not exact")
            base_raw_path = path_for(base_page["path"])
            require(digest_file(base_raw_path) == base_sha, "ID 23677: pinned base Dragon pickaxe bytes changed")
            base_quote = str(proof.get("baseOwnMiningDefinition", ""))
            mapping_quote = str(proof.get("baseExplicitCosmeticMapping", ""))
            finished_quote = str(proof.get("ownFinishedVariantDefinition", ""))
            aesthetic_quote = str(proof.get("ownAppearanceOnlyClause", ""))
            require(base_quote and collapsed(base_quote) in collapsed(base_raw_path.read_text(encoding="utf-8")) and
                    "mining" in plain(base_quote).casefold(), "ID 23677: base's own mining function is not proven")
            mapping_raw = base_raw_path.read_text(encoding="utf-8")
            require(mapping_quote and collapsed(mapping_quote) in collapsed(mapping_raw) and
                    "zalcano shard" in plain(mapping_quote).casefold() and
                    "dragon pickaxe (or)" in plain(mapping_quote).casefold() and
                    "only alters its appearance" in plain(mapping_quote).casefold(),
                    "ID 23677: exact Zalcano-to-(or) appearance-only mapping is not literal base-page text")
            require(collapsed(finished_quote) == collapsed(own_lead) and collapsed(finished_quote) in collapsed(raw),
                    "ID 23677: finished variant own-definition quote is not exact")
            require(aesthetic_quote and collapsed(aesthetic_quote) in collapsed(raw) and
                    "aesthetic" in plain(aesthetic_quote).casefold() and
                    "no additional bonuses" in plain(aesthetic_quote).casefold(),
                    "ID 23677: appearance-only/no-extra-bonus clause is not established")
            require(not any(k in proof for k in ("inheritedRoles", "inheritedTags", "inheritedActions", "inheritedBonuses")),
                    "ID 23677: variant proof carries inherited claims")
        validated_case_checks += 1

    require(dict(tab_counts) == {"skilling-tools": 149, "currency-utilities": 2},
            "unchanged primary tabs differ from the exact 149/2 reviewed route split")

    approval_pin = "pending"
    approval_record_hash = None
    approved_mode = policy.get("status") == "root-reviewed primary assignments only"
    if approved_mode:
        require(policy.get("schema") == 1 and policy.get("scope") == "unchanged primary assignments only",
                "final policy schema/scope does not match the approved primary-only contract")
        require(policy.get("decision") == "certify", "final primary-only policy decision must be certify")
        require(policy.get("expectedCaseCount") == 151 and policy.get("expectedApprovedItemIds") == sorted(expected_ids),
                "final policy must pin exactly the approved 151 case IDs")
        require(independent is not None and
                normalize_hash(policy.get("sourceHashes", {}).get("independentReview")) == digest_file(independent_path),
                "final policy must bind the exact final independent review report")
    if approvals_path.is_file():
        approvals = load_json(approvals_path)
        approval_entry = approvals.get("approvedPolicies", {}).get("tool-primary-approved-policy.json")
        if approval_entry:
            require(approvals.get("schema") == 1 and
                    approvals.get("status") == "root-reviewed exact policy pins",
                    "detached root policy approval container schema/status mismatch")
            canonical = digest(json.dumps(policy, ensure_ascii=False, sort_keys=True,
                                          separators=(",", ":")).encode("utf-8"))
            require(normalize_hash(approval_entry.get("canonicalSha256")) == canonical,
                    "detached root approval canonical policy pin mismatch")
            require(normalize_hash(approval_entry.get("sha256")) == digest_file(policy_path),
                    "detached root approval byte hash mismatch")
            require(approval_entry.get("decision") == "certify" and
                    int(approval_entry.get("caseCount", -1)) == 151 and
                    [int(i) for i in approval_entry.get("approvedItemIds", [])] == sorted(expected_ids),
                    "detached root approval exact ID set/count mismatch")
            approval_pin = "matched detached exact-set root policy pin"
        elif approved_mode:
            raise ValueError("approved Tool policy lacks its detached exact-set approval entry")
        approval_record_hash = digest_file(approvals_path)
    else:
        if approved_mode:
            raise ValueError("approved Tool policy requires the detached root approval record")
        pending.append("detached root policy approval record is not present")
    if approved_mode:
        require(approval_pin == "matched detached exact-set root policy pin",
                "approved status requires a matching detached approval pin")
    else:
        pending.append("final root semantic approval and detached policy pin remain pending")

    return {
        "schema": "tool-primary-provenance-verification/v1",
        "status": "TECHNICAL_PROVENANCE_CHECKS_PASSED_ROOT_REVIEW_REMAINS_SEPARATE" if not pending
                  else "TECHNICAL_PROVENANCE_CHECKS_PASSED_APPROVAL_OR_REPORT_INPUT_PENDING",
        "semanticApproval": "not inferred by this verifier",
        "detachedApprovalPin": approval_pin,
        "pendingRequirements": pending,
        "exactScope": {
            "originalCandidateCount": 152,
            "originalSourceReadHolds": 13,
            "independentExceptionId": EXCEPTION_ID,
            "rootDraftCaseCount": len(case_map),
            "rootDraftItemIds": sorted(case_map),
            "tabCounts": dict(tab_counts),
            "onlyApprovedClaims": "unchanged TOOL category/subcategory and the exact reviewed tab; no added roles or tags",
        },
        "validatedRows": validated_case_checks,
        "pouchPreparationRowsValidated": pouch_rows_validated,
        "variantProofId23677Validated": 23677 in case_map,
        "sourceHashes": {
            **{k: digest_file(p) for k, p in {
                "policy": policy_path,
                "immutableRootDraft": draft_path,
                "candidatePolicy": candidate_path,
                "frozenToolPacket": frozen_path,
                "correctedOwnSourcePacket": source_path,
                "mainThreadSourceReview": main_review_path,
                "articleIndex": index_path,
            }.items()},
            "independentReview": digest_file(independent_path) if independent_path.is_file() else None,
            "detachedApprovalRecord": approval_record_hash,
        },
        "reportNote": "Technical source and exact-set checks establish provenance only; they do not substitute for root semantic approval or apply a production change.",
    }


def verify_policy(policy: dict[str, Any]) -> dict[str, Any]:
    """Replay the exact detached approval using the fixed frozen input paths."""
    require(policy.get("schema") == 1 and policy.get("status") == "root-reviewed primary assignments only", "Tool policy lacks explicit root approval status")
    require(policy == load_json(DEFAULT_POLICY), "supplied Tool policy differs from fixed approved file")
    args = argparse.Namespace(policy=DEFAULT_POLICY, root_draft=DEFAULT_ROOT_DRAFT,
        candidate_policy=DEFAULT_CANDIDATE, frozen_packet=DEFAULT_FROZEN_PACKET,
        source_packet=DEFAULT_SOURCE_PACKET, main_review=DEFAULT_MAIN_REVIEW,
        independent_review=DEFAULT_INDEPENDENT, article_index=DEFAULT_ARTICLE_INDEX,
        approvals=DEFAULT_APPROVALS)
    result = verify(args)
    require(result.get("validatedRows") == 151 and not result.get("pendingRequirements") and
            result.get("detachedApprovalPin") == "matched detached exact-set root policy pin",
            "Tool approved provenance gate is incomplete")
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--policy", default=DEFAULT_POLICY)
    parser.add_argument("--root-draft", default=DEFAULT_ROOT_DRAFT)
    parser.add_argument("--candidate-policy", default=DEFAULT_CANDIDATE)
    parser.add_argument("--frozen-packet", default=DEFAULT_FROZEN_PACKET)
    parser.add_argument("--source-packet", default=DEFAULT_SOURCE_PACKET)
    parser.add_argument("--main-review", default=DEFAULT_MAIN_REVIEW)
    parser.add_argument("--independent-review", default=DEFAULT_INDEPENDENT)
    parser.add_argument("--article-index", default=DEFAULT_ARTICLE_INDEX)
    parser.add_argument("--approvals", default=DEFAULT_APPROVALS)
    parser.add_argument("--output", default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    try:
        result = verify(args)
    except Exception as exc:
        result = {"schema": "tool-primary-provenance-verification/v1", "status": "FAILED",
                  "error": str(exc), "semanticApproval": "not inferred"}
        code = 1
    else:
        code = 0
    output_path = path_for(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": result["status"], "report": str(output_path),
                      "validatedRows": result.get("validatedRows", 0),
                      "pendingRequirements": result.get("pendingRequirements", result.get("missingInputs", []))}, sort_keys=True))
    raise SystemExit(code)


if __name__ == "__main__":
    main()
