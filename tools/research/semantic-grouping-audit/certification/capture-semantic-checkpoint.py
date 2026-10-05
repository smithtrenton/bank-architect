#!/usr/bin/env python3
"""Freeze candidate mechanics and an honest full-universe metadata coverage register."""
import argparse
import collections
import csv
import gzip
import hashlib
import importlib.util
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
DIMENSIONS = ('functions-effects', 'skills-recipes', 'contents-containers',
              'acquisition-origin', 'applicability-restrictions', 'consumption-state',
              'competing-roles', 'bank-context')

def sha(raw):
    return hashlib.sha256(raw).hexdigest()

def read_rows(path):
    raw = path.read_bytes()
    if path.suffix == '.gz':
        raw = gzip.decompress(raw)
    return [json.loads(line) for line in raw.decode('utf-8').splitlines()]

def json_bytes(value):
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':')) + '\n').encode('utf-8')

def pin(path):
    return {'path': path.relative_to(ROOT).as_posix(), 'sha256': sha(path.read_bytes())}

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--pilot-definitions', required=True, type=Path)
args = parser.parse_args()
spec = importlib.util.spec_from_file_location('semantic_records', HERE / 'semantic-records.py')
validator = importlib.util.module_from_spec(spec)
spec.loader.exec_module(validator)
docs = ROOT / 'docs/research/category-certification'
research = ROOT / 'tmp/root-review'
pilot = research / 'semantic-metadata-sufficiency-20261003'
materials = research / 'materials-first100-semantic-capture-20261003'
candidate_paths = [pilot / 'candidate-assertions.jsonl', materials / 'pilot-assertions.jsonl']
assert sha(candidate_paths[0].read_bytes()) == '8221d7271d2917103c24fc53569452c14ab558e6110cbb18a4b80d44bc602bcc'
assert sha(candidate_paths[1].read_bytes()) == 'bcb5bac410b1d257938ceb242d98cc6252983b66730dce19e60a7617d209a1b1'
coverage_paths = [pilot / 'dimension-coverage.jsonl', materials / 'pilot-dimension-coverage.jsonl']
definition_paths = [args.pilot_definitions.resolve(), materials / 'predicate-definitions.json']
coverage_addendum = research / 'semantic-metadata-definition-reconciliation-20261003/coverage-row-overrides.jsonl'
assert sha(coverage_addendum.read_bytes()) == '0205356371f189cf115132dc7b830708faa98f4ab61a4adbeb37123d358d6e92'
baseline_path = docs / 'semantic-records-baseline.jsonl.gz'
effective_path = ROOT / 'tmp/category-certification/after-coverage.tsv'
placement_path = docs / 'approved-assignments.tsv'
manifest_path = docs / 'approved-assignments-manifest.json'
assert sha(effective_path.read_bytes()) == '4968b43a92ec9851552b485e8212ccdada955c1082c9314f9ba67ca018bb47c3'
assert sha(placement_path.read_bytes()) == '49e28abc0a2bf436f62089001f9c2b81df5c46a2b19535c6e78a9cc0022bb87e'
assert sha(manifest_path.read_bytes()) == 'f940e87caf845c2af8af4468de81a6c492a2e283780d0816c03f30da50e0de35'
baseline = validator.records(baseline_path)
facts = []
for path in candidate_paths:
    facts.extend(validator.records(path, sources=True).values())
assert len(facts) == 49
assert all(r['recordType'] == 'fact-assessment' and r['status'] == 'unassessed' and r['reviewStage'] == 'candidate' and isinstance(r['factValue'], dict) for r in facts)
assert len({r['recordId'] for r in facts}) == len(facts)
definitions = [json.loads(path.read_bytes()) for path in definition_paths]
defined = collections.Counter((d['predicate'], d['predicateVersion']) for packet in definitions for d in packet.get('predicates', packet.get('definitions', [])))
assert all(defined[(r['predicate'], r['predicateVersion'])] == 1 for r in facts), 'Missing or ambiguous candidate predicate definition'
with effective_path.open(encoding='utf-8-sig', newline='') as stream:
    effective = {int(r['itemId']): r for r in csv.DictReader(stream, delimiter='\t')}
with placement_path.open(encoding='utf-8-sig', newline='') as stream:
    placement = {int(r['itemId']): r for r in csv.DictReader(stream, delimiter='\t')}
baseline_ids = {r['itemId'] for r in baseline.values() if r['recordType'] == 'category-assessment'}
assert baseline_ids == set(effective) == set(placement) and len(effective) == 34085
legacy_tags = {(r['itemId'], r['tag']['name']) for r in baseline.values() if r['recordType'] == 'tag-assessment'}
current_tags = {(i, tag) for i, r in effective.items() for tag in r['tags'].split(',') if tag}
assert legacy_tags == current_tags and len(legacy_tags) == 1926
fact_map = {r['recordId']: r for r in facts}
refs = collections.defaultdict(set)
dimension_rows = []
for path in coverage_paths:
    dimension_rows.extend(read_rows(path))
