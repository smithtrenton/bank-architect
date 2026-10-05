import json, pathlib, hashlib, re, csv
ROOT = pathlib.Path.cwd()
BASE = ROOT / 'tmp/category-certification/reviews/transport-v21/full-shard-review-v1.json'
OUT = ROOT / 'tmp/category-certification/reviews/transport-v22'
OUT.mkdir(parents=True, exist_ok=True)
report = json.loads(BASE.read_text(encoding='utf-8'))
idx = json.loads((ROOT/'tmp/category-certification/wiki-articles/article-index.json').read_text(encoding='utf-8'))
packets = {int(o['itemId']):o for o in map(json.loads,(ROOT/'tmp/category-certification/reviewer-packets/currency-runes-teleport.jsonl').read_text(encoding='utf-8').splitlines()) if o}
ledger = {int(o['itemId']):o for o in map(json.loads,(ROOT/'tmp/category-certification/root-approved-decisions-with-clue-scrolls.jsonl').read_text(encoding='utf-8').splitlines()) if o}
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def facts(v):
 p=v['params']; s=v.get('suffix','')
 def get(k): return p.get(k+s,p.get(k)) if s else p.get(k)
 return {'variant':v.get('variant'),'suffix':s,**{k:get(k) for k in ['id','name','options','wornoptions','equipable','stackable','tradeable','quest','noteable','examine'] if get(k) is not None}}
def route(i):
 c=packets[i]['current']; l=ledger[i]
 if (l['proposedCategory'],l['proposedSubcategory'],l['proposedIronmanTabKey']) != (c['category'],c['subcategory'],c['ironmanTabKey']): raise ValueError(f'{i}: packet/full ledger route mismatch')
 return {'category':c['category'],'subcategory':c['subcategory'],'ironmanTabKey':c['ironmanTabKey']}
def intro(raw,title):
 m=re.search(r"'''"+re.escape(title)+r"s?'''",raw,re.I)
 if not m: raise ValueError('bold subject absent: '+title)
 at=m.start()
 start=raw.rfind('\n',0,at)+1
 # Retain the complete first-section subject/use text, including exact markup.
 end=raw.find('\n==',at)
 if end<0: end=len(raw)
 q=raw[start:end].strip()
 if m.group(0).lower() not in q.lower(): raise AssertionError(title)
 return q
def add_case(i,title,kind,why,expected):
 if i in {x['itemId'] for x in report['newSourceBackedProposals']}: raise ValueError(f'duplicate proposal {i}')
 if i not in packets or i not in ledger: raise ValueError(f'{i}: missing packet/ledger')
 if i in range(8014,8023): raise ValueError('user-policy hold')
 ent=idx.get(title)
 if not ent: raise ValueError(f'{i}: no exact source page {title}')
 sp=ROOT/ent['path']
 if sha(sp)!=ent['sha256']: raise ValueError(f'{title}: body hash mismatch')
 v=ent.get('variants',{}).get(str(i))
 if not v: raise ValueError(f'{i}: exact variant missing on {title}')
 f=facts(v)
 if str(i) != str(f.get('id')): raise ValueError(f'{i}: exact variant id mismatch {f}')
 lead=intro(sp.read_text(encoding='utf-8'),title)
 cur=route(i)
 if cur != expected: raise ValueError(f'{i}: expected current route {expected}, found {cur}')
 row=packets[i]['current']
 report['newSourceBackedProposals'].append({'itemId':i,'title':title,'status':'PROPOSED_UNCHANGED_SOURCE_BACKED_PRIMARY','kind':kind,'currentRoute':cur,'proposedRoute':cur,'currentTags':row.get('tags',[]),'tagsClaimed':False,'rolesClaimed':None,'rationale':why,'source':{'sourceTitle':title,'sourceRevision':ent['revid'],'sourceUrl':ent['sourceUrl'],'sourceSha256':ent['sha256'],'rawPath':ent['path'],'exactItemId':i},'exactVariantStateFacts':f,'ownSubjectLeadAndMechanicsLiteral':lead,'priorDecision':{'decision':ledger[i]['decision'],'rationale':ledger[i]['rationale']}})

