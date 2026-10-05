import json,pathlib,hashlib,re,collections
ROOT=pathlib.Path.cwd(); BASE=ROOT/'tmp/category-certification/reviews/transport-v23/full-per-id-adjudication-v1.json'; OUT=ROOT/'tmp/category-certification/reviews/transport-v24'; OUT.mkdir(parents=True,exist_ok=True)
base=json.loads(BASE.read_text(encoding='utf-8')); sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
assert sha(BASE)=='e9ed09021eab36d89905783ce1923e4e9a4a0f1185c883e289072d5d90b90991'
def section(raw,anchor):
 at=raw.find(anchor)
 if at<0: raise ValueError('anchor absent '+anchor)
 if anchor.startswith('=='):
  end=raw.find('\n==',at+2); end=len(raw) if end<0 else end; return raw[at:end].strip()
 lo=raw.rfind('\n\n',0,at)+2; hi=raw.find('\n\n',at); hi=len(raw) if hi<0 else hi
 q=raw[lo:hi].strip()
 if anchor not in q: raise AssertionError(anchor)
 return q
# Adjudications for exact rows that were still open in v23. Each entry records a per-ID conclusion or a concrete, evidence-defined hold.
CLEAN=('CLEANUP','cleanup','storage-cleanup')
def rec(ids,kind,route=None,why='',anchor=None):
 for i in ids: decisions[i]={'kind':kind,'route':route,'why':why,'anchor':anchor}
