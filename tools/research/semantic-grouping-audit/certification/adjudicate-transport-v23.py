import json, pathlib, hashlib, re, collections
ROOT=pathlib.Path.cwd(); BASE=ROOT/'tmp/category-certification/reviews/transport-v22/full-shard-review-v1.json'; OUT=ROOT/'tmp/category-certification/reviews/transport-v23'
OUT.mkdir(parents=True,exist_ok=True)
base=json.loads(BASE.read_text(encoding='utf-8')); index=json.loads((ROOT/'tmp/category-certification/wiki-articles/article-index.json').read_text(encoding='utf-8'))
packets={int(x['itemId']):x for x in map(json.loads,(ROOT/'tmp/category-certification/reviewer-packets/currency-runes-teleport.jsonl').read_text(encoding='utf-8').splitlines()) if x}
ledger={int(x['itemId']):x for x in map(json.loads,(ROOT/'tmp/category-certification/root-approved-decisions-with-clue-scrolls.jsonl').read_text(encoding='utf-8').splitlines()) if x}
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()

def facts(v):
 p=v['params'];s=v.get('suffix','')
 def get(k):return p.get(k+s,p.get(k)) if s else p.get(k)
 fields=['id','name','options','wornoptions','equipable','stackable','tradeable','quest','noteable','examine']
 return {'variant':v.get('variant'),'suffix':s,**{k:get(k) for k in fields if get(k) is not None}}
def own_context(raw,i):
 # Start at the exact ID's own Infobox Item id field, then use the first bold subject statement.
 m=re.search(r'(?m)^\|id\d*\s*=\s*[^\n|]*\b'+str(i)+r'\b[^\n]*$',raw)
 if not m: raise ValueError(f'{i}: exact id line not found in raw Infobox Item')
 lead=re.search(r"'''[^\n]{2,140}?'''",raw[m.end():])
 if not lead:
  tail=raw[m.end():]; lines=tail.splitlines(); offset=m.end()
  for line in lines:
   stripped=line.strip()
   if not stripped or stripped.startswith(('}}','{{','[[File:','{|','|')):
    offset+=len(line)+1;continue
   break
  en=raw.find('\n==',offset);en=len(raw) if en<0 else en
  return raw[offset:en].strip()
 at=m.end()+lead.start();st=raw.rfind('\n',0,at)+1;en=raw.find('\n==',at);en=len(raw) if en<0 else en
 return raw[st:en].strip()
def section(raw,anchor):
 at=raw.find(anchor)
 if at<0:raise ValueError('source anchor absent '+anchor)
 if anchor.startswith('=='):
  end=raw.find('\n==',at+2);end=len(raw) if end<0 else end
  return raw[at:end].strip()
 lo=raw.rfind('\n\n',0,at)+2;hi=raw.find('\n\n',at);hi=len(raw) if hi<0 else hi
 q=raw[lo:hi].strip()
 if anchor not in q:raise AssertionError(anchor)
 return q

def related_sections(raw,cat):
 headings=list(re.finditer(r'(?m)^==([^=]+)==\s*$',raw))
 names=[m.group(1).strip() for m in headings]
 if cat=='TELEPORT': priority=['Teleportation','Teleport','Benefits','Charging','Recharging','Combat stats','Restrictions','Uses','Changes']
 elif cat=='CURRENCY': priority=['Spending','Uses','Exchange','Rewards','Purchases','Obtaining','Earning','Limitations','Changes']
 else: priority=['Runecraft','Usage','Benefits','Combination','Charging','Recharging','Limitations','Uses','Creation','Combat stats','Changes']
 chosen=[]
 for key in priority:
  for m,name in zip(headings,names):
   if key.lower() not in name.lower():continue
   end=raw.find('\n==',m.end());end=len(raw) if end<0 else end
   q=raw[m.start():end].strip()
   if q not in chosen:chosen.append(q)
   break
  if len(chosen)>=4:break
 return chosen