# The exact amulet/medallion variants are added individually only when their active state is explicit.
# Drakan's medallion and charged Giantsoul have direct transport functions and zero combat-stat role;
# the two neckwear with positive magic/prayer bonuses are recorded below as competing cases instead.
tele_expected={'category':'TELEPORT','subcategory':'teleport','ironmanTabKey':'currency-utilities'}
add_case(22400,"Drakan's medallion",'unlimited_player_teleport_gear','Own exact Wear/Teleport variant provides unlimited player teleport to named destinations; article records quest and destination unlock requirements. Its combat-stat table is all zero, so the direct transport function is not competing with an equipment-stat purpose.',tele_expected)
add_case(30638,'Giantsoul amulet','active_charged_player_teleport','Exact Charged variant exposes Rub with three named destinations. Its own lead says the charged amulet teleports players to lair entrances; full lead also records untradeable boss-loot acquisition. The charged state and direct movement function support the unchanged teleport route.',tele_expected)
for _iid in (22400,30638):
 _case=report['newSourceBackedProposals'][-1] if _iid==30638 else next(x for x in report['newSourceBackedProposals'] if x['itemId']==_iid)
 _ent=idx[_case['title']];_raw=(ROOT/_ent['path']).read_text(encoding='utf-8')
 _st=_raw.find('==Combat stats==');_en=_raw.find('\n==',_st+1)
 if _st<0 or _en<0:raise ValueError(f'{_iid}: expected combat-stat context missing')
 _case['competingContextLiterals']=[_raw[_st:_en].strip()]

# Ordinary talismans: exact own pages identify each item's altar-entry function, and distinguish
# consumption as a crafting ingredient from the retained talisman access function.
talisman_cases=[
(1438,'Air talisman'),(1440,'Earth talisman'),(1442,'Fire talisman'),(1444,'Water talisman'),(1446,'Body talisman'),(1448,'Mind talisman'),(1450,'Blood talisman'),(1452,'Chaos talisman'),(1454,'Cosmic talisman'),(1456,'Death talisman'),(1458,'Law talisman'),(1460,'Soul talisman'),(1462,'Nature talisman'),(5516,'Elemental talisman'),(26798,'Catalytic talisman')]
rune_focus={'category':'RUNE','subcategory':'runecrafting-focus','ironmanTabKey':'skilling-tools'}
for i,title in talisman_cases:
 add_case(i,title,'rune_altar_access_talisman','The exact item page defines the talisman as allowing access to its named runic altar(s), and its lead describes using altar access for Runecraft. Any tiara or combination-rune consumption is also retained in the cited own lead as a separate crafting use.',rune_focus)

# Imbued tiaras: exact own pages say they are worn to enter an identified altar and free an
# inventory slot; this is a concrete Runecraft tool function, not an inference from the name.
tiara_cases=[(5527,'Air tiara'),(5529,'Mind tiara'),(5531,'Water tiara'),(5533,'Body tiara'),(5535,'Earth tiara'),(5537,'Fire tiara'),(5539,'Cosmic tiara'),(5541,'Nature tiara'),(5543,'Chaos tiara'),(5545,'Law tiara'),(5547,'Death tiara'),(5549,'Blood tiara'),(26801,'Catalytic tiara'),(26804,'Elemental tiara')]
for i,title in tiara_cases:
 add_case(i,title,'imbued_rune_altar_access_tiara','The exact own article states that this wearable tiara gives entry to its named altar while worn, preserving an inventory slot for essence. It therefore has an explicit Runecraft access/tool function. Its creation from a base tiara is recorded as a secondary manufacturing relation, not treated as its use.',rune_focus)

# Four exact currency articles have direct recurring exchange/spend evidence; quote their own use clauses.
currency_route={'category':'CURRENCY','subcategory':'currency','ironmanTabKey':'currency-utilities'}
def add_currency(i,title,why,anchors=()):
 add_case(i,title,'recurring_currency_exchange_entitlement',why,currency_route)
 obj=report['newSourceBackedProposals'][-1]
 ent=idx[title];raw=(ROOT/ent['path']).read_text(encoding='utf-8')
 lits=[]
 for a in anchors:
  at=raw.find(a)
  if at<0: raise ValueError(f'{i} currency quote anchor absent: {a}')
  lo=raw.rfind('\n\n',0,at)+2;hi=raw.find('\n\n',at)
  if hi<0:hi=len(raw)
  q=raw[lo:hi].strip()
  if a not in q:raise AssertionError((i,a))
  lits.append(q)
 obj['mechanicLiterals']=lits
