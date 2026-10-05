#!/usr/bin/env python3
"""Build a read-only exact-source review packet for residual CLUE/UNIQUE rows."""
import collections
import hashlib
import importlib.util
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
PACKET = ROOT / "tmp/category-certification/reviewer-packets/clue-unique.jsonl"
DECISIONS = ROOT / "tmp/category-certification/reviews/collections/clue-unique-corrected.jsonl"
CLUE = ROOT / "tmp/category-certification/reviews/root-clue-scrolls/decisions.jsonl"
ROOT_APPROVED = ROOT / "tmp/category-certification/root-approved-decisions-with-clue-scrolls.jsonl"
INDEX = ROOT / "tmp/category-certification/wiki-articles/article-index.json"
OUTDIR = ROOT / "tmp/category-certification/reviews/collections/residual-source-review-v1"
OUT = OUTDIR / "decisions.jsonl"
SUMMARY = OUTDIR / "summary.json"
GEAR_VERIFY = ROOT / "tools/research/semantic-grouping-audit/certification/verify-gear-bonus-sources.py"

spec = importlib.util.spec_from_file_location("gear_verify", GEAR_VERIFY)
gear_verify = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gear_verify)

FUNCTION_RE = re.compile(r"(?i)\b(?:used|use|opens?|opening|contains?|unlocks?|unlock|allows?|allow|can be|can follow|follows? the player|is a clue|equipable|equipped|worn|wear|wield|display|mounted|stuffed|restored|combine|created|crafted|required to|enhance|decorative|cosmetic|protect|summon|consume|consumed|reward bag|reward chest|chest opens|key opens|charges|follower|pet companion|read|study|teleport|access|bonus|stat|turn(?:ed)? into|transform|appearance|costume|kit|upgrade)\b")
COSMETIC_RE = re.compile(r"(?i)\b(?:cosmetic|appearance|fashion|costume|outfit|ornament(?:ation)?|emote|decorative|no combat bonuses|purely for looks)\b")
DISPLAY_RE = re.compile(r"(?i)\b(?:can be stuffed|stuffed by|mounted (?:in|on)|mount(?:ed)? (?:in|on)|displayed (?:in|as|on)|put on display|display as (?:a )?trophy|trophy case|taxiderm(?:y|ist)|construction room.*?(?:trophy|mounted)|mounted in the (?:quest )?hall)\b")
PET_RE = re.compile(r"(?i)\b(?:can be summoned|summon(?:ed)? as|can follow the player|follows the player|pet companion|is a pet|pet version|adult pet|puppy|morph(?:s|ed)? into|transmog(?:s|ged)? into)\b")
CONTAINER_RE = re.compile(r"(?i)\b(?:can be opened|open(?:ing)? (?:the |this )?(?:container|chest|casket|box|crate|bag|coffer)|search(?:ed)? to receive|contains? (?:a|an|the|random|various)|contents? (?:include|are)|open(?:s)? to reveal|reward(?:s)? from opening)\b")
KEY_RE = re.compile(r"(?i)\b(?:key opens|opens? the [^.;]{0,100}(?:chest|door|gate|room|vault|lair)|used to (?:open|unlock|enter)|grants? access|allows? entry|access to the [^.;]{0,100}(?:boss|lair|vault|chest|room))\b")
UPGRADE_RE = re.compile(r"(?i)\b(?:upgrade(?:s|d)?|imbue(?:s|d)?|charge(?:s|d)?|recharge(?:s|d)?|combine(?:s|d)? with|used to create|turn(?:s|ed)? .*? into|used on .*? to (?:make|create|upgrade|charge|imbue)|can be attached|used to enhance)\b")
READ_RE = re.compile(r"(?i)\b(?:read|reading|study|written|text reads|book contains|lore|story|letter|journal|diary|note says|transcript)\b")
FOOD_RE = re.compile(r"(?i)\b(?:can be eaten|can be drunk|eaten to|heals? \d+|restores? \d+|can be cooked|cooked into|edible|food item|eat option)\b")
TOOL_RE = re.compile(r"(?i)\b(?:used to (?:cut|mine|fish|catch|dig|light|repair|craft|smelt|fletch|brew|mix|make|create)|used as (?:a |an )?(?:tool|weapon)|tool for|allows? players? to|used with .*? to (?:cut|mine|fish|dig|repair|craft)|provides? access|teleports? the player|unlocks? the .*? teleport)\b")
NPC_RE = re.compile(r"(?i)\b(?:npc|zamorak|saradomin|lucien|zaros|armadyl|valdez|mahjarrat)\b|\{\{citeNPC")
PLAYER_MECH_RE = re.compile(r"(?i)\b(?:player|players|you can|your |can still|can be used|can be worn|can be wielded|equipped by|worn by|wielded by|attack bonus|defen[cs]e bonus|prayer bonus|after (?:the )?quest|completing the quest|teleport|unlocks? access)\b")
POLICY_HOLIDAY_RE = re.compile(r"(?i)\b(?:Halloween|Christmas|Easter|holiday|seasonal event|Hallowe'en|birthday event)\b")
ACTIVITY_RE = re.compile(r"(?i)\b(?:Castle Wars|Barbarian Assault|Pest Control|Fight Pits|TzHaar Fight Cave|Last Man Standing|minigame|activity-only|during (?:the )?activity|in the arena)\b")
CLUE_FUNCTION_RE = re.compile(r"(?i)\b(?:used to solve (?:a |the )?clue|used in (?:a |the )?clue step|clue step|emote clue requirement|used to follow the clue|used to complete (?:a |the )?treasure trail|treasure trails (?:clue|step) tool)\b")
RELIC_FUNCTION_RE = re.compile(r"(?i)\b(?:relic|relics)\b.{0,100}\b(?:salvag(?:e|ed|ing)|excavat(?:e|ed|ion)|recover(?:ed|ing))\b|\b(?:salvag(?:e|ed|ing)|excavat(?:e|ed|ion)|recover(?:ed|ing))\b.{0,100}\b(?:relic|relics)\b")
QUEST_FLAG_RE = re.compile(r"(?i)\bquest\b|\[\[(?:[A-Za-z '()]+ )?quest\]\]")
MATERIAL_RE = re.compile(r"(?i)\b(?:quest|player|players|used|use|only|after|during|worn|wear|wield|open|contain|unlock|access|reward|obtain|cosmetic|appearance|pet|stuff|mount|display|trophy|read|study|book|note|teleport|charge|upgrade|consume|eat|drink|food|emote|stat|bonus|tool|activity|minigame|combat|defen[cs]e|prayer|clue)\b")


