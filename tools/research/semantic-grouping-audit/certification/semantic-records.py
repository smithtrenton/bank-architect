#!/usr/bin/env python3
"""Offline semantic snapshots. Structural/source replay never grants semantic approval."""
from __future__ import annotations
import argparse, collections, csv, gzip, hashlib, json, math, pathlib, re

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parents[3]
SCHEMA = HERE / "semantic-records.schema.json"
FORMAT = "semantic-item-assertion/v1"


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)


def digest(value):
    return hashlib.sha256(value).hexdigest()


def no_duplicate_keys(pairs):
    result = {}
    for key, value in pairs:
        if key in result: raise ValueError(f"Duplicate JSON property: {key}")
        result[key] = value
    return result


def decode(value):
    result = json.loads(value, object_pairs_hook=no_duplicate_keys,
                        parse_constant=lambda value: (_ for _ in ()).throw(ValueError(value)))
    canonical(result)  # Reject nonfinite nested numbers too.
    return result


def local_source(value):
    path = (ROOT / value).resolve()
    if not path.is_relative_to(ROOT.resolve()): raise ValueError("Source path escapes the repository")
    return path


def load(path):
    raw = path.read_bytes()
    return gzip.decompress(raw) if path.suffix == ".gz" else raw


def key(row):
    kind = row["recordType"]
    if kind == "tag-assessment": claim = row["tag"]
    elif kind == "category-assessment": claim = {"namespace": "primary-category"}
    elif kind == "fact-assessment":
        claim = {"namespace": row["fact"]["namespace"], "name": row["fact"]["name"],
                 "predicate": row["predicate"], "predicateVersion": row["predicateVersion"],
                 "claimSource": row.get("claimSource", "curated"), "state": row["state"],
                 "qualifiers": row.get("qualifiers", {})}
    else: claim = row["relationship"]
    if kind == "tag-assessment": claim = {k: claim[k] for k in ("namespace", "name")}
    return canonical([row["itemId"], kind, claim])


def seal(row):
    row["recordId"] = "claim-" + digest(key(row).encode("utf-8"))
    return row


def matches_type(value, name):
    return {"object": isinstance(value, dict), "array": isinstance(value, list),
            "string": isinstance(value, str), "integer": type(value) is int,
            "number": type(value) in (int, float) and math.isfinite(value),
            "boolean": type(value) is bool, "null": value is None}[name]


def check_schema(value, rule, root, where="record"):
    # Deliberately limited to keywords used by the bundled schema, with unknown keywords rejected.
    supported = {"$schema", "$id", "$ref", "$defs", "title", "description", "type", "required", "properties",
                 "additionalProperties", "const", "enum", "pattern", "minLength", "minimum", "minItems",
                 "minProperties", "items", "uniqueItems", "allOf", "oneOf", "if", "then", "format"}
    unknown = set(rule) - supported
    if unknown: raise ValueError(f"Unsupported schema keywords: {sorted(unknown)}")
    if "$ref" in rule:
        target = root
        for part in rule["$ref"].removeprefix("#/").split("/"): target = target[part]
        check_schema(value, target, root, where)
    if "type" in rule and not matches_type(value, rule["type"]): raise ValueError(f"{where}: expected {rule['type']}")
    if "const" in rule and (type(value) is not type(rule["const"]) or value != rule["const"]): raise ValueError(f"{where}: invalid constant")
    if "enum" in rule and value not in rule["enum"]: raise ValueError(f"{where}: invalid enum")
    if isinstance(value, str):
        if len(value) < rule.get("minLength", 0): raise ValueError(f"{where}: empty string")
        if "pattern" in rule and not re.search(rule["pattern"], value): raise ValueError(f"{where}: pattern mismatch")
    if type(value) in (int, float) and value < rule.get("minimum", -math.inf): raise ValueError(f"{where}: below minimum")
    if isinstance(value, dict):
        missing = set(rule.get("required", [])) - set(value)
        if missing: raise ValueError(f"{where}: missing {sorted(missing)}")
        if len(value) < rule.get("minProperties", 0): raise ValueError(f"{where}: insufficient properties")
        props = rule.get("properties", {})
        if rule.get("additionalProperties") is False and set(value) - set(props): raise ValueError(f"{where}: unknown properties")
        for name in value.keys() & props.keys(): check_schema(value[name], props[name], root, f"{where}.{name}")
    if isinstance(value, list):
        if len(value) < rule.get("minItems", 0): raise ValueError(f"{where}: insufficient items")
        if rule.get("uniqueItems") and len({canonical(x) for x in value}) != len(value): raise ValueError(f"{where}: duplicate items")
        if "items" in rule:
            for index, item in enumerate(value): check_schema(item, rule["items"], root, f"{where}[{index}]")
    for child in rule.get("allOf", []): check_schema(value, child, root, where)
    if "oneOf" in rule:
        count = 0
        for child in rule["oneOf"]:
            try: check_schema(value, child, root, where); count += 1
            except ValueError: pass
        if count != 1: raise ValueError(f"{where}: expected exactly one matching shape")
    if "if" in rule:
        try: check_schema(value, rule["if"], root, where)
        except ValueError: pass
        else: check_schema(value, rule.get("then", {}), root, where)


