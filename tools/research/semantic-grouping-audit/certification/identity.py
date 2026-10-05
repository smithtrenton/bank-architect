#!/usr/bin/env python3
"""Certify exact item identity links from RuneLite's local cache and Wiki cache.

This is a developer-only audit. It does not modify plugin code or user data.
It reads an OSRS Jagex cache directory, the compiled current coverage export,
and the audit's cached Wiki item and item_id buckets. Wiki item_id entries are
reported as page-index pointers only; only RuneLite cache definition opcodes
establish note, placeholder, and bought-variant links.
"""
from __future__ import annotations

import argparse
import bz2
import collections
import csv
import datetime as dt
import gzip
import hashlib
import json
import pathlib
import re
import struct
import zlib
import sys


ROOT = pathlib.Path(__file__).resolve().parents[4]
DEFAULT_CACHE = pathlib.Path.home() / ".runelite/jagexcache/oldschool/LIVE"
DEFAULT_COVERAGE = ROOT / "tmp/category-certification/current-coverage.tsv"
DEFAULT_WIKI_CACHE = ROOT / "tmp/semantic-audit/cache"
DEFAULT_JOINED = ROOT / "tmp/semantic-audit/joined.jsonl"
DEFAULT_ARTICLE_INDEX = ROOT / "tmp/category-certification/wiki-articles/article-index.json"
DEFAULT_OUT = ROOT / "tmp/category-certification"