def read_jsonl(path):
    return [json.loads(x) for x in path.read_text(encoding="utf-8").splitlines() if x.strip()]


def sha_bytes(data):
    return "sha256:" + hashlib.sha256(data).hexdigest()


def sha_file(path):
    return sha_bytes(path.read_bytes())


def norm(text):
    return re.sub(r"\s+", " ", text).strip()


def line_endings(text):
    return text.replace("\r\n", "\n").replace("\r", "\n")


def consume_templates(block):
    i = 0
    while True:
        while i < len(block) and block[i].isspace():
            i += 1
        if not block.startswith("{{", i):
            return block[i:]
        depth = 0
        j = i
        while j < len(block) - 1:
            if block.startswith("{{", j):
                depth += 1
                j += 2
            elif block.startswith("}}", j):
                depth -= 1
                j += 2
                if depth == 0:
                    i = j
                    break
            else:
                j += 1
        else:
            return block[i:]


def own_lead(text):
    intro = re.split(r"(?m)^\s*==", line_endings(text), maxsplit=1)[0]
    tail = consume_templates(intro)
    for block in re.split(r"\n[ \t]*\n+", tail):
        block = block.strip()
        if not block:
            continue
        probe = analysis_text(consume_templates(block))
        visible = [x.strip() for x in probe.splitlines() if x.strip() and not x.strip().startswith("[[Category:")]
        if any(re.search(r"[A-Za-z]{2,}", x) for x in visible):
            return block
    return ""


def source_paragraphs(text):
    section = "(lead)"
    out = []
    first = True
    normalized = line_endings(text)
    for raw in re.split(r"\n[ \t]*\n+", normalized):
        block = raw.strip()
        if not block:
            continue
        if first and block.startswith("{{"):
            after = consume_templates(block).strip()
            if not after:
                first = False
                continue
            block = after
        first = False
        headings = re.findall(r"(?m)^\s*(={2,6}[^\n]*={2,6})\s*$", block)
        if headings:
            section = headings[-1].strip()
            if re.fullmatch(r"={2,6}[^\n]*={2,6}", block):
                continue
        if block.startswith(("[[Category:", "{{reflist")):
            continue
        if re.fullmatch(r"\[\[Category:[^]]+\]\]", block):
            continue
        out.append({"section": section, "text": block})
    return out


def exact_binding(params, item_id):
    return [{"field": k, "value": v} for k, v in params.items()
            if re.fullmatch(r"id\d*", str(k), re.I) and str(v).strip().isdigit() and int(str(v).strip()) == item_id]


