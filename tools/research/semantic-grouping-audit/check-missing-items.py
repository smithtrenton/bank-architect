#!/usr/bin/env python3
"""Export every Wiki item-infobox record and compare exact IDs with runtime coverage.

Developer-only; no account data, production network access or automatic imports.
"""
import argparse
import collections
import csv
import hashlib
import json
import pathlib
import re

import audit


def write_csv(path, fields, rows):
    with path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def cell(value):
    return json.dumps(value, ensure_ascii=False) if isinstance(value, (list, dict)) else value


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--coverage", type=pathlib.Path, required=True,
                        help="Optional runtime coverage export from exportEffectiveItemClassifications")
    parser.add_argument("--output", type=pathlib.Path, default=pathlib.Path("tmp/missing-item-audit"))
    parser.add_argument("--refresh", action="store_true")
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    # Read and validate inputs before any network requests.
    with args.coverage.open(encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream, delimiter="\t")
        required = {"itemId", "auditScope", "itemCategory", "catalogName", "ironmanTabKey"}
        if not required <= set(reader.fieldnames or []):
            raise ValueError("Not a runtime coverage export: " + str(args.coverage))
        coverage = {}
        for row in reader:
            ident = int(row["itemId"])
            if ident <= 0 or ident in coverage:
                raise ValueError("Invalid or duplicate coverage ID: " + str(ident))
            coverage[ident] = row
    rows = audit.fetch_bucket("infobox_item", audit.ITEM_FIELDS, args.output / "cache", args.refresh)
    by_id = collections.defaultdict(list)
    full = []
    namespace_count = collections.Counter()
    for row in rows:
        # Keep every infobox source and every raw ID, including prefixed namespaces.
        for raw_id in audit.listify(row.get("item_id")) or [""]:
            text = str(raw_id).strip()
            ident = int(text) if re.fullmatch(r"[1-9][0-9]*", text) else None
            if ident is not None:
                by_id[ident].append(row)
            else:
                namespace_count["no_id" if not text else "non_numeric_id"] += 1
            known = coverage.get(ident)
            status = ("NO_NUMERIC_ID" if ident is None else "MISSING_FROM_CATALOG" if known is None
                      else "UNKNOWN_CLASSIFICATION" if known["itemCategory"] == "UNKNOWN" else "RECOGNIZED")
            full.append(dict(itemId=ident, rawItemId=raw_id, catalogStatus=status,
                             auditScope=known["auditScope"] if known else "",
                             catalogName=known["catalogName"] if known else "",
                             ironmanTabKey=known["ironmanTabKey"] if known else "",
                             sourceUrl=audit.wiki_url(row["page_name"]),
                             **{key: cell(row.get(key)) for key in audit.ITEM_FIELDS}))
    missing = []
    missing_sources = []
    for ident in sorted(set(by_id) - set(coverage)):
        # Deduplicate only repeated IDs within one record; never collapse distinct source records.
        facts = {json.dumps(row, sort_keys=True, ensure_ascii=False): row for row in by_id[ident]}
        records = list(facts.values())
        entry = dict(itemId=ident,
                     itemNames=" | ".join(sorted({str(r.get("item_name") or "") for r in records})),
                     pageNames=" | ".join(sorted({r["page_name"] for r in records})),
                     sourceRecordCount=len(records),
                     sourceUrls=" | ".join(sorted({audit.wiki_url(r["page_name"]) for r in records})),
                     sourceRecords=json.dumps(records, ensure_ascii=False, sort_keys=True))
        missing.append(entry)
        missing_sources.append(dict(item_id=ident, wiki_records=records))
    fields = ["itemId", "rawItemId", "catalogStatus", "auditScope", "catalogName", "ironmanTabKey", "sourceUrl"] + audit.ITEM_FIELDS
    write_csv(args.output / "wiki-full-item-list.csv", fields, full)
    write_csv(args.output / "missing-items.csv",
              ["itemId", "itemNames", "pageNames", "sourceRecordCount", "sourceUrls", "sourceRecords"], missing)
    audit.save(args.output / "missing-items.json", missing_sources)
    scope_counts = collections.Counter(coverage[i]["auditScope"] for i in set(by_id) & set(coverage))
    registry_absent = [i for i in by_id if i not in coverage or coverage[i]["auditScope"] == "SUPPLEMENTAL"]
    summary = dict(generated_at=audit.utc(), api=audit.API, license="CC BY-NC-SA 3.0",
                   attribution="OSRS Wiki contributors", infobox_records=len(rows),
                   distinct_numeric_ids=len(by_id), expanded_csv_records=len(full),
                   non_numeric_records=dict(namespace_count), wiki_ids_absent_from_bundled_registry=len(registry_absent),
                   missing_runtime_catalog_ids=len(missing), covered_wiki_ids_by_research_scope=dict(scope_counts),
                   covered_ids_with_unknown_classification=sum(coverage[i]["itemCategory"] == "UNKNOWN" for i in set(by_id) & set(coverage)),
                   multiple_source_record_ids=sum(len({json.dumps(r, sort_keys=True) for r in facts}) > 1 for facts in by_id.values()),
                   coverage_input=str(args.coverage), coverage_sha256=hashlib.sha256(args.coverage.read_bytes()).hexdigest(),
                   limitations=["All numeric Wiki item-infobox IDs, not a complete Jagex cache or proof of live bankability.",
                                "No name-based joins; historical/interface/beta prefixes remain non-numeric.",
                                "Wiki variants and removal dates are preserved; missing does not mean safe to import.",
                                "Research exclusions are separate from runtime recognition.",
                                "Bucket pages are fetched sequentially, not as an atomic snapshot; refresh in a new output directory for comparison."])
    audit.save(args.output / "summary.json", summary)
    files = sorted(args.output.glob("*.csv")) + sorted(args.output.glob("*.json")) + sorted((args.output / "cache").glob("*.json"))
    audit.save(args.output / "manifest.json", dict(generated_at=audit.utc(), attribution="OSRS Wiki contributors", license="CC BY-NC-SA 3.0",
        files=[dict(path=str(p.relative_to(args.output)), sha256=hashlib.sha256(p.read_bytes()).hexdigest()) for p in files if p.name != "manifest.json"]))
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
