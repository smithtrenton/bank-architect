#!/usr/bin/env python3
"""Replay the frozen root review and exact primary-only Materials tranche."""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
CERT = Path(__file__).resolve().parent
DRAFT = ROOT / 'tmp/root-review/materials-v15-g101-340-draft-20261003'
CONFIG = {
    'materials-v15-g101-340-primary-approved-policy.json':
        ('unchanged-policy-draft.json', '0a2ca5c08c52607abef1094fbbfa27702fb49bc50ac1e9422ba6f442ed0001ee', 'certify', 37),
    'materials-v15-g101-340-corrections-approved-policy.json':
        ('corrections-policy-draft.json', 'cd2cf86b42cc5ed5616ff5d137da8b738457b4ce2287b3782d447361098190aa', 'revise', 152),
}
AUDITS = {
    'tmp/root-review/materials-v15-g101-240-independent-20261003/audited-206-items.jsonl':
        'dbb8e06e4d5a9e86e20a69122d547baa9a4bf2cf3163aadb68123e59a5700ce8',
    'tmp/root-review/materials-v15-g241-340-independent-20261003/independent-audit-109-items.jsonl':
        '6ca74f142ae8e18bed1faf7f3c13e78ec4ea5e5840a641af9a61ccccd00c619c',
    'tmp/root-review/materials-v15-g241-340-independent-20261003/README.md':
        'db9c647a9ad22fbd0353d0b0b270a21c3be7cec81a0ef5107e09b5a57c419432',
}
# Root-selected sections supply use evidence where an acquisition-only lead does not.
SECTIONS = {13421: 'Use', 28620: 'Combat stats',
            29338: 'Prayer info', 29340: 'Prayer info', 29342: 'Prayer info'}


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    return json.loads(path.read_text(encoding='utf-8-sig'))


def require(ok, message):
    if not ok:
        raise ValueError(message)


def make_policy(name):
    filename, digest, decision, count = CONFIG[name]
    path = DRAFT / filename
    require(sha(path) == digest, 'Complete immutable root-reconciled draft changed')
    draft = read(path)
    mapping = read(DRAFT / 'root-frozen-input-paths.json')
    require(set(mapping) == set(draft['inputs']), 'Frozen logical input map changed')
    cases = []
    for row in draft['cases']:
        item = row['itemId']; own = row['exactOwnVariant']; target = row['proposedRootTarget']
        paragraphs = row['ownPositiveAndCompetingParagraphs']
        if item in SECTIONS:
            selected = [p for p in paragraphs if p['section'] == SECTIONS[item]
                        and p['kind'] == 'root-finding-relevant-full-section']
        else:
            selected = [p for p in paragraphs if p['kind'] == 'complete-own-lead']
        require(len(selected) == 1, f'#{item}: unique root-selected own use section absent')
        clauses = list(dict.fromkeys(p['text'] for p in paragraphs
                                    if p['kind'] != 'recipe_or_exact_variant_template'))
        params = own['completeArticleIndexParams']; suffix = str(own['suffix'] or '')
        facts = []
        for base in ('id', 'name', 'version', 'examine', 'options', 'equipable', 'quest', 'bankable'):
            field = base + suffix if base + suffix in params else base
            if field in params:
                facts.append({'field': field, 'value': str(params[field])})
        cases.append(dict(itemId=item, title=row['sourceTitle'], sourceRevision=row['sourcePin']['revision'],
            sourceSha256=row['sourcePin']['sha256'], expectedDecision=decision,
            proposedCategory=target['category'], proposedSubcategory=target['subcategory'],
            proposedIronmanTabKey=target['ironmanTabKey'], semanticExcerpt=clauses[0],
            positiveFunctionExcerpt=selected[0]['text'], secondaryExcerpts=clauses[1:],
            exactVariantFacts=facts, rationale=row['rootReadingFinding'],
            stateScopeNotes={'exactOwnVariant': own, 'scope': 'Primary bank placement only; tags, roles and availability unassessed.'}))
    return dict(schema=1, policyFile=name, status='root-reviewed primary assignments only',
        expectedDecision=decision, expectedCaseCount=count,
        sourceInputPaths={**mapping, 'rootDraft': path.relative_to(ROOT).as_posix(),
                          **{key: key for key in AUDITS}},
        sourceHashes={**{key: value['sha256'] for key, value in draft['inputs'].items()},
                      'rootDraft': digest, **AUDITS},
        approvalScope='Category, subtype and tab only; retain all existing tags and observed bank rows.',
        rootSemanticDecision='Root read exact own sources for 315 IDs in groups101–340. Approve189 placements; preserve109 holds and17 exclusions including newly excluded13532. Positive full leads and selected Use/Prayer/cosmetic sections retain competing functions and exact states. Activity acquisition alone does not limit ordinary use. Pheasant hat and three statuettes resolved from full own sections; missing bankable is never No.',
        cases=cases)