def select_variant_fields(params, item_id):
    ids = exact_binding(params, item_id)
    if len(ids) != 1:
        return {}, {}
    id_field = ids[0]["field"]
    suffix = re.fullmatch(r"id([0-9]*)", id_field, re.I).group(1)
    bases = ("id", "version", "name", "image", "options", "equipable", "quest", "tradeable", "bankable", "stackable", "noteable", "destroy", "examine", "value", "weight", "alchable", "members", "exchange")
    selected, raw_keys = {}, {}
    for base in bases:
        candidate = f"{base}{suffix}"
        key = candidate if candidate in params else base if base in params else None
        if key is not None:
            selected[base] = params[key]
            raw_keys[base] = key
    selected["numericIdField"] = id_field
    raw_keys["numericId"] = id_field
    return selected, raw_keys


def article_pages(byid, item_id, evidence):
    candidates = byid.get(item_id, [])
    preferred = []
    for e in evidence:
        for title, art in candidates:
            if title == e.get("sourceTitle") and str(art.get("revid")) == str(e.get("sourceRevision")) and "sha256:" + art.get("sha256", "") == e.get("sourceHash"):
                preferred.append((title, art))
    if len(preferred) == 1:
        return preferred, "matched_previous_pinned_exact_page"
    if not candidates:
        return [], "no_exact_infobox_id_in_index"
    if len(candidates) == 1:
        return candidates, "one_exact_infobox_id_page"
    return candidates, "multiple_exact_infobox_id_pages"


def bonus_facts(text, suffix):
    found = []
    stat_keys = set(gear_verify.STAT_FIELDS.values()) | {"slot"}
    for raw in gear_verify.iter_templates(text):
        name, fields, duplicates = gear_verify.parse_template(raw)
        if name not in {"infobox bonuses", "infobox bonus"}:
            continue
        values = {}
        for key in stat_keys:
            pair = gear_verify.suffix_param(fields, key, suffix)
            if pair:
                values[pair[0]] = pair[1]
        if values:
            found.append({"template": raw, "fields": values, "duplicateKeys": duplicates})
    return found


def bonus_summary(bonuses):
    totals, positive, negative = [], [], []
    for block in bonuses:
        for key, value in block["fields"].items():
            if key == "slot":
                continue
            number = gear_verify.source_number(value)
            if number is not None and number != 0:
                fact = {"field": key, "value": value}
                totals.append(fact)
                (positive if number > 0 else negative).append(fact)
    slots = [b["fields"].get("slot") for b in bonuses if b["fields"].get("slot")]
    return {"nonzeroFields": totals, "positiveFields": positive, "negativeFields": negative, "slots": slots, "hasExplicitZeroBonusTemplate": bool(bonuses) and not totals}


def analysis_text(raw):
    """Remove templates/comments/refs only for classification; raw quotes stay intact."""
    text = re.sub(r"<!--.*?-->", " ", raw, flags=re.S)
    text = re.sub(r"<ref\b[^>]*>.*?</ref>", " ", text, flags=re.I | re.S)
    text = re.sub(r"<ref\b[^>]*/>", " ", text, flags=re.I)
    out = []
    i = 0
    while i < len(text):
        if text.startswith("{{", i):
            depth = 0
            j = i
            while j < len(text) - 1:
                if text.startswith("{{", j):
                    depth += 1
                    j += 2
                elif text.startswith("}}", j):
                    depth -= 1
                    j += 2
                    if depth == 0:
                        break
                else:
                    j += 1
            i = j + 1
        else:
            out.append(text[i])
            i += 1
    text = "".join(out)
    text = re.sub(r"\[\[([^]|]+)\|([^]]+)\]\]", r"\1 \2", text)
    text = re.sub(r"\[\[([^]]+)\]\]", r"\1", text)
    text = re.sub(r"\[\[(?:File|Image|Category):[^]]*\]\]", " ", text, flags=re.I)
    return text


def material_contexts(paras):
    return [{"section": p["section"], "text": p["text"]} for p in paras if MATERIAL_RE.search(analysis_text(p["text"]))]


