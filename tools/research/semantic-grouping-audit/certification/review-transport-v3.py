import argparse, collections, hashlib, json, re
from pathlib import Path
ROOT=Path(__file__).resolve().parents[4]
BASE=ROOT/'tmp/category-certification'
PREV=BASE/'reviews/transport-v2/decisions.jsonl'
PACKET=BASE/'reviewer-packets/currency-runes-teleport.jsonl'
INDEX=BASE/'wiki-articles/article-index.json'
OUT=BASE/'reviews/transport-v3'

def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def exact(index,i):
 h=[(t,e) for t,e in index.items() if i in e.get('exactInfoboxItemIds',[]) and str(i) in e.get('variants',{})]
 return h[0] if len(h)==1 else None
def after_infobox(text):
 a=text.find('{{Infobox Item')
 if a<0:return 0
 depth=0
 for j in range(a,len(text)-1):
  if text[j:j+2]=='{{':depth+=1
  elif text[j:j+2]=='}}':
   depth-=1
   if depth==0:return j+2
 return 0
def quote_sentence(text,marker):
 body=after_infobox(text); p=text.find(marker,body)
 if p<0: raise ValueError(f'marker absent: {marker}')
 left=max(body,text.rfind('\n\n',body,p)+2); right=text.find('\n\n',p)
 if right<0:right=len(text)
 para=' '.join(text[left:right].split()); m=para.find(marker)
 # A bounded sentence from the subject paragraph; exclude adjoining lore/list material.
 prev=[x.end() for x in re.finditer(r'[.!?](?:\s|$)',para[:m])]
 start=prev[-1] if prev else (para.rfind(']]',0,m)+2 if ']]' in para[:m] else 0)
 endm=re.search(r'[.!?](?:\s|$)',para[m:]); end=m+endm.end() if endm else min(len(para),m+420)
 q=para[start:end].strip()
 if not q or marker not in q: raise ValueError(f'quote failed marker: {marker}')
 return q
def ev(i,index,marker):
 hit=exact(index,i)
 if not hit: raise ValueError(f'no unique exact article for {i}')
 title,e=hit; path=ROOT/e['path']
 if sha(path)!=e['sha256']: raise ValueError(f'raw article hash mismatch {i}')
 params=e['variants'][str(i)].get('params',{})
 ids={part.strip() for k,v in params.items() if k=='id' or re.fullmatch(r'id[1-9][0-9]*',k) for part in (v if isinstance(v,list) else [v]) for part in str(part or '').split(',')}
 if str(i) not in ids: raise ValueError(f'variant params do not bind numeric ID {i}')
 text=path.read_text(encoding='utf-8')
 return {'kind':'exact_wiki','source':e['sourceUrl'],'sourceTitle':title,'sourceRevision':e['revid'],'sourceHash':'sha256:'+e['sha256'],'itemId':i,'quote':quote_sentence(text,marker)}
