import argparse,collections,hashlib,json,re
from pathlib import Path
ROOT=Path(__file__).resolve().parents[4];BASE=ROOT/'tmp/category-certification';PREV=BASE/'reviews/transport-v7/decisions.jsonl';PACKET=BASE/'reviewer-packets/currency-runes-teleport.jsonl';INDEX=BASE/'wiki-articles/article-index.json';OUT=BASE/'reviews/transport-v8'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def exact(index,i):
 h=[(t,e) for t,e in index.items() if i in e.get('exactInfoboxItemIds',[]) and str(i) in e.get('variants',{})]
 return h[0] if len(h)==1 else None
def cite(index,i,marker):
 hit=exact(index,i)
 if not hit:raise ValueError(f'no exact source {i}')
 title,e=hit;path=ROOT/e['path']
 if sha(path)!=e['sha256']:raise ValueError(f'hash mismatch {i}')
 params=e['variants'][str(i)].get('params',{});ids={p.strip() for k,v in params.items() if k=='id' or re.fullmatch(r'id[1-9][0-9]*',k) for val in (v if isinstance(v,list) else [v]) for p in str(val or '').split(',')}
 if str(i) not in ids:raise ValueError(f'exact variant params missing {i}')
 text=path.read_text(encoding='utf8');a=text.find('{{Infobox Item');dep=0;body=0
 if a>=0:
  for j in range(a,len(text)-1):
   if text[j:j+2]=='{{':dep+=1
   elif text[j:j+2]=='}}':
    dep-=1
    if dep==0:body=j+2;break
 pos=text.find(marker,body)
 if pos<0:raise ValueError(f'marker absent {i}: {marker}')
 left=max(body,text.rfind('\n\n',body,pos)+2);right=text.find('\n\n',pos);right=len(text) if right<0 else right;para=' '.join(text[left:right].split());m=para.find(marker)
 stops=[x.end() for x in re.finditer(r'[.!?](?:\s|$)',para[:m])];start=stops[-1] if stops else (para.rfind(']]',0,m)+2 if ']]' in para[:m] else 0);z=re.search(r'[.!?](?:\s|$)',para[m:]);end=m+z.end() if z else min(len(para),m+450)
 return {'kind':'exact_wiki','source':e['sourceUrl'],'sourceTitle':title,'sourceRevision':e['revid'],'sourceHash':'sha256:'+e['sha256'],'itemId':i,'quote':para[start:end].strip()}
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--previous',type=Path,default=PREV);ap.add_argument('--packets',type=Path,default=PACKET);ap.add_argument('--index',type=Path,default=INDEX);ap.add_argument('--output',type=Path,default=OUT);a=ap.parse_args();ds=[json.loads(x) for x in a.previous.read_text(encoding='utf8').splitlines() if x.strip()];by={d['itemId']:d for d in ds};idx=json.loads(a.index.read_text(encoding='utf8'))
 # Mage Training Arena coins are converted by the Coin Collector into ordinary banked coins.
 d=by[8890]
 if d['decision']!='unresolved':raise ValueError('expected unresolved MTA coins')
 d.update(decision='certify',proposedCategory='CURRENCY',proposedSubcategory='currency',proposedIronmanTabKey='currency-utilities',proposedRoles=['spendable_exchange_value'],proposedTags=[],semanticPredicate='Exact ID 8890 is deposited into the Coin Collector and exchanged for regular coins deposited to the bank.',rationale='The exact item article describes a fixed conversion: each 100 MTA coins placed in the Coin Collector yields 10 ordinary coins to the bank. This is documented exchange value, not an inference from the name or alchemy provenance.',evidence=[cite(idx,8890,'For every set of 100 coins deposited into the [[Coin Collector]]')],identityLinks=[])
 # Transportation Incantations is a temporary library delivery, not a teleport device; the article explicitly says bank deposit is disabled.
 d=by[13537]
 if d['decision']!='unresolved':raise ValueError('expected unresolved Transportation Incantations')
 d.update(decision='revise',proposedCategory='CLEANUP',proposedSubcategory='cleanup',proposedIronmanTabKey='storage-cleanup',proposedRoles=['temporary_task_item','nonbankable_item'],proposedTags=[],semanticPredicate='Exact ID 13537 is a temporary library delivery book that no longer unlocks transport spells and cannot be deposited in a bank.',rationale='The exact article says NPCs ask the player to find and deliver this library book, and that it may no longer be deposited to a bank. A later update removed the Kourend teleport spell unlock from its contents. It is neither a transport device nor a retained teleport supply; generic cleanup is the closest supported destination.',evidence=[cite(idx,13537,'Delivering the book yields a [[book of arcane knowledge]]'),cite(idx,13537,'The book may no longer be deposited to a bank')],identityLinks=[])
 out=a.output/'decisions.jsonl';a.output.mkdir(parents=True,exist_ok=True);out.write_text(''.join(json.dumps(x,ensure_ascii=False,sort_keys=True)+'\n' for x in ds),encoding='utf8')
 result={'version':'transport-review-v8','previousSha256':'sha256:'+sha(a.previous),'articleIndexSha256':'sha256:'+sha(a.index),'packetSha256':'sha256:'+sha(a.packets),'recordCount':len(ds),'changedCount':2,'changedItemIds':[8890,13537],'decisions':dict(collections.Counter(x['decision'] for x in ds)),'notes':'Adds one exact exchange-value certification and removes a nonbankable task book from TELEPORT. V1-v7 remain unchanged.'}
 (a.output/'summary.json').write_text(json.dumps(result,ensure_ascii=False,indent=2,sort_keys=True)+'\n',encoding='utf8');print(json.dumps(result,indent=2))
if __name__=='__main__':main()
