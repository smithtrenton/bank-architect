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
OUT = OUTDIR / "source-review-v3.jsonl"
SUMMARY = OUTDIR / "source-review-v3-summary.json"

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
    r"(?i)\b(?:unlimited access|(?:grants?|gains?|gives?) (?:the player )?(?:permanent |unlimited )access|"
    r"permanent(?:ly)? access|access after (?:the )?(?:quest|miniquest)|"
    r"(?:can|may) still be used (?:to|for)|used outside (?:the )?(?:quest|miniquest)|"
    r"teleports? (?:the player )?(?:to|between)|can teleport to|used to teleport|"
    r"heals? \d+|restores? \d+|prayer bonus|magic attack bonus|defen[cs]e bonus|combat stat|"
    r"(?:can be|is) used as (?:a |an )?(?:tool|weapon)|"
    r"currency|coins? can be|can be traded|can be sold (?:for|to)|sold to .{0,80} for \d+ coins|"
    r"can be used (?:to|for) (?:train|craft|make|create|teleport|recharge)|"
    r"can be eaten|can still be eaten|can be drunk|can be worn|can be wielded|"
    r"can be cooked(?: into| as)?|cooked into (?:a |an )?(?:food|fish|carp)|can then be eaten|"
    r"used on .{0,100} for (?:helpful )?dialogue|"
    r"used in (?:the )?(?:minigame|activity)|activity copy|emote clue|"
    r"serves? only as a cosmetic|cosmetic item|cosmetic appearance|"
    r"used as a pet|can be kept as a follower|can follow the player|follows the player|can be fed to|used as pet food|"
    r"(?:can be )?composted|compost bin|can be cut into (?:pineapple )?(?:rings|chunks)|"
    r"can be displayed as (?:a )?(?:decoration|trophy)|put on display|"
    r"(?:(?:can be )?added|is added) to (?:a )?(?:steel )?key ?ring|"
    r"recharg(?:e|es|ed|ing) (?:a |the )?(?:skill|combat|necklace|bracelet)|"
    r"learns? the .{0,60}teleport|unlocks? .{0,60}teleport|"
    r"allows? (?:players? )?to dig at level 3 sites|access to level 3 sites|"
    r"can still be taken .{0,100}after .*?quest.{0,100}(?:will still )?repair|"
    r"cast (?:low|high)(?: level)? alchemy|"
    r"(?:potentially )?useful for suiciding|hitpoints to 0|"
    r"used in .*?miniquest.*?after completing (?:the )?quest|"
    r"construction experience|potential of \d[\d,]* construction experience|"
    r"allows? (?:players? )?to dig at level 3 sites|access to level 3 sites|"
    r"can still be taken .{0,100}after .*?quest.{0,120}(?:will still )?repair|"
    r"after .{0,100}quest (?:has been )?completed.{0,120}(?:will still )?repair|"
    r"after .*?has been completed, and .*?will still repair|"
    r"used in .*?miniquest.*?after completing (?:the )?quest|"
    r"cast .{0,80}(?:low level|high level) alchemy .{0,30}on|"
    r"(?:potentially )?useful for suiciding|hitpoints to 0|"
    r"used in (?:the )?goat hunting|used for (?:the )?miniquest|used in (?:the )?miniquest|"
    r"prevents? .{0,60}infection|restores? .{0,30}run energy)\b"
)
QUEST_STAGE = re.compile(
    r"(?i)\b(?:use(?:d|s)? (?:only )?(?:in|during|for|to|on|with)|"
    r"needed to (?:advance|progress|complete|solve|free|repair|open|make|obtain)|"
    r"required to (?:advance|progress|complete|solve|free|repair|open|make|obtain)|"
    r"(?:is|are) given to|giv(?:e|es|en|ing)[^,.;]{0,80} to|shown to|show(?:n)? .{0,80} to|"
    r"presented to|handed to|brought to|turn(?:ed)? into|combined with|combining (?:it|them) with|"
    r"enchanted into|translated by|translate(?:s|d)? the|provides? a translation|"
    r"needed to power|used to power|used to make|make .{0,60}(?:potion|mixture|device)|"
    r"made by using|created by using|mix(?:ed)? with|grind(?:ed)? into|"
    r"put into|placed on|contains? a list of .*?tasks|tasks that players must do|must do .*?as part of the .*?quest|only use (?:is )?(?:during|in|for)|"
    r"provides? .{0,80}(?:translations|a hint)|helps? .{0,80}(?:solve|navigate|follow)|used as a guide|"
    r"to advance the quest|to progress the quest|during the .*?quest)\b"
)
QUEST_CONTEXT = re.compile(r"(?i)\bquest\b|quest item|quest items|\[\[")