def semantic_contexts(paras):
    result = []
    for p in paras:
        text = p["text"]
        analysis = analysis_text(text)
        signals = []
        for label, regex in (("cosmetic_or_appearance", COSMETIC_RE), ("trophy_display", DISPLAY_RE), ("companion_or_pet", PET_RE), ("openable_container", CONTAINER_RE), ("key_access", KEY_RE), ("upgrade_or_charge", UPGRADE_RE), ("readable_text", READ_RE), ("food_or_consumable", FOOD_RE), ("tool_or_persistent_utility", TOOL_RE), ("clue_solving_function", CLUE_FUNCTION_RE), ("salvage_recovery_function", RELIC_FUNCTION_RE), ("function_language", FUNCTION_RE)):
            if regex.search(analysis):
                signals.append(label)
        if signals:
            result.append({"section": p["section"], "signals": signals, "text": text})
    return result


def own_history_npc_only(p):
    return bool(re.search(r"(?i)history", p["section"]) and NPC_RE.search(p["text"]) and not PLAYER_MECH_RE.search(p["text"]))


def role_facts(paras):
    contexts = semantic_contexts(paras)
    out = []
    for p in contexts:
        if own_history_npc_only(p):
            continue
        signals = set(p["signals"])
        if signals.intersection({"cosmetic_or_appearance", "trophy_display", "companion_or_pet", "openable_container", "key_access", "upgrade_or_charge", "readable_text", "food_or_consumable", "tool_or_persistent_utility", "clue_solving_function", "salvage_recovery_function"}):
            out.append(p)
    return out


