#!/usr/bin/env python3
"""Replay the separate exact-ID deposit prohibition and complete export union."""
from __future__ import annotations

import argparse
import csv
import hashlib
import importlib.util
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
CERT = Path(__file__).resolve().parent
POLICY = CERT / 'bank-ignore-supplemental-approved-policy.json'
PIN = CERT / 'bankability-supplemental-approvals.json'
QUOTE = 'The book may no longer be deposited to a bank to prevent their use as an efficient [[Runecraft]] training method.'
PINS = {
    'tmp/category-certification/wiki-articles/text/15311009.txt': '8b59cf506dea330ac3f4784a70371c4ff4666f57bad34f300b2aea49c8f412ac',
    'tmp/category-certification/wiki-articles/packets/005720.json': '9ea922543e50a0db3d96f6747a47385e2d8d24ac3163ed783086c834e388ae9d',
    'tmp/root-review/bank-ignore-13532-addendum-review-20261003/assessment.md': '0ce6c10020c586ee342d885f958a56e2b3e543667cf04bd2f5524944833747d8',
    'tmp/root-review/bank-ignore-13532-addendum-review-20261003/source-pins.json': '68eb6b8721dca40ec18ca026e1cf081afc54689a0c76d64f4b54d193e398be98',
    'tmp/root-review/bank-ignore-13532-addendum-review-20261003/semantic-exceptions.json': '9f8c48196738fc1242d1f233aa89824238878f1ca7644f35e0c2ae7b4e014c3b',
    'tmp/root-review/bank-ignore-supplemental-integration-20261003/before-decisions.jsonl': 'e9d971ef20aaa58ec7588204017185f53bf928f3d0fd927900169c40fbf56741',
    'tmp/root-review/bank-ignore-supplemental-integration-20261003/before-coverage.tsv': '9b7ef11ae5e345972892cdf513b4885381afb7ec626237371cd32840c5228574',
    'tools/research/semantic-grouping-audit/certification/bank-ignore-approved-policy.json': '460c115cffbb01115814005b3f50ce521ecad600b6065493383606d628f1e4d8',
    'tools/research/semantic-grouping-audit/certification/bankability-policy-approvals.json': '476398ae9ba40f135f9ce398e353582df7ddb45ff60f0eea80d83de5e689e78a',
    'tools/research/semantic-grouping-audit/certification/verify-bank-ignore-policy.py': 'f116adf235f2f3fb7722e86b180f8621ed3d8fdb71b94188c82f5cd653e0e0dc',
    'src/main/resources/com/pkoka5/ironmanbankarchitect/catalog/non-bankable-item-ids.tsv': '489eaf847ce6963e4235bf718bfeb2bed945af3d980a3cdc6fea8596561f6e10',
    'src/main/java/com/pkoka5/ironmanbankarchitect/catalog/BankabilityPolicy.java': 'd4bcbc02151ba76957228f8053b3f58b6c17b244a49437cdad11c30fdbb8b52a',
}


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    return json.loads(path.read_text(encoding='utf-8-sig'))


def require(ok, message):
    if not ok:
        raise ValueError(message)


def canonical_sha(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False,
                                     separators=(',', ':')).encode()).hexdigest()


def expected_policy():
    return {
        'schema': 'root-approved-bank-ignore-supplemental/v1',
        'status': 'root-reviewed exact supplemental deposit prohibition',
        'decisionAxis': 'storage.player-bank.depositable',
        'preserveEveryObservedBankRow': True,
        'rule': 'The exact own current article binds ID 13532 and records an unconditional no-deposit change. Missing bankable remains unknown. Exclude only unobserved deposit candidates; retain every observed row and the raw reference assignment.',
        'categoryTagsAndSecondaryRoles': 'unassessed',
        'sourceHashes': PINS,
        'cases': [{
            'itemId': 13532, 'sourceTitle': 'Ideology of Darkness',
            'sourceRevision': 15311009,
            'sourcePath': 'tmp/category-certification/wiki-articles/text/15311009.txt',
            'sourceSha256': PINS['tmp/category-certification/wiki-articles/text/15311009.txt'],
            'proofKind': 'direct_own_article_no_bank_deposit_change',
            'exactIdField': ['|id = 13532'], 'bankabilityField': [],
            'bankableFieldStatus': 'missing; unknown',
            'quote': QUOTE, 'changeDate': '16 May 2019',
            'defaultPresetAction': 'EXCLUDE_FROM_UNOBSERVED_PRESET_CANDIDATES',
            'liveObservedBankAction': 'ALWAYS_PRESERVE_OBSERVED_ROW',
            'rootSemanticDecision': 'The full pinned page has no repeal or phase condition; its later change only renames the item. Approval is solely depositability, not primary category or availability.',
        }],
    }