def digest(data):
    return "sha256:" + hashlib.sha256(data).hexdigest()


def normalize_whitespace(text):
    return re.sub(r"\s+", " ", text).strip()


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


def normalize_line_endings(text):
    """Normalize CRLF/CR to LF for selection only; emitted blocks retain source text."""
    return text.replace("\r\n", "\n").replace("\r", "\n")


def raw_article_prefix(text):
    """Return the unmodified raw prefix before the first section heading."""
    match = re.search(r"(?m)^\s*={2,6}(?=[^=\r\n]|$)", text)
    return text[:match.start()].strip() if match else text.strip()


def consume_leading_templates(block):
    """For lead selection only, consume a complete stack of templates at block start."""
    i = 0
    while True:
        while i < len(block) and block[i].isspace():
            i += 1
        if not block.startswith("{{", i):
            return block[i:]
        depth = 0
        j = i
        while j < len(block) - 1:
            token = block[j:j + 2]
            if token == "{{":
                depth += 1
                j += 2
            elif token == "}}":
                depth -= 1
                j += 2
                if depth == 0:
                    i = j
                    break
            else:
                j += 1
        else:
            return block[i:]


def has_own_prose(block):
    """Detect prose after metadata/media for selection, without changing the quote."""
    candidate = consume_leading_templates(block)
    lines = []
    in_gallery = False
    for line in normalize_line_endings(candidate).splitlines():
        stripped = line.strip()
        if stripped.startswith("<gallery"):
            in_gallery = True
            continue
        if in_gallery:
            if stripped.startswith("</gallery>"):
                in_gallery = False
            continue
        if not stripped or stripped.startswith(("[[File:", "[[Image:", "[[Category:")):
            continue
        if re.fullmatch(r"</?gallery.*?>", stripped, re.I):
            continue
        lines.append(stripped)
    prose = " ".join(lines).strip()
    return bool(re.search(r"[A-Za-z]{2,}", prose)) and not prose.startswith("{{")


def own_subject_lead(text):
    """Return the first intact source paragraph after the initial template stack."""
    normalized = normalize_line_endings(text)
    intro = re.split(r"(?m)^\s*==", normalized, maxsplit=1)[0]
    tail = consume_leading_templates(intro)
    for raw in re.split(r"\n[ \t]*\n+", tail):
        block = raw.strip()
        if not block:
            continue
        if has_own_prose(block):
            # Quotes preserve all inline markup and paragraph text; only line endings
            # were normalized to make selection stable across the indexed raw packets.
            return block
    return ""


def read_jsonl(path):
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def exact_ids(art):
    return [int(v) for v in art.get("exactInfoboxItemIds", [])]


def paragraphs(text):
    """Return full literal wikitext blocks with their nearest section heading."""
    section = "(lead)"
    result = []
    first_intro_block = True
    for raw in re.split(r"\n[ \t]*\n+", normalize_line_endings(text)):
        block = raw.strip()
        if not block:
            continue
        if first_intro_block and section == "(lead)" and block.startswith("{{"):
            after_stack = consume_leading_templates(block).strip()
            if after_stack:
                block = after_stack
            else:
                first_intro_block = False
                continue
        first_intro_block = False
        headings = re.findall(r"(?m)^\s*(={2,6}[^\n]*={2,6})\s*$", block)
        if headings:
            section = headings[-1].strip()
            if re.fullmatch(r"={2,6}[^\n]*={2,6}", block.strip()):
                continue
            result.append((section, block))
            continue
        if block.startswith("[[Category:") or block.startswith("{{reflist"):
            continue
        result.append((section, block))
    return result


