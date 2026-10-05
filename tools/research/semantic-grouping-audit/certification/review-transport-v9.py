import argparse,collections,hashlib,json,re
from pathlib import Path
ROOT=Path(__file__).resolve().parents[4];BASE=ROOT/'tmp/category-certification';PREV=BASE/'reviews/transport-v8/decisions.jsonl';PACKET=BASE/'reviewer-packets/currency-runes-teleport.jsonl';INDEX=BASE/'wiki-articles/article-index.json';OUT=BASE/'reviews/transport-v9'
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
 ap=argparse.ArgumentParser();ap.add_argument('--previous',type=Path,default=PREV);ap.add_argument('--packets',type=Path,default=PACKET);ap.add_argument('--index',type=Path,default=INDEX);ap.add_argument('--output',type=Path,default=OUT);a=ap.parse_args();ds=[json.loads(x) for x in a.previous.read_text(encoding='utf8').splitlines() if x.strip()];by={d['itemId']:d for d in ds};idx=json.loads(a.index.read_text(encoding='utf8')); repaired=[]
 # For certified travel items whose old quote was only an examine line/template, cite the exact lead mechanic.
 weak=[]
 for d in ds:
  if d['decision']=='certify' and any(e.get('quote','').lstrip().startswith(('|examine','{{External')) for e in d.get('evidence',[])):
   weak.append(d['itemId'])
 for i in weak:
  hit=exact(idx,i)
  if not hit:continue
  title,e=hit;text=(ROOT/e['path']).read_text(encoding='utf8')
  a0=text.find('{{Infobox Item');dep=0;body=0
  if a0>=0:
   for j in range(a0,len(text)-1):
    if text[j:j+2]=='{{':dep+=1
    elif text[j:j+2]=='}}':
     dep-=1
     if dep==0:body=j+2;break
  raw=text[body:]
  # Remove image markup before finding the first direct subject-function sentence.
  raw=re.sub(r'\[\[File:.*?\]\]',' ',raw,flags=re.I)
  patterns=[r'are consumable \[\[teleport scrolls\]\] that teleport[^.]{0,180}',r'is a \[\[magic tablet\]\] that can be broken[^.]{0,220}',r'is an item that can be used to teleport[^.]{0,180}',r'allows players to teleport[^.]{0,180}',r'can be used to teleport[^.]{0,180}',r'return conveniently to the \[\[Land of Snow\]\]',r'holds four types of \[\[runes\]\] instead of three']
  marker=None
  for pat in patterns:
   m=re.search(pat,raw,re.I)
   if m:marker=m.group(0);break
  if marker:
   by[i]['evidence']=[cite(idx,i,marker)];repaired.append(i)
 # This sack supplies two spells, one transport and one combat-control. Its primary grouping is unresolved.
 i=24615;d=by[i]
 d.update(decision='unresolved',proposedRoles=None,roleClaimScope='unassessed',evidence=[cite(idx,i,'allows players to cast [[Tele Block]] and [[Teleport to Target]] without needing the [[runes]] for it')],identityLinks=[],rationale='The exact item is consumed to supply two spells, one of which teleports to a target and one of which blocks teleports. The source proves both effects but does not establish which primary grouping should control this dual-role sack.',semanticPredicate='Exact ID 24615 has a dual spell-supply function; the primary transport versus general spell-supply placement is unresolved.')
 # Blueprints construct a portal; the blueprint itself is a Construction input, not the player transport device.
 i=33122;d=by[i]
 d.update(decision='revise',proposedCategory='SKILLING',proposedSubcategory='construction-material',proposedIronmanTabKey='resources',proposedRoles=['construction_material'],proposedTags=[],semanticPredicate='Exact ID 33122 is consumed as a player-owned-house Construction input to build a separate exit portal.',rationale='The article says the blueprints are used to construct an Annihilation exit portal and are not returned when the portal is removed. The separate portal performs transport; this exact item is its construction material.',evidence=[cite(idx,i,'They are used to construct an [[Exit portal#Wilderness|Annihilation exit portal]]')],identityLinks=[])
 out=a.output/'decisions.jsonl';a.output.mkdir(parents=True,exist_ok=True);out.write_text(''.join(json.dumps(x,ensure_ascii=False,sort_keys=True)+'\n' for x in ds),encoding='utf8')
 result={'version':'transport-review-v9','previousSha256':'sha256:'+sha(a.previous),'articleIndexSha256':'sha256:'+sha(a.index),'packetSha256':'sha256:'+sha(a.packets),'recordCount':len(ds),'changedCount':len(repaired)+2,'directLeadEvidenceRepaired':len(repaired),'repairedItemIds':repaired,'unresolvedDualRoleSpellSupply':[24615],'revisedPortalConstructionInput':[33122],'decisions':dict(collections.Counter(x['decision'] for x in ds)),'notes':'Replaces examine-only citations with exact lead mechanics, leaves dual-role spell sack unresolved, and separates portal construction blueprints from the portal transport function. Earlier versions remain unchanged.'}
 (a.output/'summary.json').write_text(json.dumps(result,ensure_ascii=False,indent=2,sort_keys=True)+'\n',encoding='utf8');print(json.dumps(result,indent=2))
if __name__=='__main__':main()