def rows(path):
    with path.open(encoding='utf-8', newline='') as stream:
        values = list(csv.DictReader(stream, delimiter='\t'))
    result = {int(row['itemId']): row for row in values}
    require(len(values) == len(result) == 34085, 'Full unique denominator changed')
    return result


def verify(*, draft=False, coverage=None):
    policy = read(POLICY)
    require(policy == expected_policy(), 'Complete root-reviewed policy changed')
    for rel, digest in PINS.items():
        require(sha(ROOT / rel) == digest, 'Pinned input changed: ' + rel)
    spec = importlib.util.spec_from_file_location('prior_bank', CERT / 'verify-bank-ignore-policy.py')
    require(spec is not None and spec.loader is not None, 'Prior verifier unavailable')
    prior = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(prior)
    prior.verify_policy()
    case = policy['cases'][0]
    raw = (ROOT / case['sourcePath']).read_bytes().decode('utf-8')
    boxes = list(prior.infoboxes(raw))
    require(len(boxes) == 1, 'Unique own Infobox Item missing')
    fields = {key: value.strip() for key, value in re.findall(r'^\s*\|\s*(\w+)\s*=\s*([^\n]*)', boxes[0], re.M)}
    require(fields.get('id') == '13532' and fields.get('name') == 'Ideology of Darkness'
            and not any(re.fullmatch(r'bankable\d*', key) for key in fields),
            'Own identity or missing-field scope changed')
    require('|date = 16 May 2019\n|update = Farming Improvements and Rebalancing Existing Content\n|change = ' + QUOTE in raw.replace('\r\n', '\n'), 'Exact dated deposit prohibition absent')
    packet = read(ROOT / 'tmp/category-certification/wiki-articles/packets/005720.json')
    pages = [page for page in packet['data']['query']['pages'] if page['title'] == case['sourceTitle']]
    require(len(pages) == 1 and len(pages[0]['revisions']) == 1, 'Unique own source packet page missing')
    revision = pages[0]['revisions'][0]
    require(revision['revid'] == case['sourceRevision']
            and revision['slots']['main']['content'] == raw.replace('\r\n', '\n'),
            'Own source packet revision or full raw content differs')
    frozen = ROOT / 'tmp/root-review/bank-ignore-supplemental-integration-20261003/before-decisions.jsonl'
    decisions = [json.loads(line) for line in frozen.read_text(encoding='utf-8').splitlines()]
    require(len(decisions) == len({row['itemId'] for row in decisions}) == 34085
            and next(row for row in decisions if row['itemId'] == 13532)['decision'] == 'unresolved',
            'Frozen scope is not an unresolved exact ID')
    if not draft:
        pin = read(PIN)
        require(pin == {'schema': 1, 'status': 'root-reviewed exact supplemental bankability pin',
                        'reviewer': 'root', 'policyFile': POLICY.name, 'policySha256': sha(POLICY),
                        'canonicalSha256': canonical_sha(policy), 'approvedItemIds': [13532], 'caseCount': 1},
                'Detached approval bytes, complete contents or exact ID changed')
    if coverage:
        before = rows(ROOT / 'tmp/root-review/bank-ignore-supplemental-integration-20261003/before-coverage.tsv')
        after = rows(coverage)
        require(after.keys() == before.keys(), 'Export added or dropped exact IDs')
        old_ids = {case['itemId'] for case in read(CERT / 'bank-ignore-approved-policy.json')['cases']}
        require(13532 not in old_ids and len(old_ids | {13532}) == 720, 'Separate case overlaps prior policy')
        require({item for item, row in after.items() if row['auditScope'] == 'EXCLUDED_NON_BANKABLE'}
                == (old_ids | {13532}) & after.keys(), 'Complete exclusion union differs')
        for item, row in before.items():
            expected = dict(row)
            if item == 13532:
                expected['auditScope'] = 'EXCLUDED_NON_BANKABLE'
            require(after[item] == expected, f'#{item}: other scope, assignment or tags changed')
    return {'technicalGate': 'passed', 'semanticApprovalGranted': False,
            'supplementalCases': 1, 'combinedPolicyCases': 720, 'combinedInScope': 708,
            'combinedOutsideScope': 12, 'detachedApprovalVerified': not draft,
            'coverageVerified': bool(coverage)}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--draft', action='store_true')
    parser.add_argument('--coverage', type=Path)
    args = parser.parse_args()
    print(json.dumps(verify(draft=args.draft, coverage=args.coverage), sort_keys=True))
