#!/usr/bin/env python3
"""Generate exact-ID root-review proposals for unchanged ordinary spell runes.

Frozen-input research only. No production preset, tag, role, or approval-ledger
file is written. The fixed allowlist is reviewed against each exact Wiki page,
full lead, pinned body hash, and exact-ID Infobox Item variant.
"""
from __future__ import annotations
import hashlib,json,re
from pathlib import Path

ROOT=Path(__file__).resolve().parents[4]
DECISIONS=ROOT/'tmp/category-certification/reviews/transport-v15/decisions.jsonl'
PACKET=ROOT/'tmp/category-certification/reviewer-packets/currency-runes-teleport.jsonl'
INDEX=ROOT/'tmp/category-certification/wiki-articles/article-index.json'
OUT=ROOT/'tmp/category-certification/reviews/transport-v17/ordinary-spellcasting-runes-review.json'
# Only normal tradeable/usable spell-rune types, including combination runes.
# Exact-ID exception and alias rows remain in the rejection section.
POSITIVE_IDS={554,555,556,557,558,559,560,561,562,563,564,565,566,
              4694,4695,4696,4697,4698,4699,9075,21880,28929,30843}
MECHANIC_RE=re.compile(r'\b(?:spell|spells|cast|casting|teleportation)\b',re.I)
COMPETING_RE=re.compile(r'\b(?:runecraft|runic altar|altar|craft(?:ed|ing)?|spell|cast|coin|currency|exchange|shop|purchase|cost|consume|consumed|tradeable|traded|price|offering|alchemy|combat|armor|armour|ingredient|used in place of)\b',re.I)
RELEVANT_VARIANT_FIELDS=re.compile(r'^(?:id\d*|name\d*|version\d*|members|quest|tradeable|bankable|equipable|stackable|noteable|options|wornoptions|examine|value\d*|exchange\d*|weight|destroy)$',re.I)


def read_jsonl(path): return [json.loads(line) for line in path.read_text(encoding='utf-8-sig').splitlines() if line.strip()]
def sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()
def extract_lead(raw):
    pos=raw.find('{{Infobox Item')
    if pos<0: raise ValueError('no Infobox Item')
    end=re.search(r'\n}}\s*\n',raw[pos:])
    if not end: raise ValueError('unterminated Infobox Item')
    return raw[pos+end.end():].split('\n==',1)[0].strip()
def split_paragraphs(raw): return [part.strip() for part in re.split(r'\n\s*\n',raw) if part.strip()]
def exact_variant_fields(variant):
    return {k:v for k,v in variant.get('params',{}).items() if RELEVANT_VARIANT_FIELDS.match(k)}
def actual_spell_mechanics(lead):
    # Keep literal source paragraphs, not detector text or category facets.
    result=[]
    for para in split_paragraphs(lead):
        if MECHANIC_RE.search(para) and re.search(r'\b(?:used|use|requiring|require|cast|casting|spend|spent|cost|costs|provides|counts)\b',para,re.I):
            result.append(para)
    return result
def normalized(text): return re.sub(r'\s+',' ',text).casefold()

