import argparse,csv,hashlib,json,re
from collections import Counter
from pathlib import Path
ROOT=Path(__file__).resolve().parents[4]
BASE=ROOT/'tmp/category-certification'
DEFAULT_PACKET=BASE/'reviewer-packets/currency-runes-teleport.jsonl'
DEFAULT_INDEX=BASE/'wiki-articles/article-index.json'
DEFAULT_OLD=BASE/'reviews/transport/decisions.jsonl'
DEFAULT_OUT=BASE/'reviews/transport-v2'
IDENTITY=BASE/'identity-links.jsonl'
IDENTITY_POLICY=ROOT/'tools/research/semantic-grouping-audit/certification/identity-policy.json'

def sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()
def exact(index,i):
 hits=[(title,e) for title,e in index.items() if i in e.get('exactInfoboxItemIds',[]) and str(i) in e.get('variants',{})]
 return hits[0] if len(hits)==1 else None
# Exact-ID review decisions. Evidence is extracted from the pinned page only after verifying its variant ID and hash.
RULES={
6770:('certify','TELEPORT','teleport','currency-utilities',['checkpoint_teleport'],[],'Following the exact directions teleports the player to the current Ratcatchers checkpoint; the item itself performs movement even though it is quest-associated.','Choosing to follow them results'),
9469:('certify','TELEPORT','teleport','currency-utilities',['teleport_consumable'],[],'The exact Grand Tree seed pod is a single-use teleport item, so it remains active movement gear.','single-use teleport item'),
10972:('certify','TELEPORT','teleport','currency-utilities',['teleport_consumable'],[],'The exact Dorgesh-kaan sphere teleports the player to a random location in Dorgesh-Kaan and is consumed on use.',']]s the player to a random location'),
11060:('certify','TELEPORT','teleport','currency-utilities',['teleport_consumable'],[],'The exact goblin village sphere teleports the player to a random location in Goblin Village and is consumed on use.',']]s the player to a random location'),
8022:('revise','CLEANUP','cleanup','storage-cleanup',['unobtainable_internal_item'],[],'The exact Telekinetic Grab tablet is described as unobtainable and only assumed to be an intended spell tablet; it has no usable transport function.','is an [[unobtainable item]]'),
11177:('revise','CLEANUP','cleanup','storage-cleanup',['museum_minigame_artifact'],[],'The exact dusty jewellery item cannot be worn and has no use outside the Varrock Museum minigame.','Players cannot wear this jewellery'),
13108:('revise','GEAR','weapon','combat-gear',['combat_equipment'],[],'The exact Wilderness sword is equipable weapon gear; its article documents diary reward/reclaim and combat-stat placement, not a teleport.','The \'\'\'Wilderness sword 1\'\'\' is a reward from completing'),
13109:('revise','GEAR','weapon','combat-gear',['combat_equipment'],[],'The exact Wilderness sword is equipable weapon gear; its article documents diary reward/reclaim and combat-stat placement, not a teleport.','The \'\'\'Wilderness sword 2\'\'\' is an [[Achievement Diary]] reward'),
13392:('revise','TELEPORT','teleport','currency-utilities',['rechargeable_teleport_device'],[],'The exact inert Xeric talisman variant is explicitly chargeable with lizardman fangs; the same item functions as a teleport talisman once charged.','Lizardman fang]]s can be added to give one charge per fang'),
13658:('revise','TELEPORT','teleport-charge','currency-utilities',['teleport_charge'],[],'The exact card is used to charge Chronicle, the book that teleports the player; its primary role is a teleport charge rather than a direct device.','is used to charge the [[Chronicle]]'),
21387:('certify','TELEPORT','teleport-container','currency-utilities',['teleport_scroll_container'],[],'Exact variant parameters identify this as the empty master scroll book, and the article says the book stores teleport scrolls for later dispatch.','The master scroll book can store up to 1000'),
21389:('certify','TELEPORT','teleport-container','currency-utilities',['teleport_scroll_container'],[],'Exact variant parameters identify this as the filled master scroll book, whose stored teleport scrolls are dispatched by the book.','The master scroll book can store up to 1000'),
21541:('certify','TELEPORT','teleport-tablet','currency-utilities',['teleport_consumable'],[],'The exact Volcanic Mine tablet can be broken to teleport the player to the mine entrance.','is a [[magic tablet]] that can be broken'),
21816:('revise','GEAR','hands','combat-gear',['combat_equipment'],[],'The exact charged bracelet is worn on the hands and reduces damage from revenants; that is combat protection, not transport.','damage from revenants is reduced by 75%'),
21817:('revise','GEAR','hands','combat-gear',['combat_equipment'],[],'The exact uncharged bracelet is wearable combat gear that can be charged with revenant ether; its empty state is not a teleport function.','damage from revenants is reduced by 75%'),
23904:('certify','TELEPORT','teleport','currency-utilities',['return_teleport'],[],'The exact Gauntlet crystal is a single-use teleport that returns players to the activity starting room; its explicit return behavior is functional travel.','single-use item received when starting the [[Gauntlet]]'),
23959:('revise','SKILLING','crafting-material','resources',['teleport_device_crafting_input'],[],'The exact enhanced seed is a crafting input used with crystal shards at a singing bowl to create an eternal teleport crystal; it does not itself teleport.','The \'\'\'enhanced crystal teleport seed\'\'\' is a [[Crystal seed (disambiguation)|crystal seed]]'),
26948:('certify','TELEPORT','teleport','currency-utilities',['rechargeable_teleport_device'],[],'The exact charged Pharaoh\'s sceptre variant provides charged teleports to the Kharidian pyramids.','The sceptre provides teleports to each'),
26950:('certify','TELEPORT','teleport','currency-utilities',['rechargeable_teleport_device'],[],'The exact charged Pharaoh\'s sceptre variant provides charged teleports to the Kharidian pyramids.','The sceptre provides teleports to each'),
28369:('revise','TOOL','quest-utility','skilling-tools',['quest_utility'],['quest-use'],'The exact Anima portal is placed as a defensive quest tool that draws Shadow Realm Lost Souls away from the player and can be recalled; it does not transport players.','When placed in the Undercity') ,
29271:('certify','TELEPORT','teleport','currency-utilities',['transport_network_device'],[],'The exact basic quetzal whistle teleports to built landing sites and opens the transport interface.','is a teleportation item that takes players to any built'),
29273:('certify','TELEPORT','teleport','currency-utilities',['transport_network_device'],[],'The exact enhanced quetzal whistle teleports to built landing sites and opens the transport interface.','is a teleportation item that takes players to any built'),
29275:('certify','TELEPORT','teleport','currency-utilities',['transport_network_device'],[],'The exact perfected quetzal whistle teleports to built landing sites and opens the transport interface.','is a teleportation item that takes players to any built'),
30966:('revise','TELEPORT','transport-access','currency-utilities',['installable_transport_network'],[],'The exact ancient teleporter item installs a paired local transport link that moves players between placed endpoints; its banked role is access to that installed network.','Once a pair has been placed'),
}
# Courier cargo IDs share a page but each ID is an independently indexed destination variant.
COURIER_IDS=[32441,32455,32472,32492,32642,32660,32682,32784,32944,32969,32970]

