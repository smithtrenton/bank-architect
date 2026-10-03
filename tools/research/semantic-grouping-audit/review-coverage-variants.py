#!/usr/bin/env python3
"""Reproducible exact-ID coverage and variant collision review for the local Wiki snapshot."""
import collections, csv, json, pathlib, re

ROOT = pathlib.Path(__file__).resolve().parents[3]
CACHE = ROOT / "tmp/semantic-audit/cache"
EFFECTIVE = ROOT / "tmp/semantic-audit/effective.tsv"
OUT = ROOT / "tmp/semantic-audit/reviews/coverage-variants"
OUT.mkdir(parents=True,exist_ok=True)
CAT_FIELDS = []
RESTRICTED_NAME = re.compile(r"\b(?:league|trailblazer|deadman|dmm|lms|last man standing|bounty hunter|bh|corrupted|cr|battle royale|tutorial|minigame|blighted)\b", re.I)

def rows(value):
    return value if isinstance(value, list) else ([] if value is None else [value])

def id_value(value):
    raw = str(value)
    stripped = raw.strip()
    if re.fullmatch(r"[1-9][0-9]*", stripped):
        return int(stripped), raw != stripped
    return None, False

def identity(row):
    return (str(row.get("page_name", "")), str(row.get("page_name_sub", "")),
            tuple(sorted(str(x) for x in rows(row.get("item_id")))))

