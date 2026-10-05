#!/usr/bin/env python3
"""Replay the separately approved, conditional bank-context placement cohort."""
import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
CERT = ROOT / 'tools/research/semantic-grouping-audit/certification'
INPUT = ROOT / 'tmp/root-review/bank-context-placement-candidates-20261003'
SNAPSHOT = ROOT / 'tmp/root-review/bank-context-placement-integration-20261003/before-decisions.jsonl'

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def read(path):
    return json.loads(path.read_text(encoding='utf-8'))

def rows(path):
    return [json.loads(line) for line in path.read_text(encoding='utf-8').splitlines() if line.strip()]

def canonical(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
                                    separators=(',', ':')).encode()).hexdigest()

def verify():
    path = CERT / 'bank-context-placement-approved-policy.json'
    policy = read(path)
    pin = read(CERT / 'bank-context-placement-approvals.json')
    approved = pin['approvedPolicy']
    assert pin['status'] == 'root-reviewed conditional bank-context policy pin'
    assert policy['schema'] == 'root-approved-bank-context-placement/v1'
    assert policy['status'] == 'root-reviewed conditional canonical placement only'
    assert policy['axis'] == approved['axis'] == 'bank-context.canonical-primary-placement'
    assert policy['decision'] == approved['decision'] == 'certify'
    assert approved['name'] == path.name and approved['sha256'] == sha(path)
    assert approved['canonicalSha256'] == canonical(policy)
    for relative, expected in policy['sourceHashes'].items():
        assert sha(ROOT / relative) == expected, relative
    assert sha(SNAPSHOT) == '4b0ba8748a5cabf6b71f0328be3b2066043a316f518a9c316d69c4908edd14fc'
    snapshot_rows = rows(SNAPSHOT)
    snapshot = {r['itemId']: r for r in snapshot_rows}
    assert len(snapshot) == len(snapshot_rows) == 34085
    assert Counter(r['decision'] for r in snapshot_rows) == Counter(
        {'certify': 2625, 'revise': 307, 'exclude': 706, 'unresolved': 30447})
    candidates = rows(INPUT / 'same-assignment-candidates.jsonl')
    assert sha(INPUT / 'same-assignment-candidates.jsonl') == '16b32d4ae918b59bad21143dd7615415a8fba8c67dd95336041da0c64808f029'
    expected_cases = [{'itemId': r['itemId'], 'targetItemId': r['targetItemId'],
                       'relation': r['relation']} for r in sorted(candidates, key=lambda r: r['itemId'])]
    assert policy['cases'] == expected_cases
    assert approved['caseCount'] == len(expected_cases) == 1490
    assert approved['approvedItemIds'] == sorted(r['itemId'] for r in candidates)
    assert len(set(approved['approvedItemIds'])) == 1490
    edges = defaultdict(list)
    graph = defaultdict(set)
    for e in rows(ROOT / 'tmp/category-certification/identity-links.jsonl'):
        edges[e['fromItemId']].append(e)
        if e['relation'] in {'NOTE_VARIANT_OF', 'PLACEHOLDER_FOR'}:
            graph[e['fromItemId']].add(e['toItemId'])
    index = read(ROOT / 'tmp/category-certification/wiki-articles/article-index.json')
    own_ids = {int(i) for a in index.values() for i in a.get('exactInfoboxItemIds', [])}
    identity_hash = sha(ROOT / 'tmp/category-certification/identity-links.jsonl')
    assert identity_hash == '2fdcab1851e7509818b88cc89882c095687d41e87d07a8774adb121236705c4e'
    quarantined = {r['itemId'] for r in rows(INPUT / 'quarantined-placeholder-edges.jsonl')}
    pins = read(INPUT / 'source-pins.json')
    for p in pins['pins']:
        body_path = ROOT / p['localPath']
        assert sha(body_path) == p['sha256']
        assert (p['title'], p['revision'], p['sha256']) in {
            ('Bank', 15359494, 'f3ac75d1f65f9e25d973f697d873605dd4068a837c8e7be63ea246309c7c0bd5'),
            ('Bank note', 15337973, 'b32655b2b112d5704b55efc589839b848906f0c71122b70001123b67f9a08a94')}
        body = body_path.read_bytes().decode('utf-8').replace('\r\n', '\n').replace('\r', '\n')
        for passage in p['passages']:
            assert passage['text'] in body
    for c in candidates:
        item, target, relation = c['itemId'], c['targetItemId'], c['relation']
        assert item > 0 and target > 0 and item != target
        assert item not in own_ids and item not in quarantined
        assert relation in {'NOTE_VARIANT_OF', 'PLACEHOLDER_FOR'}
        assert snapshot[item]['decision'] == 'unresolved'
        base = snapshot[target]
        assert base['decision'] in {'certify', 'revise'}
        route = dict(zip(('category', 'subcategory', 'ironmanTabKey'),
                         (base['proposedCategory'], base['proposedSubcategory'], base['proposedIronmanTabKey'])))
        assert c['proposedBankContextAssignment'] == route
        assert all(c['currentAliasAssignment'][k] == v for k, v in route.items())
        assert all(snapshot[item][k] == base[k] for k in (
            'proposedCategory', 'proposedSubcategory', 'proposedIronmanTabKey'))
        edge = [e for e in edges[item] if e['relation'] in {'NOTE_VARIANT_OF', 'PLACEHOLDER_FOR'}]
        assert len(edge) == 1 and edge[0]['toItemId'] == target and edge[0]['relation'] == relation
        typed = c['typedCacheEvidence']
        assert typed['identityIndexHash'] == identity_hash
        assert {k: typed[k] for k in ('fromItemId', 'toItemId', 'relation')} == {
            'fromItemId': item, 'toItemId': target, 'relation': relation}
        assert any(all(e.get(k) == typed.get(k) for k in (
            'fromItemId', 'toItemId', 'relation', 'cacheField', 'cacheOpcode',
            'sourcePath', 'sourceHash', 'sourceRevision', 'configIndexRevision'))
                   for e in edge[0]['evidence'] if e['kind'] == 'typed_identity')
        visited, pending = set(), [target]
        while pending:
            node = pending.pop()
            assert node != item
            if node not in visited:
                visited.add(node)
                pending.extend(graph[node])
        own = c['exactTargetWikiEvidence']
        a = index[own['sourceTitle']]
        assert target in {int(i) for i in a['exactInfoboxItemIds']}
        assert own['sourceRevision'] == a['revid'] and own['sourceHash'] == a['sha256']
        assert sha(ROOT / a['path']) == a['sha256']
        if relation == 'NOTE_VARIANT_OF':
            assert a['variants'][str(target)]['params'].get('noteable') != 'No'
            assert a['variants'][str(target)]['params'].get('tradeable') != 'No'
        assert any(e.get('itemId') == target and e['kind'] in {'exact_wiki', 'direct_variant'}
                   for e in base['evidence'])
    return policy, candidates, snapshot, pins

if __name__ == '__main__':
    _, candidates, _, _ = verify()
    print('Verified 1490 conditional bank-context placements; raw functions/tags/availability unassessed')
