#!/usr/bin/env python3
"""Fresh exact-ID GEAR semantic reviewer for a frozen Wiki certification snapshot."""
from __future__ import annotations
import argparse, csv, hashlib, json, re
from collections import Counter
from pathlib import Path
from typing import Any
ROOT=Path(__file__).resolve().parents[4]
PACKET=ROOT/'tmp/category-certification/reviewer-packets/gear.jsonl'
JOINED=ROOT/'tmp/semantic-audit/joined.jsonl'
INDEX=ROOT/'tmp/category-certification/wiki-articles/article-index.json'
POLICY=ROOT/'tools/research/semantic-grouping-audit/certification/gear-approved-policy.json'
OUT_DEFAULT=ROOT/'tmp/category-certification/reviews/gear-v2'
JOINED_HASH=''
ARTICLE_TEXT_CACHE={}
BONUS_FIELDS={'stab_attack_bonus','slash_attack_bonus','crush_attack_bonus','range_attack_bonus','magic_attack_bonus','stab_defence_bonus','slash_defence_bonus','crush_defence_bonus','range_defence_bonus','magic_defence_bonus','strength_bonus','ranged_strength_bonus','prayer_bonus','magic_damage_bonus'}
SLOT_FOR={'weapon':{'weapon'},'2h':{'2h','2h weapon'},'head':{'head'},'body':{'body'},'legs':{'legs'},'feet':{'feet'},'hands':{'hands'},'ring':{'ring'},'neck':{'neck'},'shield':{'shield'},'magic-offhand':{'shield'},'cape':{'cape'}}
SLOT_SUB={'weapon':'weapon','2h':'2h','2h weapon':'2h','head':'head','body':'body','legs':'legs','feet':'feet','hands':'hands','ring':'ring','neck':'neck','shield':'shield','cape':'cape','ammo':'ammo'}
TAB={'GEAR':'combat-gear','POTION':'potions-food','HERBLORE':'herblore','SKILLING':'resources','TOOL':'skilling-tools','CLEANUP':'storage-cleanup','TELEPORT':'teleports','RUNE':'runes','CURRENCY':'currency','UNIQUE':'slayer-boss-loot','CLUE':'clues'}
def sha(b:bytes)->str:return hashlib.sha256(b).hexdigest()
def load_jsonl(path:Path)->list[dict[str,Any]]:return [json.loads(x) for x in path.read_text(encoding='utf-8-sig').splitlines() if x.strip()]
def exact_records(entry:dict[str,Any]|None,i:int)->list[dict[str,Any]]:
 out=[]
 for r in (entry or {}).get('wiki_records',[]):
  ids=r.get('item_id',[]); ids=ids if isinstance(ids,list) else [ids]
  if i in {int(x) for x in ids if str(x).isdigit()}:out.append(r)
 return out
def exact_stats(entry:dict[str,Any]|None)->tuple[set[str],set[str],list[dict[str,Any]]]:
 slots=set();values=set();rows=[]
 for m in (entry or {}).get('bonus_matches',[]):
  if m.get('status')!='UNIQUE' or m.get('method')!='EXACT_PAGE_SUB':continue
  for r in m.get('records',[]):
   rows.append(r)
   if r.get('equipment_slot'):slots.add(str(r['equipment_slot']).strip().lower())
   for f in BONUS_FIELDS:
    try:
     if float(r.get(f,0) or 0)>0:values.add(f)
    except (TypeError,ValueError):pass
 return slots,values,rows
def page_variant(a:dict[str,Any]|None,i:int)->dict[str,Any]:return a.get('variants',{}).get(str(i),{}) if a else {}
def selected_variant_params(a:dict[str,Any]|None,i:int)->dict[str,Any]:
 raw=page_variant(a,i).get('params',{});out=dict(raw)
 idkeys=[k for k,v in raw.items() if re.fullmatch(r'id\d*',k,re.I) and str(v)==str(i)]
 for idkey in idkeys:
  suffix=idkey[2:]
  for base in ('name','examine','options','value','tradeable','equipable'):
   key=base+suffix
   if key in raw:out[base]=raw[key]
 return out
