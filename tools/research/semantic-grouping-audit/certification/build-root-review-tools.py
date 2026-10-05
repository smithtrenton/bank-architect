#!/usr/bin/env python3
"""Build a pinned-source review packet for unchanged TOOL candidates.

This emits research material only. It does not approve semantic decisions or
change any plugin data. The output directory is keyed by immutable input hashes
and refuses to overwrite an existing directory.
"""
from __future__ import annotations

import hashlib
import json
import re
from collections import defaultdict
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[4]
PACKET = ROOT / "tmp/category-certification/reviewer-packets/tools.jsonl"
DECISIONS = ROOT / "tmp/category-certification/reviews/tools/tools/decisions.jsonl"
INDEX = ROOT / "tmp/category-certification/wiki-articles/article-index.json"
OUT_ROOT = ROOT / "tmp/category-certification/reviews"

FUNCTION_CUES = re.compile(
    r"\b(use|used|uses|using|allow|allows|allows|require|required|requires|"
    r"hold|holds|store|stores|fill|fills|empty|empties|wear|wield|equip|"
    r"light|lights|protect|protects|prevent|prevents|access|shortcut|"
    r"teleport|transport|unlock|open|repair|recharge|charge|degrad|"
    r"consume|consum|destroy|crumble|disintegrat|benefit|effect|"
    r"craft|make|produce|harpoon|catch|trap|mine|woodcut|farming|"
    r"runecraft|slayer|quest|combat|damage|bonus|skill|capacity)\b",
    re.IGNORECASE,
)
ACCESS_CUES = re.compile(
    r"\b(access|shortcut|teleport|transport|unlock|enter|exit|door|"
    r"travel|reach|bank|return|move to|opens?)\b",
    re.IGNORECASE,
)
CONSUMED_CUES = re.compile(
    r"\b(consum(?:e|ed|es|ing)|single.use|one.time|crumble|disintegrat|"
    r"destroyed after|is lost when|will lose|used up)\b",
    re.IGNORECASE,
)
ACTIVITY_CUES = re.compile(
    r"\b(only|during|within|inside|after completing|quest|minigame|"
    r"slayer task|while .* in|while .* at)\b",
    re.IGNORECASE,
)
RELEVANT_SECTIONS = re.compile(
    r"\b(use|usage|function|benefit|effect|quest|capacity|degrad|repair|"
    r"transport|teleport|access|combat|bonus|light|charge|recipe|"
    r"creation|equipment|location|mechanic|properties)\b",
    re.IGNORECASE,
)
SOURCE_SECTIONS_TO_SKIP = re.compile(
    r"\b(item sources?|drop sources?|shop locations?|spawns?|changes?|"
    r"gallery|references?|trivia|sound effects?)\b",
    re.IGNORECASE,
)

