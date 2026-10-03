#!/usr/bin/env python3
"""Reproduce the pinned-source, exact-ID review of the October 2 missing-item cohort."""
import argparse
import collections
import csv
import hashlib
import html
import json
import pathlib
import re

import audit

POLICY = pathlib.Path(__file__).parent / "policies/missing-items-2026-10-02.json"


def item_boxes(text):
    """Balanced template extraction; NPC IDs and nested templates never become item IDs."""
    text = re.sub(r"<!--.*?-->", "", text, flags=re.S)
    for match in re.finditer(r"\{\{Infobox Item(?=\s|\|)", text, re.I):
        pos = match.start()
        depth = 0
        while pos < len(text):
            if text[pos:pos+2] == "{{":
                depth += 1
                pos += 2
            elif text[pos:pos+2] == "}}":
                depth -= 1
                pos += 2
                if depth == 0:
                    break
            else:
                pos += 1
        if depth:
            raise ValueError("Unbalanced item infobox")
        params = dict(re.findall(r"^\|\s*([^=\n]+?)\s*=\s*(.*)$", text[match.start():pos], re.M))
        # The outer Multi Infobox labels apply only to the corresponding item template.
        labels = re.findall(r"^\|text[0-9]+\s*=\s*(.*)$", text[:match.start()], re.M)
        yield params, labels[-1] if labels else ""


def variants(text):
    result = {}
    for params, label in item_boxes(text):
        for field, raw in params.items():
            if not re.fullmatch(r"id[0-9]*", field):
                continue
            suffix = field[2:]
            for token in raw.split(","):
                token = token.strip()
                if not re.fullmatch(r"[1-9][0-9]*", token):
                    continue
                ident = int(token)
                if ident in result:
                    raise ValueError("Ambiguous article item ID " + str(ident))
                result[ident] = dict(params=params, label=label, suffix=suffix,
                                    variant=params.get("version" + suffix, ""),
                                    name=params.get("name" + suffix, params.get("name", "")))
    return result


def fetch(policy, output):
    packets = []
    sources = policy["sources"] + policy.get("context_sources", [])
    for offset in range(0, len(sources), 40):
        revisions = [s["revid"] for s in sources[offset:offset+40]]
        path = output / "pinned-articles" / (str(offset) + ".json")
        if path.exists():
            packet = json.loads(path.read_text(encoding="utf-8"))
            if packet["revids"] != revisions:
                raise ValueError("Pinned acquisition differs; use a new output directory")
        else:
            data, url = audit.request(dict(action="query", prop="revisions", rvprop="ids|timestamp|content",
                                           rvslots="main", revids="|".join(map(str, revisions))))
            packet = dict(retrieved_at=audit.utc(), source_url=url, revids=revisions, data=data)
            audit.save(path, packet)
        packets.append(packet)
    index = []
    for packet in packets:
        for page in packet["data"]["query"]["pages"]:
            for revision in page.get("revisions", []):
                path = output / "article-text" / (str(revision["revid"]) + ".txt")
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(revision["slots"]["main"]["content"], encoding="utf-8")
                index.append(dict(title=page["title"], revid=revision["revid"], path=str(path)))
    if {r["revid"] for r in index} != {s["revid"] for s in sources}:
        raise ValueError("Pinned acquisition does not cover all source revisions")
    audit.save(output / "article-index.json", index)


def write_csv(path, rows):
    with path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows({k: json.dumps(v, ensure_ascii=False) if isinstance(v, (dict, list)) else v
                         for k, v in row.items()} for row in rows)


