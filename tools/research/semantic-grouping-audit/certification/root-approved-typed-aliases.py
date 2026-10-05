#!/usr/bin/env python3
"""Build a separate proposal ledger for typed aliases of the exact root-approved endpoints.

Reads frozen local research inputs only. It never modifies production configuration or
existing review packets. Placeholder and note proposals remain scoped to bank storage.
"""
from __future__ import annotations
import argparse, collections, csv, datetime as dt, hashlib, json, pathlib, re

ROOT = pathlib.Path(__file__).resolve().parents[4]
CERT = ROOT / "tools/research/semantic-grouping-audit/certification"
OUTDIR = ROOT / "tmp/category-certification/root-review"
CLUE_RULE = CERT / "clue-scroll-approved-rule.json"
CLUE_DECISIONS = ROOT / "tmp/category-certification/reviews/root-clue-scrolls/decisions.jsonl"
APPROVED_DECISIONS = ROOT / "tmp/category-certification/checkpoints/0f20ae6/root-approved-decisions-with-clue-scrolls.jsonl"
ROOT_POLICY_APPROVALS = ROOT / "tmp/category-certification/root-review/root-policy-approvals-0f20ae6.json"
POLICY_NAMES = [
    "cleanup-other-policy.json", "materials-approved-policy.json",
    "gear-approved-policy.json", "utility-approved-policy.json",
    "cleanup-gear-approved-policy.json", "gear-slot-approved-policy.json",
]
COHORT_POLICY_NAMES = POLICY_NAMES + ["gear-primary-approved-policy.json"]
EXTENDED_COHORT_POLICY_NAMES = COHORT_POLICY_NAMES + [
    "food-primary-approved-policy.json", "raw-food-primary-approved-policy.json",
]
IDENTITY_LINKS = ROOT / "tmp/category-certification/identity-links.jsonl"
IDENTITY_REPORT = ROOT / "tmp/category-certification/identity-report.json"
ARTICLE_INDEX = ROOT / "tmp/category-certification/wiki-articles/article-index.json"
IDENTITY_POLICY = CERT / "identity-policy.json"
COVERAGE = ROOT / "tmp/category-certification/current-coverage.tsv"
EFFECTIVE = ROOT / "tmp/category-certification/current-effective.tsv"


