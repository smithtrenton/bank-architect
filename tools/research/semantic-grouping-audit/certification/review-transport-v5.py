import argparse,collections,hashlib,json,re
from pathlib import Path
ROOT=Path(__file__).resolve().parents[4];BASE=ROOT/'tmp/category-certification'
PREV=BASE/'reviews/transport-v4/decisions.jsonl';PACKET=BASE/'reviewer-packets/currency-runes-teleport.jsonl';INDEX=BASE/'wiki-articles/article-index.json';OUT=BASE/'reviews/transport-v5'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def exact(index,i):
 hits=[(t,e) for t,e in index.items() if i in e.get('exactInfoboxItemIds',[]) and str(i) in e.get('variants',{})]
 return hits[0] if len(hits)==1 else None
def body_start(text):
 a=text.find('{{Infobox Item');dep=0
 if a<0:return 0
 for j in range(a,len(text)-1):
  if text[j:j+2]=='{{':dep+=1
  elif text[j:j+2]=='}}':
   dep-=1
   if dep==0:return j+2
 return 0
def cite(index,i,marker):
 hit=exact(index,i)
 if not hit:raise ValueError(f'no exact variant {i}')
 title,e=hit;path=ROOT/e['path']
 if sha(path)!=e['sha256']:raise ValueError(f'raw SHA mismatch {i}')
 pars=e['variants'][str(i)].get('params',{});ids={part.strip() for k,v in pars.items() if k=='id' or re.fullmatch(r'id[1-9][0-9]*',k) for val in (v if isinstance(v,list) else [v]) for part in str(val or '').split(',')}
 if str(i) not in ids:raise ValueError(f'variant parameters do not identify {i}')
 text=path.read_text(encoding='utf8');b=body_start(text);pos=text.find(marker,b)
 if pos<0:raise ValueError(f'marker absent {i}: {marker}')
 left=max(b,text.rfind('\n\n',b,pos)+2);right=text.find('\n\n',pos);right=len(text) if right<0 else right;para=' '.join(text[left:right].split());m=para.find(marker)
 stops=[x.end() for x in re.finditer(r'[.!?](?:\s|$)',para[:m])];start=stops[-1] if stops else (para.rfind(']]',0,m)+2 if ']]' in para[:m] else 0)
 tail=re.search(r'[.!?](?:\s|$)',para[m:]);end=m+tail.end() if tail else min(len(para),m+400)
 return {'kind':'exact_wiki','source':e['sourceUrl'],'sourceTitle':title,'sourceRevision':e['revid'],'sourceHash':'sha256:'+e['sha256'],'itemId':i,'quote':para[start:end].strip()}
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--previous',type=Path,default=PREV);ap.add_argument('--packets',type=Path,default=PACKET);ap.add_argument('--index',type=Path,default=INDEX);ap.add_argument('--output',type=Path,default=OUT);a=ap.parse_args()
 ds=[json.loads(x) for x in a.previous.read_text(encoding='utf8').splitlines() if x.strip()];by={d['itemId']:d for d in ds};index=json.loads(a.index.read_text(encoding='utf8'))
 changes={
 1460:('revise','CLEANUP','cleanup','storage-cleanup',['unobtainable_internal_item'],[],'was an [[unobtainable item]]','The exact Soul talisman was never obtainable and the Soul Altar does not require one; it cannot serve as a retained altar focus.'),
 5525:('revise','SKILLING','crafting-material','resources',['crafting_material'],[],'They are a purely cosmetic head slot item','The plain tiara is a cosmetic Crafting product that is consumed/used to create distinct attuned talisman tiaras; it does not itself grant altar access.'),
 4035:('revise','CLEANUP','quest-item','storage-cleanup',['quest_item'],['quest-use'],'It will no longer teleport you to the boss fight arena','The sigil teleports only during Monkey Madness I and the article says it stops after the boss is defeated and may be discarded; its retained role is quest/cosmetic residue.'),
 24460:('revise','CLUE','cosmetic','clues-cosmetics',['cosmetic_collectible'],[],'unlock a [[Xeric]]ian themed [[Home Teleport]] [[Animation overrides|animation override]]','Reading this scroll unlocks a Home Teleport animation; the item itself does not move the player.'),
 27416:('revise','CLUE','cosmetic','clues-cosmetics',['cosmetic_collectible'],[],'unlock a speedrunning-themed [[Home Teleport]] [[Animation overrides|animation override]]','Reading this scroll unlocks an animation override; it is not a teleport scroll, although the selected animation changes casting time.'),
 29622:('revise','CLUE','cosmetic','clues-cosmetics',['cosmetic_collectible'],[],'unlock a Deadman: Armageddon-themed [[Home Teleport]] [[animation override]]','This scroll unlocks an animation override for the separate Home Teleport spell; it does not itself teleport.'),
 33018:('revise','CLUE','cosmetic','clues-cosmetics',['cosmetic_collectible'],[],'unlock a [[Lever (Deserted Keep)|Wilderness lever]] themed [[Home Teleport]] [[animation override]]','This scroll unlocks an animation override for the separate Home Teleport spell; it does not itself teleport.'),
 12846:('revise','TELEPORT','transport-access','currency-utilities',['teleport_spell_unlock'],[],'is an item that can be read to unlock the [[Teleport to Target]] spell','The exact scroll grants access to a separate teleport spell after reading; it is an ability unlock, not an item that itself transports the player.'),
 28330:('revise','TELEPORT','transport-access','currency-utilities',['teleport_destination_unlock'],[],'is used on the [[ring of shadows]] to unlock a teleport to','This tablet unlocks a destination option on a separate teleport ring; it is transport access, not a direct teleport item.'),
 28331:('revise','TELEPORT','transport-access','currency-utilities',['teleport_destination_unlock'],[],'is used on the [[ring of shadows]] to unlock a teleport to','This tablet unlocks a destination option on a separate teleport ring; it is transport access, not a direct teleport item.'),
 28332:('revise','TELEPORT','transport-access','currency-utilities',['teleport_destination_unlock'],[],'is used on the [[ring of shadows]] to unlock a teleport to','This tablet unlocks a destination option on a separate teleport ring; it is transport access, not a direct teleport item.'),
 28333:('revise','TELEPORT','transport-access','currency-utilities',['teleport_destination_unlock'],[],'is used on the [[ring of shadows]] to unlock a teleport to','This tablet unlocks a destination option on a separate teleport ring; it is transport access, not a direct teleport item.'),
 24587:('revise','CURRENCY','currency','currency-utilities',['spendable_exchange_value'],[],'It can be used on a [[banker]]','The exact rune pouch note is a tradeable redemption voucher exchanged for a separate rune pouch; it is not itself a rune-storage container.'),
 }
 for i,(action,cat,sub,tab,roles,tags,marker,why) in changes.items():
  d=by[i]
  if d['decision']!='certify':raise ValueError(f'expected certificate {i}, got {d["decision"]}')
  d.update(decision=action,proposedCategory=cat,proposedSubcategory=sub,proposedIronmanTabKey=tab,proposedRoles=roles,proposedTags=tags,semanticPredicate=f'Exact ID {i} supports {cat}/{sub}, not its prior transport/rune classification.',rationale=why,evidence=[cite(index,i,marker)],identityLinks=[])
 # Replace weak citations on otherwise valid certificates with direct item mechanics, exact IDs/revisions/hashes.
 quote_updates={
 12791:'is an item that can store 16,000 of three types of runes',24416:'is an item that can store 16,000 of three types of runes',
 23904:'It teleports players back to the starting room',6103:'is a [[teleport crystal]] that has run out of charges',19707:'possessing identical stats and features of a regular [[amulet of glory]]',22517:'are a consumable teleport item that can be equipped',
 4067:'Tickets can be spent on items in the [[Castle Wars Ticket Exchange]] shop',10934:'The token given can be exchanged for the reward',10935:'The token given can be exchanged for the reward',10936:'The token given can be exchanged for the reward',10942:'The token given can be exchanged for the reward',10943:'The token given can be exchanged for the reward',10944:'The token given can be exchanged for the reward',12012:'They can be traded in for various rewards from',
 }
 for i,marker in quote_updates.items():
  d=by[i]
  if d['decision']!='certify':raise ValueError(f'expected preserved cert {i}, got {d["decision"]}')
  d['evidence']=[cite(index,i,marker)]
 # Keep all source evidence as exact item/variant. No prior file is overwritten.
 out=a.output/'decisions.jsonl';a.output.mkdir(parents=True,exist_ok=True);out.write_text(''.join(json.dumps(d,ensure_ascii=False,sort_keys=True)+'\n' for d in ds),encoding='utf8')
 summary={'version':'transport-review-v5','previousSha256':'sha256:'+sha(a.previous),'articleIndexSha256':'sha256:'+sha(a.index),'packetSha256':'sha256:'+sha(a.packets),'recordCount':len(ds),'changedItemIds':sorted(set(changes)|set(quote_updates)),'changedCount':len(set(changes)|set(quote_updates)),'decisionChanges':sorted(changes),'citationRepairs':sorted(quote_updates),'decisions':dict(collections.Counter(d['decision'] for d in ds)),'notes':'Corrects direct semantic counterexamples and replaces weak nonmechanics excerpts; v1-v4 remain unchanged.'}
 (a.output/'summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2,sort_keys=True)+'\n',encoding='utf8');print(json.dumps(summary,indent=2))
if __name__=='__main__':main()
