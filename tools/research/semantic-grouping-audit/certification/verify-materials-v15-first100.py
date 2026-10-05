#!/usr/bin/env python3
"""Replay the frozen first-100 root review; replay is not semantic approval."""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
CERT = Path(__file__).resolve().parent
DRAFT = ROOT / 'tmp/root-review/materials-v15-first100-policy-draft-v2-20261003'
CONFIG = {
    'materials-v15-primary-approved-policy.json': ('unchanged-policy-draft.json',
        'f4f00a28472aa0bcd3e108d9d2923e1a13ff1f2c3a91a8ab8eca0db3edd78731', 'certify', 7),
    'materials-v15-corrections-approved-policy.json': ('corrections-policy-draft.json',
        '9d67919cae9249a291d08ec8e1f89549ec460ba6a35f4ec2affb138014b0d84f', 'revise', 75),
}
AUDIT = 'tmp/root-review/materials-v15-first100-independent-20261003/independent-audit.jsonl'
AUDIT_SHA = '2e8232ab75a65f2b7cdc968cac9341eccfeb0f4777dc3e4a47ba0d4847b4b9eb'
NOTES = 'tmp/root-review/materials-v15-root-reading-20261003/first100-final-root-notes-v2.jsonl'
NOTES_SHA = 'e73e94cd8da7b639fe63d7c923c06af84195f40c104a52ad0a70e89f6d77bb97'
# Root-selected full own-function paragraphs, rather than creation-only leads.
SELECTORS = {948: 1, 1941: 5, 2138: 1, 2351: 1, 2355: 1, 3353: 1,
             3404: 1, 4670: 2, 4671: 2, 4672: 2, 4673: 2,
             6045: 1, 6169: 1, 6173: 1}
ADDITIONAL = {
    4707: 'It describes the story of the brave heroes that are buried there and what just happened to them to bring about the beginning of their end.',
    6094: 'It is to be mixed with a [[barrel of naphtha]] to obtain a [[naphtha apple mix]].',
    6865: 'The marionette can be operated to do 4 different moves, which are jump, walk, dance, and bow.',
    6866: 'The marionette can be operated to do 4 different moves, which are jump, walk, dance, and bow.',
    6867: 'The marionette can be operated to do 4 different moves, which are jump, walk, dance, and bow.',
}


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    return json.loads(path.read_text(encoding='utf-8-sig'))


def require(value, message):
    if not value:
        raise ValueError(message)


def make_policy(name):
    filename, digest, decision, count = CONFIG[name]
    path = DRAFT / filename
    require(sha(path) == digest, 'Frozen reconciled draft changed')
    draft = read(path)
    frozen = {
        'docs/research/category-certification/approved-assignments.tsv': 'live-approved-assignments-623e.tsv',
        'docs/research/category-certification/approved-assignments-manifest.json': 'live-approved-assignments-manifest-623e.json',
        'tmp/category-certification/root-approved-decisions-with-clue-scrolls.jsonl': 'live-root-approved-decisions-623e.jsonl',
        'tools/research/semantic-grouping-audit/certification/root-policy-approvals.json': 'live-root-policy-approvals-623e.json',
    }
    paths = {key: (DRAFT / frozen[key]).relative_to(ROOT).as_posix() if key in frozen else key
             for key in draft['inputs']}
    cases = []
    for row in draft['cases']:
        item = row['itemId']; pin = row['sourcePin']; own = row['exactOwnVariant']
        clauses = list(dict.fromkeys(c['text'] for c in row['fullPositiveAndCompetingSourceClauses']))
        positive = ADDITIONAL.get(item, clauses[SELECTORS.get(item, 0)])
        if positive not in clauses:
            clauses.append(positive)
        params = own['fullArticleIndexParams']; suffix = str(own['suffix'] or '')
        fields = []
        for base in ('id', 'name', 'version', 'examine', 'options', 'equipable', 'quest', 'bankable'):
            field = base + suffix if base + suffix in params else base
            if field in params:
                fields.append({'field': field, 'value': str(params[field])})
        target = row['rootSupportedTarget']
        cases.append(dict(itemId=item, title=row['sourceTitle'], sourceRevision=pin['revision'],
            sourceSha256=pin['sha256'], expectedDecision=decision,
            proposedCategory=target['category'], proposedSubcategory=target['subcategory'],
            proposedIronmanTabKey=target['ironmanTabKey'], semanticExcerpt=clauses[0],
            positiveFunctionExcerpt=positive, secondaryExcerpts=clauses[1:],
            exactVariantFacts=fields, rationale=row['rootReadingFinding'],
            stateScopeNotes={'exactOwnVariant': own, 'scope': 'Primary placement only; tags, secondary roles and availability unassessed.'}))
    return dict(schema=1, policyFile=name, status='root-reviewed primary assignments only',
        expectedDecision=decision, expectedCaseCount=count,
        sourceInputPaths={**paths, 'rootDraft': path.relative_to(ROOT).as_posix(),
                          'finalRootNotes': NOTES, 'independentAudit': AUDIT},
        sourceHashes={**{k: v['sha256'] for k, v in draft['inputs'].items()}, 'rootDraft': digest,
                      'finalRootNotes': NOTES_SHA, 'independentAudit': AUDIT_SHA},
        approvalScope='Category, subtype and tab only; every existing tag and observed bank row is preserved.',
        rootSemanticDecision='Read exact own sources for 109 IDs in 100 groups. Approve 82 positive placements; retain all 27 holds including Black prism. Resolve independent exceptions without inferring Tiny net reusability or copying Woolly hat warmth to scarf.',
        cases=cases)


