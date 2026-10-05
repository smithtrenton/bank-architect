import json, pathlib, hashlib
ROOT=pathlib.Path.cwd()
report_path=ROOT/'tmp/category-certification/reviews/transport-v20/full-shard-review-v1.json'
report=json.loads(report_path.read_text(encoding='utf-8'))
index=json.loads((ROOT/'tmp/category-certification/wiki-articles/article-index.json').read_text(encoding='utf-8'))
packets=[json.loads(x) for x in (ROOT/'tmp/category-certification/reviewer-packets/currency-runes-teleport.jsonl').read_text(encoding='utf-8').splitlines()]
prior={int(y['itemId']):y for y in (json.loads(x) for x in (ROOT/'tmp/category-certification/reviews/transport/decisions.jsonl').read_text(encoding='utf-8').splitlines() if x.strip())}
coverage={}
import csv
with (ROOT/'tmp/category-certification/current-coverage.tsv').open(encoding='utf-8-sig',newline='') as f:
 for x in csv.DictReader(f,delimiter='\t'): coverage[int(x['itemId'])]=x

def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def paragraph(text,anchor):
 ix=text.find(anchor)
 if ix<0: raise ValueError('anchor missing '+anchor)
 lo=text.rfind('\n\n',0,ix)+2; hi=text.find('\n\n',ix)
 if hi<0:hi=len(text)
 q=text[lo:hi].strip()
 if anchor not in q:raise ValueError('quote mismatch '+anchor)
 return q

def resolved_facts(var):
 params=var['params']; suffix=var.get('suffix','')
 def get(field):
  if suffix and field+suffix in params:return params[field+suffix]
  return params.get(field)
 return {'variant':var.get('variant'),'suffix':suffix,**{k:get(k) for k in ['id','name','options','wornoptions','equipable','stackable','tradeable','quest','noteable','bankable','examine'] if get(k) is not None}}

def add_case(iid,kind,definition,mechanic,acquisition,competing,rationale,target_category=None,target_subcategory='currency'):
 matches=[(t,e) for t,e in index.items() if str(iid) in e.get('variants',{})]
 if len(matches)!=1:raise ValueError((iid,'exact index page count',len(matches)))
 title,entry=matches[0]; sp=ROOT/entry['path']; raw=sp.read_text(encoding='utf-8'); h=sha(sp)
 if h!=entry['sha256']:raise ValueError((iid,'hash mismatch'))
 var=entry['variants'][str(iid)]; facts=resolved_facts(var)
 if str(iid) not in str(facts.get('id')):raise ValueError((iid,'exact selected infobox ID mismatch',facts))
 row=coverage[iid]; packet=next(p for p in packets if int(p['itemId'])==iid)
 if (row['itemCategory'],row['subcategory'],row['ironmanTabKey'])!=(packet['current']['category'],packet['current']['subcategory'],packet['current']['ironmanTabKey']):raise ValueError((iid,'frozen/current mismatch'))
 return {'itemId':iid,'title':title,'status':'PROPOSED_SOURCE_BACKED_PRIMARY','kind':kind,'currentRoute':{'category':row['itemCategory'],'subcategory':row['subcategory'],'ironmanTabKey':row['ironmanTabKey']},'proposedRoute':{'category':target_category or row['itemCategory'],'subcategory':target_subcategory,'ironmanTabKey':row['ironmanTabKey']},'currentTags':packet['current'].get('tags',[]),'tagsClaimed':False,'rolesClaimed':None,'rationale':rationale,'source':{'sourceTitle':title,'sourceRevision':entry['revid'],'sourceUrl':entry['sourceUrl'],'sourceSha256':h,'rawPath':entry['path'],'exactItemId':iid},'exactVariantStateFacts':facts,'ownSubjectLeadLiteral':paragraph(raw,definition),'mechanicLiterals':[paragraph(raw,x) for x in mechanic],'acquisitionLiterals':[paragraph(raw,x) for x in acquisition],'competingContextLiterals':[paragraph(raw,x) for x in competing],'priorDecision':{'decision':prior[iid]['decision'],'rationale':prior[iid]['rationale']}}

