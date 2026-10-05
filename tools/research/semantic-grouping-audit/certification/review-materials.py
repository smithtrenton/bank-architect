#!/usr/bin/env python3
"""Build source-backed exact-ID SKILLING/FARMING certification decisions."""
import collections, hashlib, json, re, os
from pathlib import Path
ROOT = Path(__file__).resolve().parents[4]
PACKET = ROOT / "tmp/category-certification/reviewer-packets/skilling-farming.jsonl"
INDEX = ROOT / "tmp/category-certification/wiki-articles/article-index.json"
OUT_DIR = ROOT / "tmp/category-certification/reviews/materials"
OUT = OUT_DIR / "skilling-farming.jsonl"
SUMMARY = OUT_DIR / "summary.json"
SHARD = "skilling-farming"
TARGET_REVIEW_FILES = [
    "cleanup-other/decisions.jsonl", "cleanup-quest/decisions.jsonl",
    "collections/clue-unique.jsonl", "gear/decisions.jsonl",
    "materials/skilling-farming.jsonl", "supplies/decisions.jsonl",
    "tools/decisions.jsonl", "transport/decisions.jsonl",
]
LINK = re.compile(r"\[\[([^\]|#]+)(?:#[^\]|]*)?(?:\|([^\]]+))?\]\]")
SPACE = re.compile(r"\s+")
RULES = {
 "farming": [r"\b(?:seeds?|seedlings?|saplings?)\b.{0,140}\b(?:grown|grow|planted|plant|patch)",r"\b(?:planted|planting|sown|sowing)\b.{0,120}\b(?:patch|seed|grow|flower|crop|tree|bush|sapling|pot)",r"\b(?:tree|crop|flower|bush) patch\b",r"\b(?:compost|plant cure)\b.{0,140}\b(?:plant|crop|patch|supercompost|farming|bin)"],
 "seed": [r"\b(?:seeds?|saplings?|seedlings?)\b.{0,140}\b(?:grown|grow|planted|plant|patch)",r"\bfrags?\b.{0,140}\b(?:farming|plant(?:ed|ing)?|coral nursery)\b",r"\b(?:planted|planting|sown|sowing)\b.{0,120}\b(?:patch|seed|grow|flower|crop|tree|bush|sapling)"],
 "coral-fragment": [r"\b(?:coral )?frags?\b.{0,140}\b(?:planted|planting|coral nursery|farming|grow|grown|harvest)",r"\b(?:planted|planting|grown|grow|harvested|harvest)\b.{0,140}\b(?:coral )?frags?\b",r"\bcoral nursery\b.{0,140}\b(?:frag|plant|grow|harvest|coral)"],
 "herb-seed": [r"\bherb(?:s|er)? seeds?\b",r"\bherb patch\b",r"\bplanted?\b.{0,100}\b(?:herb|snape grass|allotment)\b",r"\bsnape grass seeds?\b.{0,140}\b(?:plant(?:ed|ing)?|sown|allotment patch)\b"],
 "produce": [r"\b(?:harvest(?:ed|ing)?|grown|picked)\b.{0,130}\b(?:patch|farm|crop|bush|tree|plant|fruit|herb)",r"\b(?:patch|crop|bush|tree|plant)\b.{0,130}\b(?:harvest|produce|yield|berries|fruit)",r"\bfarming patch\b"],
 "produce-container": [r"\b(?:store|hold|contain(?:s|ed)?|filled with|fill)\b.{0,120}\b(?:produce|fruit|crop|harvest|vegetable|onion|cabbage|tomato|potato)",r"\b(?:produce|fruit|crop|harvest|vegetable|onion|cabbage|tomato|potato)\b.{0,120}\b(?:bag|basket|crate|container|store|hold|sack)"],
 "farming-supply": [r"\b(?:protect|protection|compost|fertili[sz]e|water|care for|cure|heal|fill with soil|used to plant)\b.{0,120}\b(?:crop|plant|patch|tree|farming|seed|pot)",r"\b(?:crop|plant|patch|tree|seed|pot)\b.{0,120}\b(?:protect|compost|fertili[sz]e|water|cure|heal|soil)",r"used in the farming skill to turn tree seeds into seedlings",r"an empty plant pot can be filled"],
 "ammo-component": [r"\b(?:used|combined|attached|fletched|crafted|smelted)\b.{0,130}\b(?:arrow|arrowhead|arrowtip|bolt|dart|javelin|ammunition)",r"\b(?:arrow|arrowhead|arrowtip|bolt|dart|javelin)\b.{0,130}\b(?:made|fletched|crafted|attached|used)",r"\b(?:make|making|fletch|attach)\b.{0,90}\b(?:arrow|bolt|dart)",r"\b(?:longbow|shortbow|crossbow|ballista)\b.{0,130}\b(?:made|strung|fletch|crafted|string)",r"\b(?:made|strung|fletch|crafted|string)\b.{0,130}\b(?:longbow|shortbow|crossbow|ballista)"],
 "ore": [r"\b(?:mined|mine|smelted|smelt|ore|ore vein)\b.{0,130}\b(?:ore|metal|bar|rock|mine|smith)",r"\b(?:ore|metal)\b.{0,130}\b(?:mined|mine|smelt|bar)"],
 "log": [r"\b(?:chopped|cut|felled)\b.{0,120}\b(?:tree|log|wood)",r"\b(?:logs?|wood)\b.{0,120}\b(?:woodcutting|firemaking|fletching|plank|chop)"],
 "uncut-gem": [r"\buncut\b.{0,120}\b(?:gem|jewel|cut|mine)",r"\b(?:mined|mine|cut)\b.{0,120}\b(?:gem|jewel|stone)"],
 "gem": [r"\b(?:cut|crafted|used|made)\b.{0,120}\b(?:gem|jewel|amulet|ring|necklace|bracelet)",r"\b(?:gem|jewellery|jewelry)\b.{0,120}\b(?:cut|craft|make|used)"],
 "cooking-material": [r"\b(?:ingredient|used|added|combined|cooked)\b.{0,120}\b(?:cook|cooking|food|dish|meal|pie|cake|stew)",r"\b(?:cook|cooking)\b.{0,120}\b(?:ingredient|food|dish|meal)"],
 "raw-food": [r"\b(?:raw|uncooked)\b.{0,100}\b(?:fish|meat|food|foodstuff)",r"\b(?:cooked|cook|cooking)\b.{0,120}\b(?:fish|meat|food)"],
 "prayer-resource": [r"\b(?:bury|buried|scatter|offered)\b.{0,120}\b(?:prayer|altar|bone|ashes)",r"\b(?:bones?|ashes)\b.{0,120}\b(?:prayer|bury|altar|scatter)"],
 "crafting-jewellery": [r"\b(?:craft|crafted|make|made|string|enchanted)\b.{0,140}\b(?:jewellery|jewelry|amulet|ring|necklace|bracelet)",r"\b(?:amulet|ring|necklace|bracelet)\b.{0,120}\b(?:crafted|made|enchanted|jewellery|jewelry)"],
 "crafting-material": [r"\b(?:used|combined|crafted|made)\b.{0,130}\b(?:craft|crafting|item|product|hide|leather|thread|needle)"],
 "leather": [r"\b(?:tanned|tanning|leather|hide)\b.{0,130}\b(?:craft|crafted|armor|armour|leather|hide)",r"\b(?:hide|leather)\b.{0,130}\b(?:tanned|tanning|craft|crafted)"],
 "textile": [r"\b(?:spun|weav(?:e|ed|ing)|woven|textile|cloth|thread|wool|silk)\b.{0,130}\b(?:spin|weav|craft|make|made|used)",r"\b(?:spin|weav|craft|make)\b.{0,100}\b(?:cloth|thread|wool|silk|textile)"],
 "glass-material": [r"\b(?:glass|molten glass|soda ash|sand)\b.{0,140}\b(?:glassblow|molten glass|craft|make|furnace)",r"\b(?:glassblow|molten glass)\b.{0,140}\b(?:glass|sand|soda ash)"],
 "construction-material": [r"\b(?:used|required|needed|consumed)\b.{0,130}\b(?:construction|build|building|plank|furniture|player-owned house)",r"\b(?:construction|build|building)\b.{0,130}\b(?:material|plank|nail|stone|used)"],
 "hunter-resource": [r"\b(?:hunter|trap|snare|bird snare|box trap)\b.{0,130}\b(?:bait|trap|used|ingredient|catch|hunter)",r"\b(?:bait|trap)\b.{0,130}\b(?:hunter|catch|creature)"],
 "fishing-material": [r"\b(?:fishing|fish|bait|fished|caught)\b.{0,130}\b(?:rod|bait|fish|fishing|catch)"],
 "bones": [r"\b(?:bury|buried|scatter|bones?|prayer|altar)\b.{0,130}\b(?:bury|prayer|altar|bones?|experience)"],
 "resource": [r"\b(?:used|required|needed|consumed|processed|obtained|gathered|mined|chopped|fished|harvested)\b.{0,130}\b(?:skill|craft|item|resource|ore|log|material|product|process|tool)"],
 "skilling": [r"\b(?:used|required|needed|consumed|processed|obtained|gathered|mined|chopped|fished|harvested|crafted|made|caught|burnt|burned)\b.{0,140}\b(?:skill|craft|item|resource|ore|log|material|product|process|tool|experience|level|cooking|fishing|hunter)",r"\b(?:crafting|construction|fletching|mining|smithing|firemaking|farming|woodcutting|hunter|fishing|sailing)\b.{0,140}\b(?:used|material|item|resource|process|recipe|make|craft)",r"\b(?:caught|mined|chopped|fished|harvested|gathered)\b.{0,140}\b(?:level|experience|using|with|skill|spot|tree|ore|patch|resource)\b"],
}