# Exact-ID case table: action, destination category/subcategory/tab, semantic roles, tags, quote marker, rationale.
CASES={
 1464:('certify','CURRENCY','currency','currency-utilities',['spendable_exchange_value'],[],'They can be exchanged with the [[Ticket Merchant]]','The ticket is expressly redeemable for the Ranging Guild prize exchange.'),
 30038:('certify','CURRENCY','currency','currency-utilities',['spendable_exchange_value'],[],'Termites serve as the currency for','Termites are explicitly the currency for a named repeatable shop; the anteater use is not the basis for classification.'),
 13307:('certify','CURRENCY','currency','currency-utilities',['spendable_exchange_value'],[],'It can be used on [[Nigel]]','Blood money is spent for a named Deadman Mode purchase; this is mode-specific value, not general-purpose coins.'),
 22820:('certify','CURRENCY','currency','currency-utilities',['spendable_exchange_value'],[],'Molch pearls can be traded to Alry','Molch pearls are redeemable at the named shop for equipment and progression rewards.'),
 24719:('certify','CURRENCY','currency','currency-utilities',['spendable_exchange_value'],[],'It can be purchased from the [[Mysterious Hallowed Goods]] shop','The token is bought with hallowed marks and consumed for additional activity time; this is a documented access/time utility.'),
 25527:('certify','CURRENCY','currency','currency-utilities',['spendable_exchange_value'],[],'It is used as currency in','Stardust is expressly currency in a named shop and also pays to recharge named items.'),
 563:('certify','RUNE','rune','currency-utilities',['spellcasting_supply'],[],'The \'\'\'law rune\'\'\' is a [[Runes|rune]] used in all','Law rune is directly documented as a consumable for teleportation and telekinesis spells.'),
 4694:('certify','RUNE','rune','currency-utilities',['spellcasting_supply'],[],'They can be used as one [[fire rune]]','Steam rune substitutes for fire and water runes in casting; it is an active spell supply.'),
 4695:('certify','RUNE','rune','currency-utilities',['spellcasting_supply'],[],'They count as two separate runes: one [[water rune]]','Mist rune substitutes for its component runes in casting; it is an active spell supply.'),
 4696:('certify','RUNE','rune','currency-utilities',['spellcasting_supply'],[],'They count as two separate runes: one [[earth rune]]','Dust rune substitutes for its component runes in casting; it is an active spell supply.'),
 4697:('certify','RUNE','rune','currency-utilities',['spellcasting_supply'],[],'will cost only one smoke rune','Smoke rune substitutes for its component runes in casting; it is an active spell supply.'),
 4698:('certify','RUNE','rune','currency-utilities',['spellcasting_supply'],[],'will spend only one mud rune','Mud rune substitutes for its component runes in casting; it is an active spell supply.'),
 4699:('certify','RUNE','rune','currency-utilities',['spellcasting_supply'],[],'will spend only one lava rune','Lava rune substitutes for its component runes in casting; it is an active spell supply.'),
 9075:('certify','RUNE','rune','currency-utilities',['spellcasting_supply'],[],'are [[runes]] used in all','Astral runes are expressly required by Lunar spellcasting.'),
 28929:('certify','RUNE','rune','currency-utilities',['spellcasting_supply'],[],'they can be used in place of fire runes','Sunfire runes function as fire-rune substitutes in spells and provide a documented combat spell effect.'),
}
# The article distinguishes altar-access tiaras from spell runes. Cite the exact item’s equipped altar-entry mechanic.
TIARAS={5527:'air',5529:'mind',5531:'water',5533:'body',5535:'earth',5537:'fire',5539:'cosmic',5541:'nature',5543:'chaos',5545:'law',5547:'death',5549:'blood',22121:'wrath',26804:'elemental'}
for i,n in TIARAS.items():
 marker=(f'When a {n} tiara is equipped' if n=='nature' else f'While {"an" if n[0] in "aeiou" else "a"} {n} tiara is equipped')
 CASES[i]=('certify','RUNE','runecrafting-focus','skilling-tools',['runecrafting_focus'],[],marker,'The exact tiara grants altar entry while equipped, making it a Runecraft focus rather than a spell rune.')