def infobox_body_start(text):
 start=text.find('{{Infobox Item')
 if start<0:return 0
 depth=0;i=start
 while i<len(text)-1:
  token=text[i:i+2]
  if token=='{{':depth+=1;i+=2;continue
  if token=='}}':
   depth-=1;i+=2
   if depth==0:return i
   continue
  i+=1
 return 0

def para_quote(text,marker):
 body=infobox_body_start(text)
 pos=text.find(marker,body)
 if pos<0:return ''
 left=max(body,text.rfind('\n\n',body,pos)+2)
 right=text.find('\n\n',pos)
 if right<0:right=len(text)
 paragraph=' '.join(text[left:right].split())
 mpos=paragraph.find(marker)
 # Cite only the sentence carrying the direct mechanic, excluding acquisition lore and section boilerplate.
 boundaries=[m.end() for m in re.finditer(r'[.!?](?:\s|(?=\{\{)|$)',paragraph[:mpos])]
 if boundaries:
  start=boundaries[-1]
 else:
  prefix=paragraph[:mpos]
  # The first body sentence often follows an image/template with no punctuation.
  start=prefix.rfind(']]')+2 if ']]' in prefix else 0
  if paragraph[start:mpos].strip() in {'}}','}} '}:
   start=mpos
 stop_match=re.search(r'[.!?]',paragraph[mpos:])
 stop=mpos+stop_match.end() if stop_match else len(paragraph)
 return paragraph[start:stop].strip()