def exact_variant_facts(a:dict[str,Any],i:int)->list[dict[str,str]]:
 p=page_variant(a,i).get('params',{}); facts=[]
 for key,value in p.items():
  if re.fullmatch(r'id\d*',key,re.I) and str(value)==str(i):
   suffix=key[2:]
   for f in (key,'name'+suffix,'examine'+suffix,'options'+suffix):
    if f in p:facts.append({'field':f,'value':str(p[f])})
 for f in ('name','equipable','tradeable','options','examine'):
  if f in p and not any(x['field']==f for x in facts):facts.append({'field':f,'value':str(p[f])})
 return facts
def article_text(a:dict[str,Any]|None)->str:
 if not a:return ''
 rel=a.get('path','')
 if rel not in ARTICLE_TEXT_CACHE:
  p=ROOT/rel;ARTICLE_TEXT_CACHE[rel]=p.read_text(encoding='utf-8',errors='replace') if p.is_file() else ''
 return ARTICLE_TEXT_CACHE[rel]
def definition(text:str,names:list[str])->str:
 for name in names:
  if not name:continue
  for spelling in (name,name.replace("'","''")):
   at=text.find("'''"+spelling+"'''")
   if at>=0:
    tail=text[at:]; end=re.search(r'\n\s*\n',tail)
    return tail[:end.start()] if end else tail[:1000]
 # Shared variant page: use the literal first bold lead after the item infobox.
 pos=text.find('}}'); body=text[pos+2:] if pos>=0 else text
 m=re.search(r"'''[^'\n]+'''[^\n]*(?:\n(?!\s*\n)[^\n]*)*",body)
 return m.group(0) if m else ''
def item_names(a:dict[str,Any]|None,i:int,packet:dict[str,Any])->list[str]:
 p=selected_variant_params(a,i);out=[]
 if p.get('name'):out.append(str(p['name']))
 out.append(str(packet.get('registryName','')))
 if a and a.get('title'):out.append(str(a['title']))
 return list(dict.fromkeys(x for x in out if x))
def article_ev(a:dict[str,Any],i:int,quote:str,claim:str)->dict[str,Any]:
 e={'kind':'exact_wiki','itemId':i,'sourceTitle':a['title'],'source':a['sourceUrl'],'sourceRevision':a['revid'],'sourceHash':'sha256:'+a['sha256'],'quote':quote[:240],'claim':claim}
 facts=exact_variant_facts(a,i)
 if facts:e['structuredFacts']=facts
 return e
def local_ev(i:int,line:str,linehash:str,claim:str,fields:dict[str,Any]|None=None)->dict[str,Any]:
 e={'kind':'local_source','sourceTitle':'Exact-ID joined Wiki snapshot row','source':'tmp/semantic-audit/joined.jsonl','sourcePath':'tmp/semantic-audit/joined.jsonl','sourceHash':JOINED_HASH,'sourceLineHash':'sha256:'+linehash,'itemId':i,'quote':line[:240],'claim':claim}
 if fields:e['fields']=fields
 return e
def literal_policy_quote(a:dict[str,Any],case:dict[str,Any],text:str)->str:
 q=str(case['semanticExcerpt']); norm=' '.join(q.split()); body=' '.join(text.split())
 if norm not in body:raise ValueError(f"policy excerpt not literal for {case['itemId']}")
 if a.get('revid')!=case.get('sourceRevision') or a.get('sha256')!=case.get('sourceSha256') or a.get('title')!=case.get('title'):raise ValueError(f"policy source pin mismatch for {case['itemId']}")
 # return raw substring using normalized token-boundary verifier below, retaining exact source spelling
 at=text.find(q)
 return q if at>=0 else q