def verify_source(row, evidence):
    if evidence["kind"] != "exact-wiki":
        raise ValueError("--sources currently supports exact-wiki evidence only; use the existing typed-cache/policy verifiers for other evidence")
    if evidence["subjectItemId"] != row["itemId"] or evidence["exactVariant"]["itemId"] != row["itemId"]:
        raise ValueError("Direct Wiki evidence belongs to another item")
    path = local_source(evidence["sourcePath"])
    raw = path.read_bytes()
    if digest(raw) != evidence["sourceSha256"].removeprefix("sha256:"): raise ValueError(f"Source hash mismatch: {path}")
    body = raw.decode("utf-8")
    if not evidence["sourceUrl"].endswith("/revision/" + str(evidence["sourceRevision"])) or path.stem != str(evidence["sourceRevision"]):
        raise ValueError("Source URL/revision/path disagreement")
    norm = lambda value: re.sub(r"\s+", " ", value).strip()
    variant = evidence["exactVariant"]; block = variant["infoboxRaw"]
    if not re.match(r"\{\{\s*Infobox Item\b", block, re.I) or norm(block) not in norm(body): raise ValueError("Unbound infobox")
    line = variant["idFieldLiteral"]
    match = re.fullmatch(r"\s*\|\s*(id[0-9]*)\s*=\s*([0-9, ]+)\s*", line)
    if not match or match[1] != variant["idField"] or row["itemId"] not in [int(x.strip()) for x in match[2].split(",")]: raise ValueError("Unbound numeric ID")
    if norm(line) not in norm(block) or norm(evidence["quote"]) not in norm(body): raise ValueError("Missing source literal")
    lead = row.get("sourceObservation", {}).get("ownPageLeadLiteral", "")
    if lead and norm(lead) not in norm(body): raise ValueError("Missing retained lead literal")
    for field, value in variant["fields"].items():
        if not re.search(r"\|\s*" + re.escape(field) + r"\s*=\s*" + re.escape(str(value)) + r"\s*(?:\r?\n|\|)", block): raise ValueError(f"Unbound variant field: {field}")


def records(path, sources=False):
    return parse_records(load(path), str(path), sources)


