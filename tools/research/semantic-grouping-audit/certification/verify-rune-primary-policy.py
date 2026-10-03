#!/usr/bin/env python3
"""Replay provenance for the separately root-approved 23 ordinary spell runes."""
from __future__ import annotations
import argparse
import hashlib
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
CERT = Path(__file__).resolve().parent
BASE = ROOT / 'tmp/category-certification'
IDS = set(range(554, 567)) | set(range(4694, 4700)) | {9075, 21880, 28929, 30843}
# These positive phrases are specific to the root-read own-item definitions.
POSITIVE = {
    554: 'They are used to cast fire-based combat spells',
    555: 'They are used to cast water-based combat spells',
    556: 'They are used in every combat spell and most teleportation spells',
    557: 'They are used to cast earth-based combat spells',
    558: 'mind rune is used for the strike spells',
    559: 'Body runes are low level runes used for',
    560: 'Death runes are one of the runes used to cast spells',
    561: 'Nature runes are runes used for transmutation spells',
    562: 'Chaos runes are used for low level missile spells',
    563: 'law rune is a rune used in all teleportation and telekinesis spells',
    564: 'cosmic rune is a rune used primarily in enchanting spells',
    565: 'Blood runes are one of the runes used to cast spells',
    566: 'Soul runes are one of the runes used to cast spells',
    4694: 'any spell requiring one fire rune, one water rune, or both will spend only one steam rune',
    4695: 'any spell requiring one water rune, one air rune, or both will spend only one mist rune',
    4696: 'any spell requiring one earth rune, one air rune, or both will spend only one dust rune',
    4697: 'any spell requiring one fire rune, one air rune, or both will cost only one smoke rune',
    4698: 'any spell requiring one water rune, one earth rune, or both will spend only one mud rune',
    4699: 'any spell requiring one fire rune, one earth rune, or both will spend only one lava rune',
    9075: 'Astral runes are runes used in all Lunar Spells',
    21880: 'they are used for surge spells',
    28929: 'they can be used in place of fire runes for non-combat spells',
    30843: 'any spell requiring one cosmic rune, one soul rune, or both will spend only one aether rune',
}


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def plain(text: str) -> str:
    text = re.sub(r'\[\[([^\]|]+)(?:\|([^\]]+))?\]\]', lambda m: m[2] or m[1], text)
    return ' '.join(text.replace(chr(39) * 3, '').replace(chr(39) * 2, '').split())


