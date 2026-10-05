#!/usr/bin/env python3
"""Build an exact-ID, full-source review packet for unchanged cleanup-quest candidates."""
import collections
import hashlib
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
INPUT = ROOT / "tmp/category-certification/reviews/candidate-group-packet.jsonl"
INDEX = ROOT / "tmp/category-certification/wiki-articles/article-index.json"
OUTDIR = ROOT / "tmp/category-certification/reviews/cleanup-quest"
OUT = OUTDIR / "source-review.jsonl"
SUMMARY = OUTDIR / "source-review-summary.json"

MATERIAL = re.compile(
    r"(?i)\b(?:quest|used?|using|useful|require[sd]?|needed?|obtain(?:ed|able)?|"
    r"acquir(?:e|ed|able)|reward|complete[sd]?|after|before|during|only|outside|"
    r"post.?quest|wield|wear|equip(?:ped|ment)?|attack|combat|defen[cs]|prayer|"
    r"heal(?:s|ed)?|restore[sd]?|drink|eat(?:en|ing)?|consum(?:e|ed|able)|"
    r"teleport|access|unlock|open(?:s|ed)?|enter|exit|tool|weapon|armou?r|"
    r"skill|coins?|currency|exchange|sell|shop|purchase|buy|grant|unlock|"
    r"permanent|emote|cosmetic|appearance|pet|follow|store|bank|drop|destroy|"
    r"reobtain|read|book|letter|note|map|spell|ability|transform|craft|make|"
    r"combine|repair|charge|activate|release|bury|play|look|inspect|lore|"
    r"quest item|activity|minigame|collection log)\b"
)
NONQUEST_USE = re.compile(
    r"(?i)\b(?:unlimited access|gain(?:s|ed)? access after|permanent(?:ly)? access|"
    r"after (?:the )?(?:quest|miniquest) (?:is )?(?:complete[sd]?|finished)|"
    r"after completing (?:the )?(?:quest|miniquest)|post.?quest|can still|"
    r"continues? to|used outside|outside (?:the )?(?:quest|miniquest)|"
    r"teleport(?:s|ation)?|heals? \d+|restores? \d+|prayer bonus|"
    r"magic attack bonus|defen[cs]e bonus|combat stat|used as (?:a |an )?(?:tool|weapon)|"
    r"access after (?:the )?(?:quest|miniquest)|currency|coins? can be|"
    r"can be traded|can be sold|can be used (?:to|for) (?:train|craft|make|create|teleport)|"
    r"can be eaten|can be drunk|can be worn|can be wielded|used in other quests?|"
    r"used in (?:the )?(?:minigame|activity)|minigame|activity copy|emote clue|"
    r"cosmetic|appearance|follower|pet|post.?quest (?:use|function|benefit)|"
    r"compost|can be cut into|can be used as (?:food|a food)|"
    r"display(?:ed)? (?:in|at)|display case|unlocks? access to)\b"
)
QUEST_STAGE = re.compile(
    r"(?i)\b(?:use(?:d|s)? (?:only )?(?:in|during|for|to|on|with)|"
    r"needed to (?:advance|progress|complete|solve|free|repair|open|make|obtain)|"
    r"required to (?:advance|progress|complete|solve|free|repair|open|make|obtain)|"
    r"(?:is|are) given to|give[sn]? .{0,80} to|shown to|show(?:n)? .{0,80} to|"
    r"presented to|handed to|brought to|turn(?:ed)? into|combined with|"
    r"made by using|created by using|mix(?:ed)? with|grind(?:ed)? into|"
    r"put into|placed on|to advance the quest|to progress the quest|during the .*?quest)\b"
)
QUEST_CONTEXT = re.compile(r"(?i)\bquest\b|quest item|quest items|\[\[")


def digest(data):
    return "sha256:" + hashlib.sha256(data).hexdigest()


def remove_template(text, name):
    """Remove a balanced named template, including nested templates."""
    pattern = re.compile(r"\{\{\s*" + re.escape(name) + r"\b", re.I)
    out = text
    while match := pattern.search(out):
        depth = 0
        i = match.start()
        end = len(out)
        while i < len(out) - 1:
            token = out[i:i + 2]
            if token == "{{":
                depth += 1
                i += 2
            elif token == "}}":
                depth -= 1
                i += 2
                if depth == 0:
                    end = i
                    break
            else:
                i += 1
        out = out[:match.start()] + "\n" * out[match.start():end].count("\n") + out[end:]
    return out