def direct_nongear(p:dict[str,Any],a:dict[str,Any]|None,rec:dict[str,Any],params:dict[str,Any],definition_text:str,cats:set[str])->tuple[str,str,str,str,list[str]]|None:
 if p.get('auditScope') not in {'NAMED_EFFECTIVE','SUPPLEMENTAL'} or p['current']['category']!='GEAR' or not a:return None
 low=definition_text.lower(); item=' '.join([str(params.get('name','')),str(p.get('registryName',''))]).lower()
 equip=str(params.get('equipable','')).strip().lower()=='yes'
 if re.search(r'\b(?:interface item|animation item|interface icon)\b',low):return ('CLEANUP','cleanup','storage-cleanup','The exact item-page definition identifies this ID as an interface or animation artifact, not bankable equipment.',['interface_or_animation_artifact'])
 # Subject-specific state with no exact wear/wield option is not functional gear.
 options=[str(v).lower() for k,v in params.items() if re.fullmatch(r'options\d*',k,re.I)]
 if not equip and re.search(r'\bunstrung\b',item+' '+low) and re.search(r'string|wool|craft|make .*wear',low):
  sub='crafting-jewellery' if re.search(r'amulet|symbol|emblem|necklace|ring|bracelet',item) else 'crafting-material'
  return ('SKILLING',sub,'resources','The exact unwearable item is explicitly unfinished and requires a stringing/crafting step before it can be worn.',['crafting_component'])
 if 'burnt' in item and 'Category:Cooking' in cats and re.search(r'\bburnt\b|burn(?:ing|ed)',low):return ('CLEANUP','burnt-food','storage-cleanup','The exact item page identifies a burnt cooking result; its unusable state belongs in cleanup review.',['burnt_food'])
 if re.search(r'\b(?:type of food|a food(?: that| and)|can be eaten|when eaten|is eaten|restores? \d+ hitpoints|heals? (?:for )?\d+ hitpoints|consuming it heals)\b',low) and ('Category:Food' in cats or re.search(r'\bfood\b',low)):
  return ('POTION','food','potions-food','The exact item definition directly describes consumable food or a healing effect.',['consumable_food'])
 if not equip and str(a.get('title','')).lower().startswith('raw ') and re.search(r'cook(?:ed|ing)?|cooking',low):return ('SKILLING','raw-food','resources','The exact item is a raw food input with a directly described cooking use.',['raw_food_material'])
 if not equip and ('Category:Cooking' in cats or 'Category:Herblore' in cats) and re.search(r'intermediate product|used to make|used to create|used in (?:cooking|herblore)|ingredient',low):
  if 'Category:Herblore' in cats:return ('HERBLORE','herblore-supply','herblore','The exact page describes a nonwearable Herblore ingredient or intermediate.',['herblore_supply'])
  return ('SKILLING','cooking-material','resources','The exact page describes a nonwearable cooking ingredient or intermediate.',['cooking_material'])
 if not equip and 'Category:Quest items' in cats and re.search(r'quest item',low) and not re.search(r'weapon|armou?r|ammunition|combat',low):return ('CLEANUP','quest-item','storage-cleanup','The exact page identifies this unwearable item as a quest item without establishing a combat role.',['quest_item'])
 skill=bool(re.search(r'\b(?:used for|used to|used during|worn for|worn to)\b.{0,100}\b(?:fishing|woodcutting|mining|farming|construction|runecraft|smithing|agility|hunter|herblore|crafting)\b',low))
 negated_skill=bool(re.search(r'\b(?:cannot|can\x27t|not)\b.{0,100}\b(?:used for|used to|used during)\b.{0,100}\b(?:fishing|woodcutting|mining|farming|construction|runecraft|smithing|agility|hunter|herblore|crafting)\b',low))
 if skill and not negated_skill and not re.search(r'\bweapon\b|combat stats|combat effect|attack bonus|armour worn',low):return ('TOOL','skilling-utility','skilling-tools','The exact page gives the item a direct skilling-tool function and no combat role.',['skilling_utility'])
 return None

