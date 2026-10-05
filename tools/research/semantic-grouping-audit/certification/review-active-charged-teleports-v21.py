import json,pathlib,hashlib,re,csv
ROOT=pathlib.Path.cwd()
base_path=ROOT/'tmp/category-certification/reviews/transport-v20/full-shard-review-v1.json'
OUT=ROOT/'tmp/category-certification/reviews/transport-v21'
OUT.mkdir(parents=True,exist_ok=True)
report=json.loads(base_path.read_text(encoding='utf-8'))
index=json.loads((ROOT/'tmp/category-certification/wiki-articles/article-index.json').read_text(encoding='utf-8'))
packets={int(json.loads(x)['itemId']):json.loads(x) for x in (ROOT/'tmp/category-certification/reviewer-packets/currency-runes-teleport.jsonl').read_text(encoding='utf-8').splitlines() if x.strip()}
ledger={int(json.loads(x)['itemId']):json.loads(x) for x in (ROOT/'tmp/category-certification/root-approved-decisions-with-clue-scrolls.jsonl').read_text(encoding='utf-8').splitlines() if x.strip()}

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def getfacts(v):
 p=v['params'];s=v.get('suffix','')
 def g(k):return p.get(k+s,p.get(k)) if s else p.get(k)
 return {'variant':v.get('variant'),'suffix':s,**{k:g(k) for k in ['id','name','options','wornoptions','equipable','stackable','tradeable','quest','noteable','bankable','examine'] if g(k) is not None}}
def lead_from(raw,anchor):
 start=raw.find(anchor)
 if start<0:raise ValueError('lead anchor missing '+anchor)
 end=raw.find('\n==',start)
 if end<0:end=len(raw)
 q=raw[start:end].strip()
 if anchor not in q:raise AssertionError(anchor)
 return q
def paragraph(raw,anchor):
 ix=raw.find(anchor)
 if ix<0:raise ValueError('context anchor missing '+anchor)
 lo=raw.rfind('\n\n',0,ix)+2;hi=raw.find('\n\n',ix)
 if hi<0:hi=len(raw)
 q=raw[lo:hi].strip()
 if anchor not in q:raise AssertionError(anchor)
 return q

