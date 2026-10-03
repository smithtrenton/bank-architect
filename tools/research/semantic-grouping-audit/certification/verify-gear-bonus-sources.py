#!/usr/bin/env python3
"""Independently compare gear-v2 exact-ID bonus rows with pinned Wiki templates."""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from collections import Counter, defaultdict
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, Iterable


ROOT = Path(__file__).resolve().parents[4]
DEFAULT_DECISIONS = ROOT / "tmp/category-certification/reviews/gear-v2/decisions.jsonl"
DEFAULT_JOINED = ROOT / "tmp/semantic-audit/joined.jsonl"
DEFAULT_ARTICLE_INDEX = ROOT / "tmp/category-certification/wiki-articles/article-index.json"
DEFAULT_OUTPUT = ROOT / "tmp/category-certification/reviews/gear-v2/bonus-source-proof.json"

STAT_FIELDS = {
    "stab_attack_bonus": "astab",
    "slash_attack_bonus": "aslash",
    "crush_attack_bonus": "acrush",
    "magic_attack_bonus": "amagic",
    "range_attack_bonus": "arange",
    "stab_defence_bonus": "dstab",
    "slash_defence_bonus": "dslash",
    "crush_defence_bonus": "dcrush",
    "magic_defence_bonus": "dmagic",
    "range_defence_bonus": "drange",
    "strength_bonus": "str",
    "ranged_strength_bonus": "rstr",
    "magic_damage_bonus": "mdmg",
    "prayer_bonus": "prayer",
}
SLOT_FIELD = "equipment_slot"
ACTIVE_OPTIONS = {"wear", "wield", "equip"}
DECISION_TARGET_COUNTS = {"certify": 2184, "slot_revise": 37}


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def strict_id(value: Any) -> int | None:
    text = str(value).strip()
    return int(text) if re.fullmatch(r"[0-9]+", text) else None


def split_top_level(text: str, delimiter: str) -> list[str]:
    parts: list[str] = []
    start = 0
    i = 0
    brace_depth = 0
    link_depth = 0
    while i < len(text):
        if text.startswith("{{", i):
            brace_depth += 1
            i += 2
            continue
        if text.startswith("}}", i) and brace_depth:
            brace_depth -= 1
            i += 2
            continue
        if text.startswith("[[", i):
            link_depth += 1
            i += 2
            continue
        if text.startswith("]]", i) and link_depth:
            link_depth -= 1
            i += 2
            continue
        if text[i] == delimiter and not brace_depth and not link_depth:
            parts.append(text[start:i])
            start = i + 1
        i += 1
    parts.append(text[start:])
    return parts


def template_end(text: str, start: int) -> int | None:
    depth = 1
    i = start + 2
    while i < len(text) - 1:
        if text.startswith("<!--", i):
            end_comment = text.find("-->", i + 4)
            if end_comment < 0:
                return None
            i = end_comment + 3
        elif text.startswith("{{{", i):
            parameter_depth = 1
            i += 3
            while i < len(text) - 2 and parameter_depth:
                if text.startswith("{{{", i):
                    parameter_depth += 1
                    i += 3
                elif text.startswith("}}}", i):
                    parameter_depth -= 1
                    i += 3
                else:
                    i += 1
        elif text.startswith("{{", i):
            depth += 1
            i += 2
        elif text.startswith("}}", i):
            depth -= 1
            i += 2
            if depth == 0:
                return i
        else:
            i += 1
    return None


def iter_templates(text: str) -> Iterable[str]:
    i = 0
    while i < len(text) - 1:
        if text.startswith("<!--", i):
            end_comment = text.find("-->", i + 4)
            if end_comment < 0:
                return
            i = end_comment + 3
            continue
        if text.startswith("{{{", i):
            # A triple-brace parameter is not a template invocation.
            end = text.find("}}}", i + 3)
            if end < 0:
                return
            i = end + 3
            continue
        if text.startswith("{{", i):
            end = template_end(text, i)
            if end is None:
                return
            yield text[i:end]
            # Continue inside the outer template so nested Infobox Item blocks
            # (for league/mode-specific variants) remain visible to the caller.
            i += 2
            continue
        i += 1