def own_subject_lead(text):
    """Return literal prose after leading source templates and image lines."""
    intro = re.split(r"(?m)^\s*==", text, maxsplit=1)[0]
    lines = intro.replace("\r\n", "\n").splitlines()
    kept, started, depth = [], False, 0
    for line in lines:
        stripped = line.strip()
        if depth:
            depth += line.count("{{") - line.count("}}")
            continue
        if not started and stripped.startswith("{{"):
            depth = line.count("{{") - line.count("}}")
            continue
        if not stripped:
            if started:
                kept.append("")
            continue
        if stripped.startswith(("[[File:", "[[Image:", "<gallery", "</gallery>", "[[Category:")):
            continue
        if stripped.startswith("{{") and stripped.endswith("}}"):
            continue
        started = True
        kept.append(line)
    lead = "\n".join(kept).strip()
    lead = remove_template(lead, "Otheruses")
    return lead.strip()


def read_jsonl(path):
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def exact_ids(art):
    return [int(v) for v in art.get("exactInfoboxItemIds", [])]


def paragraphs(text):
    """Return full literal wikitext blocks with their nearest section heading."""
    section = "(lead)"
    result = []
    for raw in re.split(r"\n\s*\n", text.replace("\r\n", "\n")):
        block = raw.strip()
        if not block:
            continue
        headings = re.findall(r"(?m)^\s*(={2,6}[^\n]*={2,6})\s*$", block)
        if headings:
            section = headings[-1].strip()
            body = re.sub(r"(?m)^\s*={2,6}[^\n]*={2,6}\s*$", "", block).strip()
            if body:
                result.append((section, body))
            continue
        if block.startswith("[[Category:") or block.startswith("{{reflist"):
            continue
        result.append((section, block))
    return result


def param_block(text, name):
    m = re.search(r"\{\{" + re.escape(name) + r"([^\n]*(?:\n(?!\}\})[^\n]*)*)\n\}\}", text, re.I)
    if not m:
        return {}
    return {k.strip().lower(): v.strip() for k, v in re.findall(r"(?m)^\|\s*([A-Za-z]+)\s*=\s*([^\r\n]*)", m.group(1))}


def explicit_nonquest_hits(paras):
    found = []
    for section, body in paras:
        if NONQUEST_USE.search(body):
            found.append({"section": section, "text": body})
    return found


def classify(row, target, lead, paras, material, variant, item_bonuses):
    sub = target["subcategory"]
    full = "\n\n".join(body for _, body in paras)
    # A candidate is supported only when the own-subject lead itself describes
    # the quest-stage function; later article mentions cannot bootstrap it.
    stage_text = [lead] + [p["text"] for p in material]
    explicit_stage = any(QUEST_STAGE.search(text) and QUEST_CONTEXT.search(text) for text in stage_text)
    nonquest = explicit_nonquest_hits([(p["section"], p["text"]) for p in material])
    options = str(variant.get("options", ""))
    active_bonus = any(v.strip().lstrip("+-") not in {"", "0", "0.0", "0.00"} for k, v in item_bonuses.items() if k != "slot")
    if sub == "burnt-food":
        if re.search(r"(?i)no use whatsoever|has no use|cannot be used", full):
            return "support", "Exact own article describes the burned result and explicitly says it has no use; current burnt-food cleanup grouping matches that direct statement.", ["burnt-food-no-use"]
        return "hold", "Burnt-food placement lacks an explicit no-use statement in the acquired full article.", ["needs-source-review"]
    if sub == "readable-lore":
        if ("Read" in options or "Study" in options) and any(re.search(r"(?i)transcript|story|history|lore|written|read", p["text"]) for p in material):
            return "support", "Exact variant has a reading/study action and the acquired article documents readable text/lore; no further role or tag is assessed.", ["readable-lore"]
        return "hold", "Readable-lore placement is not established by an exact source statement and active read/study state.", ["needs-source-review"]
    if sub == "junk":
        if re.search(r"(?i)no use whatsoever|has no use|cannot be used", full):
            return "support", "Exact own article explicitly says the item has no use; current junk cleanup grouping is source-supported.", ["explicit-no-use"]
        return "hold", "Junk placement lacks an exact source statement of no use.", ["needs-source-review"]
    if nonquest:
        return "hold", "Full article contains a direct competing/persistent mechanic or alternate primary purpose; quest flags or reward origin do not establish quest-item placement.", ["competing-function"]
    if active_bonus or str(variant.get("equipable", "")).lower() == "yes" or re.search(r"(?i)\b(?:Wear|Wield|Equip)\b", options):
        return "hold", "Exact item has active wearable/equipment state or nonzero bonus evidence; require primary-function review even though it is quest-associated.", ["active-equipment"]
    if not explicit_stage:
        return "hold", "The full exact-ID page does not directly establish an in-quest stage function; quest flags, acquisition timing, and candidate-group wording alone are insufficient.", ["stage-function-not-established"]
    return "support", "Exact own-subject article describes a concrete named quest-stage use, and the full article review found no explicit competing persistent/non-quest mechanic; this supports the unchanged quest-item placement without relying on quest flags or missing fields.", ["explicit-quest-stage-use"]