# Manually adjudicated source-backed semantic rules. Every application is still bound to its own exact ID variant and source page.
support_ids={
# Explicit currency, fare, redeemable reward or exchange claims.
621:'Ship tickets are exchanged for named boat rides, a direct fare entitlement; acquisition and route differ from teleporting the player.',
680:'Three exact nuggets exchange for one gold ore; the page gives a repeatable physical exchange function.',
995:'Exact ordinary coin stack is explicitly currency exchanged for items and services.',
4067:'Castle Wars tickets are earned from play and spent at the named ticket shop; repeatable reward currency.',
4278:'Ecto-tokens are explicitly currency in Port Phasmatys with recurring entry, shop, and charge uses.',
5020:'Minecart tickets pay for rides to/from Keldagrim; the exact ticket is a transport fare, not a player teleport.',5021:'Minecart tickets pay for rides to/from Keldagrim; the exact ticket is a transport fare, not a player teleport.',5022:'Minecart tickets pay for rides to/from Keldagrim; the exact ticket is a transport fare, not a player teleport.',5023:'Minecart tickets pay for rides to/from Keldagrim; the exact ticket is a transport fare, not a player teleport.',
6183:'Frog tokens are directly exchanged with Thessalia for costume pieces or a lamp; this is a one-time reward token, not ordinary money.',
8851:'Warrior guild tokens are repeatedly consumed as an entry fee and per-minute access cost; category is currency/access tender, with the minigame restriction retained.',
8951:'The exact legacy stack was currency for shop rewards and its own page says residual pieces can be counted into the successor virtual currency; the physical item is a redeemable currency state.',
11849:'Marks of Grace are explicitly currency spent at Grace’s shop and Osten for repeat rewards.',
12012:'Golden nuggets are explicitly traded for repeat rewards from Prospector Percy’s shop.',
13204:'Platinum tokens are explicitly currency representing a fixed coin exchange for player-to-player trade.',
13307:'Blood money is spent at Nigel’s shop for Deadman armour; its mode origin does not erase the direct purchase function.',
21341:'Unidentified minerals are spent at the Mining Guild Mineral Exchange for named tools and supplies.',
21555:'Numulite is explicitly currency used on Fossil Island.',
21656:'Mermaid’s tears are exchanged at Mairin’s Market for named supplies; direct shop-currency function.',
25676:'Barronite shards are explicitly described as currency/fuel for the Shard Exchange, vault entry, and repeat item purchases.',
28134:'Anima-infused bark is explicitly the primary Forestry Shop currency with repeat purchases.',
29460:'Wilderness agility tickets are repeatedly exchanged for Agility experience; direct redeemable service currency.',
29480:'Brimhaven Agility Arena tickets are repeatedly exchanged for Agility experience at a named store.',
29482:'Brimhaven vouchers are repeatedly exchanged for store items.',
# Direct rune / Runecraft tool functions.
5521:'Binding necklace has a directly stated 100% combination-rune success function and 16-use state; charges are per player, not encoded per necklace.',
12791:'Exact regular rune pouch stores up to three rune types and enables spell-casting from the contents.',
27281:'Exact divine rune pouch is an upgraded bankable four-rune container that supports spell-casting from stored runes.',
27509:'The exact locked Divine pouch variant remains the same four-rune container; its locked/death-retention state does not erase the pouch function.',
24607:'Blighted ancient ice sacks directly supply Ancient Magicks ice spells and the page says they function like runes; their Wilderness/PvP restriction is explicit.',
22118:'Wrath talisman directly grants Wrath Altar entry for Runecraft.',
22121:'Wrath tiara directly grants worn entry to Wrath Altar and saves an inventory slot.',
# Direct, item-bound player transport or reusable teleport methods.
981:'The exact Disk of Returning can be activated in the Dwarven Mine to move the player into and back out of the Blackhole; the use location is restricted.',
3690:'The exact enchanted lyre page defines player teleports to Rellekka; variant suffix/state is independently captured.',3691:'The exact enchanted lyre page defines player teleports to Rellekka; variant suffix/state is independently captured.',6125:'The exact enchanted lyre page defines player teleports to Rellekka; variant suffix/state is independently captured.',6126:'The exact enchanted lyre page defines player teleports to Rellekka; variant suffix/state is independently captured.',6127:'The exact enchanted lyre page defines player teleports to Rellekka; variant suffix/state is independently captured.',13079:'The exact enchanted lyre page defines player teleports to Rellekka; variant suffix/state is independently captured.',23458:'The imbued lyre exact variant provides infinite teleports and named unlock-gated destinations.',
6099:'Exact positive-charge crystal state teleports the player to Lletya/Prifddinas.',6100:'Exact positive-charge crystal state teleports the player to Lletya/Prifddinas.',6101:'Exact positive-charge crystal state teleports the player to Lletya/Prifddinas.',6102:'Exact positive-charge crystal state teleports the player to Lletya/Prifddinas.',13102:'Exact positive-charge crystal state teleports the player to Lletya/Prifddinas.',
9013:'The skull sceptre directly teleports to the Stronghold of Security; source also records autocast and charge/degradation context.',21276:'The imbued skull sceptre directly teleports to the Stronghold and retains its documented spell/autocast function.',
22517:'Escape crystal is a consumable player teleport out of named dangerous activities; peer activation also consumes both crystals.',
22599:'Icy basalt is a consumable player teleport to Weiss, with quest and crafting requirements explicitly stated.',22601:'Stony basalt is a consumable player teleport to Troll Stronghold; destination unlock and construction use are explicit.',
23946:'Eternal teleport crystal directly teleports to Lletya/Prifddinas with unlimited charges.',24336:'Target teleport tablet directly teleports the player to the assigned target, subject to the spell restrictions.',24441:'The exact event tablet directly teleports the player out of ScapeRune to the bakery; the lead explicitly corrects the misleading name.',24615:'Blighted sack directly supplies Tele Block/Teleport to Target casts, consumed on use, restricted to Wilderness.',24709:'Hallowed crystal shards directly teleport a player to the Sepulchre lobby from places where teleporting is allowed.',24949:'Moonclan tablet directly teleports the player to Lunar Isle after the stated visit requirement.',25818:'Book of the Dead is a retained charged book with the same named teleports as Kharedst’s memoirs; resurrection-spell use is secondary.',29090:'Calcified moth is an explicitly single-use player teleport to Cam Torum, with quest and Wilderness limits stated.',
29271:'Basic quetzal whistle is explicitly a player transport interface with up to five charges.',29273:'Enhanced quetzal whistle is explicitly a player transport interface with up to twenty charges.',29275:'Perfected quetzal whistle is explicitly a player transport interface with up to fifty charges.',
29535:'Strange teleorb directly teleports the player when activated at its specified circle; location and quest context are explicit.',30966:'Ancient teleporter pair directly transports players between placed devices; own page requires a pair and limits use to the cavern.',31099:'Mokhaiotl waystone is an explicit consumable player teleport to the Ruins of Mokhaiotl.',31890:'Bottle of portal nexus perry is a one-time player teleport; the source separately states that the boat is moved and courier cargo is lost.',32399:'Sailors’ amulet directly teleports the player to built Sailing destinations; charging cost and non-refundable state are explicit.',33120:'Imbued perfected quetzal whistle has unlimited charges and opens the player-transport interface.'}