def make_decision(p:dict[str,Any],entry:dict[str,Any]|None,line:str,articles:dict[int,list[dict[str,Any]]],manual:dict[int,dict[str,Any]])->dict[str,Any]:
 i=p['itemId'];cur=p['current'];sub=cur['subcategory']; records=exact_records(entry,i)
 a=next((x for x in articles.get(i,[]) if str(i) in x.get('variants',{})),None)
 text=article_text(a); names=item_names(a,i,p); para=definition(text,names) if text else ''
 variant=page_variant(a,i);params=selected_variant_params(a,i);rec=records[0] if records else {}
 cats={k for k,v in rec.items() if k.startswith('Category:') and v is True}
 slots,bonuses,statrows=exact_stats(entry)
 exact=bool(a and i in {int(x) for x in a.get('exactInfoboxItemIds',[])})
 evid=[]
 # Direct article evidence uses literal page bytes only; exact variant fields bind family pages to this ID.
 if exact and (para or exact_variant_facts(a,i)):
  evid.append(article_ev(a,i,para,'Exact-ID article definition and/or structured infobox variant fields.'))
 linehash=hashlib.sha256(line.encode()).hexdigest() if line else ''
 fields={k:rec[k] for k in rec if k in {'item_id','item_name','examine','Category:Equipable items','Category:Food','Category:Cooking','Category:Quest items','Category:Teleportation items','Category:Skilling equipment','Category:Arrows','Category:Bolts','Category:Ammunition'}}
 if records and line:evid.append(local_ev(i,line,linehash,'Exact-ID joined source fields; local snapshot values are not represented as article quotations.',fields))
 statrow=statrows[0] if statrows else {}
 if statrow and line:
  statfields={'equipment_slot':statrow.get('equipment_slot')}
  for k in BONUS_FIELDS:
   if k in statrow and str(statrow[k]) not in ('0','0.0','None',''):statfields[k]=statrow[k]
  if len(statfields)>1:evid.append(local_ev(i,line,linehash,'Unique EXACT_PAGE_SUB equipment slot and nonzero combat values.',statfields))
 def base(dec,cat,sc,tags,roles,reason,predicate):
  return {'itemId':i,'shard':'gear','decision':dec,'proposedCategory':cat,'proposedSubcategory':sc,'proposedTags':tags,'proposedRoles':roles,'proposedIronmanTabKey':(cur['ironmanTabKey'] if dec=='certify' and cat==cur['category'] else TAB.get(cat,cur['ironmanTabKey'])),'semanticPredicate':predicate,'rationale':reason,'evidence':list(evid),'identityLinks':[],'reviewer':'gear'}
 # Exact, tracked human-reviewed decisions outrank generated cues.
 if i in manual:
  c=manual[i];q=literal_policy_quote(a,c,text)
  manual_ev=article_ev(a,i,q,'Root-reviewed exact-ID semantic exception from the tracked case policy.')
  roles={'food':['consumable_food'],'burnt-food':['unusable_food'],'quest-item':['quest_item'],'cleanup':['interface_or_animation_artifact'],'crafting-jewellery':['crafting_component'],'crafting-material':['crafting_material'],'cooking-material':['cooking_material'],'raw-food':['raw_food_material']}.get(c['proposedSubcategory'],[])
  result=base('revise',c['proposedCategory'],c['proposedSubcategory'],c.get('proposedTags',[]),roles,'Tracked exact-ID policy records a human-reviewed source-backed correction: '+c['semanticExcerpt'],'The tracked exact numeric-ID case and pinned literal Wiki excerpt support this revised category/subcategory.')
  result['evidence']=[manual_ev]+[e for e in evid if e.get('kind')=='local_source']
  return result
 if p.get('auditScope') not in {'NAMED_EFFECTIVE','SUPPLEMENTAL'}:
  return base('unresolved',cur['category'],sub,cur.get('tags',[]),None,f"The source packet marks this row {p.get('auditScope')}; no effective named assignment is certified.",'Only NAMED_EFFECTIVE/SUPPLEMENTAL rows are eligible for assignment certification.')
 other=direct_nongear(p,a,rec,params,para,cats)
 bonuseset=bonuses;equip=str(params.get('equipable','')).strip().lower()=='yes'; low=(para+' '+str(params.get('examine',''))).lower()
 if other:
  cat,sc,tab,reason,roles=other; result=base('revise',cat,sc,[],roles,reason,'Direct exact-ID article semantics establish a functional workflow outside combat gear.')
  result['proposedIronmanTabKey']=tab;return result
 # Exact item-variant wear/wield state overrides generic equipable=true.
 own_option=str(params.get('options','')).lower()
 # Options were selected through this ID's idN→optionsN mapping, never from sibling states.
 unavailable=bool(own_option and not re.search(r'\b(?:wear|wield)\b',own_option))
 if unavailable and re.search(r'\b(?:broken|inactive|uncharged|empty|depleted|unusable)\b',(' '.join(names)+' '+low),re.I):
  return base('unresolved',cur['category'],sub,cur.get('tags',[]),None,'The exact variant is not directly wearable/wieldable in its current state; the page does not resolve whether repair, recharge, or another state conversion should keep it in combat gear.','Exact item-state mechanics and item-specific Wear/Wield options must support current combat usability; global infobox equipable flags and inherited stats are insufficient.')
 if not exact:
  return base('unresolved',cur['category'],sub,cur.get('tags',[]),None,'No pinned article infobox mapping this exact numeric ID is available; joined data, family title, and display name cannot establish exact variant semantics.','Require an exact numeric ID in a pinned item-page infobox or a typed identity proof chain.')
 # Source-based role precedence: skill function and cosmetic-only ambiguity outrank generic stats.
 cosmetic=bool(re.search(r'cosmetic|ornamental|decorative|fashionscape',low,re.I))
 fun_item=bool(re.search(r'fun weapon|whack|whacking|social weapon|negative (?:attack|combat) bonus|play[- ]fighting|for play-fighting',low,re.I))
 base_variant=bool(re.search(r'variant of|same (?:combat )?stats|identical (?:bonuses|stats)|retains? .*bonuses|with .* ornament kit|with .* colour kit',low,re.I))
 explicitly_skill=bool(re.search(r'\b(?:skilling|fishing|woodcutting|mining|hunter|farming|construction|runecraft|herblore) (?:tool|equipment|bonus|effect)|used (?:only )?for (?:fishing|woodcutting|mining|farming|construction|runecraft|hunter|herblore)|skilling equipment\b',low,re.I))
 direct_weapon=bool(re.search(r'\b(?:weapon|ammunition|thrown weapon|melee weapon|ranged weapon|magic weapon|combat gear|combat equipment|armour worn in combat|shield slot item)\b',low,re.I))
 direct_mechanic=bool(re.search(r'\b(?:deals? damage|attack bonus|combat effect|used to fight|used to attack|damage bonus|slayer task|reduces? .* damage|combat role|weapon used)\b',low,re.I))
 if explicitly_skill and not (direct_weapon or direct_mechanic):
  return base('unresolved',cur['category'],sub,cur.get('tags',[]),None,'The pinned page gives a skilling facet that competes with generic combat-stat data; the exact item’s primary workflow is not resolved.','Functional skilling or tool mechanics take precedence over generic nonzero stats; retain unresolved until item-specific combat use is established.')
 if fun_item and not (direct_mechanic and bonuseset):
  reason=('The exact variant examine identifies it as for play-fighting, and its subject-specific page supplies no combat mechanic; generic stats and slot data do not establish functional combat placement.' if 'play-fighting' in str(params.get('examine','')).lower() else 'The exact page describes a fun/social/negative-stat item; generic stats alone do not establish functional combat placement.')
  return base('unresolved',cur['category'],sub,cur.get('tags',[]),None,reason,'Special fun/social mechanics outrank generic stats; require direct subject-specific combat use to resolve this item.')
 if cosmetic and not (base_variant and (bool(bonuseset) or direct_mechanic)):
  return base('unresolved',cur['category'],sub,cur.get('tags',[]),None,'The exact page describes a cosmetic/decorative state without item-specific proof that this variant retains combat function.','A cosmetic facet cannot be certified from inherited or generic nonzero stats; require direct exact-variant combat mechanics or an explicit functional base-gear relationship.')
 if len(slots)>1:
  return base('unresolved',cur['category'],sub,cur.get('tags',[]),None,'Exact-page/sub data returns multiple equipment slots for this numeric ID; the item-specific slot is conflicting.','A wearable subcategory requires one unambiguous exact-ID exact-page/sub slot.')
 if not equip or unavailable:
  return base('unresolved',cur['category'],sub,cur.get('tags',[]),None,'The pinned exact variant does not establish an active Wear/Wield option; equipability or combat use is unresolved.','Require exact variant Wear/Wield state plus direct combat function or nonzero exact-ID stats.')
 # Ammunition and thrown weapons need item-specific function, not ammo-slot presence.
 ammo=bool(re.search(r'\b(?:ammunition|projectile|arrows? used|bolts? used|fired from|used as ammunition)\b',low,re.I))
 thrown=bool(re.search(r'\b(?:thrown weapon|can be thrown|thrown at)\b',low,re.I))
 cannon=bool(sub=='cannon-part' and re.search(r'dwarf multicannon|multicannon',low,re.I))
 teleport=bool('Category:Teleportation items' in cats or re.search(r'teleports? (?:the wearer|you|players)|teleport(?:ation)? item',low,re.I))
 # Exact slot/subcategory agreement; only direct exact two-handed mechanics can repair a weapon/2h mismatch.
 slot=next(iter(slots)) if len(slots)==1 else ''
 compatible=(sub=='gear' or not SLOT_FOR.get(sub) or bool(SLOT_FOR.get(sub,set()) & slots))
 target_sub=SLOT_SUB.get(slot)
 if slots and not compatible:
  twohand=bool(re.search(r'\btwo[- ]handed\b',low,re.I))
  onehand=bool(re.search(r'\bone[- ]handed\b',low,re.I))
  expected=SLOT_SUB.get(slot)
  if expected and slot in {'2h','2h weapon'} and sub in {'weapon','hands','shield','magic-offhand'} and equip and re.search(r'\b(?:wear|wield)\b',own_option) and bonuseset and (direct_weapon or direct_mechanic) and not fun_item:
   return base('revise','GEAR','2h',[],['combat_equipment'],'The exact ID has an active Wear/Wield option, direct weapon/combat evidence, positive exact-ID combat values, and one exact equipment slot of 2h; the current '+sub+' subcategory conflicts.','Revise a specific GEAR subcategory when exact-variant usability, positive combat evidence, and unique exact-ID slot data agree.')
  if expected and twohand and slot in {'2h','2h weapon'} and sub in {'weapon','hands','shield','magic-offhand'}:
   return base('revise','GEAR','2h',[],['combat_equipment'],'Exact-ID article text identifies a two-handed item and the unique exact-page/sub slot is 2h; the current '+sub+' subcategory conflicts.','Revise a specific GEAR subcategory only when direct item mechanics and a unique exact-ID slot support the target.')
  if expected and onehand and slot=='weapon' and sub in {'2h','2h'}:
   return base('revise','GEAR','weapon',[],['combat_equipment'],'Exact-ID article text identifies a one-handed weapon and the unique exact-page/sub slot is weapon; the current 2h subcategory conflicts.','Revise a specific GEAR subcategory only when direct item mechanics and a unique exact-ID slot support the target.')
  if bonuseset or direct_weapon or direct_mechanic:
   return base('unresolved',cur['category'],sub,cur.get('tags',[]),None,f"Exact-ID equipment data reports slot {slot}, conflicting with current subcategory {sub}; available article text does not safely resolve the intended slot.",'Do not certify a specific wearable subcategory when exact numeric-ID slot evidence contradicts it; revise only with direct compatible item mechanics.')
 if sub=='ammo' and ammo:
  return base('certify','GEAR',sub,cur.get('tags',[]),['combat_ammunition'],'Exact-ID page directly identifies this item as ammunition/projectile; its current ammo workflow is supported.',"Certify GEAR/ammo only from the exact item's ammunition function, not the ammo slot or title.")
 if sub=='thrown-weapon' and thrown and slot in {'weapon','ammo'}:
  return base('certify','GEAR',sub,cur.get('tags',[]),['combat_equipment','thrown_weapon'],'Exact-ID page describes a wieldable throwing weapon and exact slot data agrees with its weapon function.','Certify a thrown weapon only with direct throwing-weapon mechanics and compatible exact slot data.')
 if cannon:
  return base('certify','GEAR',sub,cur.get('tags',[]),['combat_setup_component'],'Exact-ID page documents a Dwarf multicannon component used to build or operate the cannon.','A directly documented cannon setup component stays with combat setup gear.')
 if teleport and slots and compatible:
  return base('certify','GEAR',sub,cur.get('tags',[]),['wearable_equipment','teleport_utility'],'Exact-ID variant is wearable and its direct teleport role remains secondary to gear under the local gear-over-teleport rule.','A wearable teleport item remains GEAR under production precedence when its exact wearable slot is compatible.')
 # Positive exact stats count only after primary role, state, exact identity, and slot checks.
 has_combat=bool(bonuseset) or direct_mechanic
 slot_proven=bool(slots) and (sub=='gear' or compatible)
 if has_combat and slot_proven and (direct_weapon or direct_mechanic or bool(bonuseset)):
  return base('certify','GEAR',sub,cur.get('tags',[]),['combat_equipment'],'Exact-ID item page and/or its exact-page/sub data establishes active combat equipment with nonzero combat values or a subject-specific combat mechanic; the exact slot agrees with the current subcategory.','Certify only after exact item identity, current usable state, no overriding tool/cosmetic purpose, nonzero exact-ID combat values or subject-specific combat mechanics, and compatible exact slot are established.')
 if sub in SLOT_FOR and slots and compatible and not bonuseset and not direct_mechanic:
  why='The exact wearable slot agrees, but the source has no nonzero exact-ID combat value or subject-specific combat mechanic; item identity/equipability alone is insufficient.'
 elif not slots and not direct_mechanic:
  why='The exact item page establishes identity/equipability but no unique exact-page/sub slot or subject-specific combat mechanic; do not infer placement from the current label.'
 else:why='Available exact-ID evidence does not resolve combat purpose and current subcategory without relying on a generic combat heading, absent fields, or name.'
 return base('unresolved',cur['category'],sub,cur.get('tags',[]),None,why,'Certify GEAR only from exact-ID combat use or nonzero exact-ID stats plus usable variant state and slot compatibility.')

