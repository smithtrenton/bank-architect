#!/usr/bin/env python3
"""Verify the separately approved Gear overlay over the published bank ledger."""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
CERT = Path(__file__).resolve().parent
PACKET = ROOT / 'tmp/root-review/gear-primary-beyond411-exact19-overlay-draft-sealed-20261004'
POLICY = CERT / 'gear-primary-exact19-approved-policy.json'
AUTHORITY = CERT / 'gear-primary-exact19-root-authorization.json'
APPROVALS = CERT / 'gear-primary-exact19-overlay-approvals.json'
WRITER = CERT / 'emit-gear-primary-exact19-overlay.py'
EXPECTED_IDS = [78, 428, 538, 542, 544, 546, 548, 589, 746, 747, 767, 777, 778, 845, 847, 855, 859, 1017, 1035]
POLICY_SHA = '09c7675fee1af67aa5c178bb86730ca5a83206b52c0f995e6442fd87b52a62b4'
PACKET_SHA = '97c95f233f45d1bd33f4f456f66d49accc828d8e712f9fd476d87b8ca48d08bb'
READING_SHA = '3d894ed915cd4294417639f1b28f59d28026a4e69316b8ad3d944bdf85ab21d9'
BASE_SHA = '2584dad7df4f0bb764bcaf4af1f5962b8cdcf247f47a8d4987155baac185001a'
INDEPENDENT = ROOT / 'tmp/root-review/gear-primary-beyond411-exact19-independent-audit-20261004/manifest.json'
INDEPENDENT_SHA = 'ca4cc16945d9684cdbc11d5d8804303bd7f01accbe16cc56caa150cf1b044b05'
SCOPE = 'primary category, subcategory, and tab only'
UNAPPROVED = ['tags', 'supplemental roles', 'availability', 'account access', 'acquisition', 'depositability', 'bankability', 'live bank state', 'secondary facts', 'semantic completeness']

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'))

def read_json(path):
    return json.loads(path.read_bytes())

def require(condition, message):
    if not condition:
        raise ValueError(message)

def checked(path, expected):
    require(sha(path) == expected, f'Hash differs: {path}')

def contained(parent, relative):
    path = (parent / relative).resolve()
    require(path.is_relative_to(parent.resolve()), f'Pin escapes packet: {relative}')
    return path

def replay_sources():
    """Replay the fixed root-reading packet before importing its checked composer."""
    checked(PACKET / 'packet-manifest.json', PACKET_SHA)
    for relative, expected in read_json(PACKET / 'packet-manifest.json')['files'].items():
        checked(contained(PACKET, relative), expected)
    checked(INDEPENDENT, INDEPENDENT_SHA)
    independent = read_json(INDEPENDENT)
    require(independent['fileCount'] == len(independent['files']) == 13, 'Independent audit file count differs')
    for entry in independent['files']:
        path = contained(INDEPENDENT.parent, entry['path'])
        checked(path, entry['sha256'])
        require(path.stat().st_size == entry['bytes'], f'Independent audit size differs: {path}')
    source = PACKET / 'compose-gear-overlay-draft.py'
    spec = importlib.util.spec_from_file_location('sealed_gear19_source_replay', source)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    base, assignments, coverage, cases = module.validate_inputs()
    require(module.BASE_DECISIONS_SHA256 == BASE_SHA, 'Frozen base constant differs')
    return module, base, assignments, coverage, cases

def tag_passthroughs(base, coverage, cases):
    """Document catalog tags carried into a decision without approving their meaning."""
    result = {}
    for case in cases:
        item = case['itemId']
        tags = [x for x in coverage[item].get('tags', '').split(',') if x]
        prior = base[item].get('proposedTags', [])
        if prior != tags:
            result[str(item)] = {'priorDecisionTags': prior, 'existingCompiledTags': tags,
                                 'assessment': 'unassessed', 'newTagApproval': False}
    return result