corrections={}
def corr(ids,cat,sub,tab,reason,anchors=()):
 for i in ids: corrections[i]={'category':cat,'subcategory':sub,'ironmanTabKey':tab,'reason':reason,'anchors':list(anchors)}
CLEAN=('CLEANUP','cleanup','storage-cleanup')
for i in [4023,11155,13680,26906]: corr([i],*CLEAN,'Exact own page shows a quest/objective or event-only function, not ordinary Runecraft consumable/container use.',())
for i in [9691,9693,9695,9697,9699]: corr([i],*CLEAN,'Exact Slug Menace rune page says this ID is a special rune used to unlock a quest door, and the exact item’s own lead explicitly negates ordinary spell payment; it is a quest key/component, not a usable rune.')
for i in [11686,11687,11688,11689,11690,11692,11694,11697,22208,11691,11693,11695,11696,11698,11699]: corr([i],*CLEAN,'Exact Barbarian Assault source says obtainable activity copies disappear when taken outside; unobtainable copies are directly marked unavailable. They are not retained bank runes.')
corr([20008],'CLUE','cosmetic','clues-cosmetics','Exact fancy tiara page identifies a master Treasure Trails reward, says it has no Runecraft perks and is purely cosmetic; costume storage supports the cosmetic placement.',('purely cosmetic',))
corr([5525],'GEAR','cosmetic','clues-cosmetics','Exact plain tiara page says the silver head item is purely cosmetic and is only a base ingredient until it is imbued; it does not itself open an altar.',('They are a purely cosmetic head slot item',))
corr([9474],'POTION','food','potions-food','The exact Gnome Restaurant reward token summons edible gnome cuisine; it is a single-use food-source entitlement, not spendable currency.',('summon a [[mounted terrorchick gnome]]',))
corr([30858],'SKILLING','smithing-material','resources','Exact Infernal nugget page defines it as a Smithing input for infernal plates/oathplate armour; no spending or currency exchange function.',('used to create [[infernal plate]]s',))
corr([31946],'SKILLING','crafting-material','resources','Exact echo pearl is used to build a fathom pearl on a boat; it is a crafting input, not a currency.',('It is used to build a [[fathom pearl]] on a [[boat]]',))
corr([33798],'SKILLING','quest-crafting-material','resources','Exact Blood Moon quest hallowed marks are consumed with the flail and sickle to craft the hallowed flail; the page explicitly distinguishes them from Sepulchre currency.',('They are combined with the [[blisterwood flail]]', 'cannot be used in their stead'))
corr([13108,13109],'GEAR','weapon','combat-gear','Exact swords 1 and 2 are iron/steel weapons with web-slashing benefits but no teleport benefit; current TELEPORT route is contradicted by the exact benefits section.',('Always slashes webs successfully',))
corr([21816,21817],'GEAR','hands','combat-gear','Exact bracelet states are revenant combat equipment; charged absorbs revenant damage and uncharged is powerless. Neither state teleports.',('damage from revenants is reduced by 75%', 'The bracelet is dull and powerless.'))
corr([4035],*CLEAN,'The exact sigil marks squad membership; the page’s own Trivia explicitly says the sigil does not teleport the player. Its quest teleport is an external trap spell and ends after the boss.',('the sigil itself does not teleport the player character',))
corr([11177],*CLEAN,'Exact museum Jewellery item cannot be worn and has no use outside the Varrock Museum minigame; its possible 5-coin exchange/storage-crate outcomes are not teleport use.',('Players cannot wear this jewellery',))
corr([13537],*CLEAN,'The own book page states the former teleport unlock was removed and the physical book is a library reference; no current teleport action remains.')
corr([24545],*CLEAN,'Exact dummy portal is an unobtainable interface item seen only in a chatbox message.',('unobtainable item',))
for i in [24460,27416,29622,33018]: corr([i],'CLUE','cosmetic','clues-cosmetics','Exact scroll is consumed to unlock a Home Teleport animation override, not to move the player; current TELEPORT route confuses an animation with transport.',('animation override',))
for i in [28369,28375]: corr([i],*CLEAN,'Exact anima portal/device or schematic is a quest object used to distract Lost Souls or have Ketla create the object; neither transports a player.')
for i in [32441,32455,32472,32492,32642,32660,32682,32784,32944,32969,32970]: corr([i],*CLEAN,'Exact crate is temporary courier cargo; the page says players cannot teleport or leave port with it and the item is confiscated after leaving.',('Players cannot unequip the crate normally', 'the crate will be removed'))
for i in [26887,26888,26889,26890,26891,26892,26893,26894,26895,26896,26897,26898]: corr([i],*CLEAN,'Exact portal talisman opens an altar route only inside Guardians of the Rift and the page says it cannot be kept after the game; it is not a bank teleport item.',('Portal talismans cannot be kept after the game ends',))

