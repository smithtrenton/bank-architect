#!/usr/bin/env python3
"""Verify detached deposit policy, exact own sources and retained coverage."""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
CERT = Path(__file__).resolve().parent
POLICY = CERT / 'bank-ignore-approved-policy.json'
APPROVALS = CERT / 'bankability-policy-approvals.json'
RESOURCE = ROOT / 'src/main/resources/com/pkoka5/ironmanbankarchitect/catalog/non-bankable-item-ids.tsv'
FINAL = ROOT / 'tmp/root-review/bank-ignore-final-review-20261003'
FINAL_CASES_SHA = '4ecdccea5bdce487b69d88af5537cd6628dc76e351ae7c5296ea490976ce7002'
FINAL_IDS_SHA = '46a524060b39823979e9df69104536a686e109ac401f0af7da50e7a9dfa976d0'
GATE = ROOT / 'tmp/category-certification/root-review/runtime-bank-ignore-gate-v1'
CONTEXT = ROOT / 'tmp/root-review/bank-ignore-conditional-context-v2'
HOLDS = {4678, 4679, 4680, 4681, 10835, 30808, 6643}


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    return json.loads(path.read_text(encoding='utf-8-sig'))


def jsonl(path):
    return [json.loads(line) for line in path.read_text(encoding='utf-8-sig').splitlines() if line.strip()]


def require(ok, message):
    if not ok:
        raise ValueError(message)


def canonical_sha(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False,
                                     separators=(',', ':')).encode()).hexdigest()


def infoboxes(text):
    for match in re.finditer(r'\{\{Infobox Item\b', text):
        depth = 0
        for token in re.finditer(r'\{\{|\}\}', text[match.start():]):
            depth += 1 if token.group() == '{{' else -1
            if depth == 0:
                yield text[match.start():match.start() + token.end()]
                break
        else:
            raise ValueError('Unclosed own item infobox')


def verify_source(case):
    item = case['itemId']; path = ROOT / case['sourcePath'].replace('\\', '/')
    require(sha(path) == case['sourceSha256'], f'#{item}: exact raw source changed')
    raw = path.read_text(encoding='utf-8'); matches = []
    for body in infoboxes(raw):
        fields = dict(re.findall(r'^\s*\|\s*(\w+)\s*=\s*([^\n]*)', body, re.M))
        fields = {key: value.strip() for key, value in fields.items()}
        for field, value in fields.items():
            if (re.fullmatch(r'id\d*', field) and re.fullmatch(r'\d+(?:\s*,\s*\d+)*', value)
                    and item in {int(token.strip()) for token in value.split(',')}):
                matches.append((fields, field))
    require(len(matches) == 1, f'#{item}: unique exact own Infobox Item binding missing')
    fields, id_field = matches[0]
    if case['proofKind'] == 'exact_infobox_bankable_no':
        suffix = id_field[2:]
        field = 'bankable' + suffix if 'bankable' + suffix in fields else 'bankable'
        require(fields.get(field) == 'No', f'#{item}: selected variant is not explicitly bankable=No')
        require(case['bankabilityField'], f'#{item}: no cited bankability fact')
    else:
        require(case['proofKind'] == 'direct_own_article_no_bank_deposit_prose' and item in {13183, 13184},
                f'#{item}: unapproved direct proof type')
        require('This item cannot be deposited into a bank.' in raw and not case['bankabilityField'],
                f'#{item}: direct no-deposit proof absent')
    require(case['liveObservedBankAction'] == 'ALWAYS_PRESERVE_OBSERVED_ROW' and
            case['defaultPresetAction'] == 'EXCLUDE_FROM_UNOBSERVED_PRESET_CANDIDATES',
            f'#{item}: live observation and deposit candidate scopes conflated')