def exclusion_reason(iid,decision,packet,article,variant):
    title=article.get('title','') if article else ''
    name=(packet.get('catalogName') or packet.get('registryName') or '').lower()
    if iid in {9691,9693,9695,9697,9699}:
        return 'quest-imitation rune: exact Slug Menace source states it cannot be used to cast a spell and is used for quest progression'
    if iid in {9690,9692,9694,9696,9698,11155}:
        return 'quest-only rune derivative/quest component; no ordinary spellcasting-rune mechanics for this exact state'
    if 11686<=iid<=11699 or iid==22208:
        return 'Barbarian Assault mode-only rune copy; its exact variant is distinct from ordinary bankable spell rune'
    if iid in {6422,6424,6426,6428,6430,6432,6434,6436,6438,7554,7556,7558,7560}:
        return 'no exact numeric-ID Wiki infobox fact in the frozen packet; alias or activity copy is not inferred from the shared ordinary-rune name'
    if 'poh shield' in name or 'poh shield' in title.lower() or any(x in name for x in ('collection log','collection staff','dragonmask','sailing boat keel','fletching arrow','fletching dart','nails rune','zogre brutal','tgod rune')):
        return 'unresolved identity or incompatible display/material/ammunition use; exact spell-rune semantics are not established for this ID'
    if article is None or variant is None:
        return 'no exact-ID Wiki article/variant proof in the frozen packet; no semantic propagation by name or alias'
    if 'talisman' in title.lower() or 'tiara' in title.lower() or 'pouch' in title.lower() or 'pouch' in name:
        return 'Runecraft altar access, headgear, or rune storage is a distinct primary function from a spellcasting rune'
    if iid==24607 or 'blighted' in title.lower():
        return 'blighted mode-specific spell sack; excluded from ordinary rune cohort'
    if 'Binding necklace' in title:
        return 'Runecraft production utility, not an item spent as a spellcasting rune'
    if 'ground astral' in title.lower():
        return 'quest-specific processed rune component; exact item is not used as an ordinary spell rune'
    return f"v15 {decision.get('decision')} status/category candidate not admitted by the strict exact spell-rune allowlist"