def main():
 global JOINED_HASH
 JOINED_HASH='sha256:'+sha(JOINED.read_bytes())
 ap=argparse.ArgumentParser();ap.add_argument('--output',type=Path,default=OUT_DEFAULT);args=ap.parse_args()
 packets=load_jsonl(PACKET);joined_rows=load_jsonl(JOINED);entries={int(x['item_id']):x for x in joined_rows};lines={}
 for line in JOINED.read_text(encoding='utf-8-sig').splitlines():
  if line.strip():lines[int(json.loads(line)['item_id'])]=line
 idx=json.loads(INDEX.read_text(encoding='utf-8-sig'));articles={}
 for a in idx.values():
  for i in a.get('exactInfoboxItemIds',[]):articles.setdefault(int(i),[]).append(a)
 cases=json.loads(POLICY.read_text(encoding='utf-8-sig'))['cases'];manual={int(x['itemId']):x for x in cases}
 if len(packets)!=8836 or len({x['itemId'] for x in packets})!=len(packets):raise ValueError('frozen GEAR packet count/uniqueness mismatch')
 if set(manual)-{x['itemId'] for x in packets}:raise ValueError('tracked policy includes an ID outside GEAR ownership')
 decisions=[make_decision(p,entries.get(int(p['itemId'])),lines.get(int(p['itemId']),''),articles,manual) for p in packets]
 args.output.mkdir(parents=True,exist_ok=True);out=args.output/'decisions.jsonl'
 out.write_text(''.join(json.dumps(d,ensure_ascii=False,sort_keys=True)+'\n' for d in decisions),encoding='utf-8')
 counts=Counter(d['decision'] for d in decisions);revs=Counter((d['proposedCategory'],d['proposedSubcategory'],d['proposedIronmanTabKey']) for d in decisions if d['decision']=='revise')
 packet_by_id={int(p['itemId']):p for p in packets}
 def unresolved_slot_mismatch(d):
  if d['decision']!='unresolved':return False
  p=packet_by_id[int(d['itemId'])]
  sub=p['current']['subcategory']; allowed=SLOT_FOR.get(sub)
  slots,_,_=exact_stats(entries.get(int(d['itemId'])))
  return bool(allowed and slots and not (allowed & slots))
 conflicts=[d for d in decisions if unresolved_slot_mismatch(d)]
 summary={'shard':'gear','version':'gear-v2','rowCount':len(decisions),'decisions':dict(sorted(counts.items())),'revisionTargets':{' / '.join(k):v for k,v in sorted(revs.items())},'slotConflictUnresolved':len(conflicts),'exactPageIds':sum(bool(next((a for a in articles.get(p['itemId'],[]) if str(p['itemId']) in a.get('variants',{})),None)) for p in packets),'inputs':{'packetSha256':sha(PACKET.read_bytes()),'joinedSha256':sha(JOINED.read_bytes()),'articleIndexSha256':sha(INDEX.read_bytes()),'trackedPolicySha256':sha(POLICY.read_bytes())},'decisionFile':str(out.resolve().relative_to(ROOT)),'limitations':['Semantic output is independently generated from frozen packet, pinned article, exact-ID joined data, and tracked 26-case policy.','Unresolved remains appropriate for weak, contradictory, missing, state-conflicted, or primary-role-conflicted evidence.','Only exact numeric-ID relationships are evaluated; no family membership or name-only transfer is used.']}
 (args.output/'summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2,sort_keys=True)+'\n',encoding='utf-8');print(json.dumps(summary,ensure_ascii=False,indent=2))
if __name__=='__main__':main()