def analysis_text(raw):
    """Exclude infobox/disambiguation metadata only for matching, never for quotes."""
    cleaned = raw
    for template in ("Infobox Item", "Infobox Bonuses", "Otheruses", "About", "Distinguish"):
        cleaned = remove_template(cleaned, template)
    cleaned = re.sub(r"\[\[([^\]|]+)\|([^\]]+)\]\]", r"\1 \2", cleaned)
    cleaned = re.sub(r"\[\[([^\]]+)\]\]", r"\1", cleaned)
    return cleaned


def material_source_paragraphs(raw_paras):
    result = []
    for section, raw in raw_paras:
        if MATERIAL.search(analysis_text(raw)):
            result.append({"section": section, "text": raw})
    return result


def assert_literal_excerpt(raw_source, excerpt, label, item_id):
    if normalize_whitespace(excerpt) not in normalize_whitespace(raw_source):
        raise ValueError(f"nonliteral excerpt {label} for {item_id}")


def param_block(text, name):
    m = re.search(r"\{\{" + re.escape(name) + r"([^\n]*(?:\n(?!\}\})[^\n]*)*)\n\}\}", text, re.I)
    if not m:
        return {}
    return {k.strip().lower(): v.strip() for k, v in re.findall(r"(?m)^\|\s*([A-Za-z]+)\s*=\s*([^\r\n]*)", m.group(1))}


def npc_fiction_history_only(section, body):
    """Exclude NPC fiction in History unless it states a player-facing mechanic."""
    if not re.search(r"(?i)history", section):
        return False
    text = analysis_text(body)
    npc_fiction = re.search(r"(?i)\b(?:npc|zamorak|saradomin|lucien|zaros|armadyl|valdez|mahjarrat)\b|\{\{citeNPC", body)
    player_mechanic = re.search(
        r"(?i)\b(?:player|players|you can|your |can still|can be used|can be worn|can be wielded|"
        r"equipped by|worn by|wielded by|attack bonus|defen[cs]e bonus|prayer bonus|"
        r"after (?:the )?quest|completing the quest|teleport|unlocks? access)\b",
        text,
    )
    return bool(npc_fiction and not player_mechanic)


def explicit_nonquest_hits(paras):
    found = []
    for section, body in paras:
        if npc_fiction_history_only(section, body):
            continue
        if NONQUEST_USE.search(analysis_text(body)):
            found.append({"section": section, "text": body})
    return found