def main():
    groups = [g for g in read_jsonl(INPUT) if g.get("shard") == "cleanup-quest" and g.get("status") == "candidate unchanged placement"]
    index = json.loads(INDEX.read_text(encoding="utf-8"))
    pages = {title: art for title, art in index.items()}
    output = []
    seen = set()
    for group in groups:
        title = group["sourceTitle"]
        if title not in pages:
            raise ValueError(f"missing indexed page {title}")
        art = pages[title]
        text_path = ROOT / art["path"]
        raw_bytes = text_path.read_bytes()
        if digest(raw_bytes) != "sha256:" + art["sha256"]:
            raise ValueError(f"raw article hash mismatch: {title}")
        text = raw_bytes.decode("utf-8")
        if int(art["revid"]) != int(group["sourceRevision"]):
            raise ValueError(f"pinned revision mismatch: {title}")
        if "sha256:" + art["sha256"] != group["sourceHash"]:
            raise ValueError(f"pinned hash mismatch: {title}")
        paras = paragraphs(text)
        for row in group["rows"]:
            item_id = int(row["itemId"])
            if item_id in seen:
                raise ValueError(f"duplicate ID {item_id}")
            seen.add(item_id)
            variant = art.get("variants", {}).get(str(item_id), {})
            params = variant.get("params", {})
            id_fields = [{"field": k, "value": v} for k, v in params.items() if re.fullmatch(r"id\d*", k, re.I) and str(v).isdigit() and int(v) == item_id]
            if item_id not in exact_ids(art) or not id_fields:
                raise ValueError(f"exact numeric ID not bound in selected page variant: {item_id} / {title}")
            if int(params.get("id", item_id)) != item_id and not any(int(f["value"]) == item_id for f in id_fields):
                raise ValueError(f"variant ID mismatch: {item_id}")
            # Packet lead must be literally present in the pinned raw page; then preserve it intact.
            lead = own_subject_lead(text)
            clean_text = remove_template(remove_template(text, "Infobox Item"), "Infobox Bonuses")
            source_paras = paragraphs(clean_text)
            material = [{"section": sec, "text": block} for sec, block in source_paras if MATERIAL.search(block)]
            bonuses = param_block(text, "Infobox Bonuses")
            # For indexed shared pages, retain the exact variant state, not another ID's values.
            state_fields = {k: params[k] for k in ("id", "id1", "id2", "id3", "id4", "id5", "name", "name1", "name2", "name3", "name4", "name5", "options", "equipable", "quest", "tradeable", "stackable", "noteable", "destroy", "examine", "value", "weight") if k in params}
            target = group["candidateTarget"]
            status, reason, flags = classify(row, target, lead, paras, material, params, bonuses)
            stage_evidence = []
            if QUEST_STAGE.search(lead) and QUEST_CONTEXT.search(lead):
                stage_evidence.append({"section": "own-subject lead", "text": lead})
            for block in material:
                if QUEST_STAGE.search(block["text"]) and QUEST_CONTEXT.search(block["text"]):
                    if block not in stage_evidence:
                        stage_evidence.append(block)
            competing_hits = [block for block in material if NONQUEST_USE.search(block["text"])]
            if status == "support":
                disposition = "supported-by-source"
            elif any(flag in flags for flag in ("competing-function", "active-equipment", "consumable-review")):
                disposition = "hold-source-documents-competing-function"
            else:
                disposition = "hold-source-does-not-resolve-primary-use"
            output.append({
                "itemId": item_id,
                "name": row["name"],
                "groupId": group["groupId"],
                "reviewStatus": status,
                "reviewDisposition": disposition,
                "reviewFlags": flags,
                "reason": reason,
                "current": row["current"],
                "candidateTarget": target,
                "auditScope": row.get("auditScope"),
                "exactSource": {
                    "sourceTitle": title,
                    "sourceRevision": art["revid"],
                    "source": art.get("sourceUrl"),
                    "sourceHash": "sha256:" + art["sha256"],
                    "exactInfoboxIdFields": id_fields,
                    "variant": variant.get("variant"),
                    "suffix": variant.get("suffix"),
                    "variantState": state_fields,
                    "exactInfoboxItemIds": exact_ids(art),
                    "rawArticlePath": art["path"],
                    "rawArticleBytes": len(raw_bytes),
                },
                "literalOwnSubjectLead": lead.strip(),
                "articleHeadings": group.get("articleHeadings", []),
                "materialCompetingUseParagraphs": material,
                "directQuestFunctionEvidence": stage_evidence,
                "explicitCompetingFunctionHits": competing_hits,
                "sourceReviewRule": "Exact numeric ID bound to the pinned source variant; unchanged placement is supported only by a directly stated subject-specific function in a named quest/quest stage and no explicit continuing competing mechanic. Holds identify documented equipment, use outside a quest, consumption, or insufficient functional evidence. Quest flags, reward origin, article title/category, log membership, and absent fields never count alone. Current target and baseline tags/roles are context only; tags/roles were not assessed.",
                "bonusTemplateFacts": bonuses,
                "candidateFunctionClauses": group.get("exactFunctionClauses", []),
                "baselineRoles": row.get("baselineRoles"),
                "baselineTags": row.get("baselineTags"),
                "rolesTagsAssessment": "unassessed",
            })
    if len(output) != 484 or len(seen) != 484:
        raise ValueError(f"expected exactly 484 unique unchanged rows; got {len(output)} rows/{len(seen)} IDs")
    output.sort(key=lambda r: r["itemId"])
    OUTDIR.mkdir(parents=True, exist_ok=True)
    OUT.write_text("\n".join(json.dumps(r, ensure_ascii=False, separators=(",", ":")) for r in output) + "\n", encoding="utf-8")
    counts = collections.Counter((r["reviewStatus"], tuple(r["reviewFlags"])) for r in output)
    summary = {
        "schema": 1,
        "status": "independent source-review proposal; not root-approved",
        "inputs": {
            "candidatePacket": {"path": str(INPUT.relative_to(ROOT)), "sha256": digest(INPUT.read_bytes())},
            "articleIndex": {"path": str(INDEX.relative_to(ROOT)), "sha256": digest(INDEX.read_bytes())},
        },
        "output": {"path": str(OUT.relative_to(ROOT)), "sha256": digest(OUT.read_bytes())},
        "rowCount": len(output),
        "uniqueIds": len(seen),
        "currentSubcategoryCounts": dict(collections.Counter(r["current"]["subcategory"] for r in output)),
        "statusCounts": dict(collections.Counter(r["reviewStatus"] for r in output)),
        "statusFlagCounts": {f"{status}|{','.join(flags)}": n for (status, flags), n in counts.items()},
        "rule": "Support requires exact-ID Wiki binding and a subject-specific, source-stated function in the named quest or current cleanup subcategory. Competing-function holds require an explicit source-stated persistent/outside-quest function, active equipment use, or actual consumable mechanic; other holds identify a primary-use evidence gap. Quest flags, reward origin, article title/category/log membership, and absent fields never support placement by themselves. Exact prose lead, exact variant infobox state, full material paragraphs, direct stage-use hits, and explicit competing-use hits are preserved for review. Roles and tags remain unassessed.",
    }
    SUMMARY.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(OUT), "summary": str(SUMMARY), "rows": len(output), "counts": summary["statusCounts"]}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