def load_approved_inputs():
    """Separate root authorization and output pins are required in every CLI mode."""
    checked(POLICY, POLICY_SHA)
    pins = read_json(APPROVALS)
    require(pins.get('schema') == 'root-approved-gear19-overlay-pins/v1', 'Unknown approval-pin schema')
    require(pins.get('status') == 'root-reviewed exact overlay pins', 'Overlay is not approved')
    for path, field in [(POLICY, 'policySha256'), (AUTHORITY, 'rootAuthorizationSha256'), (Path(__file__), 'verifierSha256'), (WRITER, 'writerSha256')]:
        checked(path, pins[field])
    require(pins.get('approvedItemIds') == EXPECTED_IDS and pins.get('caseCount') == 19, 'Approval ID scope differs')
    require(pins.get('approvedAxis') == SCOPE, 'Approval axes differ')
    module, base, assignments, coverage, cases = replay_sources()
    authority = read_json(AUTHORITY)
    require(authority.get('schema') == 'root-approved-gear19-post-bank-overlay/v1', 'Unknown authority schema')
    require(authority.get('approvalStatus') == 'root-approved exact primary placements', 'No root approval')
    require(authority.get('selectedIds') == EXPECTED_IDS and authority.get('heldIds') == [942], 'Authority ID/hold scope differs')
    require(authority.get('caseCount') == 19 and authority.get('expectedChangedObjectIds') == EXPECTED_IDS, 'Authority delta differs')
    require(authority.get('approvedAxis') == SCOPE and authority.get('unapprovedAxes') == UNAPPROVED, 'Authority axes differ')
    require(authority.get('expectedDecision') == 'certify', 'Authority decision differs')
    require(authority.get('tagPassThroughs') == tag_passthroughs(base, coverage, cases), 'Catalog tag pass-through scope differs')
    require(authority.get('policySha256') == POLICY_SHA and authority.get('policyFile') == POLICY.name, 'Authority policy differs')
    require(authority.get('policyCanonicalSha256') == hashlib.sha256(canonical(read_json(POLICY)).encode()).hexdigest(), 'Canonical policy differs')
    require(read_json(POLICY)['cases'] == cases, 'Installed cases differ from root-read frozen cases')
    require(authority.get('rootReadingManifestSha256') == READING_SHA, 'Root reading differs')
    require(authority.get('researchPacketManifestSha256') == PACKET_SHA and authority.get('independentOverlayAuditSha256') == INDEPENDENT_SHA, 'Research gate provenance differs')
    expected_inputs = {
        'publishedBaseDecisionSha256': module.BASE_DECISIONS_SHA256,
        'publishedAssignmentsSha256': module.BASE_TSV_SHA256,
        'publishedAssignmentsManifestSha256': module.BASE_MANIFEST_SHA256,
        'compiledExportSha256': module.BASE_COVERAGE_SHA256,
        'articleIndexSha256': module.INDEX_SHA256,
        'rootReadingSha256': module.ROOT_READING_SHA256,
        'sourceReviewManifestSha256': module.SOURCE_REVIEW_MANIFEST_SHA256,
        'sourceReadingPacketSha256': module.SOURCE_READING_PACKET_SHA256,
        'sourcePinsSha256': module.SOURCE_PINS_SHA256,
        'independentSourceAssessmentSha256': module.INDEPENDENT_ASSESSMENT_SHA256,
        'existingLegacy32PolicyApprovalAggregateSha256': module.LEGACY_POLICY_AGGREGATE_SHA256,
        'v8PublicationProofSha256': module.V8_PUBLICATION_PROOF_SHA256,
    }
    require(all(authority.get(key) == value for key, value in expected_inputs.items()), 'Authority source/base pins differ')
    require(authority.get('overlayVerifierSha256') == sha(Path(__file__)) and authority.get('overlayWriterSha256') == sha(WRITER), 'Authority tool hashes differ')
    for case in cases:
        key = str(case['itemId'])
        require(authority['caseCanonicalSha256ByItemId'][key] == hashlib.sha256(canonical(case).encode()).hexdigest(), f'Case differs: {key}')
        require(authority['articleRevisionAndPageSha256ByItemId'][key] == {'sourceRevision': case['sourceRevision'], 'sourceSha256': case['sourceSha256']}, f'Own-page authority differs: {key}')
    require(set(authority['caseCanonicalSha256ByItemId']) == {str(i) for i in EXPECTED_IDS}, 'Extra authorized cases')
    # Both current installed policy layers remain pinned; the published base is
    # historical and need not remain the live ledger after overlay publication.
    checked(CERT / 'root-policy-approvals.json', module.LEGACY_POLICY_AGGREGATE_SHA256)
    legacy = read_json(CERT / 'root-policy-approvals.json')['approvedPolicies']
    require(len(legacy) == 32, 'Legacy policy count differs')
    for name, entry in legacy.items():
        checked(contained(CERT, name), entry['sha256'])
    for name, expected in read_json(PACKET / 'packet-manifest.json')['files'].items():
        if name.startswith('frozen/v8/') and Path(name).name not in {'publication-proof.json', 'manifest-lf-normalization-proof.json'}:
            checked(CERT / Path(name).name, expected)
    checked(ROOT / 'tmp/category-certification/after-coverage.tsv', module.BASE_COVERAGE_SHA256)
    checked(ROOT / 'tmp/category-certification/wiki-articles/article-index.json', module.INDEX_SHA256)
    return module, base, assignments, coverage, cases, authority, pins

