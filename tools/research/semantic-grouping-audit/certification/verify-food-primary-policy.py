#!/usr/bin/env python3
"""Check pinned exact-state evidence for the separately root-approved Food policy."""
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


def canonical_digest(value: dict) -> str:
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def verify_policy(policy: dict) -> dict:
    if policy.get('schema') != 1 or policy.get('status') != 'root-reviewed primary assignments only':
        raise ValueError('Food policy lacks the explicit root approval status')
    approvals = json.loads((CERT / 'root-policy-approvals.json').read_text(encoding='utf-8-sig'))
    if approvals.get('schema') != 1 or approvals.get('status') != 'root-reviewed exact policy pins':
        raise ValueError('Invalid detached root-policy approval record')
    approval = approvals['approvedPolicies']['food-primary-approved-policy.json']
    if canonical_digest(policy) != approval['canonicalSha256']:
        raise ValueError('Food policy contents differ from the separate root approval')
    inputs = {
        'articleIndex': BASE / 'wiki-articles/article-index.json',
        'suppliesPacket': BASE / 'reviewer-packets/supplies-herblore.jsonl',
        'candidatePacket': BASE / 'reviews/supplies-food-positive-v8-root-replay/food-positive-rule-candidates.jsonl',
        'adversarialReview': BASE / 'root-review/food-positive-adversarial-v1.json',
    }
    for key, path in inputs.items():
        if digest(path) != policy['sourceHashes'][key]:
            raise ValueError('Food frozen input changed: ' + key)
    index = json.loads(inputs['articleIndex'].read_text(encoding='utf-8-sig'))
    packets = {r['itemId']: r for r in map(json.loads, inputs['suppliesPacket'].read_text(encoding='utf-8-sig').splitlines())}
    candidates = {r['itemId']: r for r in map(json.loads, inputs['candidatePacket'].read_text(encoding='utf-8-sig').splitlines()) if r['reviewStatus'] == 'candidate_positive_rule'}
    adversarial = json.loads(inputs['adversarialReview'].read_text(encoding='utf-8-sig'))
    cases = policy['cases']
    case_ids = [case['itemId'] for case in cases]
    holds = {hold['itemId'] for hold in policy.get('explicitAdditionalHolds', [])}
    if len(cases) != policy['expectedCaseCount'] or len(cases) != 40 or len(set(case_ids)) != len(cases):
        raise ValueError('Food approved case count or uniqueness changed')
    if holds != {26149} or set(case_ids) != set(candidates) - holds:
        raise ValueError('Food exact cohort or mode-copy holds changed')
    if adversarial['examinedCount'] != 40 or set(adversarial['examinedIds']) != set(case_ids) or adversarial['excludedId'] != 26149 or adversarial['confirmedIssues']:
        raise ValueError('Food adversarial exact cohort or exceptions changed')
    if adversarial['inputSha256'].removeprefix('sha256:') != policy['sourceHashes']['candidatePacket']:
        raise ValueError('Food adversarial review is not bound to the frozen candidate input')
    if sorted(case_ids) != approval['approvedItemIds'] or len(cases) != approval['caseCount'] or approval['decision'] != 'certify':
        raise ValueError('Food case set differs from the separate approval')
    for case in cases:
        ident = case['itemId']
        source = index[case['title']]
        current = packets[ident]['current']
        def require(value: bool, message: str) -> None:
            if not value:
                raise ValueError(f'Food primary ID {ident}: {message}')
        require(ident in source['exactInfoboxItemIds'] and str(ident) in source['variants'], 'no exact numeric-ID source binding')
        require(case['sourceRevision'] == source['revid'] and case['sourceSha256'] == source['sha256'], 'article revision/hash mismatch')
        source_path = ROOT / source['path']
        require(digest(source_path) == source['sha256'], 'pinned source bytes changed')
        variant = source['variants'][str(ident)]
        params = variant['params']
        suffix = str(variant.get('suffix', ''))
        def own(field: str) -> str:
            return str(params.get(field + suffix if suffix and field + suffix in params else field, ''))
        require(own('id') == str(ident), 'selected item variant belongs to another ID')
        require('eat' in {v.strip().casefold() for v in own('options').split(',')} and own('equipable').casefold() == 'no', 'no own active non-equipment Eat state')
        require((case['proposedCategory'], case['proposedSubcategory']) == (current['category'], current['subcategory']) == ('POTION', 'food') and current['ironmanTabKey'] == 'potions-food', 'policy only permits unchanged Food primary targets')
        require(not case.get('proposedTags') and not case.get('addedRoles') and not case.get('tagEvidence'), 'tags and supplemental roles are unassessed')
        raw = source_path.read_text(encoding='utf-8')
        match = re.search(r"[']{3}([^\n]*?)[']{3}", raw)
        require(match is not None, 'missing own named-subject definition')
        own_lead = raw[match.start():].split('\n\n', 1)[0].strip()
        # Source files are read with universal newline conversion. Keep literal
        # Wiki template markup; no rendered/numeric substitute can replace it.
        require(case['semanticExcerpt'] == own_lead, 'not the full literal named-subject lead')
        normalized = ' '.join(raw.split())
        for excerpt in [case['semanticExcerpt'], case['nutritionExcerpt'], *case.get('secondaryExcerpts', [])]:
            require(bool(excerpt.strip()) and ' '.join(excerpt.split()) in normalized, 'source excerpt is not literal pinned text')
        nutrition = ' '.join(case['nutritionExcerpt'].split())
        require(bool(re.search(r'\b(?:heals?|restores?)\b.{0,120}\d+.{0,90}Hitpoints?', nutrition, re.I)), 'missing explicit numeric Hitpoints consumption mechanic')
        for fact in case['exactVariantFacts']:
            require(str(params.get(fact['field'])) == fact['value'], 'selected exact-state fact changed')
    return {'technicalGate': 'passed', 'recordedRootApproval': True, 'exactIdsVerified': len(cases), 'scope': 'unchanged primary Food targets only; tags and supplemental roles unassessed'}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('policy', type=Path)
    args = parser.parse_args()
    print(json.dumps(verify_policy(json.loads(args.policy.read_text(encoding='utf-8-sig'))), sort_keys=True))


if __name__ == '__main__':
    main()