ROOT_HOLDS: dict[int, str] = {
    28813: "Root flagged this as a repairable zombie-axe weapon; current TOOL/skilling-axe fit is unestablished.",
    12800: "Root flagged this as an appearance-only modifier; the kit itself is not established as a pickaxe.",
    9681: "Root flagged only a Slug Menace quest use in the lead; post-quest utility requires exact full-page support.",
    31989: "Root flagged this as explicitly single-use; persistent-container logic cannot certify it.",
    2162: "Root flagged this as edible Cooking material and consumed aerial-fishing bait; persistent-tool status is unestablished.",
    7449: "Root flagged this as a melee kitchen weapon; the item name/examine is not proof of a cooking function.",
    34030: "Root flagged a boss display use plus secondary light function; primary placement needs review.",
    11024: "Root flagged this as an Easter event object handed to the Easter Bunny; ordinary reusable Crafting-mould use is unestablished.",
    28628: "Root flagged this as a consumed entitlement to extra planks; review voucher/material routing.",
    21754: "Root flagged this as consumed after direct operation against gargoyles; consumption alone does not rule out a Tool function.",
    9771: "Root requires exact copy semantics and a skilling-versus-combat primary-use review.",
    9772: "Root requires exact copy semantics and a skilling-versus-combat primary-use review.",
    13340: "Root requires exact copy semantics and a skilling-versus-combat primary-use review.",
    13341: "Root requires exact copy semantics and a skilling-versus-combat primary-use review.",
    26822: "Root requires the unlit-state mechanics and activity-versus-general-light function to be distinguished.",
    26824: "Root requires exact lit-state effects and activity-versus-general-light use to be distinguished.",
    26826: "Root requires exact lit-state effects and activity-versus-general-light use to be distinguished.",
    26828: "Root requires exact lit-state effects and activity-versus-general-light use to be distinguished.",
    26830: "Root requires exact lit-state effects and activity-versus-general-light use to be distinguished.",
    26832: "Root requires exact lit-state effects and activity-versus-general-light use to be distinguished.",
    26834: "Root requires exact lit-state effects and activity-versus-general-light use to be distinguished.",
    26836: "Root requires exact lit-state effects and activity-versus-general-light use to be distinguished.",
    26838: "Root requires exact lit-state effects and activity-versus-general-light use to be distinguished.",
    26840: "Root requires exact lit-state effects and activity-versus-general-light use to be distinguished.",
    26842: "Root requires exact lit-state effects and activity-versus-general-light use to be distinguished.",
    26844: "Root requires exact lit-state effects and activity-versus-general-light use to be distinguished.",
    26846: "Root requires exact lit-state effects and activity-versus-general-light use to be distinguished.",
    26848: "Root requires exact lit-state effects and activity-versus-general-light use to be distinguished.",
}


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def clean_for_scan(value: str) -> str:
    value = re.sub(r"<!--.*?-->", " ", value, flags=re.S)
    value = re.sub(r"\[\[(?:File|Image):[^\]]+\]\]", " ", value, flags=re.I)
    return value.strip()


def get_page_body(text: str) -> str:
    """Skip leading page templates, including wrappers around item infoboxes."""
    pos = 0
    while pos < len(text):
        while pos < len(text) and text[pos].isspace():
            pos += 1
        if text.startswith("<!--", pos):
            end = text.find("-->", pos + 4)
            if end < 0:
                raise ValueError("Unclosed leading comment")
            pos = end + 3
            continue
        if not text.startswith("{{", pos):
            break
        depth = 0
        while pos < len(text) - 1:
            if text.startswith("{{", pos):
                depth += 1
                pos += 2
            elif text.startswith("}}", pos):
                depth -= 1
                pos += 2
                if depth == 0:
                    break
            else:
                pos += 1
        if depth != 0:
            raise ValueError("Unclosed leading template")
    return text[pos:].lstrip("\r\n")


def first_bold_subject_lead(body: str, page_title: str) -> tuple[str, bool]:
    """Return the own-subject paragraph and whether bold text matches its title."""
    # Ignore leading synced-switch/gallery templates; the first prose paragraph
    # that names a bold subject is the article's own lead paragraph.
    paragraphs = re.split(r"\n\s*\n", body)
    candidates = [p.strip() for p in paragraphs if "'''" in p and not p.lstrip().startswith(("{{", "{|"))]
    if not candidates:
        return "", False
    title_key = re.sub(r"[^a-z0-9]", "", page_title.casefold())
    title_keys = {title_key}
    if title_key.endswith("s"):
        title_keys.add(title_key[:-1])
    else:
        title_keys.add(title_key + "s")
    for paragraph in candidates:
        bolds = re.findall(r"'''([^']+)'''", paragraph)
        if any(re.sub(r"[^a-z0-9]", "", b.casefold()) in title_keys for b in bolds):
            return paragraph, True
    return candidates[0], False


