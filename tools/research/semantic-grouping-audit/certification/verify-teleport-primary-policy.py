#!/usr/bin/env python3
"""Verify evidence for separately root-approved consumable player transport."""
from __future__ import annotations
import argparse
import hashlib
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
CERT = Path(__file__).resolve().parent
BASE = ROOT / 'tmp/category-certification'


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def verify_policy(policy: dict) -> dict:
    if policy.get('schema') != 1 or policy.get('status') != 'root-reviewed primary assignments only':
        raise ValueError('Teleport policy lacks explicit root approval status')
    approvals = json.loads((CERT / 'root-policy-approvals.json').read_text(encoding='utf-8-sig'))
    if approvals.get('schema') != 1 or approvals.get('status') != 'root-reviewed exact policy pins':
        raise ValueError('Invalid detached root-policy approval record')
    approval = approvals['approvedPolicies']['teleport-primary-approved-policy.json']
    canonical = hashlib.sha256(json.dumps(policy, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode()).hexdigest()
    if canonical != approval['canonicalSha256']:
        raise ValueError('Teleport policy differs from separate root approval')
    inputs = {
        'articleIndex': BASE / 'wiki-articles/article-index.json',
        'transportPacket': BASE / 'reviewer-packets/currency-runes-teleport.jsonl',
        'candidatePacket': BASE / 'reviews/transport-v16/ordinary-teleport-consumables-review.json',
        'adversarialReview': BASE / 'root-review/transport-v16-adversarial-review-v1.json',
    }
    for key, path in inputs.items():
        if digest(path) != policy['sourceHashes'][key]:
            raise ValueError('Teleport frozen input changed: ' + key)
    index = json.loads(inputs['articleIndex'].read_text(encoding='utf-8-sig'))
    packets = {r['itemId']: r for r in map(json.loads, inputs['transportPacket'].read_text(encoding='utf-8-sig').splitlines())}
    review = json.loads(inputs['candidatePacket'].read_text(encoding='utf-8-sig'))
    candidates = {r['itemId']: r for r in review['proposals']}
    adversarial = json.loads(inputs['adversarialReview'].read_text(encoding='utf-8-sig'))
    cases = policy['cases']
    ids = [r['itemId'] for r in cases]
    if len(cases) != 72 or policy.get('expectedCaseCount') != 72 or len(set(ids)) != 72 or set(ids) != set(candidates):
        raise ValueError('Teleport exact approved cohort changed')
    if sorted(ids) != approval['approvedItemIds'] or approval['caseCount'] != 72 or approval['decision'] != 'certify':
        raise ValueError('Teleport exact case set differs from separate approval')
    if adversarial['examinedCount'] != 72 or set(adversarial['examinedIds']) != set(ids) or adversarial['summary']['confirmedCounterexampleCount'] or adversarial['summary']['cohortFailures']:
        raise ValueError('Teleport adversarial cohort or exceptions changed')
    if adversarial['inputSha256'].removeprefix('sha256:') != policy['sourceHashes']['candidatePacket']:
        raise ValueError('Teleport adversarial input binding changed')
    patterns = {
        'teleport-tablet': r'\bcan be broken(?: by players)? to teleport\b',
        'teleport-scroll': r'\bconsumable teleport scrolls that (?:can )?teleport the player\b',
        'teleport': r'\bteleports? the player to\b',
    }
    for case in cases:
        ident = case['itemId']
        source = index[case['title']]
        current = packets[ident]['current']
        candidate = candidates[ident]
        def require(condition: bool, message: str) -> None:
            if not condition:
                raise ValueError(f'Teleport primary ID {ident}: {message}')
        require(ident in source['exactInfoboxItemIds'] and str(ident) in source['variants'], 'no exact numeric-ID binding')
        require(case['sourceRevision'] == source['revid'] and case['sourceSha256'] == source['sha256'], 'article revision/hash mismatch')
        require(candidate['sourceTitle'] == case['title'] and candidate['sourceRevision'] == source['revid'] and candidate['sourceHash'].removeprefix('sha256:') == source['sha256'], 'candidate source binding changed')
        path = ROOT / source['path']
        require(digest(path) == source['sha256'], 'pinned source bytes changed')
        variant = source['variants'][str(ident)]
        params = variant['params']
        suffix = str(variant.get('suffix', ''))
        def own(field: str) -> str:
            return str(params.get(field + suffix if suffix and field + suffix in params else field, ''))
        require(own('id') == str(ident), 'selected own variant is another ID')
        options = {v.strip().casefold() for v in own('options').split(',')}
        require(own('equipable').casefold() == 'no' and own('stackable').casefold() == 'yes' and bool(options & {'break', 'teleport', 'launch', 'squash'}), 'no own active stackable non-equipment transport state')
        subcategory = case['proposedSubcategory']
        require(subcategory in patterns and (case['proposedCategory'], subcategory) == (current['category'], current['subcategory']) and current['category'] == 'TELEPORT' and current['ironmanTabKey'] == 'currency-utilities', 'only unchanged Teleport primary targets permitted')
        require(candidate['currentPrimaryRoute'] == candidate['proposedPrimaryRoute'] == {key: current[key] for key in ('category', 'subcategory', 'ironmanTabKey')}, 'candidate primary route changed')
        require(not case.get('proposedTags') and not case.get('addedRoles') and not case.get('tagEvidence'), 'tags and secondary roles are unassessed')
        raw = path.read_text(encoding='utf-8')
        match = re.search(r"[']{3}([^\n]*?)[']{3}", raw)
        require(match is not None, 'missing own-subject definition')
        lead = raw[match.start():].split('\n\n', 1)[0].strip()
        require(case['semanticExcerpt'] == lead, 'not full literal own-subject lead')
        plain = re.sub(r'\[\[([^\]|]+)(?:\|([^\]]+))?\]\]', lambda m: m[2] or m[1], lead).replace("'''", '').replace("''", '')
        positive = bool(re.search(patterns[subcategory], plain, re.I))
        if ident == 9469:
            positive = subcategory == 'teleport' and 'single-use teleport item' in plain and 'take players to' in plain and {'launch', 'squash'} <= options
        require(positive, 'missing own positive consumable player-transport definition')
        normalized = ' '.join(raw.split())
        for excerpt in case.get('secondaryExcerpts', []):
            require(bool(excerpt.strip()) and ' '.join(excerpt.split()) in normalized, 'nonliteral secondary source excerpt')
        for fact in case['exactVariantFacts']:
            require(str(params.get(fact['field'])) == fact['value'], 'exact variant fact changed')
    return {'technicalGate': 'passed', 'recordedRootApproval': True, 'exactIdsVerified': 72, 'scope': 'unchanged consumable player-transport primary targets only; tags and secondary roles unassessed'}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('policy', type=Path)
    args = parser.parse_args()
    print(json.dumps(verify_policy(json.loads(args.policy.read_text(encoding='utf-8-sig'))), sort_keys=True))


if __name__ == '__main__':
    main()