def load():
    return [json.loads(x) for x in PACKET.read_text(encoding="utf-8-sig").splitlines() if x.strip()]

def indexed():
    out = {}
    data = json.loads(INDEX.read_text(encoding="utf-8-sig"))
    for title, entry in data.items():
        for item_id in entry.get("exactInfoboxItemIds", []):
            out.setdefault(int(item_id), []).append((title, entry))
    return out

def identity_aliases(ids):
    path = ROOT / "tmp/category-certification/identity-links.jsonl"
    out = {}
    index_hash = hashlib.sha256(path.read_bytes()).hexdigest()
    with path.open(encoding="utf-8") as stream:
        for line in stream:
            item = json.loads(line)
            source_id = int(item.get("fromItemId", -1))
            if source_id not in ids or item.get("relation") not in {"NOTE_VARIANT_OF", "BOUGHT_VARIANT_OF", "PLACEHOLDER_FOR"}:
                continue
            typed = next((e for e in item.get("evidence", []) if e.get("kind") == "typed_identity"), None)
            wiki = next((e for e in item.get("evidence", []) if e.get("kind") == "exact_wiki"), None)
            if typed and wiki and int(item.get("toItemId", -1)) == int(wiki.get("itemId", -2)):
                out[source_id] = {"target":int(item["toItemId"]),"relation":item["relation"],"typed":{**typed,"identityIndexHash":index_hash},"wiki":wiki}
    return out

def load_target_reviews():
    reviewed = {}
    base = ROOT / "tmp/category-certification/reviews"
    for relative in TARGET_REVIEW_FILES:
        path = base / relative
        if not path.is_file():
            continue
        with path.open(encoding="utf-8-sig") as stream:
            for line in stream:
                if line.strip():
                    item = json.loads(line)
                    reviewed[int(item["itemId"])] = item
    return reviewed

def local_state_evidence(item_id, relation):
    evidence = []
    if relation == "NOTE_VARIANT_OF":
        path = ROOT / "tmp/category-certification/identity-policy-sources/15359494.txt"
        quote = "Storing a note in a bank, selling it to a shop, or using it on a bank booth or banker will convert the note to its item equivalent."
        evidence.append({"kind":"local_source", "source":"tmp/category-certification/identity-policy-sources/15359494.txt", "sourceHash":"sha256:"+hashlib.sha256(path.read_bytes()).hexdigest(), "itemId":item_id, "quote":quote})
    elif relation == "PLACEHOLDER_FOR":
        for relative, quote in [
            ("src/main/java/com/pkoka5/ironmanbankarchitect/bank/BankItemIds.java", "return placeholderTemplateId != -1 && placeholderItemId > 0 ? placeholderItemId : itemId;"),
            ("src/main/java/com/pkoka5/ironmanbankarchitect/bank/BankSnapshotReader.java", "return Optional.of(new BankItemSnapshot(canonicalItemId, 0, slotIndex, true));"),
        ]:
            path = ROOT / relative
            evidence.append({"kind":"local_source", "source":relative, "sourceHash":"sha256:"+hashlib.sha256(path.read_bytes()).hexdigest(), "itemId":item_id, "quote":quote})
    return evidence