families=[
 {'title':'Ring of dueling','ids':[2552,2554,2556,2558,2560,2562,2564,2566],'lead':"'''ring of dueling''' is a teleportation ring",'function':"'''ring of dueling''' is a teleportation ring",'context':['When teleporting using the ring, the message {{Mes|You rub the ring...}} will be displayed, followed by a message with the number of charges remaining'],'acquisition':[],'competing':['Due to the low cost of the ring, many players use it to bank quickly at the [[Castle Wars]] chest.'],'rationale':'The exact infobox variant is a positive-charge Ring of dueling and exposes Wear/Rub plus destinations. Its own definition calls it a teleportation ring and records the finite uses; fast banking is a destination benefit, not another item role.'},
 {'title':'Games necklace','ids':[3853,3855,3857,3859,3861,3863,3865,3867],'lead':"'''games necklace''' is a [[sapphire necklace]]",'function':"It has 8 charges which can teleport the player to [[Burthorpe]]",'context':['When teleporting using the necklace, the message {{Mes|You rub the necklace...}} will be displayed, followed by a message with the number of charges remaining'],'acquisition':[],'competing':[],'rationale':'The exact charged variant exposes Wear/Rub and named destination options; its own definition states player teleport and finite uses. Activity destinations do not imply activity-only use.'},
 {'title':'Skills necklace','ids':[11105,11107,11109,11111],'lead':"'''skills necklace''' is a [[dragon necklace]]",'function':"Like other dragonstone jewellery, it is one the [[Wilderness#Member_teleportation_up_to_level_30_Wilderness|few items]] whose teleports will work up to level 30 Wilderness",'context':['A skills necklace can be recharged at the [[Totem Pole','Wearing a skills necklace with at least one charge while [[Big fishing net|big net]] fishing will slightly increase the chance of finding a [[casket]].'],'acquisition':[],'competing':['Wearing a skills necklace with at least one charge while [[Big fishing net|big net]] fishing will slightly increase the chance of finding a [[casket]].'],'rationale':'Exact positive-charge variant has Wear/Rub and own named destination options. Teleport network is direct; fishing bonus is recorded as a secondary use and no role/tag is asserted.'},
 {'title':'Digsite pendant','ids':[11190,11191,11192,11193,11194],'lead':"'''digsite pendant''' is a [[ruby necklace]]",'function':"When enchanted, the pendant can be used to [[Teleportation|teleport]] to the north of the [[Digsite]]",'context':['It requires completion of [[The Dig Site]] quest and the spell learnt from one of the archaeologists in [[Varrock Museum]] to make or use.','The number of charges on an individual pendant is suffixed to the item\'s name. For example, an unused pendant is named "Digsite pendant (5)".'],'acquisition':[],'competing':[],'rationale':'The exact suffix identifies a positive remaining charge count and Wear/Rub destination options. Quest/spell requirements are preserved as access conditions; the item is usable transport after those conditions are met.'},
 {'title':'Slayer ring','ids':[11866,11867,11868,11869,11870,11871,11872,11873],'lead':"'''Slayer ring''' (or '''Ring of slaying''') can be used to teleport players",'function':"'''Slayer ring''' (or '''Ring of slaying''') can be used to teleport players to various locations related to [[Slayer]].",'context':['Each ring has 8 charges when crafted for teleportation. When they are all depleted, the ring crumbles'],'acquisition':['Players can purchase Slayer rings from Slayer masters for 75 [[Slayer reward point]]s each.'],'competing':['The slayer ring also allows players to contact the most advanced [[Slayer Master|Slayer master]] they are eligible to receive tasks from, consuming no charges.'],'rationale':'Exact charged states expose Rub/Teleport and destination options. Own lead states the movement function. Slayer-master contact is a separate documented use, but does not displace the direct travel role.'},
 {'title':'Ring of returning','ids':[21129,21132,21134,21136,21138],'lead':"'''ring of returning''' is a [[jade ring]]",'function':"When rubbed, the player will be teleported to their current [[respawn point]].",'context':['The ring will provide five charges before degrading to dust.'],'acquisition':[],'competing':['The ring of returning is one of the few pieces of teleportation jewellery excluded from [[jewellery box]]es, so players must retain a ring if they wish to utilise its features.'],'rationale':'The exact suffix is a positive charge count and own lead directly identifies player teleport to current respawn. Its exclusion from a jewellery box is a retention/access consideration.'},
 {'title':'Necklace of passage','ids':[21146,21149,21151,21153,21155],'lead':"'''necklace of passage''' is a [[jade necklace]]",'function':"Right-clicking the necklace in your inventory and selecting \"rub\", or right-clicking it while equipped will allow the player to teleport to one of four possible locations.",'context':['Using the necklace to teleport will consume a charge. After all five charges are used, the necklace will disintegrate into dust.'],'acquisition':[],'competing':['Equipping the necklace yields no [[Equipment Stats|stat bonuses]] so wearing it is purely cosmetic or to conserve inventory space.'],'rationale':'Each exact suffix is a positive remaining-charge variant. The own page describes player teleport and charge consumption; no combat-stat primary conflict is present.'},
 {'title':'Burning amulet','ids':[21166,21169,21171,21173,21175],'lead':"'''burning amulet''' is a [[topaz amulet]]",'function':"When rubbed, the amulet can teleport the player to various locations in the [[Wilderness]]",'context':['After all five charges are used, the amulet will disintegrate.'],'acquisition':[],'competing':['players will be given a warning before teleporting.'],'rationale':'The exact charge suffix and Wear/Rub/destination fields establish a usable current variant. Own source says it teleports the player; the Wilderness warning is retained as a use condition.'},
]