def sha256(path: pathlib.Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def read_cache_file(cache: pathlib.Path, index_id: int, file_id: int) -> bytes:
    """Read one Jagex cache file using 520-byte sectors (small file IDs)."""
    idx = cache / f"main_file_cache.idx{index_id}"
    with idx.open("rb") as stream:
        stream.seek(file_id * 6)
        entry = stream.read(6)
    if len(entry) != 6:
        raise ValueError(f"missing index entry {index_id}/{file_id}")
    length = int.from_bytes(entry[:3], "big")
    sector = int.from_bytes(entry[3:], "big")
    if not length:
        raise ValueError(f"empty cache entry {index_id}/{file_id}")
    if file_id > 0xFFFF:
        raise ValueError("cache entry needs the large-file sector header")
    out = bytearray()
    chunk = 0
    with (cache / "main_file_cache.dat2").open("rb") as stream:
        while len(out) < length:
            if not sector:
                raise ValueError(f"broken sector chain at {index_id}/{file_id}/{chunk}")
            stream.seek(sector * 520)
            head = stream.read(8)
            if len(head) != 8:
                raise ValueError(f"short sector header at {index_id}/{file_id}/{chunk}")
            got_file, got_chunk = struct.unpack(">HH", head[:4])
            next_sector = int.from_bytes(head[4:7], "big")
            got_index = head[7]
            if (got_file, got_chunk, got_index) != (file_id, chunk, index_id):
                raise ValueError(
                    f"sector mismatch expected {index_id}/{file_id}/{chunk}; "
                    f"got {got_index}/{got_file}/{got_chunk}"
                )
            amount = min(length - len(out), 512)
            payload = stream.read(amount)
            if len(payload) != amount:
                raise ValueError("short cache sector payload")
            out.extend(payload)
            sector = next_sector
            chunk += 1
    return bytes(out)


def decompress_container(blob: bytes) -> bytes:
    if len(blob) < 5:
        raise ValueError("short cache container")
    compression = blob[0]
    compressed_size = int.from_bytes(blob[1:5], "big")
    if compression == 0:
        data = blob[5:5 + compressed_size]
    else:
        if len(blob) < 9:
            raise ValueError("short compressed cache container")
        uncompressed_size = int.from_bytes(blob[5:9], "big")
        compressed = blob[9:9 + compressed_size]
        if compression == 1:
            try:
                data = bz2.decompress(compressed)
            except OSError:
                data = bz2.decompress(b"BZh1" + compressed)
        elif compression == 2:
            data = gzip.decompress(compressed)
        else:
            raise ValueError(f"unsupported cache compression {compression}")
        if len(data) != uncompressed_size:
            raise ValueError("cache container decompressed length mismatch")
    if len(data) != compressed_size and compression == 0:
        raise ValueError("raw cache container length mismatch")
    return data


def read_big_smart(data: bytes, offset: int) -> tuple[int, int]:
    if data[offset] & 0x80:
        return int.from_bytes(data[offset:offset + 4], "big") & 0x7FFFFFFF, offset + 4
    return int.from_bytes(data[offset:offset + 2], "big"), offset + 2


def decode_index(data: bytes) -> tuple[int, dict[int, dict[str, object]]]:
    """Decode RuneLite IndexData, retaining archive revisions and file IDs."""
    offset = 0
    protocol = data[offset]
    offset += 1
    if protocol < 5 or protocol > 7:
        raise ValueError(f"unsupported cache index protocol {protocol}")
    revision = -1
    if protocol >= 6:
        revision = int.from_bytes(data[offset:offset + 4], "big", signed=True)
        offset += 4
    flags = data[offset]
    offset += 1
    named = bool(flags & 1)
    sized = bool(flags & 4)
    count, offset = read_big_smart(data, offset) if protocol >= 7 else (
        int.from_bytes(data[offset:offset + 2], "big"), offset + 2
    )
    archive_ids = []
    previous = 0
    for _ in range(count):
        delta, offset = read_big_smart(data, offset) if protocol >= 7 else (
            int.from_bytes(data[offset:offset + 2], "big"), offset + 2
        )
        previous += delta
        archive_ids.append(previous)
    if named:
        offset += count * 4
    crcs = [int.from_bytes(data[offset + i * 4:offset + i * 4 + 4], "big")
            for i in range(count)]
    offset += count * 4
    sizes = [None] * count
    if sized:
        sizes = []
        for _ in range(count):
            sizes.append((int.from_bytes(data[offset:offset + 4], "big"),
                          int.from_bytes(data[offset + 4:offset + 8], "big")))
            offset += 8
    archive_revisions = []
    for _ in range(count):
        archive_revisions.append(int.from_bytes(data[offset:offset + 4], "big", signed=True))
        offset += 4
    file_counts = []
    for _ in range(count):
        value, offset = read_big_smart(data, offset) if protocol >= 7 else (
            int.from_bytes(data[offset:offset + 2], "big"), offset + 2
        )
        file_counts.append(value)
    file_ids_by_archive = []
    for file_count in file_counts:
        file_ids = []
        previous = 0
        for _ in range(file_count):
            delta, offset = read_big_smart(data, offset) if protocol >= 7 else (
                int.from_bytes(data[offset:offset + 2], "big"), offset + 2
            )
            previous += delta
            file_ids.append(previous)
        file_ids_by_archive.append(file_ids)
    archives = {}
    for i, archive_id in enumerate(archive_ids):
        archives[archive_id] = {
            "crc": crcs[i],
            "revision": archive_revisions[i],
            "compressed_size": sizes[i][0] if sizes[i] else None,
            "decompressed_size": sizes[i][1] if sizes[i] else None,
            "file_ids": file_ids_by_archive[i],
        }
    return revision, archives


def split_archive(data: bytes, file_ids: list[int]) -> dict[int, bytes]:
    if not file_ids:
        return {}
    if len(file_ids) == 1:
        return {file_ids[0]: data}
    chunks = data[-1]
    table_size = chunks * len(file_ids) * 4
    table_offset = len(data) - 1 - table_size
    if table_offset < 0:
        raise ValueError("invalid archive chunk table")
    pos = table_offset
    lengths = [[0] * chunks for _ in file_ids]
    totals = [0] * len(file_ids)
    for chunk in range(chunks):
        chunk_size = 0
        for file_index in range(len(file_ids)):
            delta = int.from_bytes(data[pos:pos + 4], "big", signed=True)
            pos += 4
            chunk_size += delta
            if chunk_size < 0:
                raise ValueError("invalid archive chunk length")
            lengths[file_index][chunk] = chunk_size
            totals[file_index] += chunk_size
    output = [bytearray() for _ in file_ids]
    pos = 0
    for chunk in range(chunks):
        for file_index in range(len(file_ids)):
            size = lengths[file_index][chunk]
            output[file_index].extend(data[pos:pos + size])
            pos += size
    if pos != table_offset or [len(x) for x in output] != totals:
        raise ValueError("archive split length mismatch")
    return dict(zip(file_ids, (bytes(x) for x in output)))


class Buffer:
    def __init__(self, data: bytes):
        self.data = data
        self.pos = 0

    def take(self, size: int) -> bytes:
        end = self.pos + size
        if end > len(self.data):
            raise ValueError("truncated item definition")
        value = self.data[self.pos:end]
        self.pos = end
        return value

    def u8(self) -> int:
        return self.take(1)[0]

    def i8(self) -> int:
        return struct.unpack(">b", self.take(1))[0]

    def u16(self) -> int:
        return int.from_bytes(self.take(2), "big")

    def i32(self) -> int:
        return int.from_bytes(self.take(4), "big", signed=True)

    def cstring(self) -> None:
        end = self.data.find(b"\0", self.pos)
        if end < 0:
            raise ValueError("unterminated item-definition string")
        self.pos = end + 1


def parse_item_links(item_id: int, data: bytes) -> dict[str, object]:
    """Read relationship fields using current RuneLite ItemLoader opcodes."""
    b = Buffer(data)
    result: dict[str, object] = {"item_id": item_id, "name": "null"}
    while True:
        op = b.u8()
        if op == 0:
            if b.pos != len(data):
                raise ValueError(f"item {item_id} has {len(data) - b.pos} trailing bytes")
            break
        if op == 1:
            b.take(2)
        elif op in (2, 3, 9):
            start = b.pos
            b.cstring()
            if op == 2:
                result["name"] = b.data[start:b.pos - 1].decode("cp1252", "replace")
        elif op in (4, 5, 6, 7, 8, 24, 26, 78, 79,
                    90, 91, 92, 93, 94, 95, 97, 98, 99, 110, 111, 112,
                    139, 140, 148, 149):
            key = {97: "noted_id", 98: "noted_template", 139: "bought_id",
                   140: "bought_template_id", 148: "placeholder_id",
                   149: "placeholder_template_id"}.get(op)
            value = b.u16()
            if key:
                result[key] = value
        elif op in (11, 15, 16, 65, 160, 251):
            pass
        elif op == 12:
            b.take(4)
        elif op in (23, 25):
            b.take(3)
        elif 30 <= op < 40:
            b.cstring()
        elif op in (40, 41):
            b.take(1 + b.data[b.pos] * 4)
        elif op == 43:
            b.take(1)
            while b.u8() != 0:
                b.cstring()
        elif op in (44, 46, 47, 49, 50, 51, 52, 53, 54):
            b.take(4)
        elif op in (45, 48):
            b.take(5)
        elif 100 <= op < 110:
            b.take(4)
        elif op in (13, 14, 27, 42, 113, 114, 115):
            b.take(1)
        elif op == 75:
            b.take(2)
        elif op == 161:
            count = b.u16()
            b.take(count * 2)
        elif op == 200:
            b.take(2)
            b.cstring()
        elif op == 201:
            b.take(1 + 2 + 2 + 4 + 4)
            b.cstring()
        elif op == 202:
            b.take(1 + 2 + 2 + 2 + 4 + 4)
            b.cstring()
        elif op == 249:
            count = b.u8()
            for _ in range(count):
                kind = b.u8()
                b.take(3)
                b.cstring() if kind == 1 else b.take(8 if kind == 2 else 4)
        else:
            raise ValueError(f"unknown item opcode {op} for item {item_id}")
    return result


def numeric_ids(value: object) -> list[int]:
    values = value if isinstance(value, list) else ([] if value is None else [value])
    output = []
    for raw in values:
        text = str(raw).strip()
        if text.isdecimal() and int(text) > 0:
            output.append(int(text))
    return output


def load_wiki(cache: pathlib.Path) -> tuple[dict[int, list[dict]], dict[int, list[dict]], dict]:
    item_packet = json.loads((cache / "infobox_item.json").read_text(encoding="utf-8"))
    lookup_packet = json.loads((cache / "item_id.json").read_text(encoding="utf-8"))
    item_facts: dict[int, list[dict]] = collections.defaultdict(list)
    for row in item_packet["rows"]:
        for ident in numeric_ids(row.get("item_id")):
            item_facts[ident].append(row)
    index_links: dict[int, list[dict]] = collections.defaultdict(list)
    for row in lookup_packet["rows"]:
        for ident in numeric_ids(row.get("id")):
            index_links[ident].append(row)
    manifest = json.loads((cache / "manifest.json").read_text(encoding="utf-8"))
    return item_facts, index_links, {
        "retrieved_at": manifest.get("retrieved_at"),
        "api": manifest.get("api"),
        "license": manifest.get("license"),
        "infobox_sha256": sha256(cache / "infobox_item.json"),
        "item_id_sha256": sha256(cache / "item_id.json"),
    }


def load_article_index(path: pathlib.Path) -> tuple[dict[int, list[dict]], dict]:
    """Load only article-index rows with parser-confirmed exact numeric item IDs."""
    index = json.loads(path.read_text(encoding="utf-8"))
    by_id: dict[int, list[dict]] = collections.defaultdict(list)
    page_meta = {}
    for title, page in index.items():
        if not isinstance(page, dict) or "exactInfoboxItemIds" not in page:
            continue
        text_path = pathlib.Path(page["path"])
        if not text_path.is_absolute():
            text_path = ROOT / text_path
        if not text_path.is_file() or sha256(text_path) != page.get("sha256"):
            raise ValueError(f"pinned article body missing or hash mismatch for {title}")
        text = text_path.read_text(encoding="utf-8")
        page_meta[title] = (page, text)
        for raw_id in page["exactInfoboxItemIds"]:
            ident = int(raw_id)
            variant = page.get("variants", {}).get(str(ident))
            if variant is None:
                raise ValueError(f"article index lacks exact variant payload for {title}/{ident}")
            suffix = variant.get("suffix", "")
            id_pattern = re.compile(r"\s*\|\s*id" + re.escape(str(suffix)
                                      ) + r"\s*=\s*([0-9,\s]+)\s*")
            id_line = None
            for line in text.splitlines():
                match = id_pattern.fullmatch(line)
                if match and str(ident) in re.split(r"[\s,]+", match.group(1).strip()):
                    id_line = line.strip()
                    break
            if id_line is None:
                raise ValueError(f"pinned article does not contain exact item ID line for {title}/{ident}")
            variant_line = ""
            if suffix:
                variant_line = next((line.strip() for line in text.splitlines()
                                     if re.fullmatch(r"\s*\|\s*version" + re.escape(str(suffix))
                                                     + r"\s*=.*", line)), "")
            by_id[ident].append({
                "sourceTitle": title, "sourceRevision": page["revid"],
                "sourceUrl": page["sourceUrl"], "sourceHash": page["sha256"],
                "sourceIndexPath": str(path), "sourceIndexHash": sha256(path),
                "itemId": ident, "quote": id_line + (("\n" + variant_line) if variant_line else ""),
                "variant": variant,
            })
    return by_id, {"path": str(path), "sha256": sha256(path), "pageCount": len(page_meta),
                   "retrievedAt": index.get("packet", {}).get("retrievedAt")}


def write_tsv(path: pathlib.Path, fields: list[str], rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields, delimiter="\t", extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({key: json.dumps(value, ensure_ascii=False, sort_keys=True)
                             if isinstance(value, (list, dict)) else value
                             for key, value in row.items()})


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cache", type=pathlib.Path, default=DEFAULT_CACHE)
    parser.add_argument("--coverage", type=pathlib.Path, default=DEFAULT_COVERAGE)
    parser.add_argument("--wiki-cache", type=pathlib.Path, default=DEFAULT_WIKI_CACHE)
    parser.add_argument("--joined", type=pathlib.Path, default=DEFAULT_JOINED)
    parser.add_argument("--article-index", type=pathlib.Path, default=DEFAULT_ARTICLE_INDEX)
    parser.add_argument("--out", type=pathlib.Path, default=DEFAULT_OUT)
    args = parser.parse_args()

    coverage = list(csv.DictReader(args.coverage.open(encoding="utf-8-sig"), delimiter="\t"))
    effective_by_id = {int(row["itemId"]): row for row in coverage}
    if len(effective_by_id) != len(coverage):
        raise ValueError("duplicate current coverage item ID")
    cache_files = [args.cache / name for name in (
        "main_file_cache.dat2", "main_file_cache.idx2", "main_file_cache.idx255")]
    before_hashes = {path.name: sha256(path) for path in cache_files}
    index_blob = read_cache_file(args.cache, 255, 2)
    item_archive_blob = read_cache_file(args.cache, 2, 10)
    after_hashes = {path.name: sha256(path) for path in cache_files}
    if before_hashes != after_hashes:
        raise RuntimeError("local cache changed during identity snapshot read; retry")
    for name, blob in (("runelite-config-index-2.bin", index_blob),
                       ("runelite-index2-item-archive10.bin", item_archive_blob)):
        (args.out / name).write_bytes(blob)
    index2_raw_crc = zlib.crc32(index_blob[:-4]) & 0xFFFFFFFF
    index2_container_revision = int.from_bytes(index_blob[-4:], "big", signed=True)
    item_index = decompress_container(index_blob)
    index_revision, archives = decode_index(item_index)
    if 10 not in archives:
        raise ValueError("config item-definition archive 10 is absent")
    archive_meta = archives[10]
    item_archive_crc = zlib.crc32(item_archive_blob[:-4]) & 0xFFFFFFFF
    if archive_meta["crc"] != item_archive_crc:
        raise ValueError("item-definition archive CRC does not match config-index metadata")
    item_archive_hash = sha256(args.out / "runelite-index2-item-archive10.bin")
    item_files = split_archive(decompress_container(item_archive_blob), archive_meta["file_ids"])
    cache_items = {ident: parse_item_links(ident, data) for ident, data in item_files.items()}
    item_facts, index_links, wiki_source = load_wiki(args.wiki_cache)
    article_sources, article_index_source = load_article_index(args.article_index)
    wiki_source["article_index"] = article_index_source

    joined_rows = {}
    with args.joined.open(encoding="utf-8") as stream:
        for line in stream:
            row = json.loads(line)
            joined_rows[int(row["item_id"])] = row

    cache_hashes = {}
    for filename in before_hashes:
        path = args.cache / filename
        cache_hashes[filename] = {"sha256": before_hashes[filename], "bytes": path.stat().st_size,
                                  "last_write_utc": dt.datetime.fromtimestamp(
                                      path.stat().st_mtime, dt.timezone.utc).isoformat()}

    relationship_rows = []
    coverage_rows = []
    for ident, catalog in sorted(effective_by_id.items()):
        definition = cache_items.get(ident)
        exact_facts = item_facts.get(ident, [])
        exact_article_sources = article_sources.get(ident, [])
        wiki_links = index_links.get(ident, [])
        item_name = definition.get("name", "") if definition else ""
        typed = []
        if definition:
            if definition.get("noted_template", -1) != -1 and definition.get("noted_id", -1) != -1:
                typed.append(("NOTE_VARIANT_OF", int(definition["noted_id"]), "notedID/notedTemplate", "97/98"))
            if definition.get("placeholder_template_id", -1) != -1 and definition.get("placeholder_id", -1) != -1:
                typed.append(("PLACEHOLDER_FOR", int(definition["placeholder_id"]), "placeholderID/placeholderTemplateID", "148/149"))
            if definition.get("bought_template_id", -1) != -1 and definition.get("bought_id", -1) != -1:
                typed.append(("BOUGHT_VARIANT_OF", int(definition["bought_id"]), "boughtId/boughtTemplateId", "139/140"))
        for relation, target, field, opcode in typed:
            target_definition = cache_items.get(target, {})
            target_facts = item_facts.get(target, [])
            target_article_sources = article_sources.get(target, [])
            evidence = [{
                "kind": "typed_identity",
                "source": "RuneLite current OSRS cache, config index 2, item-definition archive 10",
                "sourcePath": "tmp/category-certification/runelite-index2-item-archive10.bin",
                "sourceHash": item_archive_hash,
                "sourceRevision": archive_meta["revision"],
                "configIndexRevision": index_revision,
                "fromItemId": ident, "toItemId": target, "relation": relation,
                "cacheField": field, "cacheOpcode": opcode,
            }]
            for fact in target_article_sources:
                evidence.append({
                    "kind": "exact_wiki", "itemId": target,
                    "sourceTitle": fact["sourceTitle"], "source": fact["sourceUrl"],
                    "sourceRevision": fact["sourceRevision"],
                    "sourceHash": fact["sourceHash"], "sourceUrl": fact["sourceUrl"],
                    "sourceIndexHash": fact["sourceIndexHash"],
                    "quote": fact["quote"], "sourceRecord": fact["variant"],
                })
            relationship_rows.append({
                "itemId": target, "fromItemId": ident, "toItemId": target,
                "catalogName": catalog.get("catalogName", ""),
                "cacheName": item_name, "relation": relation, "targetId": target,
                "targetCacheName": target_definition.get("name", ""),
                "cacheField": field, "cacheOpcode": opcode,
                "targetWikiFactCount": len(target_article_sources),
                "targetWikiBucketFactCount": len(target_facts), "evidence": evidence,
                "wikiBucketSupport": [{
                    "source": "OSRS Wiki infobox_item bucket; exact numeric item_id match",
                    "sourceRetrievedAt": wiki_source["retrieved_at"],
                    "sourceHash": wiki_source["infobox_sha256"],
                    "sourceRecords": target_facts,
                }],
            })
        fact_status = ("EXACT_PINNED_ARTICLE_ID" if exact_article_sources else
                       "EXACT_WIKI_BUCKET_ONLY" if exact_facts else "NO_EXACT_WIKI_FACT")
        if exact_article_sources:
            identity_status = "WIKI_ARTICLE_EXACT_ID"
        elif typed:
            identity_status = "TYPED_CACHE_RELATION_ONLY"
        elif wiki_links:
            identity_status = "WIKI_INDEX_POINTER_ONLY_UNVERIFIED"
        else:
            identity_status = "UNRESOLVED_EXACT_ID"
        coverage_rows.append({
            "itemId": ident, "catalogName": catalog.get("catalogName", ""),
            "itemCategory": catalog.get("itemCategory", ""),
            "presetCategory": catalog.get("ironmanTabKey", ""),
            "wikiFactStatus": fact_status, "wikiFactCount": len(exact_article_sources),
            "wikiBucketFactCount": len(exact_facts),
            "identityStatus": identity_status, "cacheDefinitionPresent": definition is not None,
            "cacheName": item_name, "typedLinkCount": len(typed),
            "typedLinks": [{"relation": r, "targetId": t, "targetName": cache_items.get(t, {}).get("name", ""),
                            "field": f, "opcodes": o} for r, t, f, o in typed],
            "wikiIndexLinkCount": len(wiki_links),
            "wikiIndexLinks": [{"page": row.get("page_name", ""),
                                 "subpage": row.get("page_name_sub", ""),
                                 "rawId": row.get("id", [])} for row in wiki_links],
            "joinedSnapshotStatus": joined_rows.get(ident, {}).get("wiki_join_status", "NOT_IN_JOINED_SNAPSHOT"),
        })

    fields = list(coverage_rows[0]) if coverage_rows else []
    write_tsv(args.out / "identity-coverage.tsv", fields, coverage_rows)
    write_tsv(args.out / "typed-cache-relationships.tsv",
              ["itemId", "fromItemId", "toItemId", "catalogName", "cacheName", "relation", "targetId", "targetCacheName", "cacheField", "cacheOpcode", "targetWikiFactCount", "evidence"],
              relationship_rows)
    with (args.out / "identity-links.jsonl").open("w", encoding="utf-8", newline="\n") as stream:
        for row in relationship_rows:
            stream.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
    unresolved = [row for row in coverage_rows if row["wikiFactStatus"] == "NO_EXACT_WIKI_FACT"]
    write_tsv(args.out / "identity-unresolved.tsv", fields, unresolved)
    wiki_index_only = [row for row in unresolved if row["wikiIndexLinkCount"]]
    write_tsv(args.out / "wiki-index-only.tsv", fields, wiki_index_only)

    report = {
        "generated_at_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
        "coverage_path": str(args.coverage), "coverage_sha256": sha256(args.coverage),
        "identity_links_sha256": sha256(args.out / "identity-links.jsonl"),
        "coverage_rows": len(coverage_rows),
        "wiki_fact_status_counts": dict(collections.Counter(row["wikiFactStatus"] for row in coverage_rows)),
        "wiki_bucket_only_current_ids": sorted(row["itemId"] for row in coverage_rows
                                                  if row["wikiFactStatus"] == "EXACT_WIKI_BUCKET_ONLY"),
        "identity_status_counts": dict(collections.Counter(row["identityStatus"] for row in coverage_rows)),
        "typed_relationship_counts": dict(collections.Counter(row["relation"] for row in relationship_rows)),
        "typed_relationship_rows": len(relationship_rows),
        "unresolved_without_exact_wiki_facts": len(unresolved),
        "wiki_index_only_unverified_count": len(wiki_index_only),
        "cache": {"path": str(args.cache), "index_id": 2, "index_protocol": 7,
                  "index_revision": index_revision, "config_archive_id": 10,
                  "config_archive_revision": archive_meta["revision"],
                  "config_index_container_revision": index2_container_revision,
                  "config_index_archive_crc32": f"{index2_raw_crc:08x}",
                  "item_archive_crc32": f"{item_archive_crc:08x}",
                  "item_archive_expected_crc32": f"{archive_meta['crc']:08x}",
                  "frozen_containers": {
                      "runelite-config-index-2.bin": sha256(args.out / "runelite-config-index-2.bin"),
                      "runelite-index2-item-archive10.bin": item_archive_hash,
                  },
                  "item_definition_count": len(cache_items), "item_id_min": min(cache_items),
                  "item_id_max": max(cache_items), "files": cache_hashes},
        "wiki_source": wiki_source,
        "decoder_basis": {
            "source_commit": "d8e7d1e5f34e2899eda3d7cf4cd9661ae2206f22",
            "source": "RuneLite/runelite cache module; IndexType.CONFIGS=2, ConfigType.ITEM=10, "
                      "ItemDefinition fields and ItemLoader opcodes 97/98, 139/140, 148/149",
            "urls": [
                "https://github.com/runelite/runelite/blob/d8e7d1e5f34e2899eda3d7cf4cd9661ae2206f22/cache/src/main/java/net/runelite/cache/ItemManager.java",
                "https://github.com/runelite/runelite/blob/d8e7d1e5f34e2899eda3d7cf4cd9661ae2206f22/cache/src/main/java/net/runelite/cache/definitions/ItemDefinition.java",
                "https://github.com/runelite/runelite/blob/d8e7d1e5f34e2899eda3d7cf4cd9661ae2206f22/cache/src/main/java/net/runelite/cache/definitions/loaders/ItemLoader.java",
                "https://github.com/runelite/runelite/blob/d8e7d1e5f34e2899eda3d7cf4cd9661ae2206f22/cache/src/main/java/net/runelite/cache/definitions/loaders/EntityOpsLoader.java",
                "https://github.com/runelite/runelite/blob/d8e7d1e5f34e2899eda3d7cf4cd9661ae2206f22/cache/src/main/java/net/runelite/cache/index/IndexData.java",
                "https://github.com/runelite/runelite/blob/d8e7d1e5f34e2899eda3d7cf4cd9661ae2206f22/cache/src/main/java/net/runelite/cache/ConfigType.java",
                "https://github.com/runelite/runelite/blob/d8e7d1e5f34e2899eda3d7cf4cd9661ae2206f22/cache/src/main/java/net/runelite/cache/IndexType.java",
                "https://github.com/runelite/runelite/blob/d8e7d1e5f34e2899eda3d7cf4cd9661ae2206f22/cache/src/main/java/net/runelite/cache/fs/Container.java",
                "https://github.com/runelite/runelite/blob/d8e7d1e5f34e2899eda3d7cf4cd9661ae2206f22/cache/src/main/java/net/runelite/cache/fs/ArchiveFiles.java",
                "https://github.com/runelite/runelite/blob/d8e7d1e5f34e2899eda3d7cf4cd9661ae2206f22/cache/src/main/java/net/runelite/cache/fs/jagex/DiskStorage.java",
                "https://github.com/runelite/runelite/blob/d8e7d1e5f34e2899eda3d7cf4cd9661ae2206f22/cache/src/main/java/net/runelite/cache/fs/jagex/DataFile.java",
                "https://github.com/runelite/runelite/blob/d8e7d1e5f34e2899eda3d7cf4cd9661ae2206f22/cache/src/main/java/net/runelite/cache/fs/jagex/IndexFile.java",
                "https://github.com/runelite/runelite/blob/d8e7d1e5f34e2899eda3d7cf4cd9661ae2206f22/cache/src/main/java/net/runelite/cache/io/InputStream.java",
            ],
            "source_sha256": {
                "ItemManager.java": "733e6fc134a893fe7e38b6dd1859289ca5f29a95adf44ba02a7d5049141c31f5",
                "ItemDefinition.java": "c514dff3dedb4603f1780534bbbbb90d0c451f4e2efba00da8e09615089c47e5",
                "ItemLoader.java": "1c3e0d98101efb69c152ce4fe9a861acfbbe7a463ea74b079274c8de12170619",
                "EntityOpsLoader.java": "450daa36fa4ef271fd0389f85536f67400410577be5a74531201f2415bc745b7",
                "IndexData.java": "97c3a3766383f69b148b08519c7de083e198a2f75800b59e40e395e60492a030",
                "ConfigType.java": "04e76c9e77ef58b621546f69907e568b9192ed7134c1174efc6490fa1ae6bc0b",
                "IndexType.java": "99c9a8144cec4306b350cf215c96e15aed9846f4c5a8272400780bc8f5bb081a",
                "Container.java": "58fd9f2c122445babb0fd416b453439798468448a07698002d3a620a729707c9",
                "ArchiveFiles.java": "a9e0e288b562a5f1789f50894f451447b66fa3b93641cbd5cec78b0fec53fcbd",
                "DiskStorage.java": "37b28b2c042d306e464ab6e1ce3df80e9a70290109bc8f2069c63985f6e32920",
                "DataFile.java": "3ddf6201c2a90a42bb23f7a58cead3fd38d8f6de3876638abcdab007cd3fd7c8",
                "IndexFile.java": "3db65ca1aea8c4342ac8414f0679647c355db5ca6949f512bbe0fc570bf458b3",
                "InputStream.java": "8f1d66a201e8650ccf14bba7133fb276814c6a79ba507b862c35a6330d1dc07c",
            },
            "limits": [
                "Cache relationships establish variant identity only; they do not assign semantic or bank-placement roles.",
                "Wiki item_id rows without exact infobox facts are page-index pointers, not transformations or canonical identity proof.",
                "Only note, placeholder, and bought-variant references are extracted; all other ItemDefinition fields are out of scope.",
                "Cache snapshot is the locally installed RuneLite OSRS LIVE cache. Hashes and file timestamps identify this exact snapshot.",
            ],
        },
    }
    (args.out / "identity-report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({k: report[k] for k in (
        "coverage_rows", "wiki_fact_status_counts", "identity_status_counts",
        "typed_relationship_counts", "typed_relationship_rows", "unresolved_without_exact_wiki_facts",
        "wiki_index_only_unverified_count")}, indent=2))


if __name__ == "__main__":
    main()