def main():
    eff = list(csv.DictReader(EFFECTIVE.open(encoding="utf-8-sig"), delimiter="\t"))
    effective_by_id = {int(r["itemId"]): r for r in eff}
    chunks = sorted(CACHE.glob("infobox_item-[0-9]*.json"))
    raw = []
    for path in chunks:
        packet = json.loads(path.read_text(encoding="utf-8"))
        raw.extend(packet["rows"])
    merged_packet = json.loads((CACHE / "infobox_item.json").read_text(encoding="utf-8"))
    merged_rows = merged_packet["rows"]
    CAT_FIELDS = sorted({key.removeprefix("Category:") for row in merged_rows for key in row if key.startswith("Category:")})
    merged_by_key = collections.defaultdict(list)
    bonus_packet = json.loads((CACHE / "infobox_bonuses.json").read_text(encoding="utf-8"))
    bonuses_by_key = collections.defaultdict(list)
    bonuses_by_page = collections.defaultdict(list)
    def norm(value):
        return " ".join(str(value or "").strip().casefold().split())
    for bonus in bonus_packet["rows"]:
        page_key = norm(bonus.get("page_name"))
        sub_key = norm(bonus.get("page_name_sub"))
        bonuses_by_key[(page_key, sub_key)].append(bonus)
        bonuses_by_page[page_key].append(bonus)
    merged_by_page_sub = collections.defaultdict(list)
    merged_by_page = collections.defaultdict(list)
    for row in merged_rows:
        merged_by_key[identity(row)].append(row)
        merged_by_page_sub[(norm(row.get("page_name")), norm(row.get("page_name_sub")))].append(row)
        merged_by_page[norm(row.get("page_name"))].append(row)

    by_id = collections.defaultdict(list)
    all_by_id = collections.defaultdict(list)
    whitespace_ids = set()
    nonnumeric = 0
    for row in raw:
        for raw_id in rows(row.get("item_id")):
            ident, had_space = id_value(raw_id)
            if ident is None:
                nonnumeric += 1
                continue
            all_by_id[ident].append(row)
            if ident in effective_by_id:
                by_id[ident].append(row)
                if had_space:
                    whitespace_ids.add(ident)

    catalog_csv = list(csv.DictReader((ROOT / "tmp/semantic-audit/catalog-semantic-audit.csv").open(encoding="utf-8-sig")))
    item_id_packet = json.loads((CACHE / "item_id.json").read_text(encoding="utf-8"))
    item_id_rows = item_id_packet["rows"]
    lookup_by_id = collections.defaultdict(list)
    raw_id_values = []
    lookup_value_types = collections.Counter()
    typed_infobox_by_id = collections.defaultdict(list)
    for row in merged_rows:
        for raw_id in rows(row.get("item_id")):
            value = str(raw_id).strip()
            match = re.fullmatch(r"([A-Za-z]+)([0-9]+)", value)
            if match:
                typed_infobox_by_id[int(match.group(2))].append({
                    "typed_id": value, "prefix": match.group(1).casefold(),
                    "page": row.get("page_name", ""), "subpage": row.get("page_name_sub", ""),
                })
    for row in item_id_rows:
        for raw_id in rows(row.get("id")):
            raw_id_text = str(raw_id)
            raw_id_values.append(raw_id_text)
            value = raw_id_text.strip()
            if re.fullmatch(r"[1-9][0-9]*", value):
                lookup_value_types["NUMERIC_POSITIVE_TRIMMED"] += 1
                if value != raw_id_text:
                    lookup_value_types["NUMERIC_WITH_SURROUNDING_WHITESPACE"] += 1
                ident = int(value)
                if ident in effective_by_id:
                    lookup_by_id[ident].append(row)
            elif value == "0" or re.fullmatch(r"-[0-9]+", value):
                lookup_value_types["NUMERIC_NONPOSITIVE"] += 1
            else:
                prefix_match = re.fullmatch(r"([A-Za-z]+)([0-9]+)", value)
                if prefix_match:
                    lookup_value_types["PREFIXED_" + prefix_match.group(1).upper()] += 1
                else:
                    lookup_value_types["OTHER_NONNUMERIC"] += 1
    joined_by_id = {int(r["item_id"]): r for r in catalog_csv}
    out_rows = []
    candidate_rows = []
    outside_matches = []
    stats = collections.Counter()
    root_mismatch = []
    category_conflicts = []
    restricted_review = []
    alternate_rows = []
    for ident, item in effective_by_id.items():
        candidates = by_id.get(ident, [])
        # Only exact duplicate payloads collapse for candidate-identity counts; raw edge count stays visible.
        unique = list({json.dumps(r, sort_keys=True, ensure_ascii=False): r for r in candidates}.values())
        defaults = [r for r in unique if r.get("default_version") is True]
        pages = sorted({str(r.get("page_name", "")) for r in unique})
        subs = sorted({str(r.get("page_name_sub", "")) for r in unique})
        facts_with_categories = [(r, next(iter(merged_by_key.get(identity(r), [])), {})) for r in unique]
        positive_categories = sorted({
            category for _, merged in facts_with_categories
            for category in CAT_FIELDS if merged.get("Category:" + category) is True
        })
        by_cat = {}
        for category in positive_categories:
            matching = [r for r, merged in facts_with_categories if merged.get("Category:" + category) is True]
            by_cat[category] = len(matching)
            if len(matching) < len(unique) and len(unique) > 1:
                category_conflicts.append({
                    "itemId": ident, "catalogName": item["name"], "category": category,
                    "positiveCandidateRows": len(matching), "candidateRows": len(unique),
                    "pages": " | ".join(sorted({str(r.get("page_name", "")) for r in matching})),
                    "subpages": " | ".join(sorted({str(r.get("page_name_sub", "")) for r in matching})),
                    "warning": "positive membership occurs on only part of exact-ID candidate rows; preserve row scope",
                })
        title_text = " ".join(str(r.get(field, "")) for r in unique for field in ("page_name", "page_name_sub", "item_name", "version_anchor"))
        name_hints = sorted(set(m.group(0).casefold() for m in RESTRICTED_NAME.finditer(title_text)))
        direct_restricted = sorted(c for c in positive_categories if c in {"Quest items", "Minigame items", "Tutorial Island", "Leagues items", "Blighted items"})
        status = "NO_EXACT_ID_FACT" if not unique else ("EXACT_ID_SINGLE" if len(unique) == 1 else "EXACT_ID_MULTIPLE")
        lookup_candidates = lookup_by_id.get(ident, [])
        interface_suffix_candidates = [x for x in typed_infobox_by_id.get(ident, []) if x["prefix"] == "interface"]
        exact_page_sub_link_rows = []
        same_page_link_rows = []
        alternate_link_details = []
        for link_row in lookup_candidates:
            link_key = (norm(link_row.get("page_name")), norm(link_row.get("page_name_sub")))
            page_sub_candidates = merged_by_page_sub.get(link_key, [])
            if page_sub_candidates:
                exact_page_sub_link_rows.append(link_row)
            if merged_by_page.get(norm(link_row.get("page_name"))):
                same_page_link_rows.append(link_row)
            alternate_link_details.append({
                "raw_id_values": [str(v) for v in rows(link_row.get("id"))],
                "page_name": link_row.get("page_name", ""),
                "page_name_sub": link_row.get("page_name_sub", ""),
                "exact_page_sub_infobox_candidate_rows": len(page_sub_candidates),
                "infobox_candidate_ids": [str(v) for candidate in page_sub_candidates for v in rows(candidate.get("item_id"))],
            })
        if status != "NO_EXACT_ID_FACT":
            alternate_evidence_class = "PRIMARY_INFOBOX_EXACT_NUMERIC_ID"
        elif lookup_candidates and interface_suffix_candidates:
            alternate_evidence_class = "ITEM_ID_LINK_PLUS_TYPED_INTERFACE_SUFFIX_CANDIDATE"
        elif lookup_candidates and exact_page_sub_link_rows:
            alternate_evidence_class = "ITEM_ID_LINK_PLUS_EXACT_PAGE_SUB_CANDIDATE"
        elif lookup_candidates:
            alternate_evidence_class = "ITEM_ID_LINK_ONLY"
        elif interface_suffix_candidates:
            alternate_evidence_class = "TYPED_INTERFACE_INFOBOX_CANDIDATE_ONLY"
        else:
            alternate_evidence_class = "NO_NUMERIC_ITEM_ID_BUCKET_LINK"
        alternate_rows.append({
            "itemId": ident, "catalogName": item["name"], "tab": item["ironmanTabKey"],
            "primaryInfoboxStatus": status, "primaryInfoboxCandidateRows": len(unique),
            "alternateIdEvidenceClass": alternate_evidence_class,
            "alternateNumericLookupRelations": len(lookup_candidates),
            "alternateLookupPages": " | ".join(sorted({str(x.get("page_name", "")) for x in lookup_candidates})),
            "alternateLookupSubpages": " | ".join(sorted({str(x.get("page_name_sub", "")) for x in lookup_candidates})),
            "exactPageSubInfoboxCandidateLinkRows": len(exact_page_sub_link_rows),
            "samePageInfoboxCandidateLinkRows": len(same_page_link_rows),
            "literalTypedInterfaceIdCandidates": json.dumps(interface_suffix_candidates, ensure_ascii=False, sort_keys=True),
            "allNumericLookupRelations": json.dumps(alternate_link_details, ensure_ascii=False, sort_keys=True),
            "reviewBoundary": "alternate numeric id alone is not a variant proof; no page-only propagation",
        })
        catalog_flags = sorted(set(x for x in str(item.get("variantFlags", "")).split(",") if x))
        restricted_catalog_flags = sorted(set(catalog_flags) & {
            "battle-royale", "last-man-standing", "bounty-hunter", "corrupted",
            "tutorial", "league", "deadman", "inactive", "broken"
        })
        quest_values = sorted({str(r.get("quest", "")) for r in unique if r.get("quest") and str(r.get("quest")).casefold() != "no"})
        if direct_restricted or name_hints or restricted_catalog_flags or quest_values:
            restricted_review.append({
                "itemId": ident, "catalogName": item["name"], "tab": item["ironmanTabKey"],
                "wikiJoinStatus": status, "wikiCandidateRows": len(unique),
                "exactWikiRestrictedCategories": " | ".join(direct_restricted),
                "exactWikiNameHints": " | ".join(name_hints),
                "catalogRestrictedVariantFlags": " | ".join(restricted_catalog_flags),
                "questAssociatedFields": " | ".join(quest_values),
                "wikiPages": " | ".join(pages), "wikiSubpages": " | ".join(subs),
                "versionAnchors": " | ".join(sorted({str(r.get("version_anchor", "")) for r in unique if r.get("version_anchor")})),
                "warning": "provenance/role review signal only; category/name/quest context does not prove current use or storage destination",
            })
        root_status = joined_by_id.get(ident, {}).get("wiki_join_status", "")
        if root_status != status:
            root_mismatch.append({"itemId": ident, "ourStatus": status, "rootStatus": root_status, "rawCandidateRows": len(candidates)})
        stats[status] += 1
        stats["raw_exact_id_edges"] += len(candidates)
        if candidates and len(candidates) != len(unique):
            stats["duplicate_payload_edges"] += len(candidates) - len(unique)
        if ident in whitespace_ids:
            stats["exact_ids_with_whitespace_id_value"] += 1
        if len(defaults) > 1:
            stats["ids_with_multiple_default_rows"] += 1
        if unique and not defaults:
            stats["matched_ids_without_default_row"] += 1
        if direct_restricted:
            stats["ids_with_direct_restricted_category"] += 1
        if name_hints:
            stats["ids_with_restricted_name_hint"] += 1
        out_rows.append({
            "itemId": ident, "catalogName": item["name"], "tab": item["ironmanTabKey"],
            "subcategory": item["subcategory"], "constantName": item["constantName"],
            "familyHint": item["variantFamilyKey"], "exporterVariantFlags": item["variantFlags"],
            "wikiJoinStatus": status, "rootCurrentJoinStatus": root_status,
            "rawExactIdEdges": len(candidates), "distinctCandidateRows": len(unique),
            "distinctPages": len(pages), "distinctSubpages": len(subs),
            "defaultCandidateRows": len(defaults), "defaultAmbiguous": len(defaults) > 1,
            "matchedWithoutDefault": bool(unique) and not defaults,
            "sourceIdHadWhitespace": ident in whitespace_ids,
            "wikiPages": " | ".join(pages), "wikiSubpages": " | ".join(subs),
            "versionAnchors": " | ".join(sorted({str(r.get("version_anchor", "")) for r in unique if r.get("version_anchor")})),
            "removalDates": " | ".join(sorted({str(r.get("removal_date", "")) for r in unique if r.get("removal_date")})),
            "questFields": " | ".join(sorted({str(r.get("quest", "")) for r in unique if r.get("quest") and str(r.get("quest")).casefold() != "no"})),
            "directRestrictedCategories": " | ".join(direct_restricted),
            "restrictedNameHints": " | ".join(name_hints),
            "positiveWikiCategories": " | ".join(positive_categories),
            "categoryPositiveRows": json.dumps(by_cat, ensure_ascii=False, sort_keys=True),
        })
        if len(unique) > 1:
            for r in unique:
                merged = next(iter(merged_by_key.get(identity(r), [])), {})
                candidate_rows.append({
                    "itemId": ident, "catalogName": item["name"], "catalogTab": item["ironmanTabKey"],
                    "pageName": r.get("page_name", ""), "pageSubname": r.get("page_name_sub", ""),
                    "itemName": r.get("item_name", ""), "rawItemIds": " | ".join(map(str, rows(r.get("item_id")))),
                    "defaultVersion": r.get("default_version", ""), "versionAnchor": r.get("version_anchor", ""),
                    "removalDate": r.get("removal_date", ""), "quest": r.get("quest", ""),
                    "restrictedCategoriesPositive": " | ".join(c for c in CAT_FIELDS if merged.get("Category:" + c) is True),
                    "examine": r.get("examine", ""),
                })

    registry_path = ROOT / "src/main/resources/com/pkoka5/ironmanbankarchitect/catalog/item-registry.tsv"
    for line in registry_path.read_text(encoding="utf-8-sig").splitlines():
        cells = line.split("\t")
        if len(cells) != 4 or not cells[0].isdigit():
            continue
        ident, name, _, constant = cells
        numeric_id = int(ident)
        if numeric_id in effective_by_id:
            continue
        status = "OMITTED_NULL_NAME" if name.strip().casefold() in {"", "null", "null item"} else "EXCLUDED_CACHE_OR_PLACEHOLDER"
        for row in all_by_id.get(numeric_id, []):
            merged = next(iter(merged_by_key.get(identity(row), [])), {})
            page_key = norm(row.get("page_name"))
            sub_key = norm(row.get("page_name_sub"))
            bonus_matches = bonuses_by_key.get((page_key, sub_key), [])
            bonus_method = "EXACT_PAGE_SUB" if bonus_matches else "NONE"
            if not bonus_matches and len(bonuses_by_page.get(page_key, [])) == 1:
                bonus_matches = bonuses_by_page[page_key]
                bonus_method = "UNIQUE_PAGE_FALLBACK"
            categories = [c for c in CAT_FIELDS if merged.get("Category:" + c) is True]
            signals = list(categories)
            if row.get("quest") and str(row.get("quest")).casefold() != "no":
                signals.append("quest_associated")
            if bonus_matches:
                signals.append("equipment_bonus_candidate")
            outside_matches.append({
                "registryStatus": status,
                "exclusionReason": "CACHE_ONLY_CONSTANT_MARKER" if status == "EXCLUDED_CACHE_OR_PLACEHOLDER" else "NULL_LIKE_REGISTRY_NAME",
                "itemId": numeric_id, "registryName": name, "constantName": constant,
                "pageName": row.get("page_name", ""), "pageSubname": row.get("page_name_sub", ""),
                "itemName": row.get("item_name", ""), "rawItemIds": " | ".join(map(str, rows(row.get("item_id")))),
                "defaultVersion": row.get("default_version", ""), "versionAnchor": row.get("version_anchor", ""),
                "removalDate": row.get("removal_date", ""), "quest": row.get("quest", ""),
                "positiveWikiCategories": " | ".join(categories), "wikiSignals": " | ".join(sorted(set(signals))),
                "bonusJoinMethod": bonus_method, "bonusCandidateRows": len(bonus_matches),
            })

    for path, data in [
        (OUT / "effective-id-coverage.csv", out_rows),
        (OUT / "alternate-id-coverage.csv", alternate_rows),
        (OUT / "multi-match-candidates.csv", candidate_rows),
        (OUT / "outside-effective-wiki-matches.csv", outside_matches),
        (OUT / "category-scope-conflicts.csv", category_conflicts),
        (OUT / "restricted-variant-review.csv", restricted_review),
        (OUT / "root-join-mismatches.csv", root_mismatch),
    ]:
        if data:
            with path.open("w", encoding="utf-8-sig", newline="") as f:
                writer = csv.DictWriter(f, fieldnames=list(data[0].keys()))
                writer.writeheader()
                writer.writerows(data)

    strict_covered = {ident for ident, cand in by_id.items() if cand and all(id_value(v)[0] is not None and str(v) == str(id_value(v)[0]) for r in cand for v in rows(r.get("item_id")) if id_value(v)[0] == ident)}
    # Calculate parser-level strict coverage directly; other item IDs on a multi-ID row do not affect it.
    strict_ids = set()
    for row in raw:
        for raw_id in rows(row.get("item_id")):
            ident, _ = id_value(raw_id)
            if ident in effective_by_id and str(raw_id) == str(ident):
                strict_ids.add(ident)
    raw_keys = {identity(r) for r in raw}
    merged_keys = {identity(r) for r in merged_rows}
    summary = {
        "effective_ids": len(eff), "raw_wiki_item_rows": len(raw), "merged_wiki_item_rows": len(merged_rows),
        "raw_exact_effective_ids_trim_aware": len(by_id), "raw_exact_effective_edges": sum(map(len, by_id.values())),
        "trim_aware_unmatched_effective_ids": len(eff) - len(by_id),
        "strict_untrimmed_parser_effective_ids": len(strict_ids),
        "trimmed_id_values_for_effective_ids": sorted(whitespace_ids),
        "ids_with_multiple_candidate_rows": sum(1 for x in by_id.values() if len({json.dumps(r,sort_keys=True,ensure_ascii=False) for r in x}) > 1),
        "ids_with_multiple_default_rows": stats["ids_with_multiple_default_rows"],
        "matched_ids_without_default_row": stats["matched_ids_without_default_row"],
        "direct_restricted_category_id_counts": dict(collections.Counter(c for r in out_rows for c in r["directRestrictedCategories"].split(" | ") if c)),
        "restricted_name_hint_ids": stats["ids_with_restricted_name_hint"],
        "non_numeric_wiki_id_values": nonnumeric,
        "outside_effective_exact_match_registry_ids_by_status": dict(collections.Counter(
            r["registryStatus"] for r in {x["itemId"]: x for x in outside_matches}.values()
        )),
        "outside_effective_exact_match_registry_ids": len({x["itemId"] for x in outside_matches}),
        "raw_vs_merged_candidate_identity_keys_missing_from_merged": len(raw_keys - merged_keys),
        "raw_vs_merged_candidate_identity_keys_added_in_merged": len(merged_keys - raw_keys),
        "restricted_variant_review_rows": len(restricted_review),
        "restricted_catalog_flag_id_counts": dict(collections.Counter(flag for r in restricted_review for flag in r["catalogRestrictedVariantFlags"].split(" | ") if flag)),
        "exact_quest_associated_id_count": sum(1 for r in out_rows if r["questFields"]),
        "root_join_status_mismatches": len(root_mismatch),
        "category_scope_conflict_rows": len(category_conflicts),
        "root_current_join_status_counts": dict(collections.Counter(r.get("wiki_join_status","") for r in catalog_csv)),
        "alternate_id_bucket_rows": len(item_id_rows),
        "alternate_id_bucket_raw_values": len(raw_id_values),
        "alternate_id_bucket_raw_value_types": dict(lookup_value_types),
        "alternate_id_bucket_positive_numeric_effective_ids": len(lookup_by_id),
        "alternate_id_bucket_positive_numeric_effective_relations": sum(len(v) for v in lookup_by_id.values()),
        "alternate_id_bucket_new_effective_ids_over_primary_infobox": sum(1 for r in alternate_rows if r["primaryInfoboxStatus"] == "NO_EXACT_ID_FACT" and r["alternateNumericLookupRelations"] > 0),
        "alternate_id_bucket_new_ids_with_literal_interface_suffix_candidate": sum(1 for r in alternate_rows if r["primaryInfoboxStatus"] == "NO_EXACT_ID_FACT" and r["alternateNumericLookupRelations"] > 0 and r["alternateIdEvidenceClass"] == "ITEM_ID_LINK_PLUS_TYPED_INTERFACE_SUFFIX_CANDIDATE"),
        "alternate_id_bucket_new_ids_id_link_only": sum(1 for r in alternate_rows if r["alternateIdEvidenceClass"] == "ITEM_ID_LINK_ONLY"),
        "alternate_id_bucket_new_ids_with_exact_page_sub_candidate": sum(1 for r in alternate_rows if r["primaryInfoboxStatus"] == "NO_EXACT_ID_FACT" and r["exactPageSubInfoboxCandidateLinkRows"] > 0),
        "trim_aware_join_status_counts": dict(stats),
        "limitations": [
            "Exact-ID evidence is coverage only and does not establish complete mechanics.",
            "Category booleans are positive page-scoped evidence; false and missing are not negative facts.",
            "Name hints are review signals only; they do not prove restricted status.",
            "Default-version counts are reported as source metadata, not an identity filter."
        ]
    }
    (OUT / "coverage-variant-summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))

if __name__ == "__main__":
    main()