def verify_policy(*, draft=False, coverage=None):
    policy = read(POLICY)
    require(policy['schema'] == 'root-approved-bank-ignore/v1' and
            policy['status'] == 'root-reviewed deposit prohibitions only' and
            policy['preserveEveryObservedBankRow'] is True, 'Wrong bank policy scope/status')
    require(sha(FINAL / 'final-candidate-source-cases.jsonl') == FINAL_CASES_SHA and
            sha(FINAL / 'final-unconditional-candidate-ids.txt') == FINAL_IDS_SHA, 'Immutable final review changed')
    require(policy['cases'] == jsonl(FINAL / 'final-candidate-source-cases.jsonl'), 'Complete exact bank cases changed')
    require(set(policy['sourceInputPaths']) == set(policy['sourceHashes']), 'Bank source pin maps differ')
    for key, rel in policy['sourceInputPaths'].items():
        require(sha(ROOT / rel) == policy['sourceHashes'][key], f'Bank source changed: {key}')
    strict = {int(line) for line in (GATE / 'strict-absence-candidate-ids.txt').read_text().splitlines()}
    ids = [case['itemId'] for case in policy['cases']]
    require(len(ids) == len(set(ids)) == 719 and set(ids) == strict - {6643} and not set(ids) & HOLDS,
            '719 exact strict-minus-Cyan case/hold partition changed')
    require(policy['heldItemIds'] == sorted(HOLDS), 'Six conditional holds or Cyan quarantine lost')
    resource = RESOURCE.read_text(encoding='utf-8').splitlines()
    rows = [line.split('\t') for line in resource if line and not line.startswith('#')]
    require(resource[0] == '# schema=1' and len(rows) == 1 and rows[0][0] == 'non-bankable', 'Runtime resource schema changed')
    runtime_ids = [int(value) for value in rows[0][1].split(',')]
    require(runtime_ids == sorted(ids) and sha(RESOURCE) == policy['runtimeResourceSha256'], 'Runtime exact set/bytes changed')
    for case in policy['cases']:
        verify_source(case)
    audit_ids = {int(line) for line in (ROOT / policy['sourceInputPaths']['contextAuditIds']).read_text().splitlines()}
    require(len(audit_ids) == 720 and len(audit_ids & strict) == 718 and
            strict - audit_ids == {13183, 13184} and audit_ids - strict == {10835, 30808},
            'Full-page context input reconciliation changed')
    frozen = ROOT / policy['sourceInputPaths']['frozenCoverage']
    with frozen.open(encoding='utf-8', newline='') as stream:
        original = {int(row['itemId']): row for row in csv.DictReader(stream, delimiter='\t')}
    require(len(original) == 34085 and len(set(ids) & original.keys()) == 707 and
            len(set(ids) - original.keys()) == 12, 'Full 34,085-ID denominator changed')
    if not draft:
        pin = read(APPROVALS)
        require(pin['status'] == 'root-reviewed exact bankability policy pin' and pin['policySha256'] == sha(POLICY)
                and pin['canonicalSha256'] == canonical_sha(policy) and pin['approvedItemIds'] == sorted(ids)
                and pin['caseCount'] == 719, 'Detached bank approval bytes/complete contents/IDs changed')
    if coverage:
        with coverage.open(encoding='utf-8', newline='') as stream:
            rows = list(csv.DictReader(stream, delimiter='\t'))
        after = {int(row['itemId']): row for row in rows}
        require(len(rows) == len(after) == 34085 and after.keys() == original.keys(), 'Exporter dropped/added/duplicated IDs')
        require({item for item, row in after.items() if row['auditScope'] == 'EXCLUDED_NON_BANKABLE'} == set(ids) & original.keys(),
                'Export exclusion set differs from approved in-scope bank policy')
        for item, row in after.items():
            require(row['catalogScope'] == original[item]['auditScope'], f'#{item}: original catalog scope lost')
    return {'technicalGate': 'passed', 'semanticApprovalGranted': False, 'depositPolicyCases': 719,
            'inFrozenCoverage': 707, 'outsideFrozenCoverage': 12, 'heldCases': 7,
            'detachedApprovalVerified': not draft, 'coverageVerified': bool(coverage)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--draft', action='store_true')
    parser.add_argument('--coverage', type=Path)
    args = parser.parse_args()
    print(json.dumps(verify_policy(draft=args.draft, coverage=args.coverage), sort_keys=True))


if __name__ == '__main__':
    main()