# Explicit subcategory corrections for transport preparation rather than direct teleport charges.
for i in [21046,25837,28330,28331,28332,28333]: corrections[i]={'category':'TELEPORT','subcategory':'transport-access','ironmanTabKey':'currency-utilities','reason':'Exact own function adds/unlocks a destination on another transport item; it is access preparation, not a direct teleport or charge.', 'anchors':()}
for i in [6103,23959]: corrections[i]={'category':'TELEPORT','subcategory':'teleport-charge','ironmanTabKey':'currency-utilities','reason':'Exact state is a depleted seed/upgrade component used to recharge or create an active teleport crystal; it does not itself move the player.', 'anchors':()}

unresolved_reason={
'currency':'Exact page is present, but its own function is a one-time reward, activity-limited token, or nonstandard conversion; this pass does not equate a reward token/container with recurring currency without a clear reviewed rule.',
'rune':'Exact page is present, but current mechanics include activity-only, empty, charged, component, or quest states; category or bank-retention cannot be settled from the exact variant and own article excerpt.',
'teleport':'Exact page is present, but its own function has a competing gear/utility role, dynamic charge state, preparation-only state, event/quest limit, or a transport-vs-boat distinction that requires primary-route policy review.'}

rows=[];source_failures=[]
for part in base['fullPartition']:
 if part['disposition']!='EXACT_WIKI_ID_PRESENT_NEEDS_INDEPENDENT_MECHANIC_REVIEW': continue
 i=part['itemId']; pages=part['sourceAuditStatus'].get('exactNumericIdIndexPages',[])
 if not pages:
  source_failures.append({'itemId':i,'failure':'partition said exact source but exactNumericIdIndexPages empty'});continue
 title=pages[0]['sourceTitle']; ent=index.get(title)
 if not ent:
  source_failures.append({'itemId':i,'sourceTitle':title,'failure':'title absent from article index'});continue
 sp=ROOT/ent['path'];raw=sp.read_text(encoding='utf-8')
 if sha(sp)!=ent['sha256']:
  source_failures.append({'itemId':i,'sourceTitle':title,'failure':'body hash mismatch'});continue
 v=ent.get('variants',{}).get(str(i))
 if not v:
  source_failures.append({'itemId':i,'sourceTitle':title,'failure':'exact numeric variant missing'});continue
 f=facts(v)
 if str(i) not in re.findall(r'\d+',str(f.get('id'))):
  source_failures.append({'itemId':i,'sourceTitle':title,'failure':'selected variant ID list does not contain exact ID','facts':f});continue
 try: lead=own_context(raw,i)
 except Exception as exc:
  source_failures.append({'itemId':i,'sourceTitle':title,'failure':str(exc)});continue
 current=part['currentAuthoritativeRoute'];cat=current['category']
 # Manual exception / direct predicate decisions.
 if i in corrections:
  dec='CORRECTION_CANDIDATE'; target=corrections[i];proposed={k:target[k] for k in ['category','subcategory','ironmanTabKey']};reason=target['reason']; anchors=target.get('anchors',())
 elif i in support_ids:
  dec='SUPPORTED_UNCHANGED_CANDIDATE';proposed={k:current[k] for k in ['category','subcategory','ironmanTabKey']};reason=support_ids[i];anchors=()
 else:
  dec='UNRESOLVED';proposed=None;reason=unresolved_reason[cat.lower()];anchors=()
 extras=related_sections(raw,cat);context_failures=[]
 for a in anchors:
  try:
   q=section(raw,a)
   if q not in extras:extras.append(q)
  except Exception as exc: context_failures.append({'anchor':a,'failure':str(exc)})
 row={'itemId':i,'decision':dec,'currentRoute':{k:current[k] for k in ['category','subcategory','ironmanTabKey']},'proposedRoute':proposed,'proposedTags':None,'proposedRoles':None,'roleClaimScope':'unassessed','tagsClaimed':False,'exactVariantStateFacts':f,'directStateReading':('Exact variant fields are item-ID-bound; options/examine/name are reproduced below. Where the article describes charges as player/account-held or mutable, this ID alone does not establish a positive remaining count.'),'rationale':reason,'source':{'sourceTitle':title,'sourceRevision':ent['revid'],'sourceUrl':ent['sourceUrl'],'sourceSha256':ent['sha256'],'rawPath':ent['path'],'exactItemId':i},'ownSubjectAndFirstSectionLiteral':lead,'selectedMechanicAndCompetingLiterals':extras,'sourcePresenceClass':part.get('sourcePresenceClass'),'priorPartitionDisposition':part['disposition']}
 if context_failures:row['selectedContextEvidenceFailures']=context_failures
 if dec=='UNRESOLVED':row['unresolvedReason']=reason
 if dec=='CORRECTION_CANDIDATE':row['correctionScope']='candidate only; route requires root review; no policy or production write'
 if dec=='SUPPORTED_UNCHANGED_CANDIDATE':row['supportScope']='candidate only; direct function supports the unchanged primary route; no root approval'
 rows.append(row)