def verify_policy(policy):
    name = policy.get('policyFile')
    require(name in CONFIG and policy == make_policy(name), 'Complete root-selected policy changed')
    for key, rel in policy['sourceInputPaths'].items():
        require(sha(ROOT / rel) == policy['sourceHashes'][key], 'Frozen source changed: ' + key)
    draft = read(DRAFT / CONFIG[name][0])
    require(len(policy['cases']) == CONFIG[name][3], 'Exact case count changed')
    index = read(ROOT / policy['sourceInputPaths']['tmp/category-certification/wiki-articles/article-index.json'])
    frozen = ROOT / policy['sourceInputPaths']['tmp/category-certification/root-approved-decisions-with-clue-scrolls.jsonl']
    decisions = {row['itemId']: row for row in map(json.loads, frozen.read_text(encoding='utf-8').splitlines())}
    require(len(decisions) == 34085 and decisions[13532]['decision'] == 'exclude', 'Frozen bank exclusion lost')
    ids = [case['itemId'] for case in policy['cases']]
    require(len(ids) == len(set(ids)) and 13532 not in ids, 'Duplicate or excluded primary case')
    for case, row in zip(policy['cases'], draft['cases']):
        item = case['itemId']; source = index[case['title']]; own = case['stateScopeNotes']['exactOwnVariant']
        require(decisions[item]['decision'] == 'unresolved', f'#{item}: prior approval would be replaced')
        require(row['finalRootDisposition'] == 'primary-supported-pending-final-gates'
                and row['proposedRootTarget'] == {'category': case['proposedCategory'], 'subcategory': case['proposedSubcategory'],
                                                'ironmanTabKey': case['proposedIronmanTabKey']}, 'Root target changed')
        require((source['revid'], source['sha256']) == (case['sourceRevision'], case['sourceSha256']), 'Exact own pin changed')
        require(item in source['exactInfoboxItemIds'] and source['variants'][str(item)]['params'] == own['completeArticleIndexParams'], 'Exact selected variant changed')
        raw_path = ROOT / source['path']; require(sha(raw_path) == source['sha256'], 'Raw article bytes changed')
        raw = raw_path.read_bytes().decode('utf-8')
        fields = re.findall(r'^\s*\|\s*' + re.escape(own['rawIdField']) + r'\s*=\s*([^\r\n]*)', raw, re.M)
        require(any(re.fullmatch(r'\d+(?:\s*,\s*\d+)*', value.strip())
                    and item in {int(token) for token in value.split(',')} for value in fields), 'Exact comma-aware own ID binding absent')
        for quote in [case['semanticExcerpt'], case['positiveFunctionExcerpt']] + case['secondaryExcerpts']:
            require(quote.strip() and quote in raw, f'#{item}: literal own excerpt absent')
    return len(ids)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(); parser.add_argument('--write', action='store_true'); args = parser.parse_args()
    for name in CONFIG:
        policy = make_policy(name) if args.write else read(CERT / name)
        verify_policy(policy)
        if args.write:
            (CERT / name).write_text(json.dumps(policy, ensure_ascii=False, indent=2) + '\n', encoding='utf-8', newline='\n')
        print(name, len(policy['cases']), 'exact cases verified')