add_currency(6529,'Tokkul','Its own page calls TokKul the currency of Mor Ul Rek and directly lists stores where it is spent; exchange use supports the unchanged currency placement.',('TokKul can be spent in the following shops:',))
add_currency(6306,'Trading sticks','Its own page calls trading sticks the main currency of Tai Bwo Wannai and documents recurring shop trades, access fees, and parcel-service payments.',('Players can pay 100 trading sticks to access the [[Hardwood Grove]]','5000 trading sticks can be used as a one-time payment'))
add_currency(26792,'Abyssal pearls','The exact page defines pearls as Rewards Guardian drops used to purchase items at Temple Supplies and explicitly documents repeat spending for repair service and loot rolls.',('They are used to purchase items from [[Temple Supplies]]', 'Lastly, players can use 25 pearls on the Rewards Guardian for an additional loot roll.'))
add_currency(24711,'Hallowed mark','The exact stack is explicitly described as reward currency, and its own article lists repeated purchases in the Hallowed shop, including teleport access and supplies.',('These can be used at the [[Mysterious Hallowed Goods]] shop.', 'Used to teleport to the Hallowed Sepulchre lobby. They can be purchased from the [[Mysterious Hallowed Goods]] shop.'))

# Exact sourced exceptions/holds. These preserve the mechanics that prevent a naïve name/action rule.
holds=[]
for i,title,reason,anchors in [
 (13393,"Xeric's talisman",'Direct teleport function is explicit, but the same exact charged amulet has positive magic attack and magic defence bonuses; competing equipment function requires a human primary-route decision under the local gear/teleport precedence policy.',["'''Xeric's talisman''' is an amulet that allows players to teleport to locations around [[Great Kourend]].",'==Combat stats==']),
 (9106,'Astral tiara','The exact page labels this an unobtainable item and says the Astral Altar never required a tiara; current exact-ID presence does not prove a usable item or Runecraft altar-access function.',["'''astral tiara''' is an [[unobtainable item]]",'As the [[Astral Altar]] did not require a talisman or tiara to enter, it was never made obtainable.']),
 (26788,'Gold tiara','The exact page says Gold tiaras are purely cosmetic head-slot items and only serve as ingredients in crafting attuned tiaras; they do not themselves grant altar access. Current RUNE/runecrafting-focus placement is unsupported; exact destination category needs taxonomy review.', ['They are a purely cosmetic head slot item']),
 (29893,'Pendant of Ates','Direct charged teleport function is explicit, but this exact worn charged amulet also grants +3 magic defence and +2 prayer; preserve as mixed transport/equipment pending primary precedence.', ['The Pendant of Ates has 6 teleport locations, each of which must be unlocked by activating the [[Statue_(Ates)|statue of ates]] at the location.','|dmagic2 = +3']),
 (6707,'Camulet','Article provides an active Rub/teleport function and charge-dependent destinations, but exact ID alone does not encode remaining charge; do not assert currently usable charge state.', ['The Camulet has four charges','Rub']),
 (13660,'Chronicle','Article provides a Teleport action but charges are separate inserted cards; the exact item ID does not establish an available card/charge count.', ["'''Chronicle''' is an equipable book",'In order to use the Chronicle, it must be charged']),
 (31441,'Summon boat (tablet)','Break relocates the player-owned boat to a docking point; it does not transport the player. The current TELEPORT/teleport-tablet route has no direct-player-movement support and needs local transport-component taxonomy review.', ['move their [[boat]] to the nearest [[docking point]]']),
 (23904,'Teleport crystal (The Gauntlet)','Exact use does teleport the player to the Gauntlet starting room, but it is activity-issued and activity-context limited; item persistence/bankability and whether it belongs in the normal bank blueprint are not established by the own lead.', ["'''Teleport crystal''' is a single-use item received when starting the [[Gauntlet]]"])]:
 ent=idx.get(title)
 if not ent: raise ValueError(f'missing hold source {title}')
 p=ROOT/ent['path']; raw=p.read_text(encoding='utf-8')
 if sha(p)!=ent['sha256']:raise ValueError('hash mismatch '+title)
 v=ent.get('variants',{}).get(str(i))
 if not v:raise ValueError(f'hold exact variant missing {i}')
 qs=[]
 for a in anchors:
  at=raw.find(a)
  if at<0: raise ValueError(f'{i} quote anchor absent: {a}')
  # Keep a source literal paragraph when the anchor is prose; for infobox anchors preserve full line.
  if a.startswith('|') or a.startswith('=='):
   q=a
  else:
   lo=raw.rfind('\n\n',0,at)+2; hi=raw.find('\n\n',at)
   if hi<0:hi=len(raw)
   q=raw[lo:hi].strip()
  if a not in q:raise AssertionError((i,a))
  qs.append(q)
 hold={'itemId':i,'sourceTitle':title,'disposition':'REVIEWED_HOLD_OR_CORRECTION_CANDIDATE','reason':reason,'source':{'sourceTitle':title,'sourceRevision':ent['revid'],'sourceUrl':ent['sourceUrl'],'sourceSha256':ent['sha256'],'rawPath':ent['path'],'exactItemId':i},'exactVariantStateFacts':facts(v),'literalEvidence':qs}
 if i in (13393,29893):
  st=raw.find('==Combat stats==')
  en=raw.find('\n==',st+1)
  if st<0 or en<0: raise ValueError(f'{i}: combat stats section missing')
  hold['competingCombatStatSectionLiteral']=raw[st:en].strip()
 holds.append(hold)

