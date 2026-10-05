import argparse,collections,hashlib,json,re
from pathlib import Path
ROOT=Path(__file__).resolve().parents[4];BASE=ROOT/'tmp/category-certification';PREV=BASE/'reviews/transport-v13/decisions.jsonl';PACKET=BASE/'reviewer-packets/currency-runes-teleport.jsonl';INDEX=BASE/'wiki-articles/article-index.json';OUT=BASE/'reviews/transport-v14'
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
 normal=[1704,1706,1708,1710,1712,11976,11978];trimmed=[10354,10356,10358,10360,10362,11964,11966];eternal=[19707]
 for i in normal+trimmed+eternal:
  d=by[i]
  if d['decision']!='certify' or d['proposedCategory']!='TELEPORT':raise ValueError(f'expected TELEPORT cert {i}')
  if i in normal: e=cite(idx,i,'provides good damage bonuses')
  elif i in trimmed: e=cite(idx,i,'it has the same functions and stat bonuses as a regular amulet of glory')
  else:e=cite(idx,i,'possessing identical stats and features of a regular [[amulet of glory]]')
  d.update(decision='revise',proposedCategory='GEAR',proposedSubcategory='neck',proposedIronmanTabKey='combat-gear',proposedRoles=['combat_equipment','teleport_device'],proposedTags=[],semanticPredicate=f'Exact ID {i} is wearable neck gear with explicit combat stats and a useful teleport function.',rationale='The exact source documents both equipment stats and teleports. Under the local placement precedence for wearable combat gear, the active combat-equipment role controls primary category; teleport remains a documented secondary role.',evidence=[e],identityLinks=[])
 out=a.output/'decisions.jsonl';a.output.mkdir(parents=True,exist_ok=True);out.write_text(''.join(json.dumps(x,ensure_ascii=False,sort_keys=True)+'\n' for x in ds),encoding='utf8')
 result={'version':'transport-review-v14','previousSha256':'sha256:'+sha(a.previous),'articleIndexSha256':'sha256:'+sha(a.index),'packetSha256':'sha256:'+sha(a.packets),'recordCount':len(ds),'changedItemIds':sorted(normal+trimmed+eternal),'normalAmuletIds':normal,'trimmedAmuletIds':trimmed,'eternalAmuletIds':eternal,'decisions':dict(collections.Counter(x['decision'] for x in ds)),'notes':'Moves exact Glory amulet variants with documented combat stats and teleport function to GEAR/neck under local combat-gear precedence.'}
 (a.output/'summary.json').write_text(json.dumps(result,ensure_ascii=False,indent=2,sort_keys=True)+'\n',encoding='utf8');print(json.dumps(result,indent=2))
if __name__=='__main__':main()
