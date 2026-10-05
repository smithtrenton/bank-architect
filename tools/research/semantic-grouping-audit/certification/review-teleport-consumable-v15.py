#!/usr/bin/env python3
"""Build a strict, source-verifiable root-review packet from transport-v15.

This proposal builder does not mutate production data or the approved ledger.
It selects only frozen v15 certificates whose primary assignment is unchanged,
whose exact-ID variant is a non-equippable stackable item with a usable item
option, and whose own article introduction directly defines player transport.
"""
from __future__ import annotations
import hashlib, json, re
from pathlib import Path

ROOT=Path(__file__).resolve().parents[4]
DECISIONS=ROOT/'tmp/category-certification/reviews/transport-v15/decisions.jsonl'
PACKET=ROOT/'tmp/category-certification/reviewer-packets/currency-runes-teleport.jsonl'
INDEX=ROOT/'tmp/category-certification/wiki-articles/article-index.json'
OUT=ROOT/'tmp/category-certification/reviews/transport-v16/ordinary-teleport-consumables-review.json'
ACTIVE={'break','teleport','use','eat','drink','launch','squash','rub','reminisce','play','activate','operate'}
VARIANT_KEYS=re.compile(r'^(?:id\d*|name\d*|version\d*|options|wornoptions|equipable|stackable|tradeable|quest|examine|charges?\d*|uses?\d*|value\d*|destroy|weight)$',re.I)

def load_jsonl(path): return [json.loads(x) for x in path.read_text(encoding='utf-8-sig').splitlines() if x.strip()]
def sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()
def clean_markup(text):
    text=re.sub(r'\[\[File:[^\]]*\]\]','',text,flags=re.I)
    text=re.sub(r'\[\[([^]|]+)\|([^]]+)\]\]',r'\2',text)
    text=re.sub(r'\[\[([^]]+)\]\]',r'\1',text)
    return text

def intro_after_infobox(raw):
    start=raw.find('{{Infobox Item')
    if start<0: return ''
    close=re.search(r'\n}}\s*\n',raw[start:])
    if not close: return ''
    body=raw[start+close.end():]
    return body.split('\n==',1)[0].strip()

def paragraphs(raw_intro):
    return [p.strip() for p in re.split(r'\n\s*\n',raw_intro) if p.strip()]

def direct_transport_paragraphs(intro, options):
    opts={x.strip().lower() for x in options.split(',')}
    active=opts & ACTIVE
    chosen=[]
    for para in paragraphs(intro):
        flat=clean_markup(para)
        low=flat.lower()
        # A functional definition must bind movement to the item/player in its
        # own sentence/paragraph; category membership or a teleport-name alone
        # is not sufficient. Boat relocation is expressly excluded below.
        moves=('teleport' in low or 'teleports' in low or 'take players' in low or 'takes players' in low or 'transport' in low)
        player=bool(re.search(r'\b(?:players?|you)\b',low))
        action_forms={'break':('break','broken'),'teleport':('teleport','teleports','teleporting'),'use':('use','used','using'),'eat':('eat','eaten'),'drink':('drink','drunk'),'launch':('launch','launched'),'squash':('squash','squashed'),'rub':('rub','rubbed'),'reminisce':('reminisce','reminisced'),'play':('play','played'),'activate':('activate','activated'),'operate':('operate','operated')}
        item_action=bool(active) and any(re.search(r'\b(?:'+ '|'.join(re.escape(w) for w in action_forms.get(a,(a,))) +r')\b',low) for a in active)
        direct_item=bool(re.search(r"(?:^|\s)(?:the |a |an )?['’]{0,3}[a-z][^.!?]{0,100}(?:is|are|can|will|has|teleports|teleport)\b",low))
        # Tablet / scroll articles often say the item "can be broken ... to
        # teleport"; action in the exact Infobox option backs the usable state.
        if moves and player and (item_action or 'can teleport' in low or 'teleports the player' in low or 'teleport the player' in low) and direct_item:
            chosen.append(para)
    return chosen