def parse_template(raw: str) -> tuple[str, dict[str, str], list[str]]:
    body = raw[2:-2]
    parts = split_top_level(body, "|")
    name = parts[0].strip().replace("_", " ").casefold()
    fields: dict[str, str] = {}
    duplicates: list[str] = []
    for part in parts[1:]:
        assignment = split_top_level(part, "=")
        if len(assignment) < 2:
            continue
        key = assignment[0].strip().replace("_", " ").casefold()
        value = "=".join(assignment[1:]).strip()
        if key in fields:
            duplicates.append(key)
        fields[key] = value
    return name, fields, duplicates


def normalize_label(value: Any) -> str:
    text = str(value or "").strip()
    text = re.sub(r"\s+", " ", text)
    return text.casefold()


def source_number(value: Any) -> Decimal | None:
    text = str(value).strip().replace(",", "").replace("−", "-")
    text = re.sub(r"<!--.*?-->", "", text, flags=re.S)
    text = re.sub(r"\s*<ref\b[^>]*>.*?</ref>\s*", "", text, flags=re.I | re.S)
    try:
        return Decimal(text)
    except (InvalidOperation, ValueError):
        return None


def scalar_id(value: Any) -> int | None:
    if isinstance(value, list):
        values = {strict_id(v) for v in value}
        values.discard(None)
        return next(iter(values)) if len(values) == 1 else None
    return strict_id(value)


def suffix_param(fields: dict[str, str], base: str, suffix: str) -> tuple[str, str] | None:
    exact = f"{base}{suffix}"
    if exact in fields:
        return exact, fields[exact]
    if base in fields:
        return base, fields[base]
    return None


def item_variants(fields: dict[str, str]) -> list[dict[str, Any]]:
    variants: list[dict[str, Any]] = []
    for key, raw_id in fields.items():
        match = re.fullmatch(r"id([0-9]*)", key)
        if not match:
            continue
        item_id = strict_id(raw_id)
        if item_id is None:
            continue
        suffix = match.group(1)
        version = suffix_param(fields, "version", suffix)
        name = suffix_param(fields, "name", suffix)
        bucketname = suffix_param(fields, "bucketname", suffix)
        variants.append({
            "itemId": item_id,
            "idParam": key,
            "suffix": suffix,
            "version": version[1] if version else None,
            "versionParam": version[0] if version else None,
            "name": name[1] if name else None,
            "nameParam": name[0] if name else None,
            "bucketname": bucketname[1] if bucketname else None,
            "bucketnameParam": bucketname[0] if bucketname else None,
            "fields": fields,
        })
    return variants


def bonus_groups(fields: dict[str, str]) -> dict[str, dict[str, Any]]:
    suffixes = {""}
    for key in fields:
        match = re.fullmatch(r"version([0-9]*)", key)
        if match:
            suffixes.add(match.group(1))
        for base in (*STAT_FIELDS.values(), "slot"):
            match = re.fullmatch(re.escape(base) + r"([0-9]+)", key)
            if match:
                suffixes.add(match.group(1))
    groups: dict[str, dict[str, Any]] = {}
    for suffix in suffixes:
        version = suffix_param(fields, "version", suffix)
        groups[suffix] = {
            "suffix": suffix,
            "version": version[1] if version else None,
            "versionParam": version[0] if version else None,
        }
    return groups


def option_tokens(value: str) -> list[str]:
    value = re.sub(r"\[\[([^\]|]+)(?:\|([^\]]+))?\]\]", lambda m: m.group(2) or m.group(1), value)
    value = re.sub(r"<[^>]+>", " ", value)
    return [re.sub(r"\s+", " ", token).strip().casefold() for token in value.split(",") if token.strip()]


def issue(result: dict[str, Any], severity: str, code: str, detail: str) -> None:
    result["issues"].append({"severity": severity, "code": code, "detail": detail})