def evidence(i,title,e,text,marker,structured=None):
 quote=para_quote(text,marker)
 if not quote: raise ValueError(f'No direct mechanics excerpt for {i}: {marker}')
 return {'kind':'exact_wiki','source':e['sourceUrl'],'sourceTitle':title,'sourceRevision':e['revid'],'sourceHash':'sha256:'+e['sha256'],'itemId':i,'quote':quote,**({'structuredFacts':structured} if structured else {})}

def identity_chain(index,i):
 edges=[json.loads(line) for line in IDENTITY.read_text(encoding='utf-8').splitlines() if line.strip()]
 hit=[edge for edge in edges if int(edge['fromItemId'])==i and edge['relation'] in {'NOTE_VARIANT_OF','PLACEHOLDER_FOR'}]
 if len(hit)!=1: raise ValueError(f'Expected one exact note/placeholder identity edge for {i}, found {len(hit)}')
 edge=hit[0]; to=int(edge['toItemId']); exact_hit=exact(index,to)
 if not exact_hit: raise ValueError(f'Canonical endpoint {to} has no exact indexed Wiki variant')
 title,e=exact_hit; path=ROOT/e['path']
 if sha(path)!=e['sha256']: raise ValueError(f'Canonical article hash mismatch for {to}')
 text=path.read_text(encoding='utf-8')
 canonical=evidence(to,title,e,text,'change the model of the player to look like a pile of')
 typed=next((x.copy() for x in edge.get('evidence',[]) if x.get('kind')=='typed_identity'),None)
 if not typed: raise ValueError(f'No typed cache evidence in edge for {i}')
 typed['identityIndexHash']=sha(IDENTITY)
 return {'itemId':to,'fromItemId':i,'toItemId':to,'relation':edge['relation'],'evidence':[typed,canonical]},canonical