def build(policy, output, coverage_path=None):
    coverage = {}
    if coverage_path is not None:
        with coverage_path.open(encoding="utf-8-sig", newline="") as stream:
            coverage = {int(r["itemId"]): r for r in csv.DictReader(stream, delimiter="\t")}
    index = {r["revid"]: r for r in json.loads((output / "article-index.json").read_text(encoding="utf-8"))}
    if policy.get("schema") != 1:
        raise ValueError("Unexpected review policy schema")
    for context in policy.get("context_sources", []):
        if context["revid"] not in index:
            raise ValueError("Missing pinned context article; run with --fetch")
    declared = [i for source in policy["sources"] for i in source["ids"]]
    if len(declared) != 356 or len(set(declared)) != 356:
        raise ValueError("Reviewed policy must partition the original 356 IDs")
    rows = []
    supplement = []
    cosmetic = []
    article_hashes = {}
    for source in policy["sources"]:
        article = index[source["revid"]]
        path = pathlib.Path(article["path"])
        text = path.read_text(encoding="utf-8")
        article_hashes[str(source["revid"])] = hashlib.sha256(path.read_bytes()).hexdigest()
        by_id = variants(text)
        if set(by_id) != set(source["ids"]):
            raise ValueError("Article/policy exact-ID pool differs: " + source["title"])
        if source["action"] == "EXCLUDE_CACHE_EVENT" and "{{Cache}}" not in text:
            raise ValueError("Cache exclusion lacks its source marker: " + source["title"])
        for ident in source["ids"]:
            fact = by_id[ident]
            params = fact["params"]
            if source["action"] == "EXCLUDE_UNBANKABLE" and params.get("bankable", "").lower() != "no":
                raise ValueError("Unbankable exclusion lacks an explicit flag: " + str(ident))
            if source["action"] == "INCLUDE" and params.get("bankable", "").lower() == "no":
                raise ValueError("Policy includes an explicitly unbankable item: " + str(ident))
            tags = list(source["tags"])
            note = source["reason"]
            if ident in (34582, 34583):
                tags = ["quest-associated", "quest-decoy"]
                note += " This exact variant is a bad shell, not a useful musical puzzle shell."
            row = dict(itemId=ident, name=fact["name"], sourcePage=source["title"], variant=fact["variant"],
                       action=source["action"], availability="NO_CURRENT_SOURCE" if fact["label"] == "Unobtainable" else "NOT_MARKED_UNOBTAINABLE",
                       bankableFlag=params.get("bankable", "UNSPECIFIED"), equipmentFlag=params.get("equipable", "UNSPECIFIED"),
                       questFlag=params.get("quest", "UNSPECIFIED"), options=params.get("options", ""),
                       itemCategory=source["category"], subcategory=source["subcategory"], tags=tags,
                       reason=note, sourceRevision=source["revid"],
                       sourceUrl="https://oldschool.runescape.wiki/w/Special:Redirect/revision/" + str(source["revid"]))
            if not row["name"] or any(x in row["name"] for x in ("\t", "\n", "{{", "[[")):
                raise ValueError("Unresolved display name: " + str(ident))
            row["ironmanTabKey"] = {"GEAR":"combat-gear", "CLUE":"clues-cosmetics", "SKILLING":"resources",
                                    "TOOL":"skilling-tools", "TELEPORT":"currency-utilities", "UNIQUE":"slayer-boss-loot",
                                    "CLEANUP":"storage-cleanup", "UNKNOWN":""}[row["itemCategory"]]
            if coverage_path is not None:
                actual = coverage.get(ident)
                if row["action"] != "INCLUDE":
                    if actual is not None:
                        raise ValueError("Excluded cohort ID entered runtime coverage: " + str(ident))
                elif (actual is None or actual["itemCategory"] != row["itemCategory"]
                      or actual["catalogName"] != row["name"] or actual["subcategory"] != row["subcategory"]
                      or actual["ironmanTabKey"] != row["ironmanTabKey"] or set(actual["tags"].split(",")) != set(tags)):
                    raise ValueError("Runtime/policy mismatch: " + str(ident))
            rows.append(row)
            if row["action"] == "INCLUDE":
                supplement.append([str(ident), row["name"], row["itemCategory"], row["subcategory"], ",".join(tags), ""])
            if source.get("cosmetic_family"):
                key = "cosmetic-family.wyrmscraig-" + re.sub(r"[^a-z0-9]+", "-", source["title"].lower()).strip("-")
                cosmetic.append(["cosmetic-family", key, source["title"], "0", str(ident)])
    rows.sort(key=lambda r: r["itemId"])
    supplement.sort(key=lambda r: int(r[0]))
    write_csv(output / "semantic-review.csv", rows)
    audit.save(output / "semantic-review.json", rows)
    groups = [dict(sourcePage=source["title"], sourceRevision=source["revid"], exact_ids=source["ids"],
                   relation="explicit-item-infobox-variants", note="Shared source identity preserves distinct variants and roles; it is not proof of interchangeable function.")
              for source in policy["sources"]]
    audit.save(output / "semantic-groups.json", groups)
    for correction in policy.get("related_corrections", []):
        if set(variants(pathlib.Path(index[correction["sourceRevision"]]["path"]).read_text(encoding="utf-8"))) != {correction["itemId"]}:
            raise ValueError("Related correction lacks exact source identity")
        if coverage_path is not None:
            actual = coverage[correction["itemId"]]
            if any(actual[k] != correction[k] for k in ("itemCategory", "subcategory", "ironmanTabKey")) or set(actual["tags"].split(",")) != set(correction["tags"]):
                raise ValueError("Related correction differs from runtime coverage")
    audit.save(output / "related-corrections.json", policy.get("related_corrections", []))
    (output / "reviewed-supplemental-items.tsv").write_text("# schema=1\n" + "\n".join("\t".join(r) for r in supplement) + "\n", encoding="utf-8")
    (output / "cosmetic-family-additions.tsv").write_text("\n".join("\t".join(r) for r in cosmetic) + "\n", encoding="utf-8")
    summary = dict(reviewed_ids=len(rows), source_pages=len(policy["sources"]),
                   actions=dict(collections.Counter(r["action"] for r in rows)),
                   context_source_pages=len(policy.get("context_sources", [])),
                   related_corrections=len(policy.get("related_corrections", [])),
                   included_categories=dict(collections.Counter(r["itemCategory"] for r in rows if r["action"] == "INCLUDE")),
                   no_current_source_bag_ids=sum(r["availability"] == "NO_CURRENT_SOURCE" for r in rows),
                   cosmetic_family_ids=len(cosmetic), runtime_verified_ids=len(rows) if coverage_path is not None else 0,
                   article_sha256=article_hashes,
                   policy_sha256=hashlib.sha256(POLICY.read_bytes()).hexdigest(),
                   attribution="OSRS Wiki contributors", license="CC BY-NC-SA 3.0",
                   limitations=["Preset category is reviewed workflow policy, not a Wiki classification.",
                                "Unspecified bankability is not an explicit positive or negative claim.",
                                "No-current-source reward bags are retained for possible stored holdings, not asserted currently obtainable."])
    summary["context_article_sha256"] = {str(r["revid"]): hashlib.sha256(pathlib.Path(index[r["revid"]]["path"]).read_bytes()).hexdigest()
                                          for r in policy.get("context_sources", [])}
    audit.save(output / "review-summary.json", summary)
    headings = ["ID", "Item / variant", "Decision", "Category / role", "Evidence and reasoning"]
    table = []
    for r in rows:
        cells = [str(r["itemId"]), r["name"] + (" · " + r["variant"] if r["variant"] else ""),
                 r["action"] + (" · no current source" if r["availability"] == "NO_CURRENT_SOURCE" else ""),
                 r["ironmanTabKey"] + " / " + r["subcategory"] + " · " + ", ".join(r["tags"]), r["reason"]]
        table.append("<tr>" + "".join("<td>" + html.escape(c) + "</td>" for c in cells[:-1]) +
                     '<td>' + html.escape(cells[-1]) + ' <a href="' + html.escape(r["sourceUrl"], quote=True) + '">Pinned Wiki source</a></td></tr>')
    document = '<!doctype html><meta charset="utf-8"><title>Missing item semantic review</title><style>body{font:16px system-ui;margin:2rem;background:#f7f6f2;color:#252d34}table{border-collapse:collapse;width:100%}th,td{padding:.7rem;border-bottom:1px solid #ccc;text-align:left;vertical-align:top}th{position:sticky;top:0;background:#e8edea}input{padding:.7rem;width:32rem;max-width:90%}a{color:#15597c}</style><h1>356-item semantic review</h1><p>All 101 source pages are pinned. Decisions distinguish exact variants, functional roles, unbankable objects and cache/event records. Preset placement is local policy; no-current-source bags remain recognizable for stored holdings.</p><p>OSRS Wiki contributors · CC BY-NC-SA 3.0</p><input id="search" placeholder="Filter by ID, name, decision or role"><table><thead><tr>' + ''.join('<th>'+h+'</th>' for h in headings) + '</tr></thead><tbody>' + ''.join(table) + '</tbody></table><script>document.querySelector("input").addEventListener("input",e=>{let q=e.target.value.toLowerCase();document.querySelectorAll("tbody tr").forEach(r=>r.hidden=!r.textContent.toLowerCase().includes(q))});</script>'
    (output / "semantic-review.html").write_text(document, encoding="utf-8")
    print(json.dumps({k: v for k, v in summary.items() if k not in {"article_sha256", "context_article_sha256"}}, indent=2))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=pathlib.Path, default=pathlib.Path("tmp/missing-item-audit/semantic-review"))
    parser.add_argument("--coverage", type=pathlib.Path, help="Verify all decisions and routes against compiled runtime coverage")
    parser.add_argument("--fetch", action="store_true", help="Acquire the exact pinned revisions before building")
    args = parser.parse_args()
    policy = json.loads(POLICY.read_text(encoding="utf-8"))
    args.output.mkdir(parents=True, exist_ok=True)
    if args.fetch:
        fetch(policy, args.output)
    build(policy, args.output, args.coverage)


if __name__ == "__main__":
    main()