def verify_policy(policy: dict) -> dict:
    if policy.get('schema') != 1 or policy.get('status') != 'root-reviewed primary assignments only':
        raise ValueError('Rune policy lacks explicit root approval status')
    approvals = json.loads((CERT / 'root-policy-approvals.json').read_text(encoding='utf-8-sig'))
    if approvals.get('schema') != 1 or approvals.get('status') != 'root-reviewed exact policy pins':
        raise ValueError('Invalid detached root approval record')
    approval = approvals['approvedPolicies']['rune-primary-approved-policy.json']
    canonical = hashlib.sha256(json.dumps(policy, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode()).hexdigest()
    if canonical != approval['canonicalSha256']:
        raise ValueError('Rune policy differs from separate root approval')
    inputs = {
        'articleIndex': BASE / 'wiki-articles/article-index.json',
        'transportPacket': BASE / 'reviewer-packets/currency-runes-teleport.jsonl',
        'candidatePacket': BASE / 'reviews/transport-v17/ordinary-spellcasting-runes-review.json',
        'stateReplay': BASE / 'reviews/transport-v18/exact23-rune-adversarial-review.json',
        'independentReview': BASE / 'root-review/ordinary-spellcasting-runes-adversarial-v1.json',
    }
    for key, path in inputs.items():
        if digest(path) != policy['sourceHashes'][key]:
            raise ValueError('Rune frozen input changed: ' + key)
    index = json.loads(inputs['articleIndex'].read_text(encoding='utf-8-sig'))
    packets = {r['itemId']: r for r in map(json.loads, inputs['transportPacket'].read_text(encoding='utf-8-sig').splitlines())}
    review = json.loads(inputs['candidatePacket'].read_text(encoding='utf-8-sig'))
    candidates = {r['itemId']: r for r in review['positiveProposals']}
    replay = json.loads(inputs['stateReplay'].read_text(encoding='utf-8-sig'))
    ids = [r['itemId'] for r in policy['cases']]
    if len(ids) != 23 or policy.get('expectedCaseCount') != 23 or set(ids) != IDS or set(candidates) != IDS:
        raise ValueError('Rune exact approved cohort changed')
    if sorted(ids) != approval['approvedItemIds'] or approval['caseCount'] != 23 or approval['decision'] != 'certify':
        raise ValueError('Rune exact case set differs from separate approval')
    if set(replay['examinedExactItemIds']) != IDS or len(replay['ordinaryRuneCases']) != 23:
        raise ValueError('Rune exact state replay set changed')
    if replay['inputs']['proposalPacket']['sha256'].removeprefix('sha256:') != policy['sourceHashes']['candidatePacket']:
        raise ValueError('Rune state replay input binding changed')
    if any(r['directNegativeSpellUseMentionsInLead'] for r in replay['ordinaryRuneCases']):
        raise ValueError('Rune state replay contains a direct positive-cohort exception')
    independent = json.loads(inputs['independentReview'].read_text(encoding='utf-8-sig'))
    if (independent['reviewScope']['inputSha256'] != policy['sourceHashes']['candidatePacket'] or
            set(independent['reviewScope']['exactItemIds']) != IDS or
            len(independent['examinedRows']) != 23 or
            {r['itemId'] for r in independent['examinedRows']} != IDS or
            independent['conclusion']['confirmedExceptions'] or independent['conclusion']['unresolvedProposalCases']):
        raise ValueError('Independent rune review binding or exceptions changed')
    independent_rows = {r['itemId']: r for r in independent['examinedRows']}
    # External quest/mode copies are recorded as separate, unapproved item IDs.
    excluded = {r['itemId'] for cohort in replay['confirmedExceptions'].values() for r in cohort}
    if excluded & IDS or len(excluded) != 27:
        raise ValueError('Rune quest/mode copy boundary changed')
    for case in policy['cases']:
        ident = case['itemId']
        def require(condition: bool, message: str) -> None:
            if not condition:
                raise ValueError(f'Rune primary ID {ident}: {message}')
        source = index[case['title']]
        require(ident in source['exactInfoboxItemIds'] and str(ident) in source['variants'], 'no exact numeric-ID binding')
        require((case['sourceRevision'], case['sourceSha256']) == (source['revid'], source['sha256']), 'source revision/hash mismatch')
        candidate = candidates[ident]
        require(candidate['exactSourceTitle'] == case['title'] and candidate['sourceRevision'] == source['revid'] and candidate['sourceHash'].removeprefix('sha256:') == source['sha256'], 'candidate source binding changed')
        path = ROOT / source['path']
        require(digest(path) == source['sha256'], 'pinned raw source bytes changed')
        own_review = independent_rows[ident]['exactSource']
        require((own_review['title'], own_review['revision'], own_review['sha256']) == (case['title'], source['revid'], source['sha256']), 'independent source binding changed')
        variant = source['variants'][str(ident)]
        params = variant['params']
        suffix = str(variant.get('suffix', ''))
        def own(field: str) -> str:
            return str(params.get(field + suffix if suffix and field + suffix in params else field, ''))
        require(own('id') == str(ident), 'selected own variant is another ID')
        require(all(own(k).casefold() == v for k, v in {'equipable': 'no', 'stackable': 'yes', 'quest': 'no', 'tradeable': 'yes', 'noteable': 'no'}.items()), 'ordinary own non-equipment rune state changed')
        require(own('options').casefold() == 'drop', 'ordinary own option state changed')
        target = {'category': 'RUNE', 'subcategory': 'rune', 'ironmanTabKey': 'currency-utilities'}
        current = packets[ident]['current']
        require({k: current[k] for k in target} == candidate['frozenCurrentPrimaryRoute'] == candidate['proposedPrimaryRoute'] == target, 'only unchanged ordinary Rune primary route permitted')
        require((case['proposedCategory'], case['proposedSubcategory']) == ('RUNE', 'rune'), 'approved primary target changed')
        require(not case.get('proposedTags') and not case.get('addedRoles') and not case.get('tagEvidence'), 'tags and secondary roles are unassessed')
        raw = path.read_text(encoding='utf-8')
        match = re.search(chr(39) * 3 + r'([^\n]*?)' + chr(39) * 3, raw)
        require(match is not None, 'missing own-subject definition')
        lead = raw[match.start():].split('\n\n', 1)[0].strip()
        require(case['semanticExcerpt'] == lead, 'not full literal own-subject first paragraph')
        positive = case['positiveFunctionExcerpt']
        excerpts = case.get('secondaryExcerpts', [])
        require(positive in ([lead] + excerpts), 'positive function is not recorded as a literal citation')
        require(POSITIVE[ident] in plain(positive), 'missing own positive spell-payment clause')
        for excerpt in excerpts:
            require(bool(excerpt.strip()) and ' '.join(excerpt.split()) in ' '.join(raw.split()), 'nonliteral secondary excerpt')
        for fact in case['exactVariantFacts']:
            require(str(params.get(fact['field'])) == fact['value'], 'own variant fact changed')
    return {'technicalGate': 'passed', 'recordedRootApproval': True, 'exactIdsVerified': 23, 'scope': 'unchanged ordinary spellcasting-rune primary targets only; tags and secondary roles unassessed'}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('policy', type=Path)
    args = parser.parse_args()
    print(json.dumps(verify_policy(json.loads(args.policy.read_text(encoding='utf-8-sig'))), sort_keys=True))


if __name__ == '__main__':
    main()
