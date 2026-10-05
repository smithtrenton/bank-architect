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
DRAFT = ROOT / 'tmp/root-review/materials-v15-g341-493-draft-v3-20261003'
CONFIG = {
    'materials-v15-g341-493-corrections-approved-policy.json':
        ('corrections-policy-draft.json', '4d6e6ad01719aa98ac78328dcd1ddd012afe7d0429e589a9ee1a9f6ee2afb82e', 'revise', 255),
}
AUDITS = {'tmp/root-review/materials-v15-g341-493-draft-v3-20261003/frozen-inputs/independent-independent-case-audit.jsonl': '4429334f7a5dfc103265f8355c9f9088ff1c3e8ec92226409cacbc05d423f536', 'tmp/root-review/materials-v15-g341-493-draft-v3-20261003/frozen-inputs/independent-README.md': '47c40b60f88c4017a61f5ca87c8d3a54f6de5eaec9bd96d32c05d63fbcf7df1b', 'tmp/root-review/materials-v15-g341-493-draft-v3-20261003/frozen-inputs/independent-fish-crate-independent-review.json': 'e9e335ce457ffff0e732970d31112f4394aa316ecef5b85509186db2a53dc54f'}
ALAN_RESOLUTION_SHA = '4fb8f9981449a6b823c2ed80d776d12f0946a2bc5b35fb1650a54ada7bc66b6b'

# Root-selected sections supply use evidence where an acquisition-only lead does not.
SECTIONS = {item: 'Combat stats' for item in (30082, 31181, 31184, 31187, 31190, 33082, 33084)}


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
    resolution_path = DRAFT / 'root-alan-bonemeal-resolution.json'
    require(sha(resolution_path) == ALAN_RESOLUTION_SHA, 'Explicit Alan ritual-priority resolution changed')
    resolution = read(resolution_path)
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
        if item == 30975:
            cases[-1]['rationale'] = resolution['rootRationale']
            cases[-1]['contextEvidence'] = [resolution['contextEvidence']]
    return dict(schema=1, policyFile=name, status='root-reviewed primary assignments only',
        expectedDecision=decision, expectedCaseCount=count,
        sourceInputPaths={**mapping, 'rootDraft': path.relative_to(ROOT).as_posix(),
                          'rootResolution': resolution_path.relative_to(ROOT).as_posix(),
                          **{key: key for key in AUDITS}},
        sourceHashes={**{key: value['sha256'] for key, value in draft['inputs'].items()},
                      'rootDraft': digest, 'rootResolution': ALAN_RESOLUTION_SHA, **AUDITS},
        approvalScope='Category, subtype and tab only; retain all existing tags and observed bank rows.',
        rootSemanticDecision='Root read all274 exact IDs in groups341–493. Approve255 corrections; preserve10 holds and9 exclusions. Full own function/competing leads and selected zero/positive combat sections support exact targets. Six fish-crate V3 findings restore own bank/camphor recovery, without importing absent other-emptying loss rules. Alan bonemeal is explicitly selected as a ritual input with five-token output retained; generic ritual context never supplies Alan-specific XP. Tags, roles and availability remain unassessed.',
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
        for context in case.get('contextEvidence', []):
            require(item == 30975 and context['kind'] == 'local_source', 'Unexpected ritual-context evidence')
            context_source = index[context['sourceTitle']]
            require((context_source['revid'], context_source['sha256']) == (context['sourceRevision'], context['sourceHash']), 'Context source pin changed')
            context_path = ROOT / context['sourcePath']
            require(sha(context_path) == context['sourceHash'] and context['quote'] in context_path.read_bytes().decode('utf-8'), 'Generic ritual context changed')
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