def exact_check(iid,status,rationale,definition,mechanic=(),acquisition=(),competing=()):
 matches=[(t,e) for t,e in index.items() if str(iid) in e.get('variants',{})]
 if len(matches)!=1:raise ValueError((iid,'exact check page count',len(matches)))
 title,entry=matches[0]; sp=ROOT/entry['path']; raw=sp.read_text(encoding='utf-8'); h=sha(sp)
 if h!=entry['sha256']:raise ValueError((iid,'hash mismatch'))
 var=entry['variants'][str(iid)]; packet=next(p for p in packets if int(p['itemId'])==iid)
 return {'itemId':iid,'title':title,'status':status,'rationale':rationale,'source':{'sourceTitle':title,'sourceRevision':entry['revid'],'sourceUrl':entry['sourceUrl'],'sourceSha256':h,'rawPath':entry['path'],'exactItemId':iid},'exactVariantStateFacts':resolved_facts(var),'ownSubjectLeadLiteral':paragraph(raw,definition),'mechanicLiterals':[paragraph(raw,x) for x in mechanic],'acquisitionLiterals':[paragraph(raw,x) for x in acquisition],'competingContextLiterals':[paragraph(raw,x) for x in competing],'currentRoute':packet['current']}

new=[
 add_case(32083,'sawmill_cost_voucher',"'''Sawmill coupon (wood plank)''' is a type of [[sawmill coupon]] which is used to cover the {{NoCoins|100}} GP cost of converting regular [[logs]] to [[plank]]s. The coupon is only redeemable at a [[sawmill]], and cannot be substituted for coins when casting [[Plank Make]].",[],['25 sawmill coupons are awarded from the [[Pandemonium]] quest.'],[], 'Exact physical voucher pays a stated sawmill conversion cost. Its own definition limits redemption to a sawmill and states it cannot substitute for coins in Plank Make; acquisition by quest is separate from the spending function.'),
 add_case(32085,'sawmill_cost_voucher',"'''Sawmill coupon (oak plank)''' is a type of [[sawmill coupon]] which is used to cover the {{Coins|250}} cost of converting [[oak logs]] into [[oak plank]]s. The coupon is only redeemable at a [[sawmill]], and cannot be substituted for coins when casting [[Plank Make]].",[],['The [[Prying Times]] and [[Current Affairs]] quests each award 25 coupons.'],[], 'Exact physical voucher pays a stated oak-plank sawmill conversion cost. Its own definition limits redemption to a sawmill; the spell-cost exclusion is preserved. Quest acquisition does not make this use quest-only.'),
 add_case(4251,'active_rechargeable_player_teleport',"The '''ectophial''' is a reward for completing the [[Ghosts Ahoy]] quest. Players can empty it, causing them to be teleported to the [[Ectofuntus]] outside [[Port Phasmatys]]. Once the player teleports, they will automatically refill it.",['It can be used to quickly escape from fights because it is easy to replace, costs nothing, and is a one click teleport from your inventory.'],[],['Like most teleport items, the ectophial does not work past level 20 [[Wilderness]].'],'Exact own variant 4251 is the Full version and has a Teleport action. Its subject definition directly says player transport and automatic refill; the empty sibling has separate exact ID 4252 and no Teleport action.',target_subcategory='teleport'),
 add_case(21387,'empty_teleport_scroll_container',"A '''master scroll book''' is an item obtainable from any level [[Treasure Trails|Treasure Trail]] except beginner. If a [[reward casket]] would reward any type of [[teleport scroll]], there is a 1/23 chance for it to reward a master scroll book instead.",['The master scroll book can store up to 1000 of every type of teleport scroll, which is done by \"using\" the scroll with the book.','Empty master scroll books can now be exchanged with [[Watson]] to receive 10-20 [[Watson teleport|teleport scrolls to his house]].'],[],['Players can open their book to show an interface where they can either use or take out any of the stored teleport scrolls.'],'Exact variant 21387 is explicitly the Empty item: its own infobox has only Open/Drop, while the page establishes its transport purpose as a scroll container and permits exchanging the empty book for teleport scrolls. It is proposed as TELEPORT/teleport-container, not as a presently active teleport.',target_subcategory='teleport-container'),
 add_case(21389,'filled_teleport_scroll_container',"A '''master scroll book''' is an item obtainable from any level [[Treasure Trails|Treasure Trail]] except beginner. If a [[reward casket]] would reward any type of [[teleport scroll]], there is a 1/23 chance for it to reward a master scroll book instead.",['The master scroll book can store up to 1000 of every type of teleport scroll, which is done by \"using\" the scroll with the book.','Players can open their book to show an interface where they can either use or take out any of the stored teleport scrolls.'],[],[],'Exact variant 21389 is the Filled book and its own infobox supplies a Teleport action; the page explains that teleport scrolls are stored and selected through its interface. The proposal certifies TELEPORT/teleport-container; it does not assert destinations or charge counts.',target_subcategory='teleport-container'),
]
checks=[
 exact_check(9474,'HOLD_REWARD_CONTAINER_NOT_CURRENCY','This token is activated to summon food according to stored Gnome Restaurant credits; it is a reward claim/food supply, not spendable currency.',"'''Reward tokens''' are received for gaining at least 12 credits in the [[Gnome Restaurant]] [[minigame]].",['It can be used at any time to summon a [[mounted terrorchick gnome]] bearing [[Gnome cooking|gnome cuisine]].'],[],['A player may only have one reward token at a time']),
 exact_check(8890,'HOLD_MINIGAME_CASHOUT_NOT_SPENDABLE','Exact MTA coins are deposited into the Coin Collector and only a fraction is moved to bank; the page does not establish the item as player-spendable currency.',"'''Coins''' in the [[Mage Training Arena]] are produced by using alchemy spells ([[High Level Alchemy]] or [[Low Level Alchemy]]) in the [[Mage Training Arena/Alchemist's Playground|alchemist's]] section of the minigame.",['For every set of 100 coins deposited into the [[Coin Collector]], the player will have 10 coins deposited into their bank (or inventory if an Ultimate Ironman).']),
 exact_check(24719,'HOLD_ACTIVITY_TIME_CONSUMABLE_NOT_CURRENCY','The exact item adds one minute during a Hallowed Sepulchre run and is consumed; purchase using marks does not make this item currency.',"'''Hallowed token''' is an item used to add an extra minute of time during a [[Hallowed Sepulchre]] run, it is consumed upon use.",['Attempting to activate the token while outside of the Hallowed Sepulchre will result in the message: "The Hallowed token can only be used inside the Hallowed Sepulchre minigame."']),
 exact_check(29388,'HOLD_COLLECTION_TOKEN_NO_REDEMPTION','The page explicitly says the Varlamore tokens have no reward; shared infobox IDs are preserved without treating token naming as currency evidence.',"'''Tokens''' are items that can be found from completing a variety of specific [[daily reset|daily]] tasks around [[Varlamore]].",["Player: Okay... But what do I do with them all now?<br>Cobado: Do with them? Well... nothing. You've already passed the test!" ]),
 exact_check(30113,'HOLD_SET_COMPLETION_ONE_TIME_REWARD','This exact token family is used in a four-token set for a one-time surprise; the set completion exchange does not establish recurring spendable currency.',"Players can show nasty tokens to [[Nasty Nick]] by talking to him with at least one in their inventory; giving him all four will result in him giving a [[nasty surprise]] in exchange.",['Bringing all 7 [[token (Varlamore)|red tokens]] along with the 4 nasty tokens and the 1 [[token (Final Dawn)|purple token]] to [[Cobado]] will result in a one time reward']),
 exact_check(31123,'HOLD_ONE_TIME_SET_REWARD','This purple token is one component in a condition-bound collection exchanged for a one-time muffin/coin reward, not an independently reusable currency.',"If all four conditions are met, the capybara will give the player the purple token.",['The purple token can be taken to [[Cobado]] while wearing [[Orange (hat)|an orange]] as a hat along with all 7 [[token (Varlamore)|red tokens]] and all 4 [[nasty token]]s to receive a [[blueberry muffin]] and 100,000 [[coins]].']),
 exact_check(13392,'HOLD_INERT_RECHARGEABLE_EQUIPMENT_STATE','The exact ID is the inert uncharged version with no Rub option. It is retained rechargeable equipment, but active teleport function cannot be inherited from charged sibling 13393.',"|name1 = Xeric's talisman (inert)",['When first obtaining the talisman, it will be inert and uncharged. [[Lizardman fang]]s can be added to give one charge per fang'],[],['|options1 = Wear, Check, Dismantle, Drop']),
 exact_check(13537,'HOLD_BOOK_NOT_CURRENT_TELEPORT_UNLOCK','This exact item is a book with a Read option; own page says the Kourend Castle teleport unlock moved to a quest in 2024 and the book became unbankable in 2019.',"'''Transportation Incantations''' is a [[book]] written by [[Amon Ducot]] and found in the [[Arceuus Library]].",['Delivering the book yields a [[book of arcane knowledge]].'],[],['|change = The [[Kourend Castle Teleport]] spell is now unlocked by completing the quest [[Client of Kourend]], rather than through this book. As a result, the contents of the book has been altered.','|change = The book may no longer be deposited to a bank to prevent their use as an efficient [[Runecraft]] training method.']),
 exact_check(13108,'HOLD_NO_PLAYER_TELEPORT_FUNCTION','Exact Wilderness sword article proves a wearable sword and web-slashing benefit, not transport by the item.',"The '''Wilderness sword 1''' is a reward from completing the easy [[Wilderness Diary]] given to you by the [[Lesser Fanatic]] in [[Edgeville]].",['*Always slashes webs successfully']),
 exact_check(13109,'HOLD_NO_PLAYER_TELEPORT_FUNCTION','Exact medium Wilderness sword article lists a wearable sword and diary benefits but does not prove the item teleports the player.',"The '''Wilderness sword 2''' is an [[Achievement Diary]] reward for completing the [[medium Wilderness Diary]] given by the [[Lesser Fanatic]] in [[Edgeville]] and can be reclaimed from him for free if lost.",['* Always slashes webs successfully']),
 exact_check(8022,'USER_POLICY_HOLD_UNOBTAINABLE_NONTELEPORT_TABLET','Preserved unresolved under the explicit user-policy hold. The exact page describes an unobtainable intended Telekinetic Grab tablet, not a player-teleport tablet.',"The '''Telekinetic grab''' [[magic tablet]] is an [[unobtainable item]]",['It is assumed to be used to cast [[Telekinetic Grab]] without requiring to be on the [[standard spellbook]].']),
]
# Resolve the exact infobox state suffix for every source-backed partition row.
for row in report['fullPartition']:
    iid=row['itemId']; pages=row['sourceAuditStatus']['exactNumericIdIndexPages']
    if len(pages)==1:
        title=pages[0]['sourceTitle']; var=index[title]['variants'][str(iid)]
        row['exactVariantStateFacts']=resolved_facts(var)
        row['sourcePresenceClass']='EXACT_NUMERIC_ID_VARIANT'
    else:
        row['exactVariantStateFacts']=None
        row['sourcePresenceClass']='NO_EXACT_NUMERIC_ID_VARIANT'