# Exact moving-boat subject text is kept separately because the literal first paragraph includes
# the tablet's own player action and identifies the moving object, preventing name-based teleport inference.
report['v22AdditionalReviewedCases']={'status':'candidate research; no root approval', 'newProposalIds':[x['itemId'] for x in report['newSourceBackedProposals'] if x.get('status')=='PROPOSED_UNCHANGED_SOURCE_BACKED_PRIMARY'], 'newProposalCount':sum(x.get('status')=='PROPOSED_UNCHANGED_SOURCE_BACKED_PRIMARY' for x in report['newSourceBackedProposals']), 'classes':{'active_direct_teleports':[22400,30638],'rune_access_talismans':[i for i,_ in talisman_cases],'rune_access_tiaras':[i for i,_ in tiara_cases]},'reviewedHolds':holds,'scopeNotes':'All 1,138 original shard IDs remain represented by fullPartition. Rows without exact-ID source or without semantically decisive own mechanics retain their earlier hold disposition. The nine non-teleport spell tablet IDs 8014–8022 remain user-policy holds. No roles or tags are asserted.'}
by={x['itemId']:x for x in report['newSourceBackedProposals']}
holdby={x['itemId']:x for x in holds}
for row in report['fullPartition']:
 if row['itemId'] in by: row['disposition']='NEW_SOURCE_BACKED_PROPOSAL'
 elif row['itemId'] in holdby:
  row['disposition']='SOURCE_BACKED_HOLD_OR_CORRECTION_REQUIRES_POLICY_REVIEW'
  row['v22ReviewedHold']={'sourceTitle':holdby[row['itemId']]['sourceTitle'],'reason':holdby[row['itemId']]['reason']}
from collections import Counter
report['partitionCounts']=dict(Counter(x['disposition'] for x in report['fullPartition']))
report['scope']['newProposedCases']=len(report['newSourceBackedProposals'])
report['scope']['v22NewProposals']=report['v22AdditionalReviewedCases']['newProposalCount']
report['inputs']['tmp\\category-certification\\reviews\\transport-v21\\full-shard-review-v1.json']=sha(BASE)
out=OUT/'full-shard-review-v1.json'
out.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps({'output':str(out),'sha256':sha(out),'v21sha':sha(BASE),'newProposals':report['v22AdditionalReviewedCases']['newProposalCount'],'ids':report['v22AdditionalReviewedCases']['newProposalIds'],'holds':len(holds),'partitionCounts':report['partitionCounts'],'ledgerRows':len(ledger),'ownedRows':len(packets)},ensure_ascii=False,indent=2))