def classify(current, prior, exact, params, bonus, contexts, rolefacts, source_page_count):
    cat, sub = current.get("category"), current.get("subcategory")
    options = str(params.get("options", ""))
    equipable = str(params.get("equipable", "")).strip().lower() == "yes"
    active = equipable and bool(re.search(r"(?i)\b(?:wear|wield|equip)\b", options))
    stat = bool(bonus["positiveFields"])
    quest_field = str(params.get("quest", "")).strip()
    quest_item = bool(quest_field and quest_field.lower() not in {"no", "none", "false", "0"})
    cosmetic_text = any("cosmetic_or_appearance" in p["signals"] for p in rolefacts)
    has_display = any("trophy_display" in p["signals"] for p in rolefacts)
    has_pet = any("companion_or_pet" in p["signals"] for p in rolefacts)
    has_container = any("openable_container" in p["signals"] for p in rolefacts)
    has_key = any("key_access" in p["signals"] for p in rolefacts)
    has_upgrade = any("upgrade_or_charge" in p["signals"] for p in rolefacts)
    has_read = any("readable_text" in p["signals"] for p in rolefacts)
    has_food = any("food_or_consumable" in p["signals"] for p in rolefacts)
    has_tool = any("tool_or_persistent_utility" in p["signals"] for p in rolefacts)
    has_clue_function = any(CLUE_FUNCTION_RE.search(analysis_text(p["text"])) for p in rolefacts)
    has_relic_function = any(RELIC_FUNCTION_RE.search(analysis_text(p["text"])) for p in rolefacts)
    if not exact:
        return "decision_hold", "no exact numeric own-page ID binding", None
    if source_page_count != 1:
        return "decision_hold", "exact ID maps to multiple article pages; source subject binding needs manual selection", None
    activity_specific = [p for p in rolefacts if ACTIVITY_RE.search(p["text"]) and re.search(r"(?i)\b(?:used|use|can be used|only|equip|wear|wield|weapon|armor|armour)\b", p["text"])]
    if activity_specific and cat in {"CLUE", "UNIQUE"}:
        return "decision_hold", "Exact article documents an activity/minigame-specific use; primary routing for activity-mode items is pending policy.", None
    if cat == "CLUE" and sub == "cosmetic" and active and stat:
        slot = bonus["slots"][0] if bonus["slots"] else "gear"
        return "candidate_correction", "Exact variant has active Wear/Wield/Equip state and positive source-bound attack/defence/prayer bonus fields; review a primary GEAR placement against the current cosmetic assignment.", {"category": "GEAR", "subcategory": slot}
    if cat == "CLUE" and sub == "cosmetic" and active and bonus["nonzeroFields"] and not stat:
        return "decision_hold", "Exact active variant has only negative source-bound bonus fields; those penalties alone do not establish a combat-primary GEAR placement.", None
    if cat == "CLUE" and sub == "cosmetic":
        if has_pet and not cosmetic_text:
            return "candidate_correction", "Exact-ID page explicitly identifies this variant as a pet/companion that follows the player; review CLUE/collection-pet as the primary group. Companion role is directly supported, but collection-log membership and primary placement are not inferred.", {"category": "CLUE", "subcategory": "collection-pet"}
        if active and quest_item and bonus["hasExplicitZeroBonusTemplate"]:
            return "decision_hold", "Exact variant is a quest-associated wearable with an explicit zero-bonus template; its placement depends on the pending zero-stat quest-wearable retention policy.", None
        if has_food and not cosmetic_text:
            holiday = any(POLICY_HOLIDAY_RE.search(p["text"]) for p in contexts)
            if holiday:
                return "decision_hold", "Exact article documents a holiday food/consumable function; holiday edible routing is pending user policy.", None
            return "candidate_correction", "Exact article documents an edible/consumable mechanic without an explicit cosmetic function; review a consumable/current-use placement. Ordinary cosmetic kits are not routed from consumption alone.", {"category": "CLEANUP", "subcategory": "cleanup"}
        if not cosmetic_text:
            return "decision_hold", "Exact page does not directly establish an appearance/style use; wearable state, reward origin, and collection-log facets alone do not prove cosmetic primary placement.", None
    if cat == "CLUE" and sub == "treasure-trail" and not has_clue_function:
        return "decision_hold", "Exact own-item page does not directly establish clue-solving/step function; clue title, reward source, and disambiguation references alone are insufficient.", None
    if cat == "CLUE" and sub == "collection-trophy" and not has_display:
        return "decision_hold", "Collection-log or trophy examine text does not establish actual stuffing, mounting, or display mechanics in the exact page excerpts.", None
    if cat == "CLUE" and sub == "collection-pet" and not has_pet:
        return "decision_hold", "Exact variant page excerpts do not directly bind a companion/follower function; pet facets or another variant cannot be propagated.", None
    if cat == "UNIQUE" and sub in {"reward-container", "reward-drop"} and not has_container:
        return "decision_hold", "Reward origin or naming does not establish that this exact item opens/contains rewards.", None
    if cat == "UNIQUE" and sub in {"boss-access-key", "reward-key"} and not has_key:
        return "decision_hold", "Exact page evidence does not establish the named key's actual opening/entry function or persistence.", None
    if cat == "UNIQUE" and sub in {"equipment-upgrade", "weapon-upgrade", "equipment-charge"} and not has_upgrade:
        return "decision_hold", "Upgrade/charge facet or reward context lacks an exact direct transformation or charging mechanic in selected source paragraphs.", None
    if cat == "UNIQUE" and sub == "salvaging-relic" and not has_relic_function:
        return "decision_hold", "Exact source does not bind this item to an actual salvage/recovery mechanic; a relic label or facet alone is insufficient.", None
    if cat == "UNIQUE" and sub == "key-material" and not has_upgrade:
        return "decision_hold", "Exact source does not state that this item combines into or contributes to a named key.", None
    if sub == "readable-lore":
        options_read = bool(re.search(r"(?i)\b(?:read|study)\b", options))
        if not options_read or not has_read:
            return "decision_hold", "Readable-item placement requires this exact variant's active Read/Study option plus direct readable-content evidence.", None
    aligned = (
        (cat == "CLUE" and sub == "cosmetic" and cosmetic_text)
        or (cat == "CLUE" and sub == "treasure-trail" and has_clue_function)
        or (cat == "CLUE" and sub == "collection-trophy" and has_display)
        or (cat == "CLUE" and sub == "collection-pet" and has_pet)
        or (cat == "UNIQUE" and sub in {"reward-container", "reward-drop"} and has_container)
        or (cat == "UNIQUE" and sub in {"boss-access-key", "reward-key"} and has_key)
        or (cat == "UNIQUE" and sub in {"equipment-upgrade", "weapon-upgrade", "equipment-charge"} and has_upgrade)
        or (cat == "UNIQUE" and sub == "salvaging-relic" and has_relic_function)
        or (cat == "UNIQUE" and sub == "key-material" and has_upgrade)
        or (sub == "readable-lore" and has_read and bool(re.search(r"(?i)\b(?:read|study)\b", options)))
    )
    if prior.get("decision") == "certify" and aligned:
        return "source_supported_candidate", "Exact ID is bound and a direct own-item mechanic supports this current subcategory; this is an independent candidate, not an approval.", None
    if prior.get("decision") == "certify":
        return "decision_hold", "Prior certification lacks the direct exact-item mechanic required for this current primary grouping.", None
    return "decision_hold", "Exact page identity is bound, but source evidence does not resolve the current primary grouping; manual case review is needed.", None