# Avoid duplicate IDs from pinned rechecks and existing new proposals.
existing={x['itemId'] for x in report['newSourceBackedProposals']}
for x in new:
 if x['itemId'] in existing: raise ValueError(('duplicate proposal',x['itemId']))
 existing.add(x['itemId'])
 report['newSourceBackedProposals'].append(x)
report.setdefault('targetedStateAndCompetingContextChecks',[])
for x in checks:
 if x['itemId'] not in [q['itemId'] for q in report['targetedStateAndCompetingContextChecks']]: report['targetedStateAndCompetingContextChecks'].append(x)
# The supplemental exact cases are part of the full, disjoint ID partition.
proposal_by_id={x['itemId']:x for x in report['newSourceBackedProposals']}
for row in report['fullPartition']:
    if row['itemId'] in proposal_by_id:
        row['disposition']='NEW_SOURCE_BACKED_PROPOSAL'
report['partitionCounts']=dict(__import__('collections').Counter(x['disposition'] for x in report['fullPartition']))
# Bind the 34,085-row export to its existing checkpoint audit.
checkpoint_path=ROOT/'tmp/category-certification/root-review/farming-2165-checkpoint-audit.json'
checkpoint=json.loads(checkpoint_path.read_text(encoding='utf-8'))
full_ledger_path=ROOT/'tmp/category-certification/root-approved-decisions-with-clue-scrolls.jsonl'
full_ledger={int(json.loads(x)['itemId']):json.loads(x) for x in full_ledger_path.read_text(encoding='utf-8').splitlines() if x.strip()}
if checkpoint['scope']!=34085 or len(full_ledger)!=34085 or checkpoint['outputSha256']!=sha(full_ledger_path):
 raise ValueError('latest approved full-ledger output does not match its 34,085-row checkpoint')