def alias_record(row, alias, by_id, packet_hash, target_reviews):
    item_id, target_id = int(row["itemId"]), alias["target"]
    current = row["current"]
    relation = alias["relation"]
    target = next((entry for title,entry in by_id.get(target_id, []) if target_id in [int(x) for x in entry.get("exactInfoboxItemIds",[])]), None)
    target_review = target_reviews.get(target_id)
    target_wiki = next((e for e in (target_review or {}).get("evidence", [])
                        if e.get("kind") in {"exact_wiki", "direct_variant"} and int(e.get("itemId", -1)) == target_id), None)
    typed = alias["typed"]
    edge = {"kind":"typed_identity","source":typed["source"],"sourceRevision":typed.get("sourceRevision"),"sourceHash":typed.get("sourceHash"),"identityIndexHash":typed.get("identityIndexHash"),"itemId":item_id,"fromItemId":item_id,"toItemId":target_id,"relation":relation,"cacheField":typed.get("cacheField"),"cacheOpcode":typed.get("cacheOpcode"),"sourcePath":typed.get("sourcePath"),"configIndexRevision":typed.get("configIndexRevision")}
    identity_link = {"itemId":target_id,"fromItemId":item_id,"toItemId":target_id,"relation":relation,"evidence":[edge] + ([target_wiki] if target_wiki else [])}
    current_tuple = (current["category"],current["subcategory"],current["ironmanTabKey"])
    current_tags = sorted(current.get("tags", []))
    if relation == "BOUGHT_VARIANT_OF":
        predicate = "A bought-state cache edge establishes identity provenance only; the pinned identity policy forbids automatic bank or semantic inheritance for bought variants."
        rationale = "The exact cache edge identifies item {} as a bought variant of {}, but the policy does not let that state transfer use, bankability, or semantic role. This ID remains unresolved until its own exact mechanics are documented.".format(item_id,target_id)
        return {"itemId":item_id,"shard":SHARD,"decision":"unresolved","proposedCategory":current_tuple[0],"proposedSubcategory":current_tuple[1],"proposedTags":current.get("tags",[]),"proposedRoles":None,"proposedIronmanTabKey":current_tuple[2],"semanticPredicate":predicate,"rationale":rationale,"evidence":[{"kind":"local_source","source":"tools/research/semantic-grouping-audit/certification/identity-policy.json","sourceHash":"sha256:"+hashlib.sha256((ROOT/"tools/research/semantic-grouping-audit/certification/identity-policy.json").read_bytes()).hexdigest(),"itemId":item_id,"quote":"The boughtId/boughtTemplateId cache relation is exact identity provenance only."}],"identityLinks":[],"reviewer":"materials"}
    # Bank grouping can inherit only from a directly evidenced and reviewed canonical target.
    if not target or not target_review or target_review.get("decision") not in {"certify", "revise"} or not target_wiki:
        gap = "no exact canonical article" if not target else "the canonical target lacks a direct reviewed semantic assignment"
        predicate = "A typed state edge supports bank grouping only when its canonical target has its own exact, reviewed semantic evidence."
        rationale = "The frozen cache edge identifies item {} as {} item {}, but {}. Identity provenance alone does not establish this row's category, subcategory, tags, or destination.".format(item_id,relation,target_id,gap)
        return {"itemId":item_id,"shard":SHARD,"decision":"unresolved","proposedCategory":current_tuple[0],"proposedSubcategory":current_tuple[1],"proposedTags":current.get("tags",[]),"proposedRoles":None,"proposedIronmanTabKey":current_tuple[2],"semanticPredicate":predicate,"rationale":rationale,"evidence":[{"kind":"local_source","source":"tmp/category-certification/identity-links.jsonl","sourceHash":"sha256:"+hashlib.sha256((ROOT/"tmp/category-certification/identity-links.jsonl").read_bytes()).hexdigest(),"itemId":item_id,"quote":"Exact directed cache identity candidate; target semantic evidence is not sufficient for inheritance."}],"identityLinks":[],"reviewer":"materials"}
    proposed = (target_review["proposedCategory"],target_review["proposedSubcategory"],target_review["proposedIronmanTabKey"])
    proposed_tags = sorted(target_review.get("proposedTags", []))
    state_role = "bank_placeholder_slot" if relation == "PLACEHOLDER_FOR" else "bank_note_storage_state"
    roles = [state_role, "canonical_bank_grouping"]
    same = current_tuple == proposed and current_tags == proposed_tags
    decision = "certify" if same else "revise"
    local_evidence = local_state_evidence(item_id, relation)
    evidence = [edge, target_wiki] + local_evidence
    identity_link["evidence"] = [edge, target_wiki]
    if relation == "PLACEHOLDER_FOR":
        state_text = "The local bank snapshot code maps a placeholder slot to its exact placeholderId target and records placeholder state with quantity zero."
    else:
        state_text = "The pinned Bank article states that storing a note converts it to its item equivalent; this supports bank grouping only, not inherited held-item usability or properties."
    predicate = "The exact typed state edge plus independently reviewed canonical item evidence supports this bank-slot grouping while preserving the alias state as a separate role."
    rationale = "Item {} is {} item {} by the frozen cache opcode. {} Canonical item {} is directly Wiki-cited and reviewed as {}/{}/{} with tags {}; that target classification is the bank grouping basis, while this row retains its {} state. Proposed alias placement: {}/{}/{} with tags {}.".format(item_id,relation,target_id,state_text,target_id,*proposed,proposed_tags,state_role,*proposed,proposed_tags)
    return {"itemId":item_id,"shard":SHARD,"decision":decision,"proposedCategory":proposed[0],"proposedSubcategory":proposed[1],"proposedTags":proposed_tags,"proposedRoles":roles,"proposedIronmanTabKey":proposed[2],"semanticPredicate":predicate,"rationale":rationale,"evidence":evidence,"identityLinks":[identity_link],"reviewer":"materials"}