def expected_rows(module, base, coverage, cases, authority_sha):
    """Construct exact primary records; retain every existing unrelated object."""
    rows = dict(base)
    index = read_json(PACKET / 'frozen/article-index.json')
    for case in cases:
        item = case['itemId']
        tags = [x for x in coverage[item].get('tags', '').split(',') if x]
        row = module.draft_row(base[item], case, tags, index[case['title']]['sourceUrl'])
        row.pop('simulationOnly')
        row['reviewer'] = 'root-approved exact19 post-bank primary overlay'
        row['semanticPredicate'] = 'Exact own-page selected state has source-supported equipment function and positive bonuses; primary placement only.'
        row['rootApproval'] = {
            'policyFile': POLICY.name, 'policySha256': POLICY_SHA,
            'policySourceTitle': case['title'], 'policySourceRevision': case['sourceRevision'],
            'policySourceSha256': case['sourceSha256'], 'articleIndexSha256': module.INDEX_SHA256,
            'secondaryExcerpts': case['secondaryExcerpts'], 'exactVariantFacts': case['exactVariantFacts'],
            'tagEvidence': {}, 'rootAuthorizationFile': AUTHORITY.name,
            'rootAuthorizationSha256': authority_sha, 'rootReadingManifestSha256': READING_SHA,
            'caseCanonicalSha256': hashlib.sha256(canonical(case).encode()).hexdigest(),
            'approvalScope': 'primary category, subcategory and tab only; retained tags and supplemental roles remain unassessed',
        }
        rows[item] = row
    return rows

def serialized(rows):
    return ''.join(canonical(row) + '\n' for _, row in sorted(rows.items())).encode('utf-8')

def verify(decisions):
    module, base, assignments, coverage, cases, authority, pins = load_approved_inputs()
    expected = expected_rows(module, base, coverage, cases, sha(AUTHORITY))
    raw = decisions.read_bytes()
    actual_rows = [json.loads(line) for line in raw.splitlines() if line]
    actual = {r['itemId']: r for r in actual_rows}
    require(len(actual_rows) == len(actual) == 34085 and set(actual) == set(base), 'Universe differs')
    require(actual == expected, 'Decision objects differ from the authorized exact overlay')
    require(raw == serialized(expected), 'Canonical output bytes differ')
    checked(decisions, pins['expectedOutputSha256'])
    changed = [i for i in sorted(base) if base[i] != actual[i]]
    require(changed == EXPECTED_IDS and actual[942] == base[942], 'Overlay delta/hold differs')
    bank_ids = [i for i, r in base.items() if r.get('rootBankContextApproval')]
    require(len(bank_ids) == 3586 and all(actual[i] == base[i] for i in bank_ids), 'Bank provenance differs')
    correction_ids = {c['itemId'] for c in read_json(PACKET / 'frozen/v8/bank-context-corrections-approved-policy.json')['cases']}
    mismatches = set()
    for item, row in actual.items():
        if row['decision'] in {'certify', 'revise'}:
            cov = coverage[item]
            if (row['proposedCategory'], row['proposedSubcategory'], row['proposedIronmanTabKey'], sorted(row.get('proposedTags', []))) != (cov['itemCategory'], cov['subcategory'], cov['ironmanTabKey'], sorted(x for x in cov.get('tags', '').split(',') if x)):
                mismatches.add(item)
        elif row['decision'] == 'exclude' and row.get('exclusionReason') == 'NON_BANKABLE' and coverage[item].get('auditScope') != 'EXCLUDED_NON_BANKABLE':
            mismatches.add(item)
    require(mismatches == correction_ids and len(mismatches) == 2096, 'Raw-export differences exceed the frozen bank corrections')
    return {'schema': 'approved-gear19-overlay-verification/v1', 'result': 'PASS', 'decisionRows': 34085, 'changedIds': changed,
            'preservedOtherRows': 34066, 'preservedPriorActionableRows': 8133, 'preservedBankContextRows': 3586,
            'preservedExclusions': 707, 'held942Preserved': True, 'rawMismatchIdsExactlyFrozenV8Corrections': 2096,
            'ownPrimary': 3859, 'actionableRows': 8152, 'unresolvedRows': 25933,
            'approvedAxis': SCOPE, 'newSecondaryFactOrTagApprovals': 0, 'outputSha256': sha(decisions)}

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--decisions', type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(verify(args.decisions.resolve()), sort_keys=True, indent=2))