def main():
    decisions=read_jsonl(DECISIONS)
    decision_by_id={r['itemId']:r for r in decisions}
    packets={r['itemId']:r for r in read_jsonl(PACKET)}
    index=json.loads(INDEX.read_text(encoding='utf-8-sig'))
    by_id={iid:(title,a) for title,a in index.items() for iid in a.get('exactInfoboxItemIds',[])}
    proposals=[]; rejected=[]; definitions={}
    for iid in sorted(POSITIVE_IDS):
        d=decision_by_id[iid]; packet=packets[iid]; cur=packet['current']
        if d.get('decision')!='certify' or d.get('proposedCategory')!='RUNE': raise ValueError(f'{iid}: not a v15 RUNE certificate')
        expected=(cur['category'],cur['subcategory'],cur['ironmanTabKey'],cur['tags'])
        proposed=(d.get('proposedCategory'),d.get('proposedSubcategory'),d.get('proposedIronmanTabKey'),d.get('proposedTags',[]))
        if expected!=proposed: raise ValueError(f'{iid}: v15 proposal differs from frozen current route/tags')
        if iid not in by_id: raise ValueError(f'{iid}: no exact-ID article-index match')
        title,art=by_id[iid]
        if art.get('parserError'): raise ValueError(f'{iid}: parser error: {art["parserError"]}')
        if art['title']!=d['evidence'][0]['sourceTitle'] or int(art['revid'])!=int(d['evidence'][0]['sourceRevision']) or art['sha256']!=d['evidence'][0]['sourceHash'].removeprefix('sha256:'):
            raise ValueError(f'{iid}: v15 citation does not match exact indexed title/revision/hash')
        variant=art['variants'].get(str(iid))
        if not variant: raise ValueError(f'{iid}: missing exact item variant fields')
        params=variant.get('params',{})
        fields=exact_variant_fields(variant)
        lead=extract_lead(Path(ROOT/Path(art['path'])).read_text(encoding='utf-8-sig'))
        mechanics=actual_spell_mechanics(lead)
        if not mechanics: raise ValueError(f'{iid}: no literal lead mechanic for usable spell rune')
        if params.get('equipable')!='No' or params.get('stackable')!='Yes': raise ValueError(f'{iid}: exact variant state not ordinary non-equippable stack rune')
        if not any(str(iid)==str(value).strip() for key,value in fields.items() if key.lower().startswith('id')):
            raise ValueError(f'{iid}: exact variant raw ID field does not bind this item')
        rawpath=ROOT/Path(art['path'])
        if sha(rawpath)!=art['sha256']: raise ValueError(f'{iid}: article text hash mismatch')
        raw=rawpath.read_text(encoding='utf-8-sig')
        # Inspect the full article, keeping source paragraphs for runecrafting,
        # purchases/currency/consumption, spellcasting, and competing functions.
        all_paras=split_paragraphs(raw)
        contexts=[p for p in all_paras if COMPETING_RE.search(p) and not p.startswith('{{Infobox Item')]
        headings=[line.strip() for line in raw.splitlines() if line.lstrip().startswith('==')]
        key=f"{art['title']}|{art['revid']}|{art['sha256']}"
        definitions[key]={
            'sourceTitle':art['title'],'sourceRevision':art['revid'],'sourceUrl':art['sourceUrl'],
            'sourceHash':'sha256:'+art['sha256'],'rawArtifactPath':Path(art['path']).as_posix(),
            'fullOwnSubjectLead':lead,'literalSpellcastingMechanicParagraphs':mechanics,
            'fullArticleSectionHeadings':headings,'fullArticleCompetingUseAndContextParagraphs':contexts,
            'exactNumericVariant':{'label':variant.get('label'),'suffix':variant.get('suffix'),'variant':variant.get('variant'),'name':variant.get('name'),'rawInfoboxFields':fields},
        }
        proposals.append({
            'itemId':iid,'itemName':packet.get('catalogName') or packet.get('registryName'),
            'sourceDefinitionKey':key,'exactSourceTitle':art['title'],'sourceRevision':art['revid'],'sourceUrl':art['sourceUrl'],'sourceHash':'sha256:'+art['sha256'],
            'frozenCurrentPrimaryRoute':{'category':cur['category'],'subcategory':cur['subcategory'],'ironmanTabKey':cur['ironmanTabKey']},
            'proposedPrimaryRoute':{'category':cur['category'],'subcategory':cur['subcategory'],'ironmanTabKey':cur['ironmanTabKey']},
            'reviewStatus':'ROOT_REVIEW_PROPOSAL','predicate':'The exact item is a retained, stackable ordinary rune whose own source directly documents use to cast or pay the rune cost of named/defined spells.',
            'rationale':rationale_for(iid),'tagsAndRoles':'not assessed or claimed',
        })
    for iid,packet in sorted(packets.items()):
        if packet['current']['category']!='RUNE' or iid in POSITIVE_IDS: continue
        d=decision_by_id[iid]
        e=next((e for e in d.get('evidence',[]) if e.get('kind')=='exact_wiki'),None)
        title=e.get('sourceTitle') if e else None
        art=index.get(title) if title else None
        variant=art.get('variants',{}).get(str(iid)) if art else None
        reason=exclusion_reason(iid,d,packet,art,variant)
        record={'itemId':iid,'itemName':packet.get('catalogName') or packet.get('registryName'),'v15Decision':d.get('decision'),'v15ProposedCategory':d.get('proposedCategory'),'frozenCurrentRoute':packet['current'],'reason':reason}
        if e: record.update({'sourceTitle':title,'sourceRevision':e.get('sourceRevision'),'sourceUrl':e.get('source'),'sourceHash':e.get('sourceHash'),'v15SourceQuote':e.get('quote')})
        if art and variant:
            rawpath=ROOT/Path(art['path']); raw=rawpath.read_text(encoding='utf-8-sig')
            if sha(rawpath)!=art['sha256']: raise ValueError(f'{iid}: rejected-source body hash mismatch')
            intro=extract_lead(raw)
            record['exactVariantFields']=exact_variant_fields(variant)
            if iid in {9691,9693,9695,9697,9699}:
                negative=[para for para in split_paragraphs(raw) if re.search(r'unlike normal|cannot be used to cast|cannot replace a normal|cannot be used for spells',para,re.I)]
                if not negative: raise ValueError(f'{iid}: expected direct negative spell-use proof not found')
                record['exactNegativeAndQuestMechanics']=negative
            if iid in {9690,9691,9692,9693,9694,9695,9696,9697,9698,9699,11686,11687,11688,11689,11690,11691,11692,11693,11694,11695,11696,11697,11698,11699,22208,24607}:
                key=f"{art['title']}|{art['revid']}|{art['sha256']}"
                if key not in definitions:
                    definitions[key]={'sourceTitle':art['title'],'sourceRevision':art['revid'],'sourceUrl':art['sourceUrl'],'sourceHash':'sha256:'+art['sha256'],'rawArtifactPath':Path(art['path']).as_posix(),'fullOwnSubjectLead':intro,'exactNumericVariant':{'label':variant.get('label'),'suffix':variant.get('suffix'),'variant':variant.get('variant'),'name':variant.get('name'),'rawInfoboxFields':exact_variant_fields(variant)}}
                record['sourceDefinitionKey']=key
        rejected.append(record)
    # Explicitly document the required mode/quest exclusions even if shard
    # ownership or v15 assignment changes in a later rerun.
    required_exceptions=[]
    for iid in [9690,9691,9692,9693,9694,9695,9696,9697,9698,9699,11686,11687,11688,11689,11690,11691,11692,11693,11694,11695,11696,11697,11698,11699,22208]:
        if iid in packets and packets[iid]['current']['category']!='RUNE':
            required_exceptions.append({'itemId':iid,'itemName':packets[iid].get('catalogName'),'frozenCurrentRoute':packets[iid]['current'],'reason':'quest-imitation or activity-mode rune copy; not an ordinary spellcasting rune'})
    doc={'schemaVersion':1,'purpose':'Exact-ID root review proposals only; not approved ledger decisions and not production preset edits.',
         'selectionScope':'Frozen v15 RUNE candidates; unchanged category/subcategory/tab; standard or combination rune that own exact-ID source identifies as usable in spellcasting.',
         'inputs':{'v15Decisions':{'path':DECISIONS.relative_to(ROOT).as_posix(),'sha256':'sha256:'+sha(DECISIONS)},'reviewerPacket':{'path':PACKET.relative_to(ROOT).as_posix(),'sha256':'sha256:'+sha(PACKET)},'articleIndex':{'path':INDEX.relative_to(ROOT).as_posix(),'sha256':'sha256:'+sha(INDEX)},'generator':{'path':Path(__file__).relative_to(ROOT).as_posix(),'sha256':'sha256:'+sha(Path(__file__))}},
         'positiveProposals':proposals,'uniqueSourceDefinitions':definitions,'rejectedOrAmbiguousCurrentRuneRows':rejected,'additionalQuestOrModeCopyExclusions':required_exceptions,
         'counts':{'positiveProposals':len(proposals),'uniqueSourcePages':len(definitions),'rejectedOrAmbiguousCurrentRuneRows':len(rejected),'additionalQuestOrModeCopyExclusions':len(required_exceptions)}}
    OUT.parent.mkdir(parents=True,exist_ok=True)
    OUT.write_text(json.dumps(doc,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(doc['counts'],indent=2)); print('output',OUT.relative_to(ROOT))

def rationale_for(iid):
    if 554<=iid<=566: return 'Own lead directly states that this exact rune is used in/cast for spells; the full-page review retains runecrafting, shop, staff/infinite-rune, trading, and other documented contexts without asserting those secondary roles absent.'
    if 4694<=iid<=4699: return 'Own lead identifies this exact combination rune as satisfying its paired elemental rune costs for spells; the full-page review also records creation, purchases, staff supply, and quest uses.'
    if iid==9075: return 'Own lead identifies astral runes as used in Lunar spells; altar access, crafting requirements, and shop context are included from the full article.'
    if iid==21880: return 'Own lead states wrath runes are used for surge and offering spells; Dragon Slayer II altar access and the separate mode-only variant are surfaced as context.'
    if iid==28929: return 'Own article documents use in place of fire runes for non-combat spells and as a source for fire-spell effects; its searing-page crafting use is retained as competing context.'
    if iid==30843: return 'Own article directly states that aether runes cast named spells and satisfy paired cosmic/soul costs; the substantial oathplate crafting consumption and price comparison are included for primary-placement review.'
    raise ValueError(iid)
if __name__=='__main__': main()
