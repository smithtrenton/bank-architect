#!/usr/bin/env python3
"""Verify the pinned exact-state evidence for a root-reviewed primary Gear policy."""
from __future__ import annotations
import argparse
import hashlib
import json
import re
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
CERT = Path(__file__).resolve().parent
BASE = ROOT / 'tmp/category-certification'
SLOTS = {'weapon': {'weapon', 'thrown-weapon'}, '2h': {'2h'}, '2h weapon': {'2h'}, 'head': {'head'}, 'body': {'body'}, 'legs': {'legs'}, 'feet': {'feet'}, 'hands': {'hands'}, 'ring': {'ring'}, 'neck': {'neck'}, 'shield': {'shield', 'magic-offhand'}, 'cape': {'cape'}, 'ammo': {'ammo', 'thrown-weapon'}}
APPROVED_STATUS = 'root-reviewed primary assignments only'

def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()

def row_digest(row: dict) -> str:
    return hashlib.sha256(json.dumps(row, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode()).hexdigest()

def verify_policy(policy: dict, *, allow_draft: bool = False) -> dict:
    if policy.get('schema') != 1 or (policy.get('status') != APPROVED_STATUS and not allow_draft):
        raise ValueError('Gear primary policy is not an explicitly root-approved schema-1 policy')
    recorded_approval = policy.get('status') == APPROVED_STATUS
    if recorded_approval:
        approvals = json.loads((CERT / 'root-policy-approvals.json').read_text(encoding='utf-8-sig'))
        if approvals.get('schema') != 1 or approvals.get('status') != 'root-reviewed exact policy pins':
            raise ValueError('Invalid detached root-policy approval record')
        approved = approvals['approvedPolicies']['gear-primary-approved-policy.json']
        if row_digest(policy) != approved['canonicalSha256']:
            raise ValueError('Gear policy contents differ from the separately recorded root approval')
    pins = policy['sourceHashes']
    inputs = {
        'articleIndex': BASE / 'wiki-articles/article-index.json',
        'gearPacket': BASE / 'reviewer-packets/gear.jsonl',
        'bonusSourceProof': BASE / 'reviews/gear-v2/bonus-source-proof.json',
        'bonusVerifier': CERT / 'verify-gear-bonus-sources.py',
        'entailmentReview': BASE / 'reviews/gear-cohort-entailment-v2/review.jsonl',
        'rootFilter': BASE / 'root-review/gear-primary-cohort-filter-v3.json',
        'adversarialReview': BASE / 'root-review/gear-primary-cohort-adversarial-v2.json',
    }
    for key, path in inputs.items():
        if digest(path) != pins[key]:
            raise ValueError('Gear primary frozen input changed: ' + key)
    index = json.loads(inputs['articleIndex'].read_text(encoding='utf-8-sig'))
    packets = {row['itemId']: row for row in (json.loads(line) for line in inputs['gearPacket'].read_text(encoding='utf-8-sig').splitlines() if line)}
    proof = json.loads(inputs['bonusSourceProof'].read_text(encoding='utf-8-sig'))
    if proof['inputs']['articleIndexSha256'] != pins['articleIndex'] or proof.get('statusCounts') != {'consistent': 2221}:
        raise ValueError('The Gear proof does not pin the approved exact-source scope')
    proof_rows = {row['itemId']: row for row in proof['consistent']}
    if len(proof_rows) != 2221:
        raise ValueError('Gear source proof has missing or duplicate exact IDs')
    cases = policy['cases']
    if len(cases) != policy['expectedCaseCount'] or len({case['itemId'] for case in cases}) != len(cases):
        raise ValueError('Approved Gear case count or exact-ID uniqueness changed')
    case_ids = {case['itemId'] for case in cases}
    holds = {hold['itemId'] for hold in policy.get('explicitAdditionalHolds', [])}
    root_filter = json.loads(inputs['rootFilter'].read_text(encoding='utf-8-sig'))
    adversarial = json.loads(inputs['adversarialReview'].read_text(encoding='utf-8-sig'))
    audited_ids = {row['itemId'] for row in adversarial['all941ExactVariantProofRows']}
    conflicts = {row['itemId'] for row in adversarial['directActivityOnlyFindings']}
    filtered_ids = set(root_filter['eligibleItemIds'])
    if holds != {22516, 30694, 30696} or conflicts != {30694, 30696}:
        raise ValueError('Gear root-reviewed activity holds changed')
    if audited_ids != filtered_ids - {22516} or case_ids != filtered_ids - holds:
        raise ValueError('Gear cases differ from the independently reviewed exact-ID cohort')
    if case_ids & holds:
        raise ValueError('A held exact ID was substituted into the approved Gear cohort')
    if recorded_approval and (sorted(case_ids) != approved['approvedItemIds'] or len(cases) != approved['caseCount'] or approved['decision'] != 'certify'):
        raise ValueError('Gear exact case set differs from its detached approval')
    for case in cases:
        ident = case['itemId']
        row = proof_rows[ident]
        source = index[case['title']]
        current = packets[ident]['current']
        claim = case['bonusSourceProof']
        def require(value: bool, message: str) -> None:
            if not value:
                raise ValueError(f'Gear primary ID {ident}: {message}')
        require(claim['artifactPath'] == 'tmp/category-certification/reviews/gear-v2/bonus-source-proof.json' and claim['artifactSha256'] == pins['bonusSourceProof'], 'wrong proof artifact')
        require(row['status'] == 'consistent' and row['itemId'] == ident and row_digest(row) == claim['rowSha256'], 'exact proof row hash/status mismatch')
        require(row['article']['title'] == case['title'] and row['article']['revision'] == case['sourceRevision'] == source['revid'] and row['article']['sha256'] == case['sourceSha256'] == source['sha256'], 'article title/revision/hash mismatch')
        require(ident in source['exactInfoboxItemIds'] and str(ident) in source['variants'], 'source has no exact ID binding')
        raw_params = source['variants'][str(ident)]['params']
        require(str(raw_params.get(row['itemVariant']['idParam'])) == str(ident), 'proof item variant selects another ID')
        active = row['activeEquipmentOptions']
        require(active['status'] == 'explicit_active_equipment_action' and active['explicitWearWieldEquip'] and str(active['equipable']).lower() == 'yes', 'no explicit active equipment state')
        require(raw_params.get(active['equipableParam']) == active['equipable'] and raw_params.get(active['optionsParam']) == active['options'], 'selected options/equipable disagree with raw variant')
        comps = row['fieldComparisons']
        require(len(comps) == 15 and all(c.get('matches') is True for c in comps.values()), 'slot/stat comparison is incomplete or contradictory')
        slot = row['joined']['record']['equipment_slot']
        require(slot == claim['equipmentSlot'] == comps['equipment_slot']['sourceValue'], 'exact slot mismatch')
        sub = case['proposedSubcategory']
        dart_ammo = sub == 'ammo' and slot == 'weapon' and 'dart' in case['semanticExcerpt'].lower() and 'throwing' in case['semanticExcerpt'].lower()
        require(sub == 'gear' or sub in SLOTS.get(slot, set()) or dart_ammo, 'subcategory conflicts with own equipment slot')
        require(case['proposedCategory'] == current['category'] == 'GEAR' and sub == current['subcategory'] and current['ironmanTabKey'] == 'combat-gear', 'this policy permits only unchanged Gear primary targets')
        require(not case.get('addedRoles') and not case.get('proposedTags') and not case.get('tagEvidence'), 'this primary policy does not approve new role/tag claims')
        positive = any(Decimal(comp['sourceNumeric']) > 0 for name, comp in comps.items() if name != 'equipment_slot' and comp.get('sourceNumeric') is not None)
        require(positive or (slot == 'ammo' and ('ammunition' in case['semanticExcerpt'].lower() or 'arrow' in case['semanticExcerpt'].lower() or 'bolt' in case['semanticExcerpt'].lower())), 'no own positive combat bonus or directly defined ammunition function')
        text_path = ROOT / source['path']
        require(digest(text_path) == source['sha256'], 'pinned source text changed')
        raw_text = text_path.read_text(encoding='utf-8')
        subject = re.search(r"[']{3}([^\n]*?)[']{3}", raw_text)
        require(subject is not None, 'missing own subject definition')
        own_lead = raw_text[subject.start():].split('\n\n', 1)[0].strip()
        require(case['semanticExcerpt'] == own_lead, 'semantic evidence differs from the full pinned own-subject definition')
        text = ' '.join(raw_text.split())
        for excerpt in [case['semanticExcerpt'], *case.get('secondaryExcerpts', [])]:
            require(bool(excerpt.strip()) and ' '.join(excerpt.split()) in text, 'primary or bonus excerpt is not literal pinned source')
        for fact in case['exactVariantFacts']:
            require(str(raw_params.get(fact['field'])) == fact['value'], 'exact selected item-state fact changed')
    return {'technicalGate': 'passed', 'policyStatus': policy['status'], 'exactIdsVerified': len(cases), 'recordedRootApproval': recorded_approval, 'scope': 'primary targets only; tags and supplemental roles unassessed'}

def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('policy', type=Path)
    parser.add_argument('--allow-draft', action='store_true', help='verify draft provenance without approving it')
    args = parser.parse_args()
    result = verify_policy(json.loads(args.policy.read_text(encoding='utf-8-sig')), allow_draft=args.allow_draft)
    print(json.dumps(result, sort_keys=True))

if __name__ == '__main__':
    main()