def digest(path: pathlib.Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def json_file(path: pathlib.Path):
    return json.loads(path.read_text(encoding="utf-8"))


def tsv_by_id(path: pathlib.Path):
    with path.open(encoding="utf-8-sig", newline="") as stream:
        rows = list(csv.DictReader(stream, delimiter="\t"))
    result = {int(row["itemId"]): row for row in rows}
    if len(result) != len(rows):
        raise ValueError(f"duplicate IDs in {path}")
    return rows, result


def approval_sources(expected_endpoint_count):
    """Verify root-pinned exact policy bytes and a frozen root decision checkpoint."""
    approval_packet = json_file(ROOT_POLICY_APPROVALS)
    if approval_packet.get("status") != "root-reviewed exact policy pins":
        raise ValueError("root policy approval packet has unexpected status")
    decision_rows = []
    decision_provenance = {}
    with APPROVED_DECISIONS.open("rb") as decision_stream:
        for line_number, raw in enumerate(decision_stream, 1):
            if not raw.strip():
                continue
            row = json.loads(raw)
            ident = int(row["itemId"])
            if ident in decision_provenance:
                raise ValueError(f"duplicate root decision row for {ident}")
            decision_rows.append(row)
            decision_provenance[ident] = {"lineNumber": line_number,
                                          "lineSha256": hashlib.sha256(raw.rstrip(b"\r\n")).hexdigest()}
    if len(decision_rows) != 34085:
        raise ValueError(f"expected complete 34,085-row decision export, got {len(decision_rows)}")
    decision_hash = digest(APPROVED_DECISIONS)
    clue_hash = digest(CLUE_DECISIONS)
    approvals = approval_packet.get("approvedPolicies", {})
    if not approvals:
        raise ValueError("root policy approval packet contains no exact policy pins")
    policy_cases = {}
    policy_meta = []
    for name in COHORT_POLICY_NAMES:
        pin = approvals.get(name)
        if pin is None:
            raise ValueError(f"cohort policy lacks exact root approval pin: {name}")
        path = CERT / name
        packet = json_file(path)
        raw_hash = digest(path)
        canonical_hash = hashlib.sha256(json.dumps(packet, ensure_ascii=False, sort_keys=True,
                                                     separators=(",", ":")).encode()).hexdigest()
        cases = packet.get("cases", [])
        ids = [int(row["itemId"]) for row in cases]
        if (raw_hash != pin.get("sha256") or canonical_hash != pin.get("canonicalSha256")
                or len(cases) != int(pin.get("caseCount", -1))
                or set(ids) != {int(x) for x in pin.get("approvedItemIds", [])}
                or len(ids) != len(set(ids))):
            raise ValueError(f"root-approved exact policy pin mismatch: {name}")
        policy_cases[name] = {int(row["itemId"]): row for row in cases}
        policy_meta.append({"path": str(path.relative_to(ROOT)).replace("\\", "/"),
                            "sha256": raw_hash, "canonicalSha256": canonical_hash,
                            "caseCount": len(cases), "decision": pin.get("decision")})

    clue_rule = json_file(CLUE_RULE)
    clue_source_rows = [json.loads(line) for line in CLUE_DECISIONS.read_text(encoding="utf-8").splitlines() if line]
    clue_ids = {int(row["itemId"]) for row in clue_source_rows if row.get("decision") == "certify"}
    if clue_ids != {int(x) for x in clue_rule.get("approvedItemIds", [])} or len(clue_ids) != 637:
        raise ValueError("clue rule does not match its exact 637 certified decisions")

    eligible_policy_ids = {ident for cases in policy_cases.values() for ident in cases}
    eligible_ids = eligible_policy_ids | clue_ids
    expected_policy_ids = expected_endpoint_count - 637
    if len(eligible_policy_ids) != expected_policy_ids or len(eligible_ids) != expected_endpoint_count:
        raise ValueError(f"selected root policy pins plus clue rule must yield {expected_endpoint_count:,} IDs; got {len(eligible_policy_ids)} policy and {len(eligible_ids)} total")
    confirmed = [row for row in decision_rows if int(row["itemId"]) in eligible_ids]
    if len(confirmed) != expected_endpoint_count or any(row.get("decision") not in ("revise", "certify") for row in confirmed):
        raise ValueError(f"selected approved endpoint set differs from {expected_endpoint_count:,} confirmed decision rows (got {len(confirmed)})")
    endpoints = {}
    for row in confirmed:
        ident = int(row["itemId"])
        if ident in endpoints:
            raise ValueError(f"duplicate confirmed endpoint {ident}")
        approval = row.get("rootApproval") or {}
        policy_name = pathlib.PurePosixPath(str(approval.get("policyFile", ""))).name
        if policy_name in approvals:
            pin = approvals[policy_name]
            if approval.get("policySha256") != pin["sha256"] or ident not in policy_cases[policy_name]:
                raise ValueError(f"decision {ident} does not match exact root policy approval")
            policy_case = policy_cases[policy_name][ident]
            for row_key in ("proposedCategory", "proposedSubcategory", "proposedIronmanTabKey"):
                if row_key in policy_case and row.get(row_key) != policy_case.get(row_key):
                    raise ValueError(f"decision {ident} differs from pinned policy field {row_key}")
                if row_key != "proposedIronmanTabKey" and row_key not in policy_case:
                    raise ValueError(f"pinned policy case for {ident} lacks required primary field {row_key}")
            kind = "root_policy_" + str(row["decision"])
            source_path = str((CERT / policy_name).relative_to(ROOT)).replace("\\", "/")
            source_hash = pin["sha256"]
        elif "clue" in str(row.get("shard", "")):
            if ident not in clue_ids or approval.get("policySha256") != clue_hash:
                raise ValueError(f"clue endpoint {ident} does not match its exact clue decision source")
            policy_case = None
            kind = "root_clue_certify"
            source_path = str(APPROVED_DECISIONS.relative_to(ROOT)).replace("\\", "/")
            source_hash = decision_hash
        else:
            raise ValueError(f"confirmed endpoint {ident} lacks a recognized root policy/clue proof")
        row_hash = hashlib.sha256(json.dumps(row, ensure_ascii=False, sort_keys=True,
                                             separators=(",", ":")).encode()).hexdigest()
        source_row = decision_provenance[ident]
        endpoints[ident] = {
            "approvalKind": kind, "approvalPath": source_path, "approvalHash": source_hash,
            "currentApprovalSourceSha256": decision_hash, "case": row, "caseSha256": row_hash,
            "rootDecisionPath": str(APPROVED_DECISIONS.relative_to(ROOT)).replace("\\", "/"),
            "rootDecisionSha256": decision_hash, "rootDecisionLine": source_row["lineNumber"],
            "rootDecisionLineSha256": source_row["lineSha256"],
            "rootPolicyApprovalPath": str(ROOT_POLICY_APPROVALS.relative_to(ROOT)).replace("\\", "/"),
            "rootPolicyApprovalSha256": digest(ROOT_POLICY_APPROVALS),
            "rootPolicyPin": approvals.get(policy_name), "policyCase": policy_case,
            "rootApproval": approval,
        }
    if len(endpoints) != expected_endpoint_count:
        raise ValueError(f"expected {expected_endpoint_count:,} unique confirmed endpoints, got {len(endpoints)}")
    status_counts = collections.Counter(row.get("decision") for row in confirmed)
    expected_status_counts = {"revise": 230, "certify": expected_endpoint_count - 230}
    if dict(status_counts) != expected_status_counts:
        raise ValueError(f"root cohort decision counts changed: expected {expected_status_counts}, got {dict(status_counts)}")
    clue_meta = {"rulePath": str(CLUE_RULE.relative_to(ROOT)).replace("\\", "/"),
                 "ruleSha256": digest(CLUE_RULE), "decisionPath": str(CLUE_DECISIONS.relative_to(ROOT)).replace("\\", "/"),
                 "decisionSha256": clue_hash, "certifiedCount": len(clue_ids)}
    manifest = {"rootApprovedDecisionsPath": str(APPROVED_DECISIONS.relative_to(ROOT)).replace("\\", "/"),
                "rootApprovedDecisionsSha256": decision_hash, "rowCount": len(decision_rows),
                "sourceDecisionCounts": dict(collections.Counter(r.get("decision") for r in decision_rows)),
                "cohortDecisionCounts": dict(collections.Counter(r.get("decision") for r in confirmed)),
                "confirmedPrimaryCount": len(endpoints), "cohortItemIds": sorted(eligible_ids),
                "cohortPolicyNames": COHORT_POLICY_NAMES,
                "additionalConfirmedRowsOutsideExplicitCohort": sum(1 for r in decision_rows
                    if r.get("decision") in ("revise", "certify") and int(r["itemId"]) not in eligible_ids)}
    return endpoints, policy_meta, clue_meta, manifest


def endpoint_primary(source):
    case = source["case"]
    category = case.get("proposedCategory")
    subcategory = case.get("proposedSubcategory")
    if not category or not subcategory:
        raise ValueError(f"root-approved endpoint {case.get('itemId')} lacks proposed primary group")
    approved_case = source.get("policyCase") or {}
    clue_scope = str(source.get("rootApproval", {}).get("approvalScope", ""))
    if source["approvalKind"] == "root_clue_certify":
        tab_reviewed = "tab" in clue_scope.lower() and bool(case.get("proposedIronmanTabKey"))
    else:
        tab_reviewed = bool(approved_case.get("proposedIronmanTabKey"))
    return {"itemCategory": category, "subcategory": subcategory,
            "ironmanTabKey": case.get("proposedIronmanTabKey") if tab_reviewed else None,
            "ironmanTabExplicitlyReviewed": tab_reviewed,
            "rootDecisionReportedTabKey": case.get("proposedIronmanTabKey")}


def exact_id_quote(record, ident):
    body_path = pathlib.Path(record['path'])
    if not body_path.is_absolute():
        body_path = ROOT / body_path
    if digest(body_path) != record.get("sha256"):
        raise ValueError(f"pinned article body hash mismatch for item {ident}")
    body = body_path.read_text(encoding='utf-8')
    variant = record.get('variants', {}).get(str(ident), {})
    suffix = variant.get('suffix', '')
    pattern = re.compile(r'^\s*\|\s*id' + re.escape(str(suffix)) + r'\s*=\s*([0-9,\s]+)\s*$', re.I)
    for line in body.splitlines():
        m = pattern.fullmatch(line)
        if m and str(ident) in re.split(r'[\s,]+', m.group(1).strip()):
            return line.strip()
    raise ValueError(f'exact ID line unavailable in article body for {ident}')

def root_source_for(source, article_by_id, ident):
    case = source["case"]
    indexed = article_by_id.get(ident, [])
    if not indexed:
        raise ValueError(f"root-confirmed ID {ident} lacks a direct article-index exact-ID source")
    evidence = [x for x in case.get("evidence", [])
                if x.get("kind") in ("exact_wiki", "direct_variant")
                and int(x.get("itemId", -1)) == ident
                and x.get("sourceRevision") is not None and x.get("sourceHash")]
    approval = None
    title = record = None
    for candidate in evidence:
        title, record = next(((t, r) for t, r in indexed
                             if int(r["revid"]) == int(candidate["sourceRevision"])
                             and r["sha256"] == candidate["sourceHash"]
                             and (not candidate.get("sourceTitle") or t == candidate["sourceTitle"])), (None, None))
        if record is not None:
            approval = candidate
            break
    if record is None:
        raise ValueError(f"root decision exact Wiki evidence does not match the pinned direct exact-ID article source for {ident}")
    if (case.get("rootApproval", {}).get("articleIndexSha256")
            and case["rootApproval"]["articleIndexSha256"] != digest(ARTICLE_INDEX)):
        raise ValueError(f"root decision article-index hash mismatch for {ident}")
    return {"sourceTitle": title, "sourceRevision": record["revid"],
            "revisionTimestamp": record["revisionTimestamp"], "sourceUrl": record["sourceUrl"],
            "sourcePath": record["path"].replace("\\", "/"), "sourceHash": record["sha256"],
            "articleIndexHash": digest(ARTICLE_INDEX),
            "exactIdQuote": exact_id_quote(record, ident),
            "rootApprovalExactEvidence": approval,
            "rootApprovalScope": case.get("rootApproval", {}).get("approvalScope", "primary assignment only"),
            "decision": case.get("decision"), "semanticPredicate": case.get("semanticPredicate", "")}


def endpoint_role_context(source):
    case = source["case"]
    return {
        "scope": case.get("roleClaimScope", "policy case scope only"),
        "approvedRoleClaimsOrCues": case.get("proposedRoles", case.get("addedRoles", [])) or [],
        "approvedTagsOnEndpoint": case.get("proposedTags", []) or [],
        "tagEvidence": case.get("tagEvidence", {}) or {},
        "inheritance": "not inherited through typed cache identity; source/role context remains endpoint-specific",
    }


def line_records(path):
    by_line = {}
    with path.open("rb") as stream:
        for number, raw in enumerate(stream, 1):
            if not raw.strip():
                continue
            row = json.loads(raw)
            by_line[(int(row["fromItemId"]), int(row["toItemId"]), row["relation"])] = {
                "row": row, "lineNumber": number, "lineSha256": hashlib.sha256(raw.rstrip(b"\r\n")).hexdigest()}
    return by_line


def main():
    parser = argparse.ArgumentParser(description="Build root-review-only typed alias proposals from a frozen root decision checkpoint.")
    parser.add_argument("--checkpoint", choices=("0f20ae6", "e192f06"), default="0f20ae6",
                        help="Frozen root-approved endpoint checkpoint; output names remain cohort-specific.")
    args = parser.parse_args()
    global APPROVED_DECISIONS, ROOT_POLICY_APPROVALS, COHORT_POLICY_NAMES
    if args.checkpoint == "e192f06":
        APPROVED_DECISIONS = ROOT / "tmp/category-certification/checkpoints/e192f06/root-approved-decisions-with-clue-scrolls.jsonl"
        ROOT_POLICY_APPROVALS = ROOT / "tmp/category-certification/root-review/root-policy-approvals-e192f06.json"
        COHORT_POLICY_NAMES = EXTENDED_COHORT_POLICY_NAMES
        expected_endpoint_count = 1867
    else:
        APPROVED_DECISIONS = ROOT / "tmp/category-certification/checkpoints/0f20ae6/root-approved-decisions-with-clue-scrolls.jsonl"
        ROOT_POLICY_APPROVALS = ROOT / "tmp/category-certification/root-review/root-policy-approvals-0f20ae6.json"
        COHORT_POLICY_NAMES = POLICY_NAMES + ["gear-primary-approved-policy.json"]
        expected_endpoint_count = 1806
    cohort_suffix = str(expected_endpoint_count)
    endpoints, policy_meta, clue_meta, sim_manifest = approval_sources(expected_endpoint_count)
    coverage_rows, coverage = tsv_by_id(COVERAGE)
    effective_rows, effective = tsv_by_id(EFFECTIVE)
    if len(coverage) != 34085:
        raise ValueError("current assignment export row count changed")
    identity_report = json_file(IDENTITY_REPORT)
    frozen_archive = ROOT / "tmp/category-certification/runelite-index2-item-archive10.bin"
    frozen_config = ROOT / "tmp/category-certification/runelite-config-index-2.bin"
    if digest(frozen_archive) != identity_report["cache"]["frozen_containers"]["runelite-index2-item-archive10.bin"]:
        raise ValueError("frozen item archive hash does not match identity report")
    if digest(frozen_config) != identity_report["cache"]["frozen_containers"]["runelite-config-index-2.bin"]:
        raise ValueError("frozen config index hash does not match identity report")
    identity_hash = digest(IDENTITY_LINKS)
    if identity_report.get("identity_links_sha256") != identity_hash:
        raise ValueError("identity-links detached hash does not match identity report")
    article_index_packet = json_file(ARTICLE_INDEX)
    article_by_id = collections.defaultdict(list)
    for title, record in article_index_packet.items():
        for ident in record.get("exactInfoboxItemIds", []):
            article_by_id[int(ident)].append((title, record))
    for ident, source in endpoints.items():
        if ident not in coverage:
            raise ValueError(f"approved endpoint {ident} missing from current coverage")
        source["primary"] = endpoint_primary(source)
        source["wiki"] = root_source_for(source, article_by_id, ident)
        source["roles"] = endpoint_role_context(source)
    edge_index = line_records(IDENTITY_LINKS)
    edge_rows = []
    relation_counts = collections.Counter()
    bought_count = 0
    exact_source_failures = []
    current_match_counts = collections.Counter()
    approved_match_counts = collections.Counter()
    alias_revision_fields = collections.Counter()
    endpoint_revision_fields = collections.Counter()
    typed_edge_schema = {
        "PLACEHOLDER_FOR": ("placeholderID/placeholderTemplateID", "148/149"),
        "NOTE_VARIANT_OF": ("notedID/notedTemplate", "97/98"),
    }
    for (from_id, to_id, relation), provenance in sorted(edge_index.items()):
        if to_id not in endpoints:
            continue
        if relation == "BOUGHT_VARIANT_OF":
            bought_count += 1
            continue
        if relation not in ("PLACEHOLDER_FOR", "NOTE_VARIANT_OF"):
            continue
        edge = provenance["row"]
        if from_id not in coverage or to_id not in coverage:
            raise ValueError(f"identity edge references missing current assignment: {from_id}->{to_id}")
        typed_evidence = [x for x in edge.get("evidence", []) if x.get("kind") == "typed_identity"]
        wiki_evidence = [x for x in edge.get("evidence", []) if x.get("kind") == "exact_wiki" and int(x.get("itemId", -1)) == to_id]
        if len(typed_evidence) != 1 or not wiki_evidence:
            exact_source_failures.append({"fromItemId": from_id, "toItemId": to_id,
                                          "relation": relation, "typedEvidenceRows": len(typed_evidence),
                                          "exactWikiEvidenceRows": len(wiki_evidence)})
            continue
        te = typed_evidence[0]
        if (int(te.get("fromItemId", -1)) != from_id or int(te.get("toItemId", -1)) != to_id
                or te.get("relation") != relation):
            raise ValueError(f"typed evidence endpoints/relation mismatch {from_id}->{to_id}")
        if (te.get("cacheField"), str(te.get("cacheOpcode"))) != typed_edge_schema[relation]:
            raise ValueError(f"typed identity field/opcode mismatch for {relation} {from_id}->{to_id}")
        if te.get("sourcePath") != str(frozen_archive.relative_to(ROOT)).replace("\\", "/"):
            raise ValueError(f"typed identity points to a different cache artifact for {from_id}->{to_id}")
        if te.get("sourceHash") != identity_report["cache"]["frozen_containers"]["runelite-index2-item-archive10.bin"]:
            raise ValueError(f"cache archive hash mismatch on edge {from_id}->{to_id}")
        if int(te.get("sourceRevision", -1)) != int(identity_report["cache"]["config_archive_revision"]):
            raise ValueError(f"cache archive revision mismatch on edge {from_id}->{to_id}")
        if int(te.get("configIndexRevision", -1)) != int(identity_report["cache"]["index_revision"]):
            raise ValueError(f"cache index revision mismatch on edge {from_id}->{to_id}")
        alias = coverage[from_id]
        target = coverage[to_id]
        alias_effective = effective[from_id]
        target_effective = effective[to_id]
        approved = endpoints[to_id]
        exact_index_source = approved["wiki"]
        if not any(int(x.get("sourceRevision", -1)) == exact_index_source["sourceRevision"]
                   and x.get("sourceHash") == exact_index_source["sourceHash"]
                   and int(x.get("itemId", -1)) == to_id for x in wiki_evidence):
            raise ValueError(f"edge exact Wiki evidence fails target source check {from_id}->{to_id}")
        target_primary = approved["primary"]
        category_matches = alias["itemCategory"] == target_primary["itemCategory"]
        subcategory_matches = alias["subcategory"] == target_primary["subcategory"]
        tab_explicit = target_primary["ironmanTabExplicitlyReviewed"]
        tab_matches = alias["ironmanTabKey"] == target_primary["ironmanTabKey"] if tab_explicit else None
        required_fields = []
        if not category_matches: required_fields.append("itemCategory")
        if not subcategory_matches: required_fields.append("subcategory")
        if tab_explicit and not tab_matches: required_fields.append("ironmanTabKey")
        current_triple_match = all(alias[k] == target[k] for k in ("itemCategory", "subcategory", "ironmanTabKey"))
        approved_primary_match = category_matches and subcategory_matches and (tab_matches is not False)
        current_match_counts["sameTriple" if current_triple_match else "differentTriple"] += 1
        for field in ("itemCategory", "subcategory", "ironmanTabKey"):
            current_match_counts[field + ("Matches" if alias[field] == target[field] else "Differs")] += 1
        approved_match_counts["matchesReviewedPrimary" if approved_primary_match else "differsFromReviewedPrimary"] += 1
        approved_match_counts["tabExplicitlyReviewed"] += int(tab_explicit)
        approved_match_counts["tabNotExplicitlyReviewed"] += int(not tab_explicit)
        approved_match_counts["categoryMatchesReviewed"] += int(category_matches)
        approved_match_counts["subcategoryMatchesReviewed"] += int(subcategory_matches)
        if tab_explicit:
            approved_match_counts["tabMatchesReviewed"] += int(bool(tab_matches))
            approved_match_counts["tabDiffersReviewed"] += int(not bool(tab_matches))
        for field in required_fields: alias_revision_fields[field] += 1
        endpoint_fields = []
        if target["itemCategory"] != target_primary["itemCategory"]: endpoint_fields.append("itemCategory")
        if target["subcategory"] != target_primary["subcategory"]: endpoint_fields.append("subcategory")
        if tab_explicit and target["ironmanTabKey"] != target_primary["ironmanTabKey"]: endpoint_fields.append("ironmanTabKey")
        for field in endpoint_fields: endpoint_revision_fields[field] += 1
        relation_counts[relation] += 1
        tags = lambda row: [v for v in re.split(r"[,;|]", row.get("tags", "")) if v.strip()]
        row = {
            "proposalStatus": "PROPOSED_FOR_ROOT_REVIEW_ONLY",
            "proposalScope": ("placeholder bank snapshot canonicalization to root-approved endpoint; primary category/subcategory and explicit reviewed tab only"
                              if relation == "PLACEHOLDER_FOR"
                              else "bank-storage note conversion to root-approved endpoint only; no worn/eaten/held-state equivalence"),
            "relation": relation,
            "fromItemId": from_id,
            "toItemId": to_id,
            "endpointRootApproved": True,
            "endpointApproval": {"kind": approved["approvalKind"], "path": approved["approvalPath"],
                                 "fileSha256": approved["approvalHash"], "caseSha256": approved["caseSha256"],
                                 "decision": approved["case"].get("decision"),
                                 "title": exact_index_source["sourceTitle"], "reviewer": approved["case"].get("reviewer"),
                                 "rootDecisionPath": approved["rootDecisionPath"],
                                 "rootDecisionSha256": approved["rootDecisionSha256"],
                                 "rootDecisionLine": approved["rootDecisionLine"],
                                 "rootDecisionLineSha256": approved["rootDecisionLineSha256"],
                                 "rootPolicyApprovalPath": approved["rootPolicyApprovalPath"],
                                 "rootPolicyApprovalSha256": approved["rootPolicyApprovalSha256"]},
            "endpointProposedPrimary": target_primary,
            "endpointPrimarySemanticEvidence": {"itemId": to_id, **exact_index_source},
            "endpointRoleAndTagContext": approved["roles"],
            "cacheIdentityEvidence": {
                "identityLinksPath": str(IDENTITY_LINKS.relative_to(ROOT)).replace("\\", "/"),
                "identityLinksSha256": identity_hash,
                "identityIndexHash": identity_hash,
                "identityLinksLineNumber": provenance["lineNumber"],
                "identityLinksLineSha256": provenance["lineSha256"],
                "fromItemId": from_id, "toItemId": to_id, "relation": relation,
                "cacheField": te["cacheField"], "cacheOpcode": te["cacheOpcode"],
                "sourcePath": te["sourcePath"], "sourceHash": te["sourceHash"],
                "sourceRevision": te["sourceRevision"], "configIndexRevision": te["configIndexRevision"],
                "source": te["source"],
            },
            "rawAssignmentComparison": {
                "aliasCatalogName": alias.get("catalogName", ""),
                "endpointCatalogName": target.get("catalogName", ""),
                "aliasCacheName": edge.get("cacheName", ""),
                "endpointCacheName": edge.get("targetCacheName", ""),
                "aliasCurrentRaw": {k: alias.get(k, "") for k in ("itemCategory", "subcategory", "ironmanTabKey")},
                "endpointCurrentRaw": {k: target.get(k, "") for k in ("itemCategory", "subcategory", "ironmanTabKey")},
                "aliasMatchesEndpointCurrentTriple": current_triple_match,
                "aliasRawTags": tags(alias), "endpointRawTags": tags(target),
                "aliasEffectiveContext": {k: alias_effective.get(k, "") for k in ("workflowKey", "variantFamilyKey", "variantFlags", "duplicateNameKey")},
                "endpointEffectiveContext": {k: target_effective.get(k, "") for k in ("workflowKey", "variantFamilyKey", "variantFlags", "duplicateNameKey")},
                "existingTagsAndRolesAreRawContextOnly": True,
                "inheritTagsOrRoles": False,
            },
            "reviewedPrimaryComparison": {
                "aliasCategoryMatchesEndpointReviewedCategory": category_matches,
                "aliasSubcategoryMatchesEndpointReviewedSubcategory": subcategory_matches,
                "endpointTabWasExplicitlyReviewed": tab_explicit,
                "aliasTabMatchesEndpointReviewedTab": tab_matches,
                "aliasFieldsThatWouldNeedCatalogRevisionToMatchReviewedEndpoint": required_fields,
                "endpointRawFieldsThatDifferFromItsReviewedPrimary": endpoint_fields,
                "rawCatalogStatus": ("ALIAS_ASSIGNMENT_ALREADY_MATCHES_REVIEWED_ENDPOINT_PRIMARY"
                                     if approved_primary_match else "RAW_ALIAS_CATALOG_REVISION_WOULD_BE_NEEDED_TO_MATCH_REVIEWED_ENDPOINT_PRIMARY"),
                "endpointCatalogStatus": ("ENDPOINT_RAW_PRIMARY_MATCHES_REVIEWED_POLICY"
                                          if not endpoint_fields else "ENDPOINT_RAW_CATALOG_REVISION_WOULD_BE_NEEDED_FOR_REVIEWED_PRIMARY"),
                "interpretation": "This is a comparison/proposal only. It does not edit current classifications, certify existing tags/roles, or assert the alias has the endpoint's non-bank role.",
            },
            "runtimeMechanic": ("BankSnapshotReader reads placeholder template/target IDs and BankItemIds.canonical maps a valid placeholder row to placeholderItemId; the snapshot retains placeholder=true and quantity=0."
                                if relation == "PLACEHOLDER_FOR"
                                else "Pinned Wiki Bank mechanics say depositing a bank note converts it to its item equivalent. This is game bank-storage behavior; plugin BankItemIds does not canonicalize note IDs."),
            "proposedHandling": ({"canonicalBankSnapshotItemId": to_id, "primaryGroup": target_primary,
                                  "statePreserved": {"placeholder": True, "quantity": 0},
                                  "scope": "current placeholder snapshot grouping only"}
                                 if relation == "PLACEHOLDER_FOR"
                                 else {"bankDepositTargetItemId": to_id, "primaryGroup": target_primary,
                                       "scope": "game bank-storage conversion only",
                                       "doesNotClaimHeldOrUsedAliasProperties": True}),
            "explicitNonClaims": ["No automatic role/tag inheritance.", "No bought-variant inheritance.",
                                  "No worn, eaten, held-use, tradeability, or acquisition equivalence from a note edge.",
                                  "No raw catalog field has been changed."],
        }
        edge_rows.append(row)
    if exact_source_failures:
        raise ValueError(f"edges lacked target Wiki proof: {len(exact_source_failures)}")
    # Preserve one endpoint-source manifest row per approved endpoint even if no alias currently points to it.
    endpoint_manifest = []
    for ident, source in sorted(endpoints.items()):
        endpoint_manifest.append({"itemId": ident, "approvalKind": source["approvalKind"],
                                  "approvalPath": source["approvalPath"], "approvalHash": source["approvalHash"],
                                  "currentApprovalSourceSha256": source["currentApprovalSourceSha256"],
                                  "rootDecisionPath": source["rootDecisionPath"],
                                  "rootDecisionSha256": source["rootDecisionSha256"],
                                  "rootDecisionLine": source["rootDecisionLine"],
                                  "rootDecisionLineSha256": source["rootDecisionLineSha256"],
                                  "rootPolicyApprovalPath": source["rootPolicyApprovalPath"],
                                  "rootPolicyApprovalSha256": source["rootPolicyApprovalSha256"],
                                  "rootPolicyPinSha256": (source["rootPolicyPin"] or {}).get("sha256"),
                                  "caseSha256": source["caseSha256"], "proposedPrimary": source["primary"],
                                  "wikiExactSource": source["wiki"], "roleAndTagContext": source["roles"]})
    identity_policy = json_file(IDENTITY_POLICY)
    bank_mechanics = identity_policy["inputs"]["wikiBankMechanics"]
    for source_name, source_meta in bank_mechanics.items():
        body_path = ROOT / source_meta["bodyPath"].replace("\\", "/")
        if digest(body_path) != source_meta["bodySha256"]:
            raise ValueError(f"pinned Wiki mechanics body hash mismatch: {source_name}")
    runtime_refs = []
    for rel in ["src/main/java/com/pkoka5/ironmanbankarchitect/bank/BankSnapshotReader.java",
                "src/main/java/com/pkoka5/ironmanbankarchitect/bank/BankItemIds.java",
                "src/main/java/com/pkoka5/ironmanbankarchitect/overlay/BankCategoryOverlay.java",
                "src/main/java/com/pkoka5/ironmanbankarchitect/overlay/BankGuideOverlay.java"]:
        p = ROOT / rel
        lines = p.read_text(encoding="utf-8").splitlines()
        refs = []
        for i, line in enumerate(lines, 1):
            if any(token in line for token in ("InventoryID.BANK", "placeholderItemId", "placeholderTemplateId",
                                                "BankItemIds.canonical", "return placeholderItemId",
                                                "categoryIndexFor(canonicalItemId", "itemIds[slot] = canonicalItemId")):
                refs.append({"line": i, "text": line.strip()})
        runtime_refs.append({"path": rel, "sha256": digest(p), "lineEvidence": refs})
    per_relation = {}
    for relation in ("PLACEHOLDER_FOR", "NOTE_VARIANT_OF"):
        relation_rows = [row for row in edge_rows if row["relation"] == relation]
        per_relation[relation] = {
            "proposalRows": len(relation_rows),
            "uniqueAliasIds": len({row["fromItemId"] for row in relation_rows}),
            "uniqueEndpointIds": len({row["toItemId"] for row in relation_rows}),
            "aliasMatchesCurrentEndpointTriple": sum(row["rawAssignmentComparison"]["aliasMatchesEndpointCurrentTriple"] for row in relation_rows),
            "aliasDiffersFromCurrentEndpointTriple": sum(not row["rawAssignmentComparison"]["aliasMatchesEndpointCurrentTriple"] for row in relation_rows),
            "aliasMatchesReviewedEndpointPrimary": sum(row["reviewedPrimaryComparison"]["rawCatalogStatus"] == "ALIAS_ASSIGNMENT_ALREADY_MATCHES_REVIEWED_ENDPOINT_PRIMARY" for row in relation_rows),
            "aliasCatalogRevisionFieldCounts": dict(collections.Counter(field for row in relation_rows for field in row["reviewedPrimaryComparison"]["aliasFieldsThatWouldNeedCatalogRevisionToMatchReviewedEndpoint"])),
            "endpointCatalogRevisionFieldCounts": dict(collections.Counter(field for row in relation_rows for field in row["reviewedPrimaryComparison"]["endpointRawFieldsThatDifferFromItsReviewedPrimary"])),
        }
    report = {
        "schema": "ironman-bank-architect.root-confirmed-typed-alias-proposals.v2",
        "generatedAtUtc": dt.datetime.now(dt.timezone.utc).isoformat(),
        "status": "research-only proposals for independent root review; no production edits",
        "approvedEndpointUniverse": {
            "count": len(endpoints),
            "confirmedPolicyPrimaryCount": sum(1 for x in endpoints.values() if x["approvalKind"].startswith("root_policy_")),
            "confirmedCluePrimaryCount": clue_meta["certifiedCount"],
            "allPinnedPolicyCaseCount": sum(x["caseCount"] for x in policy_meta),
            "rootPolicyPinCount": len(policy_meta),
            "policyPinsNotPromotedWithoutDecisionRows": sum(x["caseCount"] for x in policy_meta)
                - sum(1 for x in endpoints.values() if x["approvalKind"].startswith("root_policy_")),
            "decisionCounts": dict(collections.Counter(x["case"]["decision"] for x in endpoints.values())),
            "fullDecisionExportCounts": sim_manifest["sourceDecisionCounts"],
            "additionalConfirmedRowsOutsideThisFrozenCohort": sim_manifest["additionalConfirmedRowsOutsideExplicitCohort"],
            "overlap": 0, "directPinnedExactWikiIdCount": len(endpoints),
            "selectedPolicySources": policy_meta, "clueSource": clue_meta,
            "rootApprovedDecisionsPath": sim_manifest["rootApprovedDecisionsPath"],
            "rootApprovedDecisionsSha256": sim_manifest["rootApprovedDecisionsSha256"],
            "rootPolicyApprovalsPath": str(ROOT_POLICY_APPROVALS.relative_to(ROOT)).replace("\\", "/"),
            "rootPolicyApprovalsSha256": digest(ROOT_POLICY_APPROVALS),
            "approvalBoundary": (f"Exactly the {len(endpoints):,} endpoint IDs in frozen checkpoint {args.checkpoint} and {len(policy_meta)} selected exact policy pins plus the clue rule are in scope: "
                                 f"{sim_manifest['cohortDecisionCounts'].get('revise', 0)} root-pinned policy revisions and "
                                 f"{sim_manifest['cohortDecisionCounts'].get('certify', 0)} certified primary decisions. Rows outside this frozen endpoint set are excluded. "
                                 "Only root-supported category/subcategory and tabs explicitly present in a selected policy case or clue approval scope are treated as reviewed; endpoint roles/tags are never inherited."),
            "endpointSourceManifestPath": f"tmp/category-certification/root-review/root-approved-endpoints-{cohort_suffix}.jsonl",
            "endpointSourceManifestRows": len(endpoint_manifest),
        },
        "frozenInputs": {
            "currentCoveragePath": str(COVERAGE.relative_to(ROOT)).replace("\\", "/"), "currentCoverageSha256": digest(COVERAGE),
            "currentEffectivePath": str(EFFECTIVE.relative_to(ROOT)).replace("\\", "/"), "currentEffectiveSha256": digest(EFFECTIVE),
            "identityLinksPath": str(IDENTITY_LINKS.relative_to(ROOT)).replace("\\", "/"), "identityLinksSha256": identity_hash,
            "identityReportPath": str(IDENTITY_REPORT.relative_to(ROOT)).replace("\\", "/"), "identityReportSha256": digest(IDENTITY_REPORT),
            "articleIndexPath": str(ARTICLE_INDEX.relative_to(ROOT)).replace("\\", "/"), "articleIndexSha256": digest(ARTICLE_INDEX),
            "cacheArchivePath": "tmp/category-certification/runelite-index2-item-archive10.bin",
            "cacheArchiveSha256": identity_report["cache"]["frozen_containers"]["runelite-index2-item-archive10.bin"],
            "configIndexPath": "tmp/category-certification/runelite-config-index-2.bin",
            "configIndexSha256": identity_report["cache"]["frozen_containers"]["runelite-config-index-2.bin"],
            "itemArchiveRevision": identity_report["cache"]["config_archive_revision"],
            "configIndexRevision": identity_report["cache"]["index_revision"],
        },
        "incomingTypedEdges": {
            "placeholderRows": sum(1 for x in edge_rows if x["relation"] == "PLACEHOLDER_FOR"),
            "noteRows": sum(1 for x in edge_rows if x["relation"] == "NOTE_VARIANT_OF"),
            "boughtEdgesToEndpointsExcludedFromAutomaticInheritance": bought_count,
            "proposalRows": len(edge_rows),
            "uniqueAliasIds": len({x["fromItemId"] for x in edge_rows}),
            "uniqueEndpointIds": len({x["toItemId"] for x in edge_rows}),
            "clueApprovedEndpointsWithIncomingProposalEdges": sum(1 for x in edge_rows if endpoints[x["toItemId"]]["approvalKind"] == "root_clue_certify"),
            "rootPolicyEndpointsWithIncomingProposalEdges": sum(1 for x in edge_rows if endpoints[x["toItemId"]]["approvalKind"].startswith("root_policy_")),
            "identityProofFailures": len(exact_source_failures),
        },
        "assignmentComparison": {
            "aliasVsCurrentCanonicalTriple": dict(current_match_counts),
            "aliasVsReviewedEndpointPrimary": dict(approved_match_counts),
            "aliasFieldRevisionWouldBeNeededCounts": dict(alias_revision_fields),
            "endpointFieldRevisionWouldBeNeededCounts": dict(endpoint_revision_fields),
            "byRelation": per_relation,
            "meaning": "Counts are mechanical raw-field comparisons. They do not constitute approval to edit the runtime catalog; tab comparison is only asserted where the root decision explicitly proposed a tab.",
        },
        "mechanics": {
            "bankWikiSource": bank_mechanics["Bank"],
            "itemsWikiSource": bank_mechanics["Items"],
            "runtimeCode": runtime_refs,
            "policy": {
                "PLACEHOLDER_FOR": "In the current bank snapshot path only, valid placeholder template/target values map the slot to the placeholder target; retain placeholder state and zero quantity.",
                "NOTE_VARIANT_OF": "Bank Wiki page supports deposit-time conversion of a note to its item equivalent. Restrict proposal to bank storage; the plugin has no note canonicalization, and this edge says nothing about wearing, eating, or held-note use.",
                "BOUGHT_VARIANT_OF": "No automatic inheritance; zero such incoming edges were found for these endpoints.",
            },
            "runtimeVerificationBoundary": {
                "typedCacheEdge": "Proves only the directed alias-ID to target-ID relation in the exact frozen item-definition archive; it does not prove that the live bank slot currently presents that alias or that any item actions/stats/effects are shared.",
                "placeholder": "Verify the live RuneLite Bank ItemComposition for the bank slot exposes a valid placeholder template marker and parent placeholder item ID; only then BankItemIds.canonical maps the slot's presented alias ID to that parent ID. The proposal is limited to parent primary-group lookup and retains placeholder=true and quantity=0. An offline typed edge alone is not runtime-slot proof.",
                "note": "The plugin currently does not canonicalize note IDs. Preserve the note alias ID as observed by the runtime catalog; Wiki bank-deposit conversion supports only a game bank-storage proposal, not automatic plugin grouping or item behavior inheritance.",
                "bought": "Never inherit automatically."
            },
        },
        "verifyAppliedScopeRecommendation": {
            "ledgerCodePath": "tools/research/semantic-grouping-audit/certification/ledger.py",
            "ledgerCodeSha256": digest(ROOT / "tools/research/semantic-grouping-audit/certification/ledger.py"),
            "currentGateBehavior": "verify_applied keys each actionable row by decision.itemId and directly compares proposed category/subcategory/tab/tags to the fresh export row with that same raw ID.",
            "placeholderScope": "Keep raw catalog assignment and effective bank-slot lookup as separate assertions. For bank-slot grouping only, if a pinned typed PLACEHOLDER_FOR edge and runtime ItemComposition marker/parent resolve alias ID to endpoint ID, verify the endpoint's effective assignment through the canonical parent ID. Do not require the raw placeholder alias catalog row to be rewritten to that category; report its raw fields separately.",
            "noteScope": "Do not reinterpret NOTE_VARIANT_OF as plugin canonicalization. Wiki Bank documents storage conversion; current plugin lookup preserves raw note IDs if observed. Keep the typed note edge as storage-conversion evidence and do not assert effective note alias grouping or transfer Wear/Eat/use properties.",
            "recommendedDecisionFields": {"rawCatalogIdentity": "fromItemId", "bankLookupIdentity": "toItemId only for verified placeholder runtime path", "verificationScope": ["raw_catalog_item", "placeholder_bank_parent_lookup", "bank_storage_conversion_only"]},
            "approvalBoundary": "This proposal makes no production change and does not approve any identity, classification, action, stat, role, or tag inheritance."
        },
        "limitations": ["This packet covers exactly the frozen 1,806 endpoint IDs from the 0f20ae6 checkpoint: 230 root-pinned policy revisions, 939 gear-primary certifications, and 637 clue certifications. Later approvals are excluded.",
                        "In this proposal, all 1,627 incoming alias edges point to the 1,169 policy endpoints; no clue endpoint has an incoming edge. None of the edge targets explicitly reviewed a tab, so alias tab comparisons are omitted.",
                        "No source/role/tag context is inherited from endpoint to alias.",
                        "Raw current-vs-reviewed mismatches are reported as revision deltas to review, not accepted edits.",
                        "All proposal rows are confined to typed placeholder/note edges whose target is in the frozen 1,806 endpoint set; no bought edges or action/stat/effect equivalence is asserted."],
    }
    OUTDIR.mkdir(parents=True, exist_ok=True)
    ledger = OUTDIR / f"root-confirmed-typed-alias-proposals-{cohort_suffix}.jsonl"
    endpoint_path = OUTDIR / f"root-approved-endpoints-{cohort_suffix}.jsonl"
    compact_path = OUTDIR / f"root-confirmed-typed-alias-review-{cohort_suffix}.tsv"
    ledger.write_text("".join(json.dumps(x, ensure_ascii=False, sort_keys=True) + "\n" for x in edge_rows), encoding="utf-8")
    endpoint_path.write_text("".join(json.dumps(x, ensure_ascii=False, sort_keys=True) + "\n" for x in endpoint_manifest), encoding="utf-8")
    compact_fields = [
        "fromItemId", "relation", "toItemId", "endpointApprovalKind", "endpointDecision",
        "endpointCategory", "endpointSubcategory", "endpointTabReviewed", "endpointTab",
        "aliasRawCategory", "aliasRawSubcategory", "aliasRawTab", "endpointRawCategory",
        "endpointRawSubcategory", "endpointRawTab", "aliasMatchesReviewedPrimary",
        "aliasFieldsNeedingCatalogRevision", "inheritanceBoundary", "cacheField", "cacheOpcode",
        "cacheSourcePath", "cacheSourceHash", "cacheRevision", "configIndexRevision",
        "identityLinksSha256", "identityLinksLine", "identityLinksLineSha256",
        "wikiTitle", "wikiRevision", "wikiSourceHash", "wikiBodyPath", "wikiArticleIndexHash",
        "rootDecisionPath", "rootDecisionSha256", "rootDecisionLine", "rootDecisionLineSha256",
    ]
    with compact_path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=compact_fields, delimiter="\t", lineterminator="\n")
        writer.writeheader()
        for item in edge_rows:
            assignment = item["rawAssignmentComparison"]
            comparison = item["reviewedPrimaryComparison"]
            cache = item["cacheIdentityEvidence"]
            wiki = item["endpointPrimarySemanticEvidence"]
            approval = item["endpointApproval"]
            proposed = item["endpointProposedPrimary"]
            writer.writerow({
                "fromItemId": item["fromItemId"], "relation": item["relation"], "toItemId": item["toItemId"],
                "endpointApprovalKind": approval["kind"], "endpointDecision": approval.get("decision", ""),
                "endpointCategory": proposed["itemCategory"], "endpointSubcategory": proposed["subcategory"],
                "endpointTabReviewed": proposed["ironmanTabExplicitlyReviewed"], "endpointTab": proposed["ironmanTabKey"] or "",
                "aliasRawCategory": assignment["aliasCurrentRaw"]["itemCategory"],
                "aliasRawSubcategory": assignment["aliasCurrentRaw"]["subcategory"],
                "aliasRawTab": assignment["aliasCurrentRaw"]["ironmanTabKey"],
                "endpointRawCategory": assignment["endpointCurrentRaw"]["itemCategory"],
                "endpointRawSubcategory": assignment["endpointCurrentRaw"]["subcategory"],
                "endpointRawTab": assignment["endpointCurrentRaw"]["ironmanTabKey"],
                "aliasMatchesReviewedPrimary": comparison["rawCatalogStatus"],
                "aliasFieldsNeedingCatalogRevision": ",".join(comparison["aliasFieldsThatWouldNeedCatalogRevisionToMatchReviewedEndpoint"]),
                "inheritanceBoundary": "placeholder bank snapshot grouping only" if item["relation"] == "PLACEHOLDER_FOR" else "bank deposit conversion only; no plugin note canonicalization",
                "cacheField": cache["cacheField"], "cacheOpcode": cache["cacheOpcode"],
                "cacheSourcePath": cache["sourcePath"], "cacheSourceHash": cache["sourceHash"],
                "cacheRevision": cache["sourceRevision"], "configIndexRevision": cache["configIndexRevision"],
                "identityLinksSha256": cache["identityLinksSha256"], "identityLinksLine": cache["identityLinksLineNumber"],
                "identityLinksLineSha256": cache["identityLinksLineSha256"],
                "wikiTitle": wiki["sourceTitle"], "wikiRevision": wiki["sourceRevision"],
                "wikiSourceHash": wiki["sourceHash"], "wikiBodyPath": wiki["sourcePath"],
                "wikiArticleIndexHash": wiki["articleIndexHash"], "rootDecisionPath": approval["rootDecisionPath"],
                "rootDecisionSha256": approval["rootDecisionSha256"], "rootDecisionLine": approval["rootDecisionLine"],
                "rootDecisionLineSha256": approval["rootDecisionLineSha256"],
            })
    report["proposalLedgerPath"] = str(ledger.relative_to(ROOT)).replace("\\", "/")
    report["proposalLedgerSha256"] = digest(ledger)
    report["endpointSourceManifestSha256"] = digest(endpoint_path)
    report["compactReviewPath"] = str(compact_path.relative_to(ROOT)).replace("\\", "/")
    report["compactReviewSha256"] = digest(compact_path)
    report["compactReviewRows"] = len(edge_rows)
    (OUTDIR / f"root-confirmed-typed-alias-report-{cohort_suffix}-corrected.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"proposalRows": len(edge_rows), "counts": report["incomingTypedEdges"],
                      "assignmentComparison": report["assignmentComparison"],
                      "ledgerSha256": report["proposalLedgerSha256"],
                      "endpointManifestSha256": report["endpointSourceManifestSha256"]}, ensure_ascii=False, indent=2))

if __name__ == "__main__":
    main()