def set_decision(d,action,cat,sub,tab,roles,tags,predicate,rationale,evidence_rows=None,links=None):
 d.update(decision=action,proposedCategory=cat,proposedSubcategory=sub,proposedIronmanTabKey=tab,proposedRoles=roles,proposedTags=tags,semanticPredicate=predicate,rationale=rationale,evidence=evidence_rows or [],identityLinks=links or [])

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--packets',type=Path,default=DEFAULT_PACKET);ap.add_argument('--index',type=Path,default=DEFAULT_INDEX);ap.add_argument('--previous',type=Path,default=DEFAULT_OLD);ap.add_argument('--output',type=Path,default=DEFAULT_OUT);a=ap.parse_args()
 packets={p['itemId']:p for p in (json.loads(x) for x in a.packets.read_text(encoding='utf-8-sig').splitlines() if x.strip())}
 index=json.loads(a.index.read_text(encoding='utf-8')); decisions=[json.loads(x) for x in a.previous.read_text(encoding='utf-8').splitlines() if x.strip()]; byid={d['itemId']:d for d in decisions}
 if len(byid)!=1138: raise ValueError(f'Expected 1138 prior decisions, got {len(byid)}')
 changed=[]
 cases=dict(RULES)
 cases.update({i:('revise','SKILLING','task-item','resources',['courier_task_cargo'],['activity-sailing'],'The exact destination variant is courier task cargo that must be delivered to its named port by boat; it is cargo, not a teleport item.','A \'\'\'crate of jewellery\'\'\' is an item that may be obtained from a [[ledger table]]') for i in COURIER_IDS})
 for i,(action,cat,sub,tab,roles,tags,why,marker) in cases.items():
  d=byid[i]
  if d['decision']!='unresolved': raise ValueError(f'Replacement unexpectedly touches already reviewed item {i}: {d["decision"]}')
  hit=exact(index,i)
  if not hit: raise ValueError(f'No exact indexed article for {i}')
  title,e=hit;path=ROOT/e['path']
  if sha(path)!=e['sha256']: raise ValueError(f'Article hash mismatch {i}')
  params=e['variants'][str(i)].get('params',{})
  param_ids={part.strip() for k,v in params.items() if re.fullmatch(r'id[1-9][0-9]*',k) or k=='id' for part in (v if isinstance(v,list) else [v]) for part in str(part or '').split(',')}
  if str(i) not in param_ids: raise ValueError(f'Exact variant params do not identify {i}')
  text=path.read_text(encoding='utf-8'); facts=None
  if i in {21816,21817}: facts=[{'field':'id2' if i==21816 else 'id1','value':str(i)},{'field':'name2' if i==21816 else 'name1','value':params.get('name2' if i==21816 else 'name1')},{'field':'equipable','value':params.get('equipable')}]
  if i in {13108,13109}: facts=[{'field':'id','value':str(i)},{'field':'name','value':params.get('name')},{'field':'equipable','value':params.get('equipable')}]
  if i in {21387,21389}: facts=[{'field':'id1' if i==21387 else 'id2','value':str(i)},{'field':'name1' if i==21387 else 'name2','value':params.get('name1' if i==21387 else 'name2')},{'field':'options1' if i==21387 else 'options2','value':params.get('options1' if i==21387 else 'options2')},{'field':'examine1' if i==21387 else 'examine2','value':params.get('examine1' if i==21387 else 'examine2')}]
  ev=evidence(i,title,e,text,marker,facts)
  if action=='certify': tags=packets[i]['current'].get('tags',[])
  pred=f'Exact item mechanics support {cat}/{sub} for numeric ID {i}.'
  set_decision(d,action,cat,sub,tab,roles,tags,pred,why,[ev])
  changed.append(i)
 # Exact mechanics can still leave the primary category unresolved when they show competing roles or a missing taxonomy target.
 ambiguous={
 4601:('recharge the [[Camulet]]','The exact article confirms Ugthanki dung can provide four Camulet charges but also identifies it as quest-associated dung with several quest uses. That secondary recharge function alone does not establish TELEPORT as its primary category.'),
 13537:('Delivering the book yields a [[book of arcane knowledge]]','The exact book article says delivery yields a book of arcane knowledge and its current contents no longer unlock Kourend teleport spells. The item does not itself move the player, but the available taxonomy does not settle whether this delivery book is a task item, cleanup item, or another tool.')
 }
 for i,(marker,why) in ambiguous.items():
  d=byid[i]
  if d['decision']!='unresolved':raise ValueError(f'Ambiguous case {i} is no longer unresolved')
  title,e=exact(index,i);path=ROOT/e['path']
  if sha(path)!=e['sha256']:raise ValueError(f'Article hash mismatch {i}')
  text=path.read_text(encoding='utf-8');ev=evidence(i,title,e,text,marker)
  d['semanticPredicate']=f'Exact mechanics for item {i} do not yet establish the primary placement.'
  d['rationale']=why;d['proposedRoles']=None;d['evidence']=[ev];d['identityLinks']=[];changed.append(i)
 # Exact note and placeholder aliases of cosmetic Ring of coins: preserve raw assignment uncertainty while documenting the actual bank representation.
 idx_hash=sha(IDENTITY);policy=json.loads(IDENTITY_POLICY.read_text(encoding='utf-8'))
 bank=policy['inputs']['wikiBankMechanics']['Bank'];bank_path=ROOT/bank['bodyPath'];bank_body=bank_path.read_text(encoding='utf-8')
 bank_quote=bank['evidence'][0]['quote']
 if sha(bank_path)!=bank['bodySha256'] or ' '.join(bank_quote.split()) not in ' '.join(bank_body.split()): raise ValueError('Pinned Bank mechanic evidence failed hash or quote verification')
 bank_evidence={'sourceTitle':'Bank','source':bank['sourceUrl'],'sourceRevision':bank['revision'],'sourceHash':'sha256:'+bank['bodySha256'],'path':bank['bodyPath'],'quote':bank_quote}
 for i,relation in [(20018,'NOTE_VARIANT_OF'),(20019,'PLACEHOLDER_FOR')]:
  d=byid[i]
  if d['decision']!='unresolved': raise ValueError(f'Alias row {i} is no longer unresolved')
  link,canonical=identity_chain(index,i)
  if link['relation']!=relation: raise ValueError(f'{i} exact cache relation differs: {link["relation"]}')
  d['semanticPredicate']='The exact typed edge identifies the alias state and exact canonical item 20017; its Wiki mechanic is cosmetic disguise, but raw alias taxonomy is distinct from the runtime bank representation.'
  d['rationale']=('Exact cache edge: '+relation+' from '+str(i)+' to canonical item 20017. The canonical Ring of coins article documents a model-change disguise, supporting CLUE/cosmetic for the underlying bank item. '+('The pinned Bank mechanic converts a deposited note to the unnoted item, so this note form is withdrawal-only. ' if relation=='NOTE_VARIANT_OF' else 'BankSnapshotReader canonicalizes a valid placeholder to placeholderID 20017 and retains placeholder state separately. ')+'This proves how the bank row resolves; it does not justify editing the raw category assignment for alias ID '+str(i)+'.')
  d['evidence']=[];d['identityLinks']=[link];d['proposedRoles']=None
  d['identityStateContext']={'policyPath':str(IDENTITY_POLICY.relative_to(ROOT)),'policySha256':'sha256:'+sha(IDENTITY_POLICY),'canonicalItemId':20017,'canonicalWikiEvidence':canonical,'identityIndexSha256':'sha256:'+idx_hash,'bankMechanicEvidence':bank_evidence,'rawAssignmentTreatment':'unchanged; unresolved for the alias ID because runtime canonicalization/state is not a raw catalog category'}
  changed.append(i)
 # Keep prior file intact; write a complete versioned replacement with changed IDs listed and all other decisions byte-equivalent JSON objects.
 a.output.mkdir(parents=True,exist_ok=True);out=a.output/'decisions.jsonl'
 out.write_text(''.join(json.dumps(d,ensure_ascii=False,sort_keys=True)+'\n' for d in decisions),encoding='utf-8')
 counts=Counter(d['decision'] for d in decisions)
 summary={'version':'transport-review-v2','inputPreviousSha256':'sha256:'+sha(a.previous),'packetSha256':'sha256:'+sha(a.packets),'articleIndexSha256':'sha256:'+sha(a.index),'identityIndexSha256':'sha256:'+idx_hash,'identityPolicySha256':'sha256:'+sha(IDENTITY_POLICY),'recordCount':len(decisions),'decisions':dict(counts),'changedItemIds':sorted(changed),'changedCount':len(changed),'decisionNotes':'Earlier review remains available at its original path. V2 changes only exact-ID rows that were unresolved in the prior shard; note/placeholder rows 20018/20019 stay unresolved for raw assignment while recording exact runtime identity state.'}
 (a.output/'summary.json').write_text(json.dumps(summary,indent=2,ensure_ascii=False,sort_keys=True)+'\n',encoding='utf-8')
 print('Wrote',len(decisions),'rows; changed',len(changed),'IDs; counts',dict(counts))
if __name__=='__main__':main()
