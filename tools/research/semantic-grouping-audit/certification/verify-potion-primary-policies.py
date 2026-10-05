#!/usr/bin/env python3
"""Replay exact potion policy provenance; technical replay never grants approval."""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
CERT = Path(__file__).resolve().parent
DRAFT = ROOT / 'tmp/root-review/potion-primary-policy-draft-v1/potion-primary-policy-draft-v1.json'
DRAFT_SHA = '976bc4853125d68c2466074d39c5dcf568c04a18498406e759d48479f52dbce4'
CONFIG = {
    'potion-primary-approved-policy.json': ('certify', 347),
    'potion-corrections-approved-policy.json': ('revise', 40),
}
AUDITS = (
    ('tmp/root-review/potion-347-retained-adversarial-v1/independent-semantic-check-v1.json',
     '95a45263fea90710c71dcfda5a3bfb0801a950cf6dc2d33f4adb169926b0f8c3'),
    ('tmp/root-review/potion-integration-independent-20261003/potion-own-leads-effects-review-v1.json',
     '8ca01381ceab5fdb12c8ba687fb1f5459415ab5a78c6b6cb919cf6845e97e34b'),
    ('tmp/root-review/potion-40-revisions-adversarial-v1/findings.jsonl',
     '1d0eb736f4e1f912104dab6e8e2d29ae6ec843a41e12f3aeaffb592568361c6e'),
)
# Root-selected own-effect paragraphs for creation/acquisition-only leads.
# These are literal paragraph selectors, not a keyword classification rule.
OWN_EFFECT_STARTS = {
    'Super energy': 'Super energy potions recover 20%',
    'Antidote+': 'Antidote+ cures [[poison]]',
    'Restore mix': '==Uses==\nRestores [[Attack]]',
    'Ancient brew': 'A dose of ancient brew [[boost]]s',
    'Forgotten brew': 'A dose of forgotten brew [[boost]]s',
    'Prayer regeneration potion': 'Each dose restores one [[Prayer points|Prayer point]]',
    'Goading potion': '==Mechanics==\nThe potion',
    'Surge potion': '==Mechanics==\n[[File:Drinking surge potion.gif',
    'Armadyl brew': 'Each dose of an Armadyl brew',
    'Bottle of ogre prayer potion': 'Drinking the bottle grants 75',
    'Blighted overload': 'A dose of blighted overload,',
}


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    return json.loads(path.read_text(encoding='utf-8-sig'))


def canonical_sha(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
                                     separators=(',', ':')).encode()).hexdigest()


def require(condition, message):
    if not condition:
        raise ValueError(message)


def source_input_path(policy, key):
    relative = policy['sourceInputPaths'][key]
    # The approved mapper pin records its historical review context.
    if (key == 'mapper' and
            relative == 'src/main/java/com/pkoka5/ironmanbankarchitect/organize/PresetCategoryMapper.java' and
            policy['sourceHashes'][key] == 'ac388c46e6be546fcdca2f5958d965b794b78e7984e674294ab98417e8dd6e8b'):
        return ROOT / 'tmp/root-review/potion-historical-mapper-context-20261003/PresetCategoryMapper.java'
    return ROOT / relative


def normalized(text):
    return ' '.join(text.split())


def read_tsv(path):
    lines = [line for line in path.read_text(encoding='utf-8').splitlines()
             if line and not line.startswith('#')]
    return [line.split('\t') for line in lines]


def dose_tab(item_id, category, sort_metadata, families):
    if category != 'POTION':
        require(category == 'CLEANUP', f'#{item_id}: unexpected potion-policy category')
        return 'storage-cleanup'
    metadata = sort_metadata.get(item_id)
    if metadata and metadata[1] == 'DOSE' and metadata[0] in families:
        if int(metadata[2]) < families[metadata[0]]:
            return 'herblore'
    return 'potions-food'