def parse_records(data, label, sources=False):
    schema = decode(SCHEMA.read_text(encoding="utf-8")); result = {}
    for number, line in enumerate(data.decode("utf-8").splitlines(), 1):
        row = decode(line)
        try:
            check_schema(row, schema, schema)
            expected = "claim-" + digest(key(row).encode("utf-8"))
            if row["recordId"] != expected: raise ValueError("Claim key/hash mismatch")
            if row["recordId"] in result: raise ValueError("Duplicate claim key")
            for evidence in row.get("evidence", []):
                if evidence["kind"] == "exact-wiki" and evidence["subjectItemId"] != row["itemId"]: raise ValueError("Evidence exact-ID mismatch")
                if sources: verify_source(row, evidence)
            if row["reviewStage"] == "root-approved":
                approved = {k: v for k, v in row.items() if k not in {"runId", "review"}}
                if row["review"]["claimSha256"].removeprefix("sha256:") != digest(canonical(approved).encode("utf-8")):
                    raise ValueError("Approved claim bytes changed")
                required_scope = {"tag-assessment": "usage-tag", "category-assessment": "primary-placement",
                                  "fact-assessment": "item-fact", "identity-link": "typed-identity"}[row["recordType"]]
                if required_scope not in row["review"]["approvalScope"]: raise ValueError("Approval does not cover this claim type")
            if row["recordType"] == "identity-link" and row["relationship"]["fromItemId"] != row["itemId"]:
                raise ValueError("Typed relationship subject/endpoint mismatch")
            if sources and row.get("sourceObservation", {}).get("localTextPath"):
                obs = row["sourceObservation"]; raw = local_source(obs["localTextPath"]).read_bytes(); raw.decode("utf-8")
                if digest(raw) != obs["rawTextRef"].removeprefix("sha256:") or row["itemId"] not in obs["exactInfoboxItemIds"]:
                    raise ValueError("Raw observation source pin/index binding mismatch")
            result[row["recordId"]] = row
        except (ValueError, KeyError) as error: raise ValueError(f"{label}:{number}: {error}") from error
    if not result: raise ValueError("Empty semantic snapshot")
    return result


