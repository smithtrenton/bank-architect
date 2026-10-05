#!/usr/bin/env python3
"""Build the separately authorized exact Gear overlay into a fresh output."""
import argparse
import importlib.util
import json
from pathlib import Path

CERT = Path(__file__).resolve().parent
ROOT = CERT.parents[3]
spec = importlib.util.spec_from_file_location('gear19_overlay_verifier', CERT / 'verify-gear-primary-exact19-overlay.py')
verifier = importlib.util.module_from_spec(spec)
spec.loader.exec_module(verifier)

parser = argparse.ArgumentParser()
parser.add_argument('--output', type=Path, required=True)
args = parser.parse_args()
output = args.output.resolve()
verifier.require(output.is_relative_to(ROOT / 'tmp/root-review'), 'Output must be an explicit research-review artifact')
verifier.require(not output.exists(), 'Refusing to overwrite existing output')
module, base, assignments, coverage, cases, authority, pins = verifier.load_approved_inputs()
current = ROOT / 'tmp/category-certification/root-approved-decisions-with-clue-scrolls.jsonl'
verifier.require(verifier.sha(current) in {verifier.BASE_SHA, pins['expectedOutputSha256']}, 'Live ledger differs from this overlay predecessor or exact result')
rows = verifier.expected_rows(module, base, coverage, cases, verifier.sha(verifier.AUTHORITY))
raw = verifier.serialized(rows)
verifier.require(verifier.hashlib.sha256(raw).hexdigest() == pins['expectedOutputSha256'], 'Composed output differs from root pin')
output.parent.mkdir(parents=True, exist_ok=True)
with output.open('xb') as stream:
    stream.write(raw)
print(json.dumps(verifier.verify(output), sort_keys=True, indent=2))