# Strong counterexamples to the current transport/rune/currency placement.
REVISES={
 32083:('CURRENCY','currency','currency-utilities',['spendable_exchange_value'],[],'is a type of [[sawmill coupon]] which is used to cover','The exact wood-plank coupon pays the listed sawmill conversion cost and belongs on the currency/utilities tab rather than resources.'),
 32085:('CURRENCY','currency','currency-utilities',['spendable_exchange_value'],[],'is a type of [[sawmill coupon]] which is used to cover','The exact oak-plank coupon pays the listed sawmill conversion cost and belongs on the currency/utilities tab rather than resources.'),
 9693:('CLEANUP','quest-item','storage-cleanup',['quest_item'],['quest-use'],'It cannot replace a normal [[air rune]] during spells','The exact Slug Menace air rune is a quest-specific door key, and the article explicitly says it cannot serve as the ordinary spell rune.'),
 9106:('CLEANUP','cleanup','storage-cleanup',['unobtainable_internal_item'],[],'is an [[unobtainable item]]','The exact astral tiara was never made obtainable and was not needed for Astral Altar access; it cannot function as a retained Runecraft focus.'),
 4023:('TOOL','quest-utility','skilling-tools',['quest_utility'],['quest-use'],'is used for making [[greegree]]s until the completion','The exact monkey talisman is an Ape Atoll utility used to create greegrees, not an altar-access Runecraft focus.'),
 30858:('SKILLING','crafting-material','resources',['crafting_material'],[],'are used to create [[infernal plate]]s','Infernal nuggets are a Smithing intermediate for oathplate armour, not exchange currency.'),
 31946:('SKILLING','crafting-material','resources',['crafting_material'],['activity-sailing'],'is used to build a [[fathom pearl]] on a [[boat]]','The exact Echo pearl is a Sailing boat-construction input, not currency.'),
 11155:('CLEANUP','quest-item','storage-cleanup',['quest_item'],['quest-use'],'The item has no use outside of these quests','The exact ground astral rune is a quest-only processed intermediate, not a spellcasting rune.'),
 20008:('CLUE','cosmetic','clues-cosmetics',['cosmetic_collectible'],[],'is obtained as a possible reward from','The exact fancy tiara is a master-clue cosmetic and explicitly provides no Runecraft perks.'),
 24545:('CLEANUP','cleanup','storage-cleanup',['unobtainable_internal_item'],[],'is an unobtainable item which shows the portal','This dummy portal is an unobtainable interface prop that never performs transport.'),
 26788:('SKILLING','crafting-material','resources',['crafting_material'],[],'They are a purely cosmetic head slot item, though they can be turned into','The gold tiara is a cosmetic Crafting product and input used to make distinct imbued focus tiaras; it is not itself an altar focus.'),
 26906:('CLEANUP','quest-item','storage-cleanup',['quest_item'],['quest-use'],'is created when using the [[Orb (Devious Minds)|orb]]','The exact Devious Minds pouch is a quest artifact used as a beacon in an NPC cutscene, not player transport or a usable rune pouch.'),
 28375:('SKILLING','construction-material','resources',['construction_material'],[],'is an item used during [[Desert Treasure II - The Fallen Empire]]','The schematic is given to an NPC to create a separate portal; it neither transports the player nor installs a player-operated network item.'),
 33798:('CLEANUP','quest-item','storage-cleanup',['quest_item'],['quest-use'],'They are combined with the [[blisterwood flail]]','This quest-specific Hallowed marks variant is a crafting input for the hallowed flail, explicitly distinct from Sepulchre exchange marks.'),
}
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--previous',type=Path,default=PREV);ap.add_argument('--packets',type=Path,default=PACKET);ap.add_argument('--index',type=Path,default=INDEX);ap.add_argument('--output',type=Path,default=OUT);a=ap.parse_args()
 rows=[json.loads(x) for x in a.previous.read_text(encoding='utf-8').splitlines() if x.strip()]; by={d['itemId']:d for d in rows}
 if len(rows)!=1138 or len(by)!=1138: raise ValueError('v2 input must contain 1,138 unique IDs')
 packets={x['itemId']:x for x in (json.loads(l) for l in a.packets.read_text(encoding='utf-8-sig').splitlines() if l.strip())}; index=json.loads(a.index.read_text(encoding='utf-8'))
 if len(packets)!=1138: raise ValueError('packet scope differs from expected 1,138')
 changed=[]
 for i,(action,cat,sub,tab,roles,tags,marker,why) in CASES.items():
  d=by[i]
  if d['decision']!='unresolved':raise ValueError(f'case {i} is not unresolved in frozen v2')
  if packets[i]['current']!={'category':cat,'subcategory':sub,'ironmanTabKey':tab,'tags':packets[i]['current'].get('tags',[])}: raise ValueError(f'certify target differs from frozen current assignment for {i}')
  e=ev(i,index,marker); d.update(decision=action,proposedCategory=cat,proposedSubcategory=sub,proposedIronmanTabKey=tab,proposedRoles=roles,proposedTags=packets[i]['current']['tags'],semanticPredicate=f'Exact item mechanics establish {cat}/{sub} for item {i}.',rationale=why,evidence=[e],identityLinks=[]);changed.append(i)
 for i,(cat,sub,tab,roles,tags,marker,why) in REVISES.items():
  d=by[i]
  if d['decision']!='unresolved':raise ValueError(f'revise case {i} is not unresolved in frozen v2')
  e=ev(i,index,marker); d.update(decision='revise',proposedCategory=cat,proposedSubcategory=sub,proposedIronmanTabKey=tab,proposedRoles=roles,proposedTags=tags,semanticPredicate=f'Exact item mechanics establish that {i} does not perform its compiled transport/rune/currency role.',rationale=why,evidence=[e],identityLinks=[]);changed.append(i)
 a.output.mkdir(parents=True,exist_ok=True);out=a.output/'decisions.jsonl';out.write_text(''.join(json.dumps(d,ensure_ascii=False,sort_keys=True)+'\n' for d in rows),encoding='utf-8')
 counts=collections.Counter(x['decision'] for x in rows)
 summary={'version':'transport-review-v3','previousSha256':'sha256:'+sha(a.previous),'packetSha256':'sha256:'+sha(a.packets),'articleIndexSha256':'sha256:'+sha(a.index),'recordCount':len(rows),'decisions':dict(counts),'changedCount':len(changed),'changedItemIds':sorted(changed),'notes':'Versioned research review; v1 and v2 remain unchanged. Every v3 action uses exact numeric-ID article+variant evidence and source revision/hash. Unresolved rows otherwise remain as in v2.'}
 (a.output/'summary.json').write_text(json.dumps(summary,indent=2,ensure_ascii=False,sort_keys=True)+'\n',encoding='utf-8');print(json.dumps(summary,indent=2))
if __name__=='__main__':main()