def check_target(decision: dict[str, Any], joined: dict[str, Any] | None,
                 joined_line_hash: str | None, joined_global_hash: str,
                 article_index: dict[str, dict[str, Any]], article_index_hash: str,
                 article_cache: dict[str, tuple[str, list[tuple[str, dict[str, str], list[str]]]]]) -> dict[str, Any]:
    item_id = decision["itemId"]
    row: dict[str, Any] = {
        "itemId": item_id,
        "decision": decision.get("decision"),
        "reviewScope": "slot-revision" if decision.get("decision") == "revise" else "certificate",
        "issues": [],
        "fieldComparisons": {},
        "source": {"joinedSha256": joined_global_hash, "joinedLineSha256": joined_line_hash,
                   "articleIndexSha256": article_index_hash},
    }
    if joined is None:
        issue(row, "contradiction", "joined_exact_id_missing", "No joined source row exists for this exact numeric item ID.")
        return row
    if joined.get("item_id") != item_id:
        issue(row, "contradiction", "joined_id_mismatch", f"Joined row item_id is {joined.get('item_id')!r}.")
    local_citations = [e for e in decision.get("evidence", [])
                       if e.get("kind") == "local_source" and e.get("sourcePath", "").replace("\\", "/").endswith("semantic-audit/joined.jsonl")]
    if not any(e.get("sourceHash", "").removeprefix("sha256:").casefold() == joined_global_hash.casefold()
               and e.get("sourceLineHash", "").removeprefix("sha256:").casefold() == (joined_line_hash or "").casefold()
               for e in local_citations):
        issue(row, "contradiction", "joined_citation_not_pinned", "Decision does not pin the exact current joined file and row hash.")

    matches = joined.get("bonus_matches", [])
    selected = [m for m in matches if m.get("method") == "EXACT_PAGE_SUB" and m.get("status") == "UNIQUE"]
    if len(selected) != 1 or len(selected[0].get("records", [])) != 1:
        issue(row, "ambiguity", "joined_bonus_match_not_unique", f"Found {len(selected)} unique EXACT_PAGE_SUB match records.")
        joined_match = selected[0] if len(selected) == 1 else None
        joined_record = joined_match.get("records", [None])[0] if joined_match else None
    else:
        joined_match = selected[0]
        joined_record = joined_match["records"][0]

    title = joined_match.get("item_page") if joined_match else None
    page_sub = joined_match.get("item_page_sub") if joined_match else None
    article = article_index.get(title) if title else None
    if not article:
        issue(row, "ambiguity", "pinned_article_missing", f"No article-index entry for exact joined page {title!r}.")
        row["joined"] = {"page": title, "pageSub": page_sub, "record": joined_record}
        return row
    article_path = Path(article.get("path", ""))
    if not article_path.is_file():
        issue(row, "contradiction", "article_text_missing", f"Pinned text file does not exist: {article_path}.")
        return row
    article_bytes = article_path.read_bytes()
    actual_article_hash = sha256_bytes(article_bytes)
    article_hash_ok = actual_article_hash.casefold() == str(article.get("sha256", "")).casefold()
    if not article_hash_ok:
        issue(row, "contradiction", "article_hash_mismatch", "Pinned article bytes do not match article-index SHA-256.")
    article_text = article_bytes.decode("utf-8", errors="replace")
    if title not in article_cache:
        article_cache[title] = (article_text, [parse_template(raw) for raw in iter_templates(article_text)])
    cached_text, templates = article_cache[title]
    exact_index_ids = {strict_id(value) for value in article.get("exactInfoboxItemIds", [])}
    if item_id not in exact_index_ids:
        issue(row, "contradiction", "article_index_exact_id_missing", "The pinned article index does not list this item ID in exactInfoboxItemIds.")

    item_templates = [fields for name, fields, _ in templates if name == "infobox item"]
    variants = [variant for fields in item_templates for variant in item_variants(fields) if variant["itemId"] == item_id]
    if len(variants) != 1:
        issue(row, "ambiguity", "exact_item_variant_not_unique", f"Raw pinned article has {len(variants)} Infobox Item variants for ID {item_id}.")
        exact_variant = variants[0] if variants else None
    else:
        exact_variant = variants[0]

    indexed_variant = article.get("variants", {}).get(str(item_id), {}).get("params", {})
    if not indexed_variant:
        issue(row, "ambiguity", "indexed_variant_missing", "The pinned index has no structured variant parameters for the exact ID.")
    if exact_variant:
        item_fields = exact_variant["fields"]
        item_suffix = exact_variant["suffix"]
        item_label = exact_variant["version"]
        item_name = exact_variant["name"]
        row["itemVariant"] = {
            "idParam": exact_variant["idParam"], "suffix": item_suffix,
            "version": item_label, "versionParam": exact_variant["versionParam"],
            "name": item_name, "nameParam": exact_variant["nameParam"],
            "bucketname": exact_variant["bucketname"], "bucketnameParam": exact_variant["bucketnameParam"],
        }
        for key in (exact_variant["idParam"], exact_variant["versionParam"], exact_variant["nameParam"],
                    exact_variant["bucketnameParam"]):
            if key and key in item_fields and key in indexed_variant and item_fields[key] != indexed_variant[key]:
                issue(row, "contradiction", "indexed_item_variant_differs", f"Article index parameter {key} differs from the raw exact article.")
        equipable = suffix_param(item_fields, "equipable", item_suffix)
        options = suffix_param(item_fields, "options", item_suffix)
        active = option_tokens(options[1]) if options else []
        active_evidence = [value for value in active if value in ACTIVE_OPTIONS]
        row["activeEquipmentOptions"] = {
            "equipable": equipable[1] if equipable else None,
            "equipableParam": equipable[0] if equipable else None,
            "options": options[1] if options else None,
            "optionsParam": options[0] if options else None,
            "tokens": active,
            "explicitWearWieldEquip": active_evidence,
        }
        equipable_value = normalize_label(equipable[1]) if equipable else ""
        if equipable_value in {"no", "false", "0"}:
            issue(row, "contradiction", "not_equipable", f"Exact variant says {equipable[0]}={equipable[1]!r}.")
        elif not equipable:
            issue(row, "ambiguity", "equipable_parameter_missing", "Exact variant has no equipable parameter.")
        if options and not active_evidence:
            issue(row, "contradiction", "no_active_equipment_option", f"Exact variant options {options[0]}={options[1]!r} contain no Wear, Wield, or Equip action.")
        elif not options:
            issue(row, "ambiguity", "options_parameter_missing", "Exact variant has no explicit options parameter; bonus values cannot establish an active equipment action.")
        if active_evidence and equipable_value in {"yes", "true", "1"}:
            row["activeEquipmentOptions"]["status"] = "explicit_active_equipment_action"
        elif active_evidence:
            issue(row, "ambiguity", "equipable_not_explicitly_yes", "A Wear/Wield/Equip option exists, but equipable is not explicitly Yes.")

    joined_label = str(page_sub).split("#", 1)[1].strip() if page_sub and "#" in str(page_sub) else None
    row["joined"] = {
        "page": title,
        "pageSub": page_sub,
        "subLabel": joined_label,
        "method": joined_match.get("method") if joined_match else None,
        "status": joined_match.get("status") if joined_match else None,
        "record": joined_record,
    }
    row["article"] = {"title": title, "revision": article.get("revid"), "sha256": actual_article_hash,
                      "expectedSha256": article.get("sha256"), "sourceUrl": article.get("sourceUrl"),
                      "path": str(article_path)}
    exact_citations = [e for e in decision.get("evidence", [])
                       if e.get("kind") in {"exact_wiki", "direct_variant"} and strict_id(e.get("itemId")) == item_id]
    matching_citation = any(
        e.get("sourceTitle") == title and e.get("sourceRevision") == article.get("revid") and
        e.get("source", "") == article.get("sourceUrl") and
        e.get("sourceHash", "").removeprefix("sha256:").casefold() == actual_article_hash.casefold()
        for e in exact_citations)
    if not matching_citation:
        issue(row, "contradiction", "decision_article_citation_not_pinned",
              "No exact-ID Wiki citation in the decision matches the bonus article's pinned title, revision, URL, and bytes hash.")

    if exact_variant:
        item_label = exact_variant.get("version")
        joined_identity_label = exact_variant.get("bucketname") or item_label
        if joined_label and joined_identity_label and normalize_label(joined_label) != normalize_label(joined_identity_label):
            issue(row, "contradiction", "joined_label_disagrees_with_exact_item_variant",
                  f"Joined subpage label {joined_label!r} differs from exact item label {joined_identity_label!r}.")
        elif joined_label and not joined_identity_label:
            issue(row, "ambiguity", "item_version_label_missing", f"Joined subpage is labeled {joined_label!r}, but exact Item variant has no bucketname or version label.")
        elif joined_identity_label and not joined_label:
            issue(row, "ambiguity", "joined_subpage_label_missing", f"Exact item label {joined_identity_label!r} is not present in joined page_name_sub.")

    bonus_templates = [(fields, duplicates) for name, fields, duplicates in templates if name == "infobox bonuses"]
    if not bonus_templates:
        issue(row, "ambiguity", "infobox_bonuses_missing", "Pinned exact article has no Infobox Bonuses template.")
        return finalize(row)
    if any(duplicates for _, duplicates in bonus_templates):
        duplicate_fields = sorted({key for _, duplicates in bonus_templates for key in duplicates})
        issue(row, "ambiguity", "duplicate_bonus_parameters", f"Bonus template repeats parameter(s): {duplicate_fields}.")

    label_candidates = {normalize_label(x) for x in (joined_label, exact_variant.get("version") if exact_variant else None) if x}
    profiles: list[tuple[int, dict[str, str], str, str | None]] = []
    for template_index, (bonus_fields, _) in enumerate(bonus_templates):
        groups = bonus_groups(bonus_fields)
        labeled = [(suffix, group) for suffix, group in groups.items() if group.get("version")]
        if labeled:
            for suffix, group in labeled:
                if normalize_label(group["version"]) in label_candidates:
                    profiles.append((template_index, bonus_fields, suffix, group["version"]))
        elif len(bonus_templates) == 1 and len(groups) == 1:
            suffix, group = next(iter(groups.items()))
            profiles.append((template_index, bonus_fields, suffix, group.get("version")))
        elif len(bonus_templates) == 1 and exact_variant and not exact_variant.get("version"):
            numeric_suffixes = {suffix for suffix in groups if suffix}
            if len(numeric_suffixes) == 1 and numeric_suffixes == {exact_variant["suffix"]}:
                suffix = exact_variant["suffix"]
                profiles.append((template_index, bonus_fields, suffix, None))
    if len(profiles) != 1:
        issue(row, "ambiguity", "bonus_version_profile_not_unique",
              f"Found {len(profiles)} bonus-template profiles matching exact item label {sorted(label_candidates)}.")
        if len(profiles) == 0:
            return finalize(row)
    template_index, bonus_fields, bonus_suffix, bonus_version = profiles[0]
    row["bonusVariant"] = {"templateIndex": template_index, "suffix": bonus_suffix,
                           "version": bonus_version,
                           "versionParam": f"version{bonus_suffix}" if f"version{bonus_suffix}" in bonus_fields else None}
    if exact_variant and exact_variant.get("suffix") and bonus_suffix and exact_variant["suffix"] != bonus_suffix:
        row["bonusVariant"]["suffixAlignment"] = "different suffixes, unique explicit version labels matched"

    if not joined_record:
        issue(row, "ambiguity", "joined_bonus_record_missing", "Unique joined page match contains no bonus record.")
        return finalize(row)
    field_map = {SLOT_FIELD: "slot", **STAT_FIELDS}
    for joined_field, bonus_base in field_map.items():
        selected_field = suffix_param(bonus_fields, bonus_base, bonus_suffix)
        joined_value = joined_record.get(joined_field)
        comparison = {"bonusField": selected_field[0] if selected_field else None,
                     "sourceValue": selected_field[1] if selected_field else None,
                     "joinedValue": joined_value}
        row["fieldComparisons"][joined_field] = comparison
        if selected_field is None:
            issue(row, "ambiguity", "bonus_field_missing", f"Infobox Bonuses lacks {bonus_base!r} for the selected exact variant.")
            continue
        if joined_value is None:
            issue(row, "ambiguity", "joined_field_missing", f"Joined EXACT_PAGE_SUB row lacks {joined_field!r}.")
            continue
        if joined_field == SLOT_FIELD:
            source_slot = normalize_label(selected_field[1])
            joined_slot = normalize_label(joined_value)
            comparison["matches"] = source_slot == joined_slot
            if source_slot != joined_slot:
                issue(row, "contradiction", "equipment_slot_mismatch",
                      f"Exact article {selected_field[0]}={selected_field[1]!r}; joined slot is {joined_value!r}.")
        else:
            source_value = source_number(selected_field[1])
            joined_number = source_number(joined_value)
            comparison["sourceNumeric"] = str(source_value) if source_value is not None else None
            comparison["joinedNumeric"] = str(joined_number) if joined_number is not None else None
            comparison["matches"] = source_value is not None and joined_number is not None and source_value == joined_number
            if source_value is None or joined_number is None:
                issue(row, "ambiguity", "bonus_value_not_numeric", f"Cannot compare {selected_field[0]}={selected_field[1]!r} with joined {joined_field}={joined_value!r}.")
            elif source_value != joined_number:
                issue(row, "contradiction", "bonus_stat_mismatch",
                      f"Exact article {selected_field[0]}={selected_field[1]!r}; joined {joined_field}={joined_value!r}.")
    return finalize(row)