def row_name(row): return row.get('catalogName') or row.get('registryName') or ''

def main():
    decisions=load_jsonl(DECISIONS)
    packets={r['itemId']:r for r in load_jsonl(PACKET)}
    articles=json.loads(INDEX.read_text(encoding='utf-8-sig'))
    selected=[]; rejected=[]; definitions={}
    for d in decisions:
        iid=d['itemId']; packet=packets[iid]; cur=packet['current']
        if cur['category']!='TELEPORT':
            continue
        ev=next((e for e in d.get('evidence',[]) if e.get('kind')=='exact_wiki'),None)
        if d.get('decision')!='certify' or d.get('proposedCategory')!='TELEPORT':
            rejected.append({'itemId':iid,'itemName':row_name(packet),'sourceTitle':ev.get('sourceTitle') if ev else None,'sourceRevision':ev.get('sourceRevision') if ev else None,'reason':f"v15 {d.get('decision')} status or target does not support an unchanged TELEPORT primary placement; retained for independent review",'v15EvidenceQuote':ev.get('quote') if ev else None,'v15ProposedCategory':d.get('proposedCategory'),'v15ProposedSubcategory':d.get('proposedSubcategory'),'frozenCurrentRoute':cur,'v15Decision':d.get('decision')})
            continue
        reason=''
        if not ev: reason='v15 lacks exact Wiki evidence'
        elif (d.get('proposedCategory'),d.get('proposedSubcategory'),d.get('proposedIronmanTabKey'),d.get('proposedTags',[])) != (cur['category'],cur['subcategory'],cur['ironmanTabKey'],cur['tags']): reason='v15 target does not exactly match the frozen current route/tags'
        else:
            art=articles.get(ev['sourceTitle'])
            if not art: reason='exact source title missing from article index'
            elif iid not in art.get('exactInfoboxItemIds',[]): reason='exact numeric ID is not bound in this article Infobox Item'
            elif int(art['revid'])!=int(ev['sourceRevision']) or art['sha256']!=ev['sourceHash'].removeprefix('sha256:'): reason='v15 revision/hash does not match pinned article index'
            else:
                variant=art['variants'].get(str(iid))
                if not variant: reason='no exact-ID variant fields'
                else:
                    params=variant.get('params',{})
                    opts=params.get('options','')
                    active={x.strip().lower() for x in opts.split(',')} & ACTIVE
                    if not active: reason='exact item variant has no active transport/use option'
                    elif params.get('equipable')!='No': reason='equipment or equipability not explicitly excluded; ordinary consumable scope excludes wearables'
                    elif params.get('stackable')!='Yes': reason='non-stackable/reusable state falls outside ordinary consumable scope'
                    elif art['title'].lower().startswith('target teleport'): reason='PvP assigned-target consumable; special activity context'
                    elif art['title'].lower().startswith('summon boat'): reason='moves boat rather than transporting the player'
                    elif 'gauntlet' in art['title'].lower(): reason='activity-specific copy, excluded by scope'
                    else:
                        rawpath=ROOT/Path(art['path'])
                        raw=rawpath.read_text(encoding='utf-8-sig')
                        if sha(rawpath)!=art['sha256']: reason='article body hash mismatch'
                        else:
                            intro=intro_after_infobox(raw)
                            actionparas=direct_transport_paragraphs(intro,opts)
                            if not actionparas: reason='no direct own-article paragraph binds exact subject/use state to player transport'
                            else:
                                full_intro='\n\n'.join(paragraphs(intro))
                                source_key=f"{art['title']}|{art['revid']}|{art['sha256']}"
                                definitions.setdefault(source_key,{
                                    'sourceTitle':art['title'],'sourceRevision':art['revid'],'sourceUrl':art['sourceUrl'],
                                    'sourceHash':'sha256:'+art['sha256'],'rawArtifactPath':str(Path(art['path']).as_posix()),
                                    'completeLeadDefinitionAndCompetingContext':full_intro,
                                    'semanticUseParagraphs':actionparas,
                                    'competingContextParagraphs':[para for para in paragraphs(intro) if para not in actionparas],
                                })
                                # Keep raw item fields that bind identity, use,
                                # action, charge/state, and item retention.
                                fields={k:v for k,v in params.items() if VARIANT_KEYS.match(k)}
                                # Exact binding metadata emitted by parser.
                                exact_variant={k:variant.get(k) for k in ('label','suffix','variant','name')}
                                exact_variant['rawInfoboxFields']=fields
                                selected.append({
                                    'itemId':iid,'itemName':row_name(packet),'sourceTitle':art['title'],
                                    'sourceRevision':art['revid'],'sourceUrl':art['sourceUrl'],'sourceHash':'sha256:'+art['sha256'],
                                    'definitionKey':source_key,'exactVariant':exact_variant,
                                    'currentPrimaryRoute':{'category':cur['category'],'subcategory':cur['subcategory'],'ironmanTabKey':cur['ironmanTabKey']},
                                    'proposedPrimaryRoute':{'category':cur['category'],'subcategory':cur['subcategory'],'ironmanTabKey':cur['ironmanTabKey']},
                                    'proposedTags':cur['tags'],'tagClaimScope':'retained-from-frozen-current-row; not reviewed or newly claimed',
                                    'proposedRoles':None,'roleClaimScope':'unassessed',
                                    'reviewStatus':'ROOT_REVIEW_PROPOSAL',
                                    'transportPredicate':'Exact-ID variant is explicitly non-equippable and stackable, exposes an active use option, and its own introduction directly defines the item as moving the player by teleport/transport.',
                                    'rationale':'The v15-certified primary route is unchanged; this proposal adds no role or tag claims. See the complete unique lead and exact variant fields for direct transport mechanics, requirements, limits, and competing contexts.',
                                })
        if reason:
            rejected.append({'itemId':iid,'itemName':row_name(packet),'sourceTitle':ev.get('sourceTitle') if ev else None,'sourceRevision':ev.get('sourceRevision') if ev else None,'reason':reason,'v15EvidenceQuote':ev.get('quote') if ev else None,'frozenCurrentRoute':cur,'v15Decision':d.get('decision')})
    selected.sort(key=lambda x:x['itemId']); rejected.sort(key=lambda x:x['itemId'])
    doc={'schemaVersion':1,'purpose':'Focused independent root-review proposal; not an approved ledger and not production data.',
         'selectionScope':'v15 TELEPORT certify rows only; unchanged current route and tags; exact-ID page binding; non-equippable, stackable usable item; own-article direct player transport definition.',
         'inputs':{'v15Decisions':{'path':str(DECISIONS.relative_to(ROOT).as_posix()),'sha256':'sha256:'+sha(DECISIONS)},'reviewerPacket':{'path':str(PACKET.relative_to(ROOT).as_posix()),'sha256':'sha256:'+sha(PACKET)},'articleIndex':{'path':str(INDEX.relative_to(ROOT).as_posix()),'sha256':'sha256:'+sha(INDEX)},'builder':{'path':str(Path(__file__).relative_to(ROOT).as_posix()),'sha256':'sha256:'+sha(Path(__file__))}},
         'sourceDefinitions':definitions,'proposals':selected,'rejectedOrAmbiguous':rejected,
         'counts':{'proposals':len(selected),'uniqueSourceDefinitions':len(definitions),'rejectedOrAmbiguous':len(rejected)}}
    OUT.parent.mkdir(parents=True,exist_ok=True)
    OUT.write_text(json.dumps(doc,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(doc['counts'],indent=2)); print('output',OUT.relative_to(ROOT))
if __name__=='__main__': main()