def make_case(candidate):
    evidence = candidate['primaryEvidence']
    lead = evidence['ownSubjectLeadLiteral']
    literals = list(dict.fromkeys([lead] + [quote for key in (
        'positiveFunctionEvidence', 'positiveEffectEvidence', 'explicitNonConsumptionEvidence',
        'consumptionRestrictionEvidence', 'competingRecipeOrProductionUses')
        for quote in evidence[key]]))
    positive = lead
    selector = OWN_EFFECT_STARTS.get(candidate['title'])
    if selector:
        matches = [quote for quote in literals if quote.startswith(selector)]
        require(len(matches) == 1, f"#{candidate['itemId']}: own-effect paragraph selector changed")
        positive = matches[0]
    state = candidate['exactVariant']['ownState']
    suffix = str(candidate['exactVariant']['suffix'] or '')
    fields = []
    for base in ('id', 'name', 'version', 'examine', 'options', 'equipable', 'quest', 'bankable'):
        field = base + suffix if base + suffix in state else base
        if field in state:
            fields.append({'field': field, 'value': str(state[field])})
    proposed = candidate['proposedAssignment']
    return {
        'itemId': candidate['itemId'], 'title': candidate['title'],
        'sourceRevision': candidate['source']['revision'],
        'sourceSha256': candidate['source']['sha256'],
        'expectedDecision': candidate['decision'],
        'proposedCategory': proposed['category'], 'proposedSubcategory': proposed['subcategory'],
        'proposedIronmanTabKey': proposed['ironmanTabKey'],
        'semanticExcerpt': lead, 'positiveFunctionExcerpt': positive,
        'secondaryExcerpts': [quote for quote in literals if quote != lead],
        'exactVariantFacts': fields, 'rationale': candidate['rootSemanticNote'],
        'stateScopeNotes': {
            'exactOwnState': state, 'doseEvidence': candidate['exactDoseEvidence'],
            'mapperDerivation': candidate['mapperDerivation'], 'bankability': candidate['bankability'],
            'rootFinding': candidate['rootFinding'],
            'requirements': [{'kind': 'persistent quest-progress drinking prerequisite',
                              'quest': 'Dragon Slayer I', 'literalSource': lead}]
                            if 'Dragon Slayer I' in lead else [],
            'scope': 'Primary category, subtype and tab only; recipe and sibling context is not inherited; tags and secondary roles unassessed.',
        },
    }


def make_policy(name):
    require(name in CONFIG, 'Policy outside exact two-name allowlist')
    require(sha(DRAFT) == DRAFT_SHA, 'Immutable potion draft changed')
    draft = read(DRAFT)
    decision, count = CONFIG[name]
    paths = {key: value['path'] for key, value in draft['inputPins'].items()
             if isinstance(value, dict) and 'path' in value}
    hashes = {key: value['sha256'] for key, value in draft['inputPins'].items()
              if isinstance(value, dict) and 'path' in value}
    paths['immutableRootPolicyDraft'] = DRAFT.relative_to(ROOT).as_posix()
    hashes['immutableRootPolicyDraft'] = DRAFT_SHA
    paths['draftBuilder'] = 'tmp/root-review/potion-primary-policy-draft-v1/build-policy-draft.mjs'
    hashes['draftBuilder'] = draft['inputPins']['buildHelperSha256']
    return {
        'schema': 1, 'policyFile': name, 'status': 'root-reviewed primary assignments only',
        'expectedDecision': decision, 'expectedCaseCount': count,
        'rule': draft['rule'], 'sourceInputPaths': paths, 'sourceHashes': hashes,
        'independentAudits': [{'path': path, 'sha256': digest} for path, digest in AUDITS],
        'approvalScope': 'Primary category, subtype and tab; preserve all tags; no supplemental-role approval.',
        'rootSemanticDecision': 'Resume complete 123-title/417-ID root v3 read. Approve the 387 exact positive cases, retain 20 holds and 10 no-bank candidates. Dragon Slayer I starting prerequisite remains a requirement, not activity-only consumption.',
        'cases': [make_case(case) for case in draft['cases'] if case['decision'] == decision],
    }