def bootstrap(args):
    inputs = [args.coverage] + ([args.observations] if args.observations else []) + ([args.wiki_observations] if args.wiki_observations else [])
    outputs = [args.output.resolve(), args.manifest.resolve()]
    if len(set(outputs)) != 2 or any(path in outputs for path in [p.resolve() for p in inputs]) or any(p.exists() for p in outputs):
        raise ValueError("Output paths must be distinct, new, and separate from inputs")
    pins = {str(p): digest(p.read_bytes()) for p in [args.coverage] + ([args.observations] if args.observations else []) + ([args.wiki_observations] if args.wiki_observations else [])}
    run = "snapshot-" + digest(canonical(pins).encode("utf-8"))[:16]
    rows = []; ids = set()
    with args.coverage.open(encoding="utf-8-sig", newline="") as stream:
        for entry in csv.DictReader(stream, delimiter="\t"):
            item = int(entry["itemId"])
            if item <= 0 or item in ids: raise ValueError("Duplicate/nonpositive coverage ID")
            ids.add(item)
            common = {"formatVersion": FORMAT, "runId": run, "itemId": item, "itemName": entry["catalogName"],
                      "status": "unassessed", "reviewStage": "candidate", "predicateVersion": 1}
            rows.append(seal({**common, "recordType": "category-assessment", "category": {"namespace": "primary-category", "name": entry["itemCategory"]},
                              "predicate": "catalog.primary-placement", "baselineCatalogAssignment": "present", "catalog": {
                                  "category": entry["itemCategory"], "subcategory": entry["subcategory"], "ironmanTabKey": entry["ironmanTabKey"], "auditScope": entry["auditScope"]}}))
            tags = entry["tags"].split(",") if entry["tags"] else []
            if len(tags) != len(set(tags)): raise ValueError("Duplicate baseline tags")
            for tag in tags:
                rows.append(seal({**common, "recordType": "tag-assessment", "tag": {"namespace": "usage-tag", "name": tag, "definitionStatus": "unregistered"},
                                  "predicate": "catalog.usage-tag-membership", "baselineCatalogAssignment": "present"}))
    outside = []
    if args.observations:
        for line in args.observations.read_text(encoding="utf-8").splitlines():
            observation = decode(line); item = observation["itemId"]
            if item not in ids: outside.append(item); continue
            line = observation["exactNumericIdFieldRawLines"][0]
            field = re.match(r"\s*\|\s*(id[0-9]*)\s*=", line)[1]
            value = line.split("=", 1)[1].strip()
            no_line = observation["explicitNoBankableFieldRawLines"][0]
            bank_field = re.match(r"\s*\|\s*(bankable[0-9]*)\s*=", no_line)[1]
            rows.append(seal({"formatVersion": FORMAT, "runId": run, "recordType": "fact-assessment", "itemId": item, "itemName": observation["name"],
                              "predicateVersion": 1, "predicate": "wiki.infobox.bankable-field-observation", "status": "unassessed", "reviewStage": "candidate",
                              "fact": {"namespace": "item-fact", "name": "wiki.infobox.bankable-field.raw-value", "valueType": "string"}, "factValue": "No",
                              "state": {"scope": "exact-item-state", "qualifiers": {"interpretation": "source-field-only; prose conditions not collapsed"}},
                              "sourceObservation": {k: v for k, v in observation.items() if k in {
                                  "itemId", "name", "pageTitle", "revision", "revisionTimestamp", "sourceCorpus", "sourcePath", "sourceSha256", "sourceUrl",
                                  "boundInfoboxRawText", "exactNumericIdFieldRawLines", "explicitNoBankableFieldRawLines", "exactVariant", "ownPageLeadLiteral", "bankabilityScope", "boundIdField", "boundIdValue"}},
                              "extensions": {"candidate-advisory": {k: v for k, v in observation.items() if k.startswith(("current", "full34085", "recommended", "ignore", "eligibility", "sourceBound"))}},
                              "evidence": [{"kind": "exact-wiki", "subjectItemId": item, "sourceTitle": observation["pageTitle"], "sourceUrl": observation["sourceUrl"],
                                            "sourceRevision": observation["revision"], "sourceSha256": observation["sourceSha256"], "sourcePath": observation["sourcePath"], "quote": no_line,
                                            "exactVariant": {"itemId": item, "fields": {field: value, bank_field: "No"}, "idField": field, "idFieldLiteral": line, "infoboxRaw": observation["boundInfoboxRawText"]}}]}))
    if args.wiki_observations:
        for line in args.wiki_observations.read_text(encoding="utf-8").splitlines():
            observation = decode(line); item = observation["itemId"]
            if item not in ids: raise ValueError("Wiki observation is outside the snapshot coverage")
            raw = local_source(observation["localTextPath"]).read_bytes()
            if digest(raw) != observation["rawTextRef"].removeprefix("sha256:") or item not in observation["exactInfoboxItemIds"]:
                raise ValueError("Wiki observation source pin or collector ID binding mismatch")
            raw.decode("utf-8")
            variant = observation["exactVariant"]
            rows.append(seal({"formatVersion": FORMAT, "runId": run, "recordType": "fact-assessment", "itemId": item,
                              "predicateVersion": 1, "predicate": "wiki.infobox.variant-observation", "status": "unassessed", "reviewStage": "candidate",
                              "fact": {"namespace": "item-fact", "name": "wiki.infobox.variant-observation", "valueType": "object"},
                              "factValue": variant["fields"], "state": {"scope": "exact-item-state", "qualifiers": {
                                  "sourceTitle": observation["sourceTitle"], "suffix": variant["suffix"]}},
                              "sourceObservation": observation}))
    rows.sort(key=lambda r: (r["itemId"], r["recordType"], r["recordId"]))
    data = "".join(canonical(row) + "\n" for row in rows).encode("utf-8")
    if args.output.exists() or args.manifest.exists(): raise ValueError("Refusing to overwrite a historical snapshot")
    checked = parse_records(data, "bootstrap", sources=True)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.manifest.parent.mkdir(parents=True, exist_ok=True)
    encoded = gzip.compress(data, mtime=0) if args.output.suffix == ".gz" else data
    with args.output.open("xb") as stream: stream.write(encoded)
    manifest = {"formatVersion": "semantic-snapshot/v1", "runId": run, "sourceGitRevision": args.revision,
                "inputs": pins, "schemaSha256": digest(SCHEMA.read_bytes()), "toolSha256": digest(pathlib.Path(__file__).read_bytes()), "recordsPath": str(args.output),
                "recordsSha256": digest(encoded), "decompressedSha256": digest(data), "coverageItems": len(ids),
                "recordCounts": dict(collections.Counter(row["recordType"] for row in checked.values())),
                "outsideObservationIds": sorted(outside), "approvalScope": "No new semantic approval; catalog imports and raw observations are unassessed"}
    with args.manifest.open("x", encoding="utf-8", newline="\n") as stream: stream.write(json.dumps(manifest, indent=2) + "\n")
    print(json.dumps(manifest))