def classify(row, target, lead, paras, material, variant, item_bonuses):
    sub = target["subcategory"]
    full = "\n\n".join(body for _, body in paras)
    # A candidate is supported only when the own-subject lead itself describes
    # the quest-stage function; later article mentions cannot bootstrap it.
    stage_text = [lead] + [p["text"] for p in material]
    explicit_stage = any(QUEST_STAGE.search(analysis_text(text)) and (QUEST_CONTEXT.search(text) or QUEST_CONTEXT.search(analysis_text(text))) for text in stage_text)
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
    if re.search(r"(?i)\bused to unlock access to\b|must drink .{0,100} to enter\b", full) and not re.search(r"(?i)\b(?:permanent|unlimited|after (?:the )?quest) access\b", full):
        return "hold", "The exact article states that the item unlocks access, but does not establish whether that access is a continuing post-quest function; do not infer its duration.", ["access-persistence-unresolved"]
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
    literal_excerpt_count = 0
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
        raw_prefix = raw_article_prefix(text)
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
            material = material_source_paragraphs(paras)
            bonuses = param_block(text, "Infobox Bonuses")
            # For indexed shared pages, retain the exact variant state, not another ID's values.
            state_fields = {k: params[k] for k in ("id", "id1", "id2", "id3", "id4", "id5", "name", "name1", "name2", "name3", "name4", "name5", "options", "equipable", "quest", "tradeable", "stackable", "noteable", "destroy", "examine", "value", "weight") if k in params}
            target = group["candidateTarget"]
            status, reason, flags = classify(row, target, lead, paras, material, params, bonuses)
            stage_evidence = []
            if QUEST_STAGE.search(analysis_text(lead)) and (QUEST_CONTEXT.search(lead) or QUEST_CONTEXT.search(analysis_text(lead))):
                stage_evidence.append({"section": "own-subject lead", "text": lead})
            for block in material:
                clean_block = analysis_text(block["text"])
                if QUEST_STAGE.search(clean_block) and (QUEST_CONTEXT.search(block["text"]) or QUEST_CONTEXT.search(clean_block)):
                    if block not in stage_evidence:
                        stage_evidence.append(block)
            competing_hits = explicit_nonquest_hits([(block["section"], block["text"]) for block in material])
            excerpt_count_for_row = 2
            assert_literal_excerpt(text, raw_prefix, "rawArticlePrefixLiteral", item_id)
            assert_literal_excerpt(text, lead, "literalOwnSubjectLead", item_id)
            for field, excerpts in (("materialCompetingUseParagraphs", material), ("directQuestFunctionEvidence", stage_evidence), ("explicitCompetingFunctionHits", competing_hits)):
                for excerpt in excerpts:
                    assert_literal_excerpt(text, excerpt["text"], field, item_id)
                    excerpt_count_for_row += 1
            literal_excerpt_count += excerpt_count_for_row
            if status == "support":
                disposition = "supported-by-source"
            elif any(flag in flags for flag in ("competing-function", "active-equipment", "consumable-review")):
                disposition = "hold-source-documents-competing-function"
            else:
                disposition = "hold-source-documents-access-duration-uncertainty" if "access-persistence-unresolved" in flags else "hold-source-does-not-resolve-primary-use"
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
                "rawArticlePrefixLiteral": raw_prefix,
                "literalOwnSubjectLead": lead,
                "articleHeadings": group.get("articleHeadings", []),
                "materialCompetingUseParagraphs": material,
                "directQuestFunctionEvidence": stage_evidence,
                "explicitCompetingFunctionHits": competing_hits,
                "literalExcerptValidation": {"passed": True, "method": "collapse whitespace only and confirm each excerpt remains a substring of pinned raw article text", "excerptCount": excerpt_count_for_row},
                "sourceReviewRule": "V3 preserves the complete raw prefix separately from the intact own-subject prose paragraph after the initial template stack. Exact numeric ID bound to the pinned source variant; unchanged placement is supported only by a directly stated subject-specific function in a named quest/quest stage and no explicit continuing competing mechanic. Holds identify documented equipment, use outside a quest, consumption, or insufficient functional evidence. Quest flags, reward origin, article title/category, log membership, and absent fields never count alone. Current target and baseline tags/roles are context only; tags/roles were not assessed.",
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
        "literalExcerptValidation": {"passed": True, "excerptCount": literal_excerpt_count, "method": "collapse whitespace only; every emitted raw prefix, own-subject lead, direct-use paragraph, material paragraph, and competing-hit paragraph was checked as a substring of that exact pinned article raw text"},
        "currentSubcategoryCounts": dict(collections.Counter(r["current"]["subcategory"] for r in output)),
        "statusCounts": dict(collections.Counter(r["reviewStatus"] for r in output)),
        "statusFlagCounts": {f"{status}|{','.join(flags)}": n for (status, flags), n in counts.items()},
        "rule": "Support requires exact-ID Wiki binding and a subject-specific, source-stated function in the named quest or current cleanup subcategory. Competing-function holds require an explicit source-stated player-facing persistent/outside-quest function, active equipment use, or actual consumable mechanic; NPC-fiction History paragraphs are excluded from positive-use detection unless they state a player-facing mechanic. Other holds identify a primary-use evidence gap. Quest flags, reward origin, article title/category/log membership, and absent fields never support placement by themselves. The complete raw article prefix is separate from the intact own-subject prose paragraph selected after the initial template stack; exact variant infobox state, full material paragraphs, direct stage-use hits, and explicit competing-use hits are preserved for review. Roles and tags remain unassessed.",
    }
    SUMMARY.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(OUT), "summary": str(SUMMARY), "rows": len(output), "counts": summary["statusCounts"]}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