for repair in read_rows(coverage_addendum):
    index = [i for i, row in enumerate(dimension_rows) if row == repair['priorRow']]
    assert len(index) == 1
    dimension_rows[index[0]] = repair['replacementRow']
for row in dimension_rows:
    item, dimension = row['itemId'], row['dimension']
    assert item in effective and dimension in DIMENSIONS
    for record_id in row.get('assertionIds', row.get('assertionRecordIds', [])):
        assert fact_map[record_id]['itemId'] == item
        refs[(item, dimension)].add(record_id)
unlinked = sorted(set(fact_map) - set().union(*refs.values()))
raw_counts = collections.Counter(r['itemId'] for r in baseline.values() if r['recordType'] == 'fact-assessment')
tags_by_item = collections.defaultdict(list)
facts_by_item = collections.defaultdict(list)
for item, tag in legacy_tags:
    tags_by_item[item].append(tag)
for row in facts:
    facts_by_item[row['itemId']].append(row['recordId'])
register = []
for item, row in sorted(effective.items()):
    register.append({'formatVersion': 'semantic-coverage-register/v1', 'itemId': item,
        'itemName': row['catalogName'] or row['registryName'],
        'catalogDecision': {'decision': placement[item]['decision'], 'metadataApprovalGranted': False},
        'legacyTags': sorted(tags_by_item[item]),
        'candidateFactRefs': sorted(facts_by_item[item]),
        'baselineRawObservationCount': raw_counts[item],
        'dimensions': {d: {'assessment': 'unassessed', 'completeness': 'not-certified',
                          'candidateFactRefs': sorted(refs[(item, d)])} for d in DIMENSIONS}})
fact_bytes = b''.join(json_bytes(r) for r in sorted(facts, key=lambda r: (r['itemId'], r['recordId'])))
coverage_bytes = b''.join(json_bytes(r) for r in register)
definition_bytes = json_bytes({'formatVersion': 'semantic-candidate-definitions-bundle/v1',
    'ruleUseAllowed': False, 'approval': 'none', 'packets': definitions})
outputs = {docs / 'semantic-capture-candidates-20261003.jsonl.gz': gzip.compress(fact_bytes, mtime=0),
    docs / 'semantic-capture-coverage-20261003.jsonl.gz': gzip.compress(coverage_bytes, mtime=0),
    docs / 'semantic-capture-predicates-20261003.json': definition_bytes}
target = docs / 'semantic-capture-manifest-20261003.json'
assert not any(path.exists() for path in [*outputs, target]), 'Never replace a historical checkpoint'
validator.parse_records(fact_bytes, 'candidate checkpoint', sources=True)
inputs = [baseline_path, docs / 'semantic-records-baseline-manifest.json', effective_path,
    placement_path, manifest_path, *candidate_paths, *coverage_paths, *definition_paths, coverage_addendum,
    HERE / 'semantic-records.py', HERE / 'semantic-records.schema.json', Path(__file__).resolve()]
manifest = {'formatVersion': 'semantic-capture-checkpoint/v1', 'approval': 'none',
    'sourceGitRevision': '3eb071e6205ba5a2c03b859ab6a020986f9f89b1', 'workingTree': 'dirty; preserved',
    'inputs': [pin(path) for path in inputs],
    'outputs': [{'path': path.relative_to(ROOT).as_posix(), 'sha256': sha(raw)} for path, raw in outputs.items()],
    'decompressedSha256': {'candidates': sha(fact_bytes), 'coverage': sha(coverage_bytes)},
    'counts': {'itemIds': 34085, 'dimensionAssessments': 34085 * len(DIMENSIONS),
        'candidateStructuredFacts': len(facts), 'candidateFactItemIds': len({r['itemId'] for r in facts}),
        'legacyTagAssignmentsPreserved': 1926, 'baselineRawObservations': sum(raw_counts.values()),
        'approvedSemanticFacts': 0, 'completedSemanticDimensions': 0},
    'unlinkedCandidateDimensionRefs': unlinked,
    'limits': ['Coverage presence is not review completion; every dimension remains unassessed.',
        'Candidate definitions are not registered for rule use; category approval does not approve facts or tags.',
        'Other research packets remain separate and unintegrated in this checkpoint.',
        'Full raw source replay requires the pinned research cache; hashes and excerpts cannot reconstruct missing full pages.']}
for path, raw in outputs.items():
    path.write_bytes(raw)
target.write_bytes(json_bytes(manifest))
print(json.dumps(manifest['counts']))