def compare(args):
    if args.output.exists() or args.output.resolve() in {args.before.resolve(), args.after.resolve()}:
        raise ValueError("Comparison output must be a new file separate from both snapshots")
    before = records(args.before); after = records(args.after); changes = []
    dimensions = {"identity": ["itemName"], "assertion": ["status", "predicate", "predicateVersion", "factValue", "factUnit", "category", "state", "qualifiers"],
                  "catalog": ["baselineCatalogAssignment", "catalog"], "evidence": ["evidence", "sourceObservation"],
                  "review": ["reviewStage", "review"], "derivation": ["derivation", "factRefs"], "definition": ["tag", "fact"], "extensions": ["extensions"]}
    for claim in sorted(before.keys() | after.keys()):
        a = before.get(claim); b = after.get(claim)
        if a is None or b is None: changed = ["record-added" if a is None else "record-removed"]
        else: changed = [name for name, fields in dimensions.items() if any(a.get(field) != b.get(field) for field in fields)]
        if changed: changes.append({"recordId": claim, "itemId": (a or b)["itemId"], "changes": changed})
    report = {"beforeRecords": len(before), "afterRecords": len(after), "changedRecords": len(changes), "changes": changes,
              "note": "Missing records are coverage differences, never refutations. Evidence changes require renewed review, not an automatic semantic conclusion."}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x", encoding="utf-8", newline="\n") as stream: stream.write(json.dumps(report, indent=2) + "\n")
    print(json.dumps({k: v for k, v in report.items() if k != "changes"}))


def verify_manifest(path, snapshot):
    manifest = decode(path.read_text(encoding="utf-8"))
    if manifest["recordsSha256"] != digest(snapshot.read_bytes()) or manifest["decompressedSha256"] != digest(load(snapshot)):
        raise ValueError("Snapshot/manifest hash mismatch")
    if manifest["schemaSha256"] != digest(SCHEMA.read_bytes()): raise ValueError("Snapshot uses different schema bytes")
    # Historical tool hashes remain provenance; the current validator may improve without changing facts.
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__); sub = parser.add_subparsers(dest="command", required=True)
    build = sub.add_parser("bootstrap"); build.add_argument("--coverage", type=pathlib.Path, required=True)
    build.add_argument("--observations", type=pathlib.Path, help="Exact bankability source-claim adapter input")
    build.add_argument("--wiki-observations", type=pathlib.Path, help="Suffix-resolved raw infobox observations; semantic interpretation remains unassessed")
    build.add_argument("--revision", required=True)
    build.add_argument("--output", type=pathlib.Path, required=True); build.add_argument("--manifest", type=pathlib.Path, required=True)
    validate = sub.add_parser("validate"); validate.add_argument("path", type=pathlib.Path); validate.add_argument("--sources", action="store_true"); validate.add_argument("--manifest", type=pathlib.Path)
    diff = sub.add_parser("compare"); diff.add_argument("before", type=pathlib.Path); diff.add_argument("after", type=pathlib.Path)
    diff.add_argument("--output", type=pathlib.Path, required=True)
    args = parser.parse_args()
    if args.command == "bootstrap": bootstrap(args)
    elif args.command == "validate":
        if args.manifest: verify_manifest(args.manifest, args.path)
        print(json.dumps({"validRecords": len(records(args.path, args.sources)), "sourceReplay": args.sources, "manifestChecked": args.manifest is not None, "semanticApprovalGranted": False}))
    else: compare(args)


if __name__ == "__main__": main()