def verify_policy(policy):
    name = policy.get('policyFile')
    require(name in CONFIG and policy == make_policy(name), 'Complete root-selected policy changed')
    for key, path in policy['sourceInputPaths'].items():
        require(sha(ROOT / path) == policy['sourceHashes'][key], 'Pinned input changed: ' + key)
    notes = [json.loads(l) for l in (ROOT / NOTES).read_text(encoding='utf-8').splitlines()]
    require(len(notes) == 109 and len({r['itemId'] for r in notes}) == 109, 'Root note universe changed')
    positive = {r['itemId']: r for r in notes if r['rootDisposition'] == 'primary-supported-pending-final-gates'}
    require(len(positive) == 82 and 4808 not in positive, '82 positive / 27 held partition changed')
    require(len(policy['cases']) == CONFIG[name][3], 'Exact case count changed')
    index = read(ROOT / 'tmp/category-certification/wiki-articles/article-index.json')
    for case in policy['cases']:
        item = case['itemId']; source = index[case['title']]; note = positive[item]
        require((source['revid'], source['sha256']) == (case['sourceRevision'], case['sourceSha256']), 'Own source pin changed')
        require(note['proposedAssignment'] == {'category': case['proposedCategory'], 'subcategory': case['proposedSubcategory'],
                'ironmanTabKey': case['proposedIronmanTabKey']}, 'Target differs from final root note')
        raw_path = ROOT / source['path']; require(sha(raw_path) == source['sha256'], 'Raw Wiki source changed')
        raw = raw_path.read_bytes().decode('utf-8'); own = case['stateScopeNotes']['exactOwnVariant']
        require(item in source['exactInfoboxItemIds'] and source['variants'][str(item)]['params'] == own['fullArticleIndexParams'], 'Exact variant changed')
        require(re.search(r'^\s*\|\s*' + re.escape(own['rawIdField']) + r'\s*=\s*' + str(item) + r'\s*$', raw, re.M), 'Own raw ID binding missing')
        for quote in [case['semanticExcerpt'], case['positiveFunctionExcerpt']] + case['secondaryExcerpts']:
            require(quote.strip() and quote in raw, f'#{item}: own literal excerpt missing')
    return len(policy['cases'])


def main():
    parser = argparse.ArgumentParser(); parser.add_argument('--write', action='store_true'); args = parser.parse_args()
    for name in CONFIG:
        policy = make_policy(name) if args.write else read(CERT / name)
        verify_policy(policy)
        if args.write:
            (CERT / name).write_text(json.dumps(policy, ensure_ascii=False, indent=2) + '\n', encoding='utf-8', newline='\n')
        print(name, len(policy['cases']), 'exact cases verified')


if __name__ == '__main__':
    main()