def literal_quote(article, normalized_quote):
    """Return a short raw-wikitext excerpt verified to occur in the pinned source."""
    target = SPACE.sub(" ", normalized_quote).strip()
    if not target:
        return ""
    for raw_line in article.splitlines():
        if target not in SPACE.sub(" ", plain(raw_line)):
            continue
        segments = re.split(r"(?<=[.!?])\s+(?=[A-Z0-9])", raw_line.strip())
        for segment in segments:
            if target in SPACE.sub(" ", plain(segment)):
                return SPACE.sub(" ", segment).strip()
        return SPACE.sub(" ", raw_line).strip()
    return normalized_quote

def plain(s):
    s = LINK.sub(lambda m: m.group(2) or m.group(1), s)
    s = re.sub(r"<ref[^>]*>.*?</ref>|<[^>]+>", " ", s, flags=re.I | re.S)
    s = re.sub(r"'{2,}", "", s)
    return SPACE.sub(" ", s).strip()

def prose(text):
    infobox = text.find("{{Infobox Item")
    end = text.find("\n}}", infobox) if infobox >= 0 else -1


    body = text[end + 3:] if end >= 0 else text
    def synced(match):
        values = re.findall(r"\|version\d+\s*=\s*([^|]+)", match.group(1), flags=re.I)
        return "\n" + "\n".join(values) + "\n"
    body = re.sub(r"\{\{Synced switch(.*?)\}\}", synced, body, flags=re.I | re.S)
    body = re.split(r"\n==\s*(?:Changes|Trivia|Item sources|Gallery|References|External links|Update history)\s*==", body, maxsplit=1, flags=re.I)[0]
    out = []
    for line in body.splitlines():
        line = line.strip()
        if not line or line.startswith(("[[File:", "==", "*", "{{", "|")):
            continue
        cleaned = plain(line)
        out.extend(re.split(r"(?<=[.!?])\s+(?=[A-Z0-9])", cleaned))
    return [SPACE.sub(" ", s).strip(" .") for s in out if len(s.strip()) >= 20]

def assess(row, sentences):
    current = row["current"]
    patterns = RULES.get(current["subcategory"], [])
    supported = [s for s in sentences if any(re.search(p, s, re.I) for p in patterns)]
    if not supported:
        return [], []
    joined = " ".join(supported)
    if any(re.search(r"upon harvesting a drift net, the drift net will be destroyed", sentence, re.I) for sentence in sentences):
        return ["skilling_activity_input"], [sentence for sentence in sentences if re.search(r"drift net fishing activity|upon harvesting a drift net", sentence, re.I)]
    if current["category"] == "FARMING":
        sub = current["subcategory"]
        roles = [{"herb-seed":"farming_plantable","seed":"farming_plantable","coral-fragment":"farming_plantable","farming":"farming_workflow","produce":"farming_harvest","produce-container":"farming_container","farming-supply":"farming_support"}.get(sub, "farming_workflow")]
        if sub == "herb-seed": roles.append("herblore_workflow")
    else:
        roles = []
        if re.search(r"\b(?:harvested|mined|chopped|fished|caught|gathered|picked|obtained)\b", joined, re.I):
            roles.append("skill_source_material")
        if re.search(r"\b(?:made into|processed into|crafted into|smelted into|cut into|spun into|woven into|fletched into|created by)\b", joined, re.I):
            roles.append("skill_processed_material")
        if re.search(r"\b(?:ingredient|used with|used to make|used to create|combined with|added to|made using|fletched|crafted|processed)\b", joined, re.I):
            roles.append("skill_recipe_input")
        if not roles:
            roles.append("skill_processed_material")
    return sorted(set(roles)), supported