for row in report['fullPartition']:
    led=full_ledger[row['itemId']]
    route=row['currentAuthoritativeRoute']
    if (led['proposedCategory'],led['proposedSubcategory'],led['proposedIronmanTabKey'])!=(route['category'],route['subcategory'],route['ironmanTabKey']):
        raise ValueError(f"{row['itemId']}: current coverage does not match latest full ledger")
    row['authoritativeFullLedgerDecision']={'decision':led['decision'],'rationale':led['rationale'],'semanticPredicate':led['semanticPredicate']}
report['authoritativeCheckpoint']={'auditPath':str(checkpoint_path.relative_to(ROOT)),'auditSha256':sha(checkpoint_path),'fullLedgerPath':str(full_ledger_path.relative_to(ROOT)),'fullLedgerSha256':sha(full_ledger_path),'fullLedgerRows':len(full_ledger),'approvedRows':checkpoint['approved'],'previousApprovedRows':checkpoint['previousApproved'],'checkpointOutputSha256':checkpoint['outputSha256'],'checkpointScope':checkpoint['scope'],'checkpointApprovalLimitation':checkpoint['scopeLimitation'],'currentCoverageTsvSha256':sha(ROOT/'tmp/category-certification/current-coverage.tsv')}
report['scope']['newProposedCases']=len(report['newSourceBackedProposals'])
report['scope']['targetedExactCounterchecks']=len(report['targetedStateAndCompetingContextChecks'])
report['sourceAwareNotes']={'teleportSourceCohort':'IDs 9469, 10972 and 11060 were rechecked against exact pages and are already included in the pinned 72-case teleport approval; they are not duplicated as new proposals.','ordinaryRuneCohort':'Law rune 563 was rechecked against its exact positive teleportation-spell definition and is already included in the pinned 23-case rune approval; it is not duplicated.','currencyVoucherBoundary':'Sawmill coupons 32083 and 32085 are proposed as narrow-use currency because the exact physical vouchers cover specific sawmill conversion costs; own-source restrictions are quoted. Reward containers and one-time collection tokens remain held.'}
report['depletedOrInactiveTeleportStates']=[
 exact_check(4252,'EMPTY_REFILLABLE_TELEPORT_STATE','Exact ID 4252 is Ectophial Empty and has Drop only; own page says it must be filled before it can be used, but automatically refills after the active teleport. Retained rechargeable transport state, not proof of current active transport.',"|version2 = Empty",['If the player loses the ectophial, they can get a replacement from [[Velorina]] in Port Phasmatys (must wear a [[ghostspeak amulet]] or [[Morytania legs 2]] or better) or purchase it from [[Perdu]] for 4,600 coins. Claiming a replacement from Velorina will give the player a full ectophial. Claiming an ectophial from Velorina if the player already has one will give an empty one instead, which the player first has to fill at the Ectofuntus before they can use it.']),
 exact_check(13392,'INERT_RECHARGEABLE_TELEPORT_GEAR','Exact ID 13392 is inert and has no Rub option; it requires fang charges before use. The article also records neck-slot combat stats, so the empty-state review retains its equipment role as a competing primary consideration.',"|name1 = Xeric's talisman (inert)",['When first obtaining the talisman, it will be inert and uncharged. [[Lizardman fang]]s can be added to give one charge per fang'],[],['|options1 = Wear, Check, Dismantle, Drop']),
 exact_check(21387,'EMPTY_TELEPORT_SCROLL_CONTAINER','Exact empty book has Open/Drop, not the filled variant Teleport option. Its own page supports storage/preparation and empty-book exchange; no current stored scroll is asserted.',"|name1 = Master scroll book (empty)",['The master scroll book can store up to 1000 of every type of teleport scroll, which is done by \"using\" the scroll with the book.','Empty master scroll books can now be exchanged with [[Watson]] to receive 10-20 [[Watson teleport|teleport scrolls to his house]].'],[],['|options1 = Open, Drop']),
 exact_check(21817,'UNCHARGED_NONTELEPORT_COMBAT_GEAR','This exact uncharged bracelet has Wear and Toggle-absorption options but no teleport action. It is revenant-defense gear; charge language does not establish transportation.',"|name1 = Bracelet of ethereum (uncharged)",['When charged, the bracelet becomes untradeable and damage from revenants is reduced by 75%, with 1 charge being consumed per attack. Revenants are also made [[tolerant]] when a charged bracelet is worn.'],[],['|options1 = Wear, Toggle-absorption, Dismantle, Drop','|examine1 = The bracelet is dull and powerless.']),
 exact_check(26945,'UNCHARGED_RECHARGEABLE_TELEPORT_WEAPON','Exact ID is the uncharged Pharaoh\'s sceptre state. The article distinguishes charging from the active teleport use and identifies this object as a weapon; do not assert an active teleport until charged.',"|version1 = Uncharged",['To recharge the sceptre, the player must talk to the [[guardian mummy]] inside Jalsavrah, the Pyramid Plunder pyramid.'],[],['The sceptre provides teleports to each of the great pyramids of the [[Kharidian Desert]], using a charge to do so.']),
 exact_check(29892,'INERT_RECHARGEABLE_TELEPORT_GEAR','Exact ID 29892 is the inert pendant state with no Rub option. Own page says it begins uncharged, must be charged, and destinations separately need unlocking; no active teleport is inferred.',"|name1 = Pendant of Ates (inert)",['Upon obtaining the pendant, it is inert and uncharged. Each [[frozen tear]] provides one charge, and the necklace holds up to 1,000 charges. The charges can be refunded, returning the tears used to charge it and reverting the pendant to its inert state.','No teleports are available by default. To unlock locations, a player must first activate the [[Statue (Ates)|statue of ates]] at each location.'],[],['|options1 = Wear, Check, Dismantle, Drop']),
 exact_check(30637,'UNCHARGED_RECHARGEABLE_TELEPORT_AMULET','Exact ID 30637 is the uncharged variant with a Charge action, while the own page says the amulet provides teleports when charged. It is a preparation state, not an active teleport state.',"|name1 = Giantsoul amulet (uncharged)",['The amulet is charged by using one set of [[big bones]] (which can be noted) and one [[law rune]] on the amulet and can contain a maximum of 16,000 charges'],[],['|options1 = Wear, Charge, Drop']),
]
report['scope']['depletedOrInactiveTeleportStateCount']=len(report['depletedOrInactiveTeleportStates'])
report_path.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps({'output':str(report_path),'sha256':sha(report_path),'newProposalIds':[x['itemId'] for x in report['newSourceBackedProposals']],'recheckedPinnedIds':[x['itemId'] for x in report['independentSourceRechecksOfPinnedCases']],'targetedChecks':len(report['targetedStateAndCompetingContextChecks'])},indent=2))