def finalize(row: dict[str, Any]) -> dict[str, Any]:
    severities = {entry["severity"] for entry in row["issues"]}
    row["status"] = "contradiction" if "contradiction" in severities else "ambiguous" if "ambiguity" in severities else "consistent"
    return row


def run(decisions_path: Path, joined_path: Path, article_index_path: Path, output_path: Path,
        expect_target_counts: bool = True) -> dict[str, Any]:
    joined_global_hash = sha256_file(joined_path)
    article_index_hash = sha256_file(article_index_path)
    article_index = json.loads(article_index_path.read_text(encoding="utf-8"))
    joined_by_id: dict[int, dict[str, Any]] = {}
    joined_line_hashes: dict[int, str] = {}
    with joined_path.open(encoding="utf-8-sig") as stream:
        for line in stream:
            raw = line.rstrip("\r\n")
            if not raw:
                continue
            entry = json.loads(raw)
            item_id = strict_id(entry.get("item_id"))
            if item_id is None:
                continue
            if item_id in joined_by_id:
                raise ValueError(f"Duplicate exact item_id {item_id} in {joined_path}")
            joined_by_id[item_id] = entry
            joined_line_hashes[item_id] = sha256_bytes(raw.encode("utf-8"))

    decisions = [json.loads(line) for line in decisions_path.read_text(encoding="utf-8-sig").splitlines() if line.strip()]
    certify = [d for d in decisions if d.get("decision") == "certify"]
    slot_revisions = [d for d in decisions if d.get("decision") == "revise" and
                      "slot" in (str(d.get("rationale", "")) + " " + str(d.get("semanticPredicate", ""))).casefold()]
    counts = {"certify": len(certify), "slot_revise": len(slot_revisions)}
    if expect_target_counts and counts != DECISION_TARGET_COUNTS:
        raise ValueError(f"gear-v2 target set changed: expected {DECISION_TARGET_COUNTS}, found {counts}; use --allow-count-change only after review")
    targets = sorted(certify + slot_revisions, key=lambda d: d["itemId"])
    article_cache: dict[str, tuple[str, list[tuple[str, dict[str, str], list[str]]]]] = {}
    rows = [check_target(d, joined_by_id.get(d["itemId"]), joined_line_hashes.get(d["itemId"]),
                         joined_global_hash, article_index, article_index_hash, article_cache)
            for d in targets]
    status_counts = Counter(row["status"] for row in rows)
    issue_counts = Counter((entry["severity"], entry["code"])
                           for row in rows for entry in row["issues"])
    report = {
        "scope": "gear-v2 certificates plus 37 slot revisions",
        "inputs": {
            "decisionPath": str(decisions_path),
            "decisionSha256": sha256_file(decisions_path),
            "joinedPath": str(joined_path),
            "joinedSha256": joined_global_hash,
            "articleIndexPath": str(article_index_path),
            "articleIndexSha256": article_index_hash,
        },
        "targetDecisionCounts": counts,
        "targetCount": len(rows),
        "statusCounts": dict(sorted(status_counts.items())),
        "issueCounts": [{"severity": severity, "code": code, "count": count}
                        for (severity, code), count in sorted(issue_counts.items())],
        "contradictions": [row for row in rows if row["status"] == "contradiction"],
        "ambiguities": [row for row in rows if row["status"] == "ambiguous"],
        "consistent": [row for row in rows if row["status"] == "consistent"],
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"Audited {len(rows)} gear decisions: {dict(sorted(status_counts.items()))}")
    print(f"Wrote pinned bonus-source contradictions and ambiguities to {output_path}")
    for entry in report["issueCounts"]:
        print(f"{entry['severity']} {entry['code']}: {entry['count']}")
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--decisions", type=Path, default=DEFAULT_DECISIONS)
    parser.add_argument("--joined", type=Path, default=DEFAULT_JOINED)
    parser.add_argument("--article-index", type=Path, default=DEFAULT_ARTICLE_INDEX)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--allow-count-change", action="store_true",
                        help="allow the explicitly selected gear-v2 target counts to differ from 2184 + 37")
    args = parser.parse_args()
    run(args.decisions, args.joined, args.article_index, args.output,
        expect_target_counts=not args.allow_count_change)


if __name__ == "__main__":
    main()