def article_sections(text: str) -> list[tuple[str, str]]:
    sections: list[tuple[str, str]] = []
    current_title = "Article lead"
    current: list[str] = []
    for line in text.splitlines():
        match = re.match(r"^(={2,4})\s*(.*?)\s*\1\s*$", line)
        if match:
            sections.append((current_title, "\n".join(current)))
            current_title = match.group(2).strip()
            current = []
        else:
            current.append(line)
    sections.append((current_title, "\n".join(current)))
    return sections


def paragraph_records(text: str) -> list[dict[str, str]]:
    records: list[dict[str, str]] = []
    for title, section_text in article_sections(text):
        if SOURCE_SECTIONS_TO_SKIP.search(title):
            continue
        section_is_material = bool(RELEVANT_SECTIONS.search(title))
        for raw in re.split(r"\n\s*\n", section_text):
            literal_paragraph = raw.strip()
            scan_text = clean_for_scan(literal_paragraph)
            if not scan_text or len(scan_text) < 24:
                continue
            if scan_text.startswith(("{{", "{|", "|", "}}", "[[Category:")):
                continue
            if not (section_is_material or FUNCTION_CUES.search(scan_text)):
                continue
            # Avoid copying source tables that are item-source/drop lists. Keep
            # functional tables (benefits, capacities, effects, recipes).
            if literal_paragraph.count("{{ItemSpawnLine") or "{{Drop sources" in literal_paragraph:
                continue
            records.append({"section": title, "literalParagraph": literal_paragraph})
    # Preserve original page order while deduplicating repeated transclusions.
    seen: set[tuple[str, str]] = set()
    unique: list[dict[str, str]] = []
    for item in records:
        key = (item["section"], item["literalParagraph"])
        if key not in seen:
            seen.add(key)
            unique.append(item)
    return unique


def variant_fields(params: dict[str, Any], suffix: str) -> dict[str, Any]:
    wanted = {
        "id", "name", "version", "examine", "options", "wornoptions",
        "equipable", "slot", "quest", "tradeable", "stackable", "noteable",
        "destroy", "charges", "weight", "value", "alchable", "bankable",
        "noted", "noteable", "charge", "degrade", "repair", "release",
    }
    out: dict[str, Any] = {}
    # Select only the exact suffix, never e.g. id15 for variant 5.
    for stem in wanted:
        selected = f"{stem}{suffix}" if suffix else stem
        if selected in params:
            out[selected] = params[selected]
        elif stem in params:
            out[stem] = params[stem]
    return dict(sorted(out.items()))


def source_flags(params: dict[str, Any], variant_name: str, page_text: str) -> list[dict[str, str]]:
    flags: list[dict[str, str]] = []
    equipable = str(params.get("equipable", "")).casefold() == "yes"
    options = " ".join(str(v) for k, v in params.items() if k.startswith("options")).casefold()
    if equipable or re.search(r"\b(wear|wield|equip)\b", options):
        flags.append({"flag": "wearable_or_equipment_option", "basis": f"equipable={params.get('equipable')}; options={options}"})
    quest = str(params.get("quest", ""))
    if quest and quest.casefold() != "no":
        flags.append({"flag": "quest_associated_variant", "basis": f"quest={quest}"})
    consumed = [p["literalParagraph"] for p in paragraph_records(page_text) if CONSUMED_CUES.search(p["literalParagraph"])]
    if consumed:
        flags.append({"flag": "consumed_or_depletable_mechanic_present", "basis": consumed[0]})
    activity = [p["literalParagraph"] for p in paragraph_records(page_text) if ACTIVITY_CUES.search(p["literalParagraph"])]
    if activity:
        flags.append({"flag": "activity_or_scope_restriction_present", "basis": activity[0]})
    return flags