def verify_policy(policy, *, draft=False):
    name = policy.get('policyFile')
    expected = make_policy(name)
    require(policy == expected, 'Complete potion policy differs from root-selected immutable cases and scope')
    for key, relative in policy['sourceInputPaths'].items():
        require(sha(source_input_path(policy, key)) == policy['sourceHashes'][key], f'Frozen source changed: {key}')
    for audit in policy['independentAudits']:
        require(sha(ROOT / audit['path']) == audit['sha256'], 'Independent potion audit changed')
    source_draft = read(DRAFT)
    partitions = [source_draft[key] for key in ('cases', 'heldCases', 'ignoreCandidates')]
    ids = [[int(case['itemId']) for case in cases] for cases in partitions]
    require(list(map(len, ids)) == [387, 20, 10], '417-ID partition sizes changed')
    all_ids = [item for partition in ids for item in partition]
    require(len(set(all_ids)) == 417 and sorted(all_ids) == source_draft['candidateAccounting']['allExactIds'],
            'Full exact-ID partition is not disjoint and exhaustive')
    require(sum(case['decision'] == 'certify' for case in source_draft['cases']) == 347,
            'Uniform certify/revise partition changed')
    index = read(ROOT / policy['sourceInputPaths']['articleIndex'])
    root_rows = [json.loads(line) for line in (ROOT / policy['sourceInputPaths']['rootV3']).read_text(
        encoding='utf-8').splitlines() if line.strip()]
    require(len(root_rows) == 123 and sum(len(row['exactIds']) for row in root_rows) == 417,
            'Complete v3 root semantic-read scope changed')
    root_by_id = {int(item): row for row in root_rows for item in row['exactIds']}
    with (ROOT / policy['sourceInputPaths']['coverage']).open(encoding='utf-8', newline='') as stream:
        coverage = {int(row['itemId']): row for row in csv.DictReader(stream, delimiter='\t')}
    sort_metadata = {int(row[0]): row[1:4] for row in read_tsv(ROOT / policy['sourceInputPaths']['itemSort'])}
    families = {row[0]: len(row[1].split(',')) for row in read_tsv(ROOT / policy['sourceInputPaths']['doseFamilies'])}
    require(len(sort_metadata) == len(read_tsv(ROOT / policy['sourceInputPaths']['itemSort'])), 'Duplicate sort metadata ID')
    candidate_by_id = {case['itemId']: case for case in source_draft['cases']}
    facts_count = quote_count = 0
    for case in policy['cases']:
        item = case['itemId']; candidate = candidate_by_id[item]; source = index[case['title']]
        require(item in set(map(int, source['exactInfoboxItemIds'])) and str(item) in source['variants'],
                f'#{item}: source lacks exact own variant')
        require(source['revid'] == case['sourceRevision'] and source['sha256'] == case['sourceSha256'],
                f'#{item}: own source identity changed')
        raw_path = ROOT / str(source['path']).replace('\\', '/')
        require(sha(raw_path) == source['sha256'], f'#{item}: raw source changed')
        raw = raw_path.read_text(encoding='utf-8'); params = source['variants'][str(item)]['params']
        for fact in case['exactVariantFacts']:
            field, value = fact['field'], fact['value']
            require(str(params.get(field, '')) == value, f'#{item}: exact fact differs: {field}')
            if field.startswith('id'):
                require(value == str(item) and re.search(r'^\s*\|\s*' + re.escape(field) +
                    r'\s*=\s*' + str(item) + r'\s*$', raw, re.M) is not None,
                    f'#{item}: exact numeric ID raw binding missing')
            facts_count += 1
        for quote in [case['semanticExcerpt'], case['positiveFunctionExcerpt']] + case['secondaryExcerpts']:
            require(quote.strip() and normalized(quote) in normalized(raw), f'#{item}: nonliteral own-source excerpt')
            quote_count += 1
        root = root_by_id[item]
        require(root['title'] == case['title'] and root['sourceSha256'] == source['sha256'] and
                root['rootSemanticNote'] == case['rationale'], f'#{item}: complete root review differs')
        current = coverage[item]; old = candidate['currentAssignment']; target = candidate['proposedAssignment']
        require((current['itemCategory'], current['subcategory'], current['ironmanTabKey']) ==
                (old['category'], old['subcategory'], old['ironmanTabKey']), f'#{item}: frozen current route differs')
        require(sorted(filter(None, current['tags'].split(','))) == sorted(old['tags']) == sorted(target['tags']),
                f'#{item}: tags must remain unchanged')
        changed = any(old[key] != target[key] for key in ('category', 'subcategory', 'ironmanTabKey'))
        require(case['expectedDecision'] == ('revise' if changed else 'certify'), f'#{item}: decision/current mismatch')
        tab = dose_tab(item, target['category'], sort_metadata, families)
        require(tab == target['ironmanTabKey'] == case['proposedIronmanTabKey'], f'#{item}: metadata-derived tab differs')
        if target['subcategory'].startswith('potion-dose-'):
            dose = int(target['subcategory'].removeprefix('potion-dose-'))
            require(dose == candidate['exactVariant']['doseCount'] == candidate['exactDoseEvidence']['doseCount'],
                    f'#{item}: subtype differs from the exact own dose state')
            metadata = sort_metadata.get(item)
            if metadata and metadata[1] == 'DOSE':
                require(int(metadata[2]) == dose, f'#{item}: subtype differs from exact dose metadata')
        require(not case.get('addedRoles') and not case.get('proposedTags') and not case.get('tagEvidence'),
                f'#{item}: primary-only scope violated')
        if item in {11505, 11960, 21994, 22221}:
            require('Dragon Slayer I' in case['semanticExcerpt'] and
                    case['stateScopeNotes']['requirements'],
                    f'#{item}: quest drinking requirement erased')
            require(target['subcategory'] == 'potion-dose-2', f'#{item}: quest unlock incorrectly became activity subtype')
        if case['title'] == 'Ancient brew':
            require(case['positiveFunctionExcerpt'].startswith(OWN_EFFECT_STARTS['Ancient brew']) and
                    any(quote.startswith('==Effects==\n===Magic boost===') for quote in case['secondaryExcerpts']),
                    f'#{item}: own Ancient brew effect must not come from Ancient mix')
    decision, count = CONFIG[name]
    require(len(policy['cases']) == count and all(case['expectedDecision'] == decision for case in policy['cases']),
            'Uniform exact cohort size/decision changed')
    if not draft:
        path = CERT / name; require(read(path) == policy, 'Approved policy is not saved at exact whitelisted path')
        approval = read(CERT / 'root-policy-approvals.json')['approvedPolicies'].get(name, {})
        require(approval.get('sha256') == sha(path) and approval.get('canonicalSha256') == canonical_sha(policy)
                and approval.get('approvedItemIds') == sorted(case['itemId'] for case in policy['cases'])
                and approval.get('caseCount') == count and approval.get('decision') == decision,
                'Detached exact policy approval pin differs')
    return {'policyFile': name, 'cases': count, 'decision': decision, 'variantFactsChecked': facts_count,
            'literalExcerptsChecked': quote_count, 'detachedApprovalVerified': not draft}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--draft', action='store_true')
    args = parser.parse_args()
    print(json.dumps({'technicalGate': 'passed', 'semanticApprovalGranted': False,
                      'results': [verify_policy(make_policy(name) if args.draft else read(CERT / name),
                                                draft=args.draft) for name in CONFIG]}, sort_keys=True))


if __name__ == '__main__':
    main()