existing_proposals={x['itemId'] for x in report['newSourceBackedProposals']}
new_cases=[]
for family in families:
 title=family['title'];
 if title not in index:raise ValueError(f'missing exact source page {title}')
 entry=index[title];raw=(ROOT/entry['path']).read_text(encoding='utf-8')
 if sha(ROOT/entry['path'])!=entry['sha256']:raise ValueError(f'{title}: source hash mismatch')
 for iid in family['ids']:
  if iid in existing_proposals:continue
  if iid not in ledger or iid not in packets:raise ValueError(f'{iid}: outside authoritative ledger/shard')
  if iid in {8014,8015,8016,8017,8018,8019,8020,8021,8022}:raise ValueError(f'{iid}: user-policy hold')
  if str(iid) not in entry.get('variants',{}):raise ValueError(f'{iid}: missing exact page variant')
  v=entry['variants'][str(iid)];facts=getfacts(v)
  if str(iid) not in str(facts.get('id')):raise ValueError(f'{iid}: selected exact variant does not name id')
  try:charges=int(re.search(r'\d+',str(v.get('variant',''))).group(0))
  except Exception:raise ValueError(f'{iid}: no positive charge count in variant label {v.get("variant")}')
  if charges<1:raise ValueError(f'{iid}: inactive/empty charge state')
  if not re.search(r'\b(Rub|Teleport)\b',str(facts.get('options',''))+' '+str(facts.get('wornoptions','')),re.I):raise ValueError(f'{iid}: no own active travel action')
  qlead=lead_from(raw,family['lead'])
  qfunc=paragraph(raw,family['function'])
  qctx=[paragraph(raw,a) for a in family.get('context',[])]
  qacq=[paragraph(raw,a) for a in family.get('acquisition',[])]
  qcomp=[paragraph(raw,a) for a in family.get('competing',[])]
  cur=packets[iid]['current'];c=coverage=None
  full=ledger[iid]
  if (full['proposedCategory'],full['proposedSubcategory'],full['proposedIronmanTabKey'])!=(cur['category'],cur['subcategory'],cur['ironmanTabKey']):raise ValueError(f'{iid}: candidate packet/full-ledger route mismatch')
  if cur['category']!='TELEPORT':raise ValueError(f'{iid}: not current TELEPORT route')
  new_cases.append({'itemId':iid,'title':title,'status':'PROPOSED_UNCHANGED_ACTIVE_CHARGED_TELEPORT','kind':'wearable_charged_player_teleport','currentRoute':{'category':cur['category'],'subcategory':cur['subcategory'],'ironmanTabKey':cur['ironmanTabKey']},'proposedRoute':{'category':cur['category'],'subcategory':cur['subcategory'],'ironmanTabKey':cur['ironmanTabKey']},'currentTags':cur.get('tags',[]),'tagsClaimed':False,'rolesClaimed':None,'exactVariantStateFacts':facts,'ownSubjectLeadLiteral':qlead,'positiveMechanicLiterals':[qfunc]+qctx,'accessAndAcquisitionLiterals':qacq,'competingContextLiterals':qcomp,'source':{'sourceTitle':title,'sourceRevision':entry['revid'],'sourceUrl':entry['sourceUrl'],'sourceSha256':entry['sha256'],'rawPath':entry['path'],'exactItemId':iid},'rationale':family['rationale'],'priorDecision':{'decision':ledger[iid]['decision'],'rationale':ledger[iid]['rationale']}})

# Merge this candidate-only cohort onto the immutable v20 base in a distinct output.
report['newSourceBackedProposals']=report['newSourceBackedProposals']+new_cases
report['activeChargedWearableTeleportCohort']={'status':'candidate only; all exact active state/source predicates replayed; no root approval','familyCounts':{f['title']:len(f['ids']) for f in families},'caseCount':len(new_cases),'ids':[x['itemId'] for x in new_cases],'exclusions':'Uncharged/inert states, ring of wealth and amulet-of-glory multi-role stats cases, activity-only items, non-player transport, and any family lacking exact numeric item-ID state evidence were excluded.'}
by={x['itemId']:x for x in report['newSourceBackedProposals']}
for row in report['fullPartition']:
 if row['itemId'] in by:row['disposition']='NEW_SOURCE_BACKED_PROPOSAL'
from collections import Counter
report['partitionCounts']=dict(Counter(x['disposition'] for x in report['fullPartition']))
report['scope']['newProposedCases']=len(report['newSourceBackedProposals'])
report['scope']['activeChargedWearableTeleportCases']=len(new_cases)
out=OUT/'full-shard-review-v1.json'
out.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps({'output':str(out),'sha256':sha(out),'activeChargedCount':len(new_cases),'activeIds':[x['itemId'] for x in new_cases],'newProposalCount':len(report['newSourceBackedProposals']),'partitionCounts':report['partitionCounts']},ensure_ascii=False,indent=2))