def record(row, by_id, packet_hash, aliases, target_reviews):
    item_id = int(row["itemId"])
    current = row["current"]
    proposed_category, proposed_subcategory, proposed_tab = current["category"], current["subcategory"], current["ironmanTabKey"]
    exact = None
    title = ""
    for candidate_title, entry in by_id.get(item_id, []):
        exact, title = entry, candidate_title
        break
    roles, sentences = [], []
    evidence = []
    if exact:
        article_path = ROOT / exact["path"].replace("\\", "/")
        article_text = article_path.read_text(encoding="utf-8")
        sentences = prose(article_text)
        roles, supported = assess(row, sentences)
        proposed_category, proposed_subcategory, proposed_tab = current["category"], current["subcategory"], current["ironmanTabKey"]
        special = None
        ambiguous = None
        fulltext = " ".join(sentences).lower()
        exact_variant = exact.get("variants", {}).get(str(item_id), {})
        exact_params = exact_variant.get("params", {})
        examine_fact = str(exact_params.get("examine", ""))
        edible_exact = str(exact_params.get("edible", "")).strip().casefold() == "yes"
        drink_use = [sentence for sentence in sentences if re.search(r"\b(?:drink|drinking|cup of tea)\b.{0,160}\b(?:heal|restor|hitpoints|run energy)\b", sentence, re.I)]
        edible_use = [sentence for sentence in sentences if re.search(r"\b(?:food item|edible|food obtained)\b.{0,160}\b(?:heal|restor|hitpoints|hit points)\b", sentence, re.I) or re.search(r"\b(?:eating|eaten)\b.{0,120}\b(?:heal|restor|hitpoints|hit points)\b", sentence, re.I)]
        food_conversion = [sentence for sentence in sentences if re.search(r"\bcooked on\b.{0,160}\b(?:create|make|produce)\b.{0,80}\b(?:soda ash|molten glass|glass)\b", sentence, re.I)]
        source_rows = row.get("sourceEvidence", {}).get("wikiRecords", [])
        facets = {key[len("Category:"):] for key, value in (source_rows[0].items() if source_rows else []) if key.startswith("Category:") and value is True}
        has_tool_identity = bool(re.search(r"\b(?:net|rod|pickaxe|axe|harpoon|spade|knife|chisel|trowel|seed dibber|watering can|sickle|tool)\b", title, re.I))
        tool_sentences = [sentence for sentence in sentences if has_tool_identity and not re.search(r"\b(?:bait|lure|uses? up|consumed|destroyed)\b", sentence, re.I) and re.search(r"\b(?:used to catch|used at .*?fishing spot|used to (?:mine|chop|harvest|plant|dig|cut)|used for fishing)\b", sentence, re.I)]
        house_plant = [sentence for sentence in sentences if re.search(r"\bplanted in the .*?garden of a player-owned house\b", sentence, re.I) and re.search(r"\bconstruction level\b", sentence, re.I)]
        forestry_input = [sentence for sentence in sentences if re.search(r"\bmulch\b.{0,120}\bused during the .*?forestry event\b", sentence, re.I)]
        flower_secondary_seed = [sentence for sentence in sentences if re.search(r"\bseeds?\b.{0,100}\bplanted in a flower patch\b.{0,140}\bherblore\b.{0,80}\bsecondary ingredient\b", sentence, re.I)]
        if current["category"] == "FARMING" and current["subcategory"] == "herb-seed" and flower_secondary_seed:
            special = ("FARMING", "seed", "seeds-farming", ["farming_plantable", "farming_yields_herblore_secondary", "farming_tree_protection_payment"], "The exact seed is planted in a flower patch and its harvest supplies a Herblore secondary; it is not itself a herb-patch seed destined for the Herblore tab.")
            supported = flower_secondary_seed
            roles = special[3]
        elif current["category"] == "FARMING" and title.casefold() == "mulch" and forestry_input:
            special = ("SKILLING", "skilling", "resources", ["skilling_activity_input"], "The exact mulch article describes a Forestry event input, not a Farming crop or Farming supply.")
            supported = forestry_input
            roles = special[3]
        elif current["category"] == "FARMING" and house_plant:
            special = ("SKILLING", "construction-material", "resources", ["construction-material", "poh-decoration"], "The exact bagged plant is a player-owned-house garden decoration placed through Construction, not a crop grown for Farming output.")
            supported = house_plant
            roles = special[3]
        elif current["category"] in {"SKILLING", "FARMING"} and ((re.search(r"\b(?:unobtainable item|unobtainable items)\b", fulltext) and re.search(r"\b(?:removed|never been obtainable|prior to the release of old school runescape)\b", fulltext, re.I)) or ("{{Unobtainable items}}" in article_text and not re.search(r"unfinished cocktail", title, re.I) and (re.search(r"\bunobtainable\b", fulltext, re.I) or re.search(r"\b(?:removed|never been obtainable|prior to the release of old school runescape)\b", fulltext, re.I)))):
            special = ("CLEANUP", "cleanup", "storage-cleanup", ["historical_unobtainable_item"], "The exact article's unobtainable marker and item-specific text establish a discontinued or unobtainable state, not an active skilling resource.")
            roles = special[3]
            supported = [sentence for sentence in sentences if re.search(r"\b(?:unobtainable|removed|never been obtainable|prior to the release of old school runescape|cannot be obtained|impossible to actually buy)", sentence, re.I)]
            if not supported and "{{Unobtainable items}}" in article_text:
                supported = ["{{Unobtainable items}}"]
        elif current["category"] == "SKILLING" and re.search(r"unfinished cocktail", fulltext) and re.search(r"previously obtained during gnome cooking", fulltext) and re.search(r"altered with the gnome restaurant rework", fulltext) and re.search(r"now, the initial ingredients are automatically added", fulltext):
            special = ("CLEANUP", "cleanup", "storage-cleanup", ["obsolete_intermediate_item"], "The exact unfinished-cocktail state was a former Gnome Cooking intermediate; the article states the workflow was reworked and the game now creates a different mixed cocktail instead.")
            supported = [sentence for sentence in sentences if re.search(r"previously obtained during gnome cooking|altered with the gnome restaurant rework|now, the initial ingredients are automatically added", sentence, re.I)]
            roles = special[3]
        elif current["category"] in {"SKILLING", "FARMING"} and ((re.search(r"\bodd bird seed\b", title, re.I) and re.search(r"quest item used in the eagles' peak quest", fulltext, re.I) and re.search(r"used to navigate", fulltext, re.I)) or (re.search(r"\b(?:red rose|orange lily|yellow pansy|indigo iris|violet tulip) seed\b", title, re.I) and re.search(r"given to gilbert to progress the event", fulltext, re.I))):
            special = ("CLEANUP", "quest-item", "storage-cleanup", ["quest_item", "event_progression_input"], "The exact seed variant is documented as an Eagles' Peak/event progression item, not a Farming planting seed.")
            supported = [sentence for sentence in sentences if re.search(r"quest item used in the eagles' peak quest|given to gilbert to progress the event", sentence, re.I)]
            roles = special[3]
        elif current["category"] == "SKILLING" and (re.search(r"\bbarcrawl card\b", title, re.I) or re.search(r"\brecords? players?['’]? progress in the .*?miniquest\b", fulltext, re.I) or re.search(r"\bused in the ernest the chicken quest\b", fulltext, re.I)):
            special = ("CLEANUP", "quest-item", "storage-cleanup", ["quest_item", "quest_progression_input"], "The exact article identifies this as a quest or miniquest progression item, not a general SKILLING resource.")
            supported = [sentence for sentence in sentences if re.search(r"\b(?:barcrawl card|records? players?['’]? progress|used in the ernest the chicken quest)\b", sentence, re.I)]
            roles = list(special[3])
            if re.search(r"\bfish food\b", title, re.I): roles.append("activity_feed_input")
        elif current["category"] == "SKILLING" and current["subcategory"] in {"skilling", "resource", "raw-resource", "fishing-material", "hunter-resource"} and str(exact_params.get("equipable", "")).strip().casefold() == "yes" and (re.search(r"\b(?:weapon|armou?r|battleaxe|blowpipe|club|sword|bow|staff|spear|scimitar|shield)\b", fulltext, re.I) or re.search(r"\bworn\b.{0,80}\bin the (?:head|body|hand|legs|feet|neck|ring|shield|cape) slot\b", fulltext, re.I) or (re.search(r"\bshield\b", examine_fact, re.I) and re.search(r"\bwhile equipped\b", fulltext, re.I))):
            slot = next((slot for slot in ["head","body","hands","legs","feet","neck","ring","shield","cape"] if re.search(r"\bworn\b.{0,80}\bin the " + re.escape({"hands":"hand"}.get(slot,slot)) + r" slot\b", fulltext, re.I)), None)
            if not slot and (re.search(r"\b(?:off-hand|off hand|shield)\b", fulltext, re.I) or (re.search(r"\bshield\b", examine_fact, re.I) and re.search(r"\bwhile equipped\b", fulltext, re.I))): slot = "shield"
            weapon = bool(re.search(r"\b(?:weapon|battleaxe|blowpipe|club|sword|bow|staff|spear|scimitar)\b.{0,100}\b(?:wield|attack|combat|weapon)\b|\b(?:wield|wielded)\b.{0,100}\b(?:weapon|battleaxe|blowpipe|club|sword|bow|staff|spear|scimitar)\b", fulltext, re.I))
            if slot or weapon:
                destination_sub = slot or "weapon"
                special = ("GEAR", destination_sub, "combat-gear", ["combat_equipment"], "The exact equipable variant is directly described as worn in a combat slot or wielded as a weapon; it belongs in GEAR rather than SKILLING materials.")
                supported = [sentence for sentence in sentences if re.search(r"\b(?:weapon|armou?r|worn|wield|wielded|while equipped)\b", sentence, re.I)]
                roles = special[3]
        elif current["category"] == "SKILLING" and current["subcategory"] == "skilling" and re.search(r"\bbones?\b.{0,90}\b(?:prayer experience|prayer exp)\b.{0,90}\bburied\b|\bburied\b.{0,90}\b(?:prayer experience|prayer exp)\b", fulltext, re.I):
            special = ("SKILLING", "bones", "resources", ["prayer_training_material"], "The exact bone article documents Prayer experience from burying this variant; classify the bone stage specifically rather than as a generic skill resource.")
            supported = [sentence for sentence in sentences if re.search(r"\b(?:bones? give|burying|buried|bone gives)\b.{0,120}\b(?:prayer experience|prayer exp)\b|\b(?:prayer experience|prayer exp)\b.{0,90}\bburied\b", sentence, re.I)]
            roles = special[3]
        elif current["category"] == "SKILLING" and current["subcategory"] == "prayer-resource" and re.search(r"ensouled", title, re.I) and re.search(r"used to gain prayer experience", fulltext) and re.search(r"reanimat", fulltext):
            roles, supported = ["prayer_training_material", "magic_reanimation_input"], [sentence for sentence in sentences if re.search(r"used to gain prayer experience", sentence, re.I) and re.search(r"reanimat", sentence, re.I)]
        elif current["category"] == "SKILLING" and current["subcategory"] == "prayer-resource" and re.search(r"used for worship at the ectofuntus", fulltext) and re.search(r"bone grinder", fulltext):
            roles, supported = ["prayer_training_material", "ectofuntus_worship_input"], [sentence for sentence in sentences if re.search(r"used for worship at the ectofuntus", sentence, re.I)]
        elif current["category"] == "SKILLING" and current["subcategory"] == "prayer-resource" and re.search(r"fossilised", title, re.I) and re.search(r"used at the mycelium pool", fulltext) and re.search(r"calcified into a .* enriched bone", fulltext):
            roles, supported = ["prayer_related_resource", "mycelium_pool_processing_input"], [sentence for sentence in sentences if re.search(r"used at the mycelium pool", sentence, re.I) and re.search(r"calcified into a .* enriched bone", sentence, re.I)]
        elif current["category"] == "FARMING" and re.search(r"(?:seed|plant pot|compost) pack", title, re.I) and re.search(r"item pack containing", fulltext) and re.search(r"farming shop", fulltext):
            roles, supported = ["farming_supply_pack", "farming_input_source"], [sentence for sentence in sentences if re.search(r"item pack containing", sentence, re.I) or re.search(r"bought from any farming shop", sentence, re.I)]
        elif current["category"] == "FARMING" and re.search(r"nest box", title, re.I) and re.search(r"when opened, it would provide a .*bird nest", fulltext) and re.search(r"nest boxes remain in the game", fulltext):
            roles, supported = ["farming_seed_container", "bird_nest_source"], [sentence for sentence in sentences if re.search(r"when opened, it would provide a .*bird nest", sentence, re.I) or re.search(r"nest boxes remain in the game", sentence, re.I)]
        elif current["category"] == "FARMING" and re.search(r"seed pack", title, re.I) and re.search(r"received from .* farming contract", fulltext) and re.search(r"taking from a seed pack rewards the player with seeds", fulltext):
            roles, supported = ["farming_seed_supply", "farming_reward_pack"], [sentence for sentence in sentences if re.search(r"seed pack.*received from|taking from a seed pack rewards", sentence, re.I)]
        elif current["category"] == "FARMING" and re.search(r"crate of", title, re.I) and re.search(r"obtained from a ledger table after taking on a courier task", fulltext) and re.search(r"delivered to the corresponding destination's port", fulltext):
            special = ("SKILLING", "skilling", "resources", ["sailing_courier_payload", "activity_delivery_item"], "The exact crate is locked to a Sailing courier task and must be delivered to its destination port; its contents do not make it a Farming input.")
            supported = [sentence for sentence in sentences if re.search(r"obtained from a ledger table after taking on a courier task", sentence, re.I) and re.search(r"delivered to the corresponding destination's port", sentence, re.I)]
            roles = special[3]
        elif current["category"] == "SKILLING" and current["subcategory"] == "ammo-component" and re.search(r"hunter spear tips", title, re.I) and re.search(r"used in crafting hunter's spears", fulltext):
            special = ("SKILLING", "crafting-material", "resources", ["skill_recipe_input", "hunter_reward_material"], "The exact item is documented as a Crafting input for Hunter's spears; it is not ammunition despite the baseline subcategory.")
            supported = [sentence for sentence in sentences if re.search(r"used in crafting hunter's spears", sentence, re.I)]
            roles = special[3]
        elif current["category"] == "SKILLING" and current["subcategory"] == "textile" and re.search(r"bow string spool", title, re.I) and re.search(r"used on an unfinished bow to string them", fulltext) and re.search(r"automatically fill up with bow strings", fulltext):
            special = ("TOOL", "tool", "skilling-tools", ["reusable_skill_tool", "fletching_workflow", "bow_string_storage"], "The exact spool stores bow strings and applies them to successive unfinished bows; it is a reusable Fletching aid rather than cloth or consumed textile input.")
            supported = [sentence for sentence in sentences if re.search(r"used on an unfinished bow to string them|automatically fill up with bow strings", sentence, re.I)]
            roles = special[3]
        elif current["category"] == "SKILLING" and current["subcategory"] == "cooking-material" and re.search(r"raw gnomebowl|raw crunchies|half baked (?:crunchy|bowl|batta|tangari|worm)", title, re.I) and re.search(r"gnome(?:bowl)? cooking|range to make|raw ingredients", fulltext) and re.search(r"(?:range|raw ingredients|cooking)", fulltext):
            roles, supported = ["skill_recipe_input", "cooking_workflow"], [sentence for sentence in sentences if re.search(r"gnomebowl cooking|raw gnomebowls|raw crunchies|range to make|half baked crunchy|raw ingredients", sentence, re.I)]
        elif current["category"] == "SKILLING" and current["subcategory"] == "ammo-component" and re.search(r"cleaning dirty arrowtips consumes 50 of them", fulltext) and re.search(r"yields arrowtips", fulltext):
            roles, supported = ["skill_recipe_input", "consumed_processing_input", "fletching_workflow"], [sentence for sentence in sentences if re.search(r"cleaning dirty arrowtips consumes 50 of them", sentence, re.I)]
        elif current["category"] == "SKILLING" and edible_exact and edible_use and food_conversion:
            ambiguous = "The exact variant is directly edible and restores hitpoints, but the same article documents a repeatable Cooking conversion into soda ash for molten glass. The item therefore has both food and glassmaking-input roles, and this preset review does not choose a primary destination from the edible fact alone."
            supported = edible_use + food_conversion
            roles = None
        elif current["category"] == "SKILLING" and edible_exact and drink_use:
            special = ("POTION", "potion", "potions-food", ["edible_drink", "restorative_consumable"], "The exact variant is a restorative drink; its primary bank role matches other cup-of-tea consumables rather than generic SKILLING resources.")
            supported = drink_use
            roles = special[3]
        elif current["category"] == "SKILLING" and edible_exact and edible_use:
            special = ("POTION", "food", "potions-food", ["edible_food", "restorative_consumable"], "The exact article says this edible variant restores hitpoints when eaten; its primary bank role is food. Any separately documented recipe or acquisition role remains secondary.")
            supported = edible_use
            roles = list(special[3])
            if re.search(r"\b(?:made by|cooked by|cooked on|created by|processed into)\b", fulltext, re.I):
                roles.append("cooking_output")
            roles = sorted(set(roles))
        elif current["category"] == "SKILLING" and "Tools" in facets and tool_sentences and not re.search(r"\b(?:destroyed|consumed|uses? up)\b", fulltext):
            special = ("TOOL", "tool", "skilling-tools", ["reusable_skill_tool"], "The exact article identifies a reusable skill implement and describes its action, so it belongs with tools rather than consumed resources.")
            supported = tool_sentences
            roles = special[3]
        elif current["category"] == "SKILLING" and "Herblore secondaries" in facets and any(re.search(r"\bherblore\b.{0,180}\b(?:potion|antipoison|antidote|serum|secondary ingredient)\b", sentence, re.I) and re.search(r"\b(?:component|ingredient|secondary|make|create)\b", sentence, re.I) for sentence in sentences):
            special = ("HERBLORE", "secondary", "herblore", ["herblore_secondary"], "The exact article and Herblore-secondary facet identify this item as a potion ingredient rather than a generic skilling resource.")
            supported = [sentence for sentence in sentences if re.search(r"\bherblore\b.{0,180}\b(?:potion|antipoison|antidote|serum|secondary ingredient)\b", sentence, re.I) and re.search(r"\b(?:component|ingredient|secondary|make|create)\b", sentence, re.I)]
            roles = special[3]
        elif current["category"] == "SKILLING" and re.search(r"has no use whatsoever|has no use at all|serves no purpose whatsoever", fulltext):
            special = ("CLEANUP", "cleanup", "storage-cleanup", ["unusable_skill_byproduct"], "The exact item page states that this failed byproduct has no use whatsoever, so it does not belong among resources.")
            supported = [s for s in sentences if re.search(r"has no use whatsoever|has no use at all|serves no purpose whatsoever", s, re.I)]
            roles = special[3]
        elif current["category"] == "SKILLING" and current["subcategory"] == "glass-material" and re.search(r"used in the herblore skill to make potions", fulltext):
            special = ("HERBLORE", "herblore-supply", "herblore", ["herblore_container", "herblore_workflow"], "The exact empty vial is described as a potion container used in Herblore; its glassblowing origin is not its bank role.")
            supported = [s for s in sentences if re.search(r"used in the herblore skill to make potions", s, re.I)]
            roles = special[3]
        quote = next((s for s in supported if len(s.split()) <= 25), "")
        if not quote and supported: quote = " ".join(supported[0].split()[:25])
        if ambiguous:
            evidence = []
            for sentence in supported:
                raw_quote = literal_quote(article_text, sentence)
                evidence.append({"kind":"exact_wiki", "sourceTitle":title, "source":exact["sourceUrl"], "sourceRevision":exact["revid"], "sourceHash":"sha256:"+exact["sha256"], "itemId":item_id, "quote":raw_quote})
            if edible_exact and evidence:
                evidence[0]["structuredFacts"] = [{"field":"edible", "value":exact_params.get("edible")}]
        elif quote:
            quote = literal_quote(article_text, quote)
            wiki = {"kind":"exact_wiki", "sourceTitle":title, "source":exact["sourceUrl"], "sourceRevision":exact["revid"], "sourceHash":"sha256:"+exact["sha256"], "itemId":item_id, "quote":quote}
            facts = []
            if edible_exact:
                facts.append({"field":"edible", "value":exact_params.get("edible")})
            if special and special[0] == "GEAR":
                facts.append({"field":"equipable", "value":exact_params.get("equipable")})
                if examine_fact:
                    facts.append({"field":"examine", "value":examine_fact})
            if facts:
                wiki["structuredFacts"] = facts
            evidence = [wiki]
        else:
            evidence = [{"kind":"local_source", "source":"tmp/category-certification/reviewer-packets/skilling-farming.jsonl", "sourceHash":"sha256:"+packet_hash, "itemId":item_id, "quote":f"Exact article index maps ID {item_id} to {title} revision {exact['revid']}, but no parsed article mechanic establishes its placement."}]
        if ambiguous:
            decision = "unresolved"
            roles = None
            predicate = "The exact variant has multiple directly documented restorative and processing roles, but the primary bank destination remains ambiguous under the reviewed workflow policy."
            rationale = "Item {} is an exact infobox variant in {} revision {}. {} The exact article evidence records both mechanics; choosing food or glassmaking input without a policy for competing primary uses would overstate the evidence.".format(item_id,title,exact["revid"],ambiguous)
        elif special and supported:
            decision = "revise"
            predicate = "Pinned exact-ID article mechanics establish a better primary material/workflow classification than the current assignment."
            rationale = "Item {} is an exact infobox variant in {} revision {}. {} Article evidence: {} Proposed placement: {}/{}, tab {}.".format(item_id, title, exact["revid"], special[4], supported[0], special[0], special[1], special[2])
            proposed_category, proposed_subcategory, proposed_tab = special[0], special[1], special[2]
        elif roles and supported:
            decision = "certify"
            predicate = "Exact pinned article prose identifies a mechanic that supports the current material/Farming subcategory and destination."
            rationale = "Item {} is explicitly present in the exact infobox variant of {} revision {}. The article states: {} This documents the item role(s) {} and supports current {}/{} placement in {}. This decision is limited to the exact ID.".format(item_id, title, exact["revid"], supported[0], ", ".join(roles), current["category"], current["subcategory"], current["ironmanTabKey"])
        else:
            decision = "unresolved"
            roles = None
            predicate = "Exact variant mechanics must support the current material/Farming category, subcategory, roles, and destination."
            rationale = "Item {} is present in {} revision {}, but article prose does not directly establish the current {} role or {} destination. Category facets, title/name, baseline tags, and recipe-title links are insufficient, so this assignment remains unresolved.".format(item_id, title, exact["revid"], current["subcategory"], current["ironmanTabKey"])
    else:
        alias = aliases.get(item_id)
        if alias:
            reviewed = alias_record(row, alias, by_id, packet_hash, target_reviews)
            if reviewed:
                return reviewed
        source = (row.get("sourceEvidence", {}).get("wikiUrls") or ["https://oldschool.runescape.wiki/"])[0]
        evidence = [{"kind":"local_source", "source":"tmp/category-certification/reviewer-packets/skilling-farming.jsonl", "sourceHash":"sha256:"+packet_hash, "itemId":item_id, "quote":"Packet carries no exactInfoboxItemIds page match for this ID."}]
        decision = "unresolved"
        roles = None
        predicate = "A pinned exact-ID article must establish the item's specific state and current placement."
        rationale = f"The exact-ID Bucket record exists for item {item_id}, but the complete pinned article index has no exactInfoboxItemIds match. Without an exact item revision and direct mechanics, current category, subcategory, roles, and Ironman destination are baseline only."
    return {"itemId":item_id,"shard":SHARD,"decision":decision,"proposedCategory":proposed_category,"proposedSubcategory":proposed_subcategory,"proposedTags":current.get("tags",[]),"proposedRoles":roles,"proposedIronmanTabKey":proposed_tab,"semanticPredicate":predicate,"rationale":rationale,"evidence":evidence,"identityLinks":[],"reviewer":"materials"}