decisions={}
# Spellbook interface sprites are explicitly unobtainable cache objects, not player-carried teleport items.
rec([3286,3289,3292,3296,3301,3306,3312,4555,4631,4634,4637,4640,4643,4646,4649,4652,7619,8828,9712], 'CORRECTION',CLEAN,'The exact Spell variant is an unobtainable cache/interface object. Its spell name is not an item the player can bank or activate; the spell itself is an interface action.','series of unobtainable items')
rec([6770], 'CORRECTION',CLEAN,'Exact directions are a Ratcatchers quest document used to locate a mansion; the item does not transport the player.','used to locate')
# These exact states retain a positive mechanic for the current primary function.
rec([772], 'SUPPORTED',None,'The staff itself grants access to the fairy-ring transport system and its own lead says it permits entry to Zanaris. The equipped blunt-weapon property is secondary to this transport-access function.','required to use the [[fairy rings|fairy ring transport system]]')
rec([4252], 'SUPPORTED',None,'This exact empty state remains the reusable Ectophial: using it empties and teleports, then the same item automatically refills. Empty describes the cycle point, not a nonfunctional/depleted item.','Once the player teleports, they will automatically refill it.')
rec([8890], 'SUPPORTED',None,'These exact Mage Training Arena coins are deposited into the Coin Collector and yield ordinary banked coins; this is an exact conversion into spendable currency rather than a reward container.','the player will have 10 coins deposited into their bank')
rec([10934,10935,10936,10942,10943,10944], 'SUPPORTED',None,'Each route-colored Temple Trekking token is directly exchangeable anywhere for a chosen listed reward. This supports its current one-time reward-currency placement without claiming it is reusable general money.','The token given can be exchanged for the reward')
rec([11968,11970], 'SUPPORTED',None,'Exact positively charged Skills necklace variant provides its listed destination options and consumes charges on use; the page’s skill-utility and equipment contexts do not displace the selected transport primary.','teleports')
# 19707 is handled as a source-specific unresolved dual-use hold below.
rec([21760], 'SUPPORTED',None,'The memoirs themselves have a Reminisce option that teleports the player to unlocked Kourend destinations; pages supply charges and the book is retained/reclaimable. Quest-item naming does not negate the direct transport use.','teleport the player near a patch of lancalliums')
rec([21863], 'SUPPORTED',None,'This exact event tablet is a usable return teleport to the Land of Snow. One-time event acquisition/replacement limits do not turn an item that can be used by the player into an activity-only copy.','return conveniently to the [[Land of Snow]]')
rec([24416], 'SUPPORTED',None,'The locked Rune pouch variant is still the exact bankable three-type rune container; its own article states that stored runes are used for spellcasting. Locked is a death-retention state, not an unusable pouch state.','Players can cast spells using the runes stored in the pouch')
rec([24587], 'SUPPORTED',None,'The exact note is directly exchanged at a banker/bank fixture for a Rune pouch and functions as a bankable replacement entitlement; it is a pouch-acquisition state, not a spell-rune consumable.','in exchange for a [[rune pouch]]')
rec([27086,30692], 'CORRECTION',CLEAN,'These exact rune-pouch variants are supplied only for the named minigame and provide temporary free spell runes during that game; they are activity copies, not retained bank rune containers.',None)
rec([29388,29389,29390,29391,29392,29393,29394,29395,29396,29397,29398,29399,29400,29401,29402,29403,29404,29405,29406,29407,31123,31124,31125,31126,31127], 'CORRECTION',CLEAN,'Exact Varlamore collection tokens are explicitly a completed collection test with no reward and no further use. They are not spendable currency despite their token names.','big reward')
rec([22207], 'CORRECTION',CLEAN,'Glistening tears can only be exchanged for underwater Agility/Thieving experience and the own page says they cannot be deposited in a bank. They are an activity-only, nonbankable training balance, not bank currency.','they cannot be deposited into a [[bank]]')
rec([29892], 'CORRECTION',('TELEPORT','teleport-charge','currency-utilities'),'This exact inert pendant cannot yet teleport; it is the retained chargeable pendant state, and frozen tears unlock charges. Record as teleport preparation/charge state rather than as an active teleport.','Upon obtaining the pendant, it is inert and uncharged.')
rec([29895], 'SUPPORTED',None,'Frozen tears are the exact direct charge material: one tear supplies one Pendant of Ates teleport charge.','each tear provides one teleport charge')
rec([30637], 'CORRECTION',('TELEPORT','teleport-charge','currency-utilities'),'This exact uncharged amulet has no active teleport charge; bones plus law rune are consumed to charge it. Preserve as a teleport-charge preparation state, not an active teleport.','The amulet is charged by using one set of [[big bones]]')
rec([33122], 'CORRECTION',('SKILLING','construction-material','resources'),'Exact blueprints are consumed to construct a player-owned-house exit portal; the later portal, rather than this blueprint item, is what players use.','They are used to construct an [[Exit portal#Wilderness|Annihilation exit portal]]')
# Additional exact cases where the source clearly distinguishes a prep item or exchange product from the current primary role.
rec([4601], 'SUPPORTED',None,'Exact Ugthanki dung directly recharges the Camulet; it is the charge material currently represented by TELEPORT/teleport-charge, not an active teleport item.','providing 4 charges')
rec([12846], 'CORRECTION',('TELEPORT','transport-access','currency-utilities'),'The scroll is read once to unlock the Teleport to Target spell. It prepares a separate spell and does not teleport the player itself.','unlock the [[Teleport to Target]] spell')
rec([30113,30114,30115,30116,30117,30118,30119,30120,30121], 'CORRECTION',CLEAN,'The exact Nasty token can only be turned into a single Nasty Surprise after collecting all four variants; it is a quest/collection exchange component, not spendable currency.','giving him all four will result in him giving a [[nasty surprise]] in exchange')
rec([31773,31776,31779,31782,31785,31788,31794,31797,31800], 'CORRECTION',CLEAN,'The exact pearl has no shop or exchange use; its documented disposition is high alchemy, with Death’s Coffer only described for the highest-value tier. This is loot/salvage, not currency.','it can be alchemised for a profit')
# More detailed, exact own-variant holds for dual-use equipment, current-state limits, or activity-bound supplies.
holds={
19707:'Unlimited player teleports are explicit, but this exact eternal glory also inherits combat bonuses and clue-step use. Teleport-versus-combat-jewellery primary precedence is unresolved.',
1704:'Uncharged glory variant has no listed remaining teleport charges. The exact amulet still has combat/equipment and other dragonstone functions, so the current teleport route is not justified by this state alone.',
1706:'One-charge glory is an equipped dragonstone amulet with combat bonuses and four destinations. The active teleport is direct, but the primary route competes with its retained combat-jewellery role.',
1708:'Two-charge glory is an equipped dragonstone amulet with combat bonuses and four destinations. Teleport and combat equipment are both directly supported; primary precedence unresolved.',
1710:'Three-charge glory is an equipped dragonstone amulet with combat bonuses and four destinations. Teleport and combat equipment are both directly supported; primary precedence unresolved.',
1712:'Four-charge glory is an equipped dragonstone amulet with combat bonuses and four destinations. Teleport and combat equipment are both directly supported; primary precedence unresolved.',
2572:'Uncharged Ring of wealth has no current teleport charge; its loot/drop effects and equipped ring state remain. Need an explicit route rule for an item whose main value persists without teleport charge.',
10354:'Trimmed glory (t4) is a cosmetic clue variant that also has four teleport charges and inherited glory combat bonuses. Exact transport and equipment/cosmetic roles conflict for primary placement.',
10356:'Trimmed glory (t3) is a cosmetic clue variant with three teleport charges and inherited glory combat bonuses. Exact transport and equipment/cosmetic roles conflict for primary placement.',
10358:'Trimmed glory (t2) is a cosmetic clue variant with two teleport charges and inherited glory combat bonuses. Exact transport and equipment/cosmetic roles conflict for primary placement.',
10360:'Trimmed glory (t1) is a cosmetic clue variant with one teleport charge and inherited glory combat bonuses. Exact transport and equipment/cosmetic roles conflict for primary placement.',
10362:'Trimmed glory is explicitly a cosmetic clue variant, and this exact ID is uncharged. No active teleport state; equipment/clue cosmetic policy is needed.',
11113:'Uncharged Skills necklace has no usable charges, while its equipment/skill utility remains. It cannot be certified as an active teleport variant.',
11118:'Four-charge Combat bracelet is wearable combat equipment with active Guild teleports. Both functions are explicit; primary precedence for this bracelet family is unresolved.',
11120:'Three-charge Combat bracelet is wearable combat equipment with active Guild teleports. Both functions are explicit; primary precedence for this bracelet family is unresolved.',
11122:'Two-charge Combat bracelet is wearable combat equipment with active Guild teleports. Both functions are explicit; primary precedence for this bracelet family is unresolved.',
11124:'One-charge Combat bracelet is wearable combat equipment with active Guild teleports. Both functions are explicit; primary precedence for this bracelet family is unresolved.',
11126:'Uncharged Combat bracelet has no usable teleport charges, but remains an equipable combat bracelet. The exact state does not support active teleport primary.',
11964:'Trimmed glory (t6) is a cosmetic clue variant with six teleport charges and inherited glory combat bonuses. Exact transport and equipment/cosmetic roles conflict for primary placement.',
11966:'Trimmed glory (t5) is a cosmetic clue variant with five teleport charges and inherited glory combat bonuses. Exact transport and equipment/cosmetic roles conflict for primary placement.',
11972:'Six-charge Combat bracelet is wearable combat equipment with active Guild teleports. Both functions are explicit; primary precedence for this bracelet family is unresolved.',
11974:'Five-charge Combat bracelet is wearable combat equipment with active Guild teleports. Both functions are explicit; primary precedence for this bracelet family is unresolved.',
11976:'Five-charge glory is an equipped dragonstone amulet with combat bonuses and four destinations. Teleport and combat equipment are both directly supported; primary precedence unresolved.',
11978:'Six-charge glory is an equipped dragonstone amulet with combat bonuses and four destinations. Teleport and combat equipment are both directly supported; primary precedence unresolved.',
11980:'Five-charge Ring of wealth (5) actively teleports but also applies its ring-of-wealth item-drop effect and combat equipment role. Primary precedence unresolved.',
11982:'Four-charge Ring of wealth actively teleports but also applies its ring-of-wealth item-drop effect and combat equipment role. Primary precedence unresolved.',
11984:'Three-charge Ring of wealth actively teleports but also applies its ring-of-wealth item-drop effect and combat equipment role. Primary precedence unresolved.',
11986:'Two-charge Ring of wealth actively teleports but also applies its ring-of-wealth item-drop effect and combat equipment role. Primary precedence unresolved.',
11988:'One-charge Ring of wealth actively teleports but also applies its ring-of-wealth item-drop effect and combat equipment role. Primary precedence unresolved.',
12785:'Uncharged imbued Ring of wealth has no teleport charge; it retains imbued ring item-drop effects and equipment status. Exact active transport predicate fails.',
13110:'Wilderness sword 3 is a weapon with diary unlocks, clue/skill utilities, and exact teleport effects. This review does not decide weapon versus utility-teleport primary precedence.',
13111:'Wilderness sword 4 is a weapon with diary unlocks, clue/skill utilities, and exact teleport effects. This review does not decide weapon versus utility-teleport primary precedence.',
13139:'Kandarin headgear 3 has combat defensive stats, light/diary benefits, and a charged teleport to Sherlock. Several concrete roles compete for primary placement.',
13140:'Kandarin headgear 4 has combat defensive stats, light/diary benefits, and a charged teleport to Sherlock. Several concrete roles compete for primary placement.',
13391:'Xeric talisman exact state has finite charges and transport access, but the source also describes additional functions/recharge state. Needs a clearer primary route decision across active and empty states.',
13392:'Xeric talisman exact state has finite charges and transport access, but the source also describes additional functions/recharge state. Needs a clearer primary route decision across active and empty states.',
19564:'Grand seed pod is a direct player escape teleport but also a wieldable combat weapon with strength bonus and a combat use. Primary route precedence unresolved.',
20786:'Imbued Ring of wealth (i5) has active teleports and the imbued item-drop effect plus wearable combat stats. Primary precedence unresolved.',
20787:'Imbued Ring of wealth (i4) has active teleports and the imbued item-drop effect plus wearable combat stats. Primary precedence unresolved.',
20788:'Imbued Ring of wealth (i3) has active teleports and the imbued item-drop effect plus wearable combat stats. Primary precedence unresolved.',
20789:'Imbued Ring of wealth (i2) has active teleports and the imbued item-drop effect plus wearable combat stats. Primary precedence unresolved.',
20790:'Imbued Ring of wealth (i1) has active teleports and the imbued item-drop effect plus wearable combat stats. Primary precedence unresolved.',
21268:'Eternal Slayer ring offers unlimited teleports but is wearable Slayer equipment with additional Slayer-function role. Primary precedence unresolved.',
24719:'Hallowed token is a consumable one-minute extension for a Hallowed Sepulchre attempt and is storable in that activity’s equipment storage. It is activity supply, not spendable general currency; a bank taxonomy route is not settled here.',
26945:'Uncharged Pharaoh’s sceptre has no remaining teleport charge and is also a wieldable polestaff with requirements. Recharging restores travel, so it is a retained recharge state; need rule for weapon-versus-depleted-teleport precedence.',
26948:'Charged Pharaoh’s sceptre has active pyramid teleports and is a wieldable polestaff with Attack/Magic requirements. The source supports both equipment and travel; primary precedence unresolved.',
26950:'Charged Pharaoh’s sceptre has active pyramid teleports and is a wieldable polestaff with Attack/Magic requirements. The source supports both equipment and travel; primary precedence unresolved.',
29895:'Frozen tears are one-charge recharge material for Pendant of Ates; their exact own item also drops from combat and is a retained teleport-charge component. Need decide component versus active-teleport subcategory policy.',
30692:'The Castle Wars pouch is explicitly supplied during a match and disappears/has no outside-game use; it cannot be a persistent bank rune container.'}
# Keep unhandled rows unresolved with individualized mechanics-grounded reasons from their exact own source text.
for r in base['perIdAdjudication']:
 i=r['itemId']
 if i not in decisions and i not in holds: continue
 src=r['source']; idx=json.loads((ROOT/'tmp/category-certification/wiki-articles/article-index.json').read_text(encoding='utf-8')); ent=idx[src['sourceTitle']]; raw=(ROOT/ent['path']).read_text(encoding='utf-8')
 if i in decisions:
  q=decisions[i]; r['decision']={'SUPPORTED':'SUPPORTED_UNCHANGED_CANDIDATE','CORRECTION':'CORRECTION_CANDIDATE'}[q['kind']]
  if q['kind']=='SUPPORTED': r['proposedRoute']=dict(r['currentRoute'])
  else: r['proposedRoute']={k:q['route'][n] for n,k in enumerate(['category','subcategory','ironmanTabKey'])}
  r['rationale']=q['why'];r['perIdMechanicFinding']=q['why']
  if q['anchor']:
   quote=section(raw,q['anchor']);r['selectedMechanicAndCompetingLiterals'].insert(0,quote);r['specificAdjudicationLiteral']=quote
  r['adjudicationScope']='candidate only; source-backed per-ID review; no policy approval/ledger decision'
 elif i in holds:
  r['decision']='UNRESOLVED';r['rationale']=holds[i];r['perIdMechanicFinding']=holds[i];r['unresolvedReason']=holds[i]
  r['adjudicationScope']='explicit source-read hold; exact function/state/competing role stated; no inherited role/tag'