def normalize_whitespace(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


def main() -> None:
    coverage = {r["itemId"]: r for r in (json.loads(x) for x in (ROOT / "tmp/category-certification/reviewer-packets/tools.jsonl").open(encoding="utf-8"))}
    decisions = [json.loads(x) for x in DECISIONS.open(encoding="utf-8")]
    selected = [d for d in decisions if d.get("reviewStatus") == "CERTIFIED"]
    if len(selected) != 165:
        raise SystemExit(f"Expected frozen 165 unchanged TOOL candidates, found {len(selected)}")
    index_bytes = INDEX.read_bytes()
    decision_bytes = DECISIONS.read_bytes()
    packet_bytes = PACKET.read_bytes()
    index = json.loads(index_bytes)
    input_hashes = {"articleIndex": sha256(index_bytes), "toolDecisions": sha256(decision_bytes), "toolPacket": sha256(packet_bytes)}
    input_hashes["generator"] = sha256(Path(__file__).read_bytes())
    key = sha256(json.dumps(input_hashes, sort_keys=True).encode("utf-8"))[:16]
    out_dir = OUT_ROOT / f"root-review-tools-{key}"
    if out_dir.exists():
        raise SystemExit(f"Refusing to overwrite existing deterministic packet directory: {out_dir}")
    out_dir.mkdir(parents=True)

    by_page: dict[tuple[str, int, str], list[dict[str, Any]]] = defaultdict(list)
    holds = 0
    for decision in selected:
        item_id = int(decision["itemId"])
        packet = coverage[item_id]
        exact_evidence = [e for e in decision.get("evidence", []) if e.get("kind") == "exact_wiki"]
        if not exact_evidence:
            raise SystemExit(f"Candidate {item_id} has no exact Wiki evidence")
        cite = exact_evidence[0]
        title = cite.get("sourceTitle", "")
        page = index.get(title)
        if not page:
            raise SystemExit(f"Missing article index entry for {item_id}: {title}")
        text_path = ROOT / page["path"]
        text_bytes = text_path.read_bytes()
        actual_hash = sha256(text_bytes)
        declared_hash = str(page.get("sha256", "")).removeprefix("sha256:")
        if actual_hash != declared_hash:
            raise SystemExit(f"Pinned source hash mismatch for {item_id} on {title}")
        if int(cite.get("sourceRevision", -1)) != int(page.get("revid", -2)):
            raise SystemExit(f"Revision mismatch for exact item {item_id} on {title}")
        variant = page.get("variants", {}).get(str(item_id))
        exact_variant = bool(variant and item_id in page.get("exactInfoboxItemIds", []))
        if not exact_variant:
            raise SystemExit(f"Exact ID {item_id} is not bound to a variant on {title}")
        params = variant.get("params", {})
        suffix = str(variant.get("suffix", ""))
        raw = text_bytes.decode("utf-8")
        body = get_page_body(raw)
        lead, lead_subject_matches_page = first_bold_subject_lead(body, title)
        functions = paragraph_records(body)
        # Use the pinned article's own-subject lead as the candidate's positive
        # basis. Prior shard quotes are not trusted here: comparative clauses
        # can describe a different named item on the same page.
        exact_clauses = [lead] if lead and lead_subject_matches_page else []
        access = [p for p in functions if ACCESS_CUES.search(p["literalParagraph"])]
        review_flags = source_flags(params, str(variant.get("variant", "")), body)
        candidate = {
            "itemId": item_id,
            "catalogName": packet.get("catalogName") or packet.get("registryName"),
            "currentUnchangedAssignment": {
                "category": packet["current"]["category"],
                "subcategory": packet["current"]["subcategory"],
                "ironmanTabKey": packet["current"]["ironmanTabKey"],
            },
            "candidateStatus": "root-review candidate only; unchanged-placement proposal, not approval",
            "source": {
                "title": title,
                "revision": page["revid"],
                "sha256": "sha256:" + declared_hash,
                "sourceUrl": page["sourceUrl"],
                "exactInfoboxItemIds": page.get("exactInfoboxItemIds", []),
                "reviewedIdIsExact": exact_variant,
                "localTextPath": str(text_path.relative_to(ROOT)),
            },
            "exactVariantStateFields": variant_fields(params, suffix),
            "firstOwnBoldSubjectLeadLiteral": lead,
            "leadBoldSubjectMatchesPageTitle": lead_subject_matches_page,
            "functionalClausesCitedByCandidate": exact_clauses,
            "allMaterialFunctionAndCompetingUseParagraphs": functions,
            "currentAccessParagraphs": access,
            "categorySpecificPositiveFunctionExplanation": (
                f"Candidate fit for the current TOOL/{packet['current']['subcategory']} assignment is limited to these exact-source clauses: "
                + " | ".join(exact_clauses)
            ),
            "sourceConflictFlagsForRootReview": review_flags,
            "rootHold": ROOT_HOLDS.get(item_id) or (None if lead_subject_matches_page else "The extracted first bold lead does not explicitly match the article title; verify the exact subject before relying on this page lead."),
        }
        if candidate["rootHold"]:
            holds += 1
        group_key = (title, int(page["revid"]), declared_hash)
        by_page[group_key].append(candidate)

    groups: list[dict[str, Any]] = []
    for (title, revid, article_hash), items in sorted(by_page.items()):
        groups.append({
            "sourceTitle": title,
            "sourceRevision": revid,
            "sourceHash": "sha256:" + article_hash,
            "items": sorted(items, key=lambda r: r["itemId"]),
        })
    # Every field represented as literal must occur in its exact pinned raw
    # article after whitespace-only normalization. This permits LF/CRLF
    # normalization while rejecting removed images, links, templates, or text.
    literal_failures: list[dict[str, Any]] = []
    raw_by_source = {(title, int(index[title]["revid"])): (ROOT / index[title]["path"]).read_text(encoding="utf-8") for title, _, _ in by_page}
    for group in groups:
        source_raw = normalize_whitespace(raw_by_source[(group["sourceTitle"], group["sourceRevision"])])
        for item in group["items"]:
            item_id = item["itemId"]
            excerpts = [("firstOwnBoldSubjectLeadLiteral", item.get("firstOwnBoldSubjectLeadLiteral", ""))]
            excerpts.extend((f"functionalClausesCitedByCandidate[{n}]", value) for n, value in enumerate(item.get("functionalClausesCitedByCandidate", [])))
            excerpts.extend((f"allMaterialFunctionAndCompetingUseParagraphs[{n}]", value["literalParagraph"]) for n, value in enumerate(item.get("allMaterialFunctionAndCompetingUseParagraphs", [])))
            excerpts.extend((f"currentAccessParagraphs[{n}]", value["literalParagraph"]) for n, value in enumerate(item.get("currentAccessParagraphs", [])))
            for field, excerpt in excerpts:
                if excerpt and normalize_whitespace(excerpt) not in source_raw:
                    literal_failures.append({"itemId": item_id, "field": field, "excerpt": excerpt[:240]})
    if literal_failures:
        raise SystemExit("Raw-source literal excerpt validation failed: " + json.dumps(literal_failures, ensure_ascii=False))
    jsonl_path = out_dir / "root-review-groups.jsonl"
    with jsonl_path.open("w", encoding="utf-8", newline="\n") as stream:
        for group in groups:
            stream.write(json.dumps(group, ensure_ascii=False) + "\n")

    md_path = out_dir / "README.md"
    with md_path.open("w", encoding="utf-8", newline="\n") as stream:
        stream.write("# TOOL unchanged-placement root review\n\n")
        stream.write("This packet is a source-review aid only. It makes no approvals and proposes no roles or tags. Rows remain candidates until root independently reviews the exact mechanics and assignment. Each source page is shown once per exact pinned title/revision; every item ID retains its own exact variant fields.\n\n")
        stream.write(f"Candidate IDs: {len(selected)}. Exact pinned pages: {len(groups)}. Explicit root holds included: {holds}.\n\n")
        stream.write("The source paragraphs are literal Wiki text. Parenthetical/exact-state exclusions are preserved in each ID's selected variant fields; no absent option or facet is treated as proof that a use does not exist.\n\n")
        for group in groups:
            stream.write(f"## {group['sourceTitle']} — revision {group['sourceRevision']}\n\n")
            stream.write(f"Source hash: `{group['sourceHash']}`. IDs: {', '.join(str(i['itemId']) for i in group['items'])}.\n\n")
            for item in group["items"]:
                stream.write(f"### {item['itemId']} — {item['catalogName']}\n\n")
                cur = item["currentUnchangedAssignment"]
                stream.write(f"Current candidate assignment: `{cur['category']}/{cur['subcategory']}` → `{cur['ironmanTabKey']}`. Exact ID binding: `{item['source']['reviewedIdIsExact']}`; bold lead matches page title: `{item['leadBoldSubjectMatchesPageTitle']}`.\n\n")
                if item.get("rootHold"):
                    stream.write(f"**Root hold:** {item['rootHold']}\n\n")
                stream.write("**Selected exact variant state fields:** `" + json.dumps(item["exactVariantStateFields"], ensure_ascii=False) + "`.\n\n")
                stream.write("**First own-bold subject lead, literal:**\n\n> " + (item["firstOwnBoldSubjectLeadLiteral"].replace("\n", " ") or "[No bold subject lead found]") + "\n\n")
                if item["functionalClausesCitedByCandidate"]:
                    stream.write("**Exact functional clauses cited by the candidate:**\n\n")
                    for clause in item["functionalClausesCitedByCandidate"]:
                        stream.write(f"> {clause}\n\n")
                stream.write("**Other material function/competing-use paragraphs:**\n\n")
                for paragraph in item["allMaterialFunctionAndCompetingUseParagraphs"]:
                    stream.write(f"- ({paragraph['section']}) {paragraph['literalParagraph']}\n")
                if not item["allMaterialFunctionAndCompetingUseParagraphs"]:
                    stream.write("- [No additional function paragraph extracted; full pinned page is linked below.]\n")
                if item["currentAccessParagraphs"]:
                    stream.write("\n**Current access/transport paragraphs:**\n\n")
                    for paragraph in item["currentAccessParagraphs"]:
                        stream.write(f"- ({paragraph['section']}) {paragraph['literalParagraph']}\n")
                stream.write("\n**Candidate positive-function explanation:** " + item["categorySpecificPositiveFunctionExplanation"] + "\n\n")
                if item["sourceConflictFlagsForRootReview"]:
                    stream.write("**Source conflict flags (review prompts, not conclusions):**\n\n")
                    for flag in item["sourceConflictFlagsForRootReview"]:
                        stream.write(f"- `{flag['flag']}` — {flag['basis']}\n")
                    stream.write("\n")
                stream.write(f"Pinned source: [{group['sourceTitle']} revision {group['sourceRevision']}]({item['source']['sourceUrl']}). Local source: `{item['source']['localTextPath']}`.\n\n")

    manifest = {
        "purpose": "Root review only; no semantic approvals, role/tag claims, or production edits.",
        "inputHashes": input_hashes,
        "selectedDecisionFilter": "reviewStatus == CERTIFIED (candidate unchanged placement); all rows remain pending root review",
        "candidateCount": len(selected),
        "uniquePinnedArticleCount": len(groups),
        "rootHoldCount": holds,
        "rootHoldItemIds": sorted(i for group in groups for i in [r["itemId"] for r in group["items"] if r.get("rootHold")]),
        "rawLiteralExcerptValidation": {"method": "whitespace-normalized substring match against each exact pinned raw article", "failureCount": len(literal_failures)},
        "outputs": {},
    }
    for path in (jsonl_path, md_path):
        data = path.read_bytes()
        manifest["outputs"][path.name] = {"sha256": sha256(data), "bytes": len(data)}
    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"directory": str(out_dir.relative_to(ROOT)), "candidateCount": len(selected), "articleCount": len(groups), "rootHoldCount": holds, "manifest": manifest}, indent=2))


if __name__ == "__main__":
    main()