# Preserve exact per-ID accounting and distinguish this complete adjudication tranche from approved decisions.
assert len(rows)+len(source_failures)==275,(len(rows),len(source_failures))
assert len({x['itemId'] for x in rows+source_failures})==275
assert {x['itemId'] for x in rows+source_failures}=={x['itemId'] for x in base['fullPartition'] if x['disposition']=='EXACT_WIKI_ID_PRESENT_NEEDS_INDEPENDENT_MECHANIC_REVIEW'}
counts=collections.Counter(x['decision'] for x in rows)
# Build the v23 full-scope review as a new file, leaving v22 immutable.
report={'schema':'transport-v23-full-scope-exact-source-adjudication','status':'candidate review only; not approval, not a policy change, not a ledger decision, no production edit','asOf':base['asOf'],'scope':{'ownedShardRows':1138,'categories':base['scope']['categories'],'fullLedgerRows':34085,'preexistingRootApprovedRows':95,'adjudicatedRemainingExactSourceRows':275,'priorV22ProposalsPreserved':len(base['newSourceBackedProposals']),'priorV22HoldsPreserved':len(base['v22AdditionalReviewedCases']['reviewedHolds']),'userPolicyHolds8014to8022':'remain unchanged and unresolved'},'inputs':{'baseV22':{'path':str(BASE.relative_to(ROOT)),'sha256':sha(BASE)},'articleIndex':{'path':'tmp/category-certification/wiki-articles/article-index.json','sha256':sha(ROOT/'tmp/category-certification/wiki-articles/article-index.json')},'currentPacket':{'path':'tmp/category-certification/reviewer-packets/currency-runes-teleport.jsonl','sha256':sha(ROOT/'tmp/category-certification/reviewer-packets/currency-runes-teleport.jsonl')},'currentLedger':{'path':'tmp/category-certification/root-approved-decisions-with-clue-scrolls.jsonl','sha256':sha(ROOT/'tmp/category-certification/root-approved-decisions-with-clue-scrolls.jsonl')}},'decisionCounts':dict(counts),'sourceFailures':source_failures,'perIdAdjudication':rows,'fullPartition':base['fullPartition'],'preservedV22Review':{'proposals':base['newSourceBackedProposals'],'holds':base['v22AdditionalReviewedCases']['reviewedHolds'],'partitionCounts':base['partitionCounts']}}
# Full partition updates only the 275 exact-source rows with this independent candidate result.
by={x['itemId']:x for x in rows}
for r in base['fullPartition']:
 if r['itemId'] in by:r['v23Adjudication']=by[r['itemId']]['decision']
out=OUT/'full-per-id-adjudication-v1.json';out.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps({'output':str(out),'sha256':sha(out),'baseV22Sha256':sha(BASE),'adjudicatedRows':len(rows),'sourceFailures':len(source_failures),'decisionCounts':dict(counts),'byCategory':{c:dict(collections.Counter(x['decision'] for x in rows if x['currentRoute']['category']==c)) for c in ['CURRENCY','RUNE','TELEPORT']}},ensure_ascii=False,indent=2))