# Recalculate summary markers but keep all fullPartition assignment updates tied to per-row decision.
by={r['itemId']:r for r in base['perIdAdjudication']};
for p in base['fullPartition']:
 if p['itemId'] in by:p['v24Adjudication']=by[p['itemId']]['decision']
counts=collections.Counter(r['decision'] for r in base['perIdAdjudication'])
base['schema']='transport-v24-full-scope-exact-source-adjudication';base['status']='candidate research only; no approval, policy change, ledger decision, production edit, or Git change'
base['inputs']['baseV23']={'path':'tmp/category-certification/reviews/transport-v23/full-per-id-adjudication-v1.json','sha256':sha(BASE)}
base['decisionCountsV24']=dict(counts);base['v24DecisionScope']={'rows':len(by),'newSpecificPerIdAdjudications':len(decisions)+len(holds),'unresolvedWithoutNewV24Note':len([r for r in by.values() if r.get('adjudicationScope')!='explicit source-read hold; exact function/state/competing role stated; no inherited role/tag' and r.get('adjudicationScope')!='candidate only; source-backed per-ID review; no policy approval/ledger decision']),'userPolicyTablets8014to8022':'remain held unchanged'}
out=OUT/'full-per-id-adjudication-v1.json';out.write_text(json.dumps(base,ensure_ascii=False,indent=2)+'\n',encoding='utf-8');print(json.dumps({'output':str(out),'sha256':sha(out),'counts':dict(counts),'decisions':len(decisions),'holds':len(holds),'unresolvedWithoutV24Note':base['v24DecisionScope']['unresolvedWithoutNewV24Note']},indent=2))