def main():
    rows, by_id = load(), indexed()
    aliases = identity_aliases({int(r["itemId"]) for r in rows})
    target_reviews = load_target_reviews()
    packet_hash = hashlib.sha256(PACKET.read_bytes()).hexdigest()
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    counts = collections.Counter()
    categories = collections.Counter()
    examples = []
    staged_out = OUT.with_name(OUT.name + ".staged-" + str(os.getpid()))
    with staged_out.open("w", encoding="utf-8", newline="\n") as f:
        for row in rows:
            if row.get("shard") != SHARD or row.get("current",{}).get("category") not in {"SKILLING","FARMING"}:
                raise ValueError(f"out-of-domain row {row.get('itemId')}")
            item = record(row, by_id, packet_hash, aliases, target_reviews)
            f.write(json.dumps(item, ensure_ascii=False, separators=(",",":"))+"\n")
            counts[item["decision"]] += 1
            categories[(row["current"]["category"],item["decision"])] += 1
            if item["decision"] == "unresolved" and len(examples)<30:
                examples.append({"itemId":item["itemId"],"name":row["catalogName"],"reason":item["rationale"]})
    summary = {"shard":SHARD,"inputRows":len(rows),"exactArticleIds":sum(bool(by_id.get(int(r["itemId"]))) for r in rows),"decisions":dict(counts),"byCategory":{f"{a}/{b}":n for (a,b),n in sorted(categories.items())},"packetSha256":"sha256:"+packet_hash,"articleIndexSha256":"sha256:"+hashlib.sha256(INDEX.read_bytes()).hexdigest(),"policy":"tools/research/semantic-grouping-audit/certification/materials-policy.json","unresolvedExamples":examples,"limitations":["Only direct article prose matching the subcategory mechanic supports certification.","Ledger validation checks packet accounting and schema, not semantic judgment quality.","No group links propagate evidence across item IDs."]}
    staged_summary = SUMMARY.with_name(SUMMARY.name + ".staged-" + str(os.getpid()))
    staged_summary.write_text(json.dumps(summary,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    staged_out.replace(OUT)
    staged_summary.replace(SUMMARY)
    print(json.dumps({"rows":len(rows),"decisions":dict(counts),"byCategory":summary["byCategory"],"output":str(OUT)},indent=2))

if __name__ == "__main__": main()