def main():
    packet = read_jsonl(PACKET)
    decisions = {r["itemId"]: r for r in read_jsonl(DECISIONS)}
    clue_rows = read_jsonl(CLUE)
    root_rows = read_jsonl(ROOT_APPROVED)
    approved_clue_ids = {r["itemId"] for r in clue_rows if r.get("decision") == "certify"}
    approved_root_ids = {r["itemId"] for r in root_rows if r.get("decision") in {"certify", "revise"}}
    residual = [r for r in packet if r["itemId"] not in approved_clue_ids and r["itemId"] not in approved_root_ids]
    if len(residual) != 1124:
        raise ValueError(f"expected 1124 residual rows after root approved exclusions, got {len(residual)}")
    index_raw = INDEX.read_bytes()
    index = json.loads(index_raw.decode("utf-8"))
    byid = collections.defaultdict(list)
    for title, art in index.items():
        for item_id in art.get("exactInfoboxItemIds", []):
            byid[int(item_id)].append((title, art))
    out = []
    seen = set()
    excerpt_count = 0
    for row in residual:
        item_id = int(row["itemId"])
        if item_id in seen:
            raise ValueError(f"duplicate residual item ID {item_id}")
        seen.add(item_id)
        prior = decisions[item_id]
        current = row["current"]
        evidence = [e for e in prior.get("evidence", []) if e.get("kind") == "exact_wiki"]
        pages, page_selection = article_pages(byid, item_id, evidence)
        article_records = []
        selected = pages[0] if len(pages) == 1 else None
        exact = False
        params = {}
        variant = {}
        contexts = []
        rolefacts = []
        bonuses = []
        title = None
        if selected:
            title, art = selected
            raw_path = ROOT / art["path"]
            raw_bytes = raw_path.read_bytes()
            if sha_bytes(raw_bytes) != "sha256:" + art["sha256"]:
                raise ValueError(f"source hash mismatch for {item_id}/{title}")
            text = raw_bytes.decode("utf-8")
            variant = art.get("variants", {}).get(str(item_id), {})
            params = variant.get("params", {})
            idfields = exact_binding(params, item_id)
            selected_params, selected_field_keys = select_variant_fields(params, item_id)
            exact = item_id in [int(x) for x in art.get("exactInfoboxItemIds", [])] and bool(idfields)
            suffix = str(variant.get("suffix", ""))
            if not suffix and idfields:
                suffix_match = re.fullmatch(r"id([0-9]*)", idfields[0]["field"], re.I)
                suffix = suffix_match.group(1) if suffix_match else ""
            bonuses = bonus_facts(text, suffix)
            parsed_paragraphs = source_paragraphs(text)
            contexts = semantic_contexts(parsed_paragraphs)
            materials = material_contexts(parsed_paragraphs)
            rolefacts = role_facts(parsed_paragraphs)
            lead = own_lead(text)
            for label, excerpt in [("literalOwnSubjectLead", lead)] + [("sourceContext", p["text"]) for p in rolefacts + contexts + materials]:
                if norm(excerpt) not in norm(text):
                    raise ValueError(f"nonliteral {label} for item {item_id} on {title}")
            article_records.append({
                "sourceTitle": title,
                "sourceUrl": art.get("sourceUrl"),
                "sourceRevision": art["revid"],
                "sourceHash": "sha256:" + art["sha256"],
                "rawArticlePath": art["path"],
                "rawArticleBytes": len(raw_bytes),
                "exactInfoboxItemIds": art.get("exactInfoboxItemIds", []),
                "exactInfoboxIdFields": idfields,
                "variant": variant.get("variant") or selected_params.get("version"),
                "suffix": suffix,
                "selectedVariantName": variant.get("name") or selected_params.get("name"),
                "selectedVariantFields": selected_params,
                "selectedVariantSourceFieldKeys": selected_field_keys,
                "exactOwnVariantFields": {k: params[k] for k in ("id", "id1", "id2", "id3", "id4", "id5", "name", "name1", "name2", "name3", "name4", "name5", "options", "equipable", "quest", "tradeable", "bankable", "stackable", "noteable", "destroy", "examine", "value", "weight") if k in params},
                "bonusTemplatesBoundBySuffix": bonuses,
                "bonusSummary": bonus_summary(bonuses),
                "collectionLogPageFacet": "[[Category:Collection log items]]" in text,
                "collectionLogFacetScope": "single-exact-id-page" if len(art.get("exactInfoboxItemIds", [])) == 1 else "shared-page-facet-not-propagated",
                "upgradePageFacet": "[[Category:Upgrade items]]" in text,
                "pageFacetExactBinding": len(art.get("exactInfoboxItemIds", [])) == 1,
                "literalOwnSubjectLead": lead,
                "sourceParagraphsWithDirectFunctionSignals": rolefacts,
                "sourceParagraphsWithSemanticContext": contexts,
                "sourceMaterialAndCompetingContexts": materials,
            })
            excerpt_count += 1 + len(rolefacts) + len(contexts) + len(materials)
        else:
            idfields = []
        ambiguous_records = []
        if not selected and pages:
            for alt_title, alt_art in pages:
                alt_path = ROOT / alt_art["path"]
                alt_bytes = alt_path.read_bytes()
                if sha_bytes(alt_bytes) != "sha256:" + alt_art["sha256"]:
                    raise ValueError(f"ambiguous source hash mismatch for {item_id}/{alt_title}")
                alt_text = alt_bytes.decode("utf-8")
                alt_variant = alt_art.get("variants", {}).get(str(item_id), {})
                alt_params = alt_variant.get("params", {})
                alt_ids = exact_binding(alt_params, item_id)
                alt_selected, alt_keys = select_variant_fields(alt_params, item_id)
                alt_paras = source_paragraphs(alt_text)
                alt_contexts = semantic_contexts(alt_paras)
                alt_materials = material_contexts(alt_paras)
                alt_roles = role_facts(alt_paras)
                alt_lead = own_lead(alt_text)
                for label, excerpt in [("literalOwnSubjectLead", alt_lead)] + [("sourceContext", p["text"]) for p in alt_roles + alt_contexts + alt_materials]:
                    if norm(excerpt) not in norm(alt_text):
                        raise ValueError(f"nonliteral {label} for ambiguous item {item_id} on {alt_title}")
                ambiguous_records.append({
                    "sourceTitle": alt_title,
                    "sourceUrl": alt_art.get("sourceUrl"),
                    "sourceRevision": alt_art.get("revid"),
                    "sourceHash": "sha256:" + alt_art["sha256"],
                    "rawArticlePath": alt_art["path"],
                    "exactInfoboxItemIds": alt_art.get("exactInfoboxItemIds", []),
                    "exactInfoboxIdFields": alt_ids,
                    "variant": alt_variant.get("variant") or alt_selected.get("version"),
                    "suffix": alt_variant.get("suffix"),
                    "selectedVariantName": alt_variant.get("name") or alt_selected.get("name"),
                    "selectedVariantFields": alt_selected,
                    "selectedVariantSourceFieldKeys": alt_keys,
                    "bonusTemplatesBoundBySuffix": bonus_facts(alt_text, str(alt_variant.get("suffix", ""))),
                    "literalOwnSubjectLead": alt_lead,
                    "sourceParagraphsWithDirectFunctionSignals": alt_roles,
                    "sourceParagraphsWithSemanticContext": alt_contexts,
                    "sourceMaterialAndCompetingContexts": alt_materials,
                    "collectionLogPageFacet": "[[Category:Collection log items]]" in alt_text,
                    "collectionLogFacetScope": "single-exact-id-page" if len(alt_art.get("exactInfoboxItemIds", [])) == 1 else "shared-page-facet-not-propagated",
                })
                excerpt_count += 1 + len(alt_roles) + len(alt_contexts) + len(alt_materials)
        status, reason, correction = classify(current, prior, exact, selected_params if selected else params, bonus_summary(bonuses), contexts, rolefacts, len(pages))
        previous = {k: prior.get(k) for k in ("decision", "proposedCategory", "proposedSubcategory", "proposedIronmanTabKey", "proposedRoles", "proposedTags", "semanticPredicate", "rationale", "reviewer")}
        out.append({
            "itemId": item_id,
            "shard": row["shard"],
            "auditScope": row.get("auditScope"),
            "catalogName": row.get("catalogName"),
            "registryName": row.get("registryName"),
            "current": current,
            "residualScope": {"excludedApprovedClueScrolls": 637, "otherRootApprovedOverlap": item_id in approved_root_ids, "frozenRootApprovedSet": "root-approved-decisions-with-clue-scrolls.jsonl"},
            "priorCollectionsDecision": previous,
            "exactWikiBindingStatus": page_selection,
            "exactWikiPages": article_records if selected else [],
            "ambiguousExactWikiPages": ambiguous_records,
            "wikiIdentityContext": {"joinStatus": row.get("sourceEvidence",{}).get("wikiJoinStatus"), "wikiLinks": row.get("sourceEvidence",{}).get("wikiLookupLinks", []), "priorWikiEvidence": evidence},
            "sourceBoundFinding": {"triage": status, "reason": reason, "candidateCorrectionTarget": correction, "directFunctionKinds": sorted({kind for p in rolefacts for kind in p["signals"]}), "collectionLogFacetIsFunction": False, "decisionNotApproval": True},
            "reviewScope": "Exact-ID page, exact infobox variant fields/options, source bonus fields, own lead, direct player mechanics and material competing contexts; no role/tag decision and no production edit.",
        })
    out.sort(key=lambda x:x["itemId"])
    if len(seen) != 1124:
        raise ValueError(f"expected 1124 unique IDs, got {len(seen)}")
    OUTDIR.mkdir(parents=True, exist_ok=True)
    OUT.write_text("\n".join(json.dumps(x,ensure_ascii=False,separators=(",",":")) for x in out)+"\n",encoding="utf-8")
    counts=collections.Counter(r["sourceBoundFinding"]["triage"] for r in out)
    reason_counts=collections.Counter((r["sourceBoundFinding"]["triage"],r["sourceBoundFinding"]["reason"]) for r in out)
    function_kind_rows=collections.Counter(kind for r in out for kind in r["sourceBoundFinding"]["directFunctionKinds"])
    subcounts=collections.Counter((r["current"]["category"],r["current"]["subcategory"]) for r in out)
    unbound=collections.Counter(r["exactWikiBindingStatus"] for r in out)
    correction_targets=collections.Counter(tuple(sorted((r["sourceBoundFinding"]["candidateCorrectionTarget"] or {}).items())) for r in out if r["sourceBoundFinding"]["candidateCorrectionTarget"])
    summary={
        "schema":1,
        "status":"read-only independent source review; no approval or production changes",
        "inputs":{p.name:{"path":str(p.relative_to(ROOT)),"sha256":sha_file(p)} for p in (PACKET,DECISIONS,CLUE,ROOT_APPROVED,INDEX)},
        "output":{"path":str(OUT.relative_to(ROOT)),"sha256":sha_file(OUT)},
        "rowCount":len(out),"uniqueIds":len(seen),"rootApprovedClueIdsExcluded":len(approved_clue_ids),"otherRootApprovedIdsInShardExcluded":len(({r["itemId"] for r in packet} & approved_root_ids)-approved_clue_ids),
        "sourceBindingStatusCounts":dict(unbound),"triageCounts":dict(counts),
        "triageReasonCounts":{f"{triage}|{reason}":n for (triage,reason),n in reason_counts.items()},
        "directFunctionKindRowCounts":dict(function_kind_rows),
        "decisionRule":{"source_supported_candidate":"Unique exact numeric ID and pinned page plus direct subject-specific player function evidence that supports the current grouping; not an approval.","candidate_correction":"Exact active wearable state plus positive exact-source attack/defence/prayer bonus fields yields a GEAR slot candidate for current CLUE/cosmetic rows. Exact follower mechanics can yield a CLUE/collection-pet primary candidate while leaving collection-log membership and primary-placement policy separate. Direct edible or activity functions remain policy holds when routing depends on pending decisions.","decision_hold":"No exact source binding, ambiguous pages, missing exact function evidence, or unresolved user policy. Facets/reward source/title alone never support primary placement."},
        "currentCategorySubcategoryCounts":{f"{a}/{b}":n for (a,b),n in subcounts.items()},
        "candidateCorrectionTargets":{str(dict(k)):v for k,v in correction_targets.items()},
        "rowsWithExactSinglePinnedPage":sum(bool(r["exactWikiPages"]) for r in out),"rowsUnboundOrAmbiguous":sum(not r["exactWikiPages"] for r in out),
        "excerptsAndContextCount":excerpt_count,
        "literalExcerptValidation":{"passed":True,"excerptCount":excerpt_count,"method":"each emitted own-subject lead and raw semantic/material paragraph was checked after whitespace collapse as a substring of the exact pinned raw article text"},
        "semanticLimits":["Facets, collection-log membership, reward origin, titles, disambiguation crossrefs and NPC-only fiction do not establish item function.","Category suggestions are triage candidates only; this packet does not approve a placement.","Exact item state does not propagate to cache aliases or other physical/morph variants.","Zero-stat quest-associated wearable, holiday edible and activity-mode routing cases remain explicit holds when detected; ordinary cosmetic kits are not held solely because opening/using the kit consumes or transforms it."],
    }
    SUMMARY.write_text(json.dumps(summary,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps({"output":str(OUT),"summary":str(SUMMARY),"rows":len(out),"triage":dict(counts),"sourceBindings":dict(unbound)},ensure_ascii=False,indent=2))

if __name__=="__main__": main()
