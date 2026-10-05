import argparse,collections,hashlib,json,re
from pathlib import Path
ROOT=Path(__file__).resolve().parents[4];BASE=ROOT/'tmp/category-certification';PREV=BASE/'reviews/transport-v5/decisions.jsonl';PACKET=BASE/'reviewer-packets/currency-runes-teleport.jsonl';INDEX=BASE/'wiki-articles/article-index.json';OUT=BASE/'reviews/transport-v6'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def exact(index,i):
 h=[(t,e) for t,e in index.items() if i in e.get('exactInfoboxItemIds',[]) and str(i) in e.get('variants',{})]
 return h[0] if len(h)==1 else None
def quote(text,marker):
 a=text.find('{{Infobox Item');depth=0
 if a<0:body=0
 else:
  body=0
  for j in range(a,len(text)-1):
   if text[j:j+2]=='{{':depth+=1
   elif text[j:j+2]=='}}':
    depth-=1
    if depth==0:body=j+2;break
 pos=text.find(marker,body)
 if pos<0:raise ValueError(f'missing quote marker {marker}')
 l=max(body,text.rfind('\n\n',body,pos)+2);r=text.find('\n\n',pos);r=len(text) if r<0 else r;para=' '.join(text[l:r].split());m=para.find(marker)
 stops=[x.end() for x in re.finditer(r'[.!?](?:\s|$)',para[:m])];start=stops[-1] if stops else (para.rfind(']]',0,m)+2 if ']]' in para[:m] else 0);z=re.search(r'[.!?](?:\s|$)',para[m:]);end=m+z.end() if z else min(len(para),m+400)
 return para[start:end].strip()
def cite(index,i,marker):
 hit=exact(index,i)
 if not hit:raise ValueError(f'not exact {i}')
 title,e=hit;path=ROOT/e['path']
 if sha(path)!=e['sha256']:raise ValueError(f'hash mismatch {i}')
 params=e['variants'][str(i)].get('params',{});ids={x.strip() for k,v in params.items() if k=='id' or re.fullmatch(r'id[1-9][0-9]*',k) for val in (v if isinstance(v,list) else [v]) for x in str(val or '').split(',')}
 if str(i) not in ids:raise ValueError(f'variant ID missing {i}')
 return {'kind':'exact_wiki','source':e['sourceUrl'],'sourceTitle':title,'sourceRevision':e['revid'],'sourceHash':'sha256:'+e['sha256'],'itemId':i,'quote':quote(path.read_text(encoding='utf8'),marker)}
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--previous',type=Path,default=PREV);ap.add_argument('--packets',type=Path,default=PACKET);ap.add_argument('--index',type=Path,default=INDEX);ap.add_argument('--output',type=Path,default=OUT);a=ap.parse_args();ds=[json.loads(x) for x in a.previous.read_text(encoding='utf8').splitlines() if x.strip()];by={d['itemId']:d for d in ds};idx=json.loads(a.index.read_text(encoding='utf8'))
 cases={i:('cannot be kept after the game ends','Portal talismans are consumed or used only inside Guardians of the Rift and cannot be banked after the minigame. Their current TELEPORT assignment would misleadingly suggest a retained travel device.') for i in range(26887,26899)}
 ba_ids=list(range(11686,11700))+[22208]
 for i in ba_ids:
  name={11686:'Fire',11687:'Water',11688:'Air',11689:'Earth',11690:'Mind',11691:'Body',11692:'Death',11693:'Nature',11694:'Chaos',11695:'Law',11696:'Cosmic',11697:'Blood',11698:'Soul',11699:'Astral',22208:'Wrath'}[i]
  marker=(f'As a result, {name} runes cannot be obtained by players.' if i in {11691,11693,11695,11696,11698,11699} else 'will disappear if the player attempts to take them outside')
  cases[i]=(marker,'This exact Barbarian Assault rune variant is either explicitly unobtainable or is an untradeable, valueless minigame supply that disappears outside the activity. It has no retained bank supply role.')
 for i,(marker,why) in cases.items():
  d=by[i]
  if d['decision']!='certify' if i in range(26887,26899) else d['decision']!='unresolved':
   raise ValueError(f'unexpected previous decision for {i}: {d["decision"]}')
  d.update(decision='revise',proposedCategory='CLEANUP',proposedSubcategory='cleanup',proposedIronmanTabKey='storage-cleanup',proposedRoles=['minigame_internal_item'],proposedTags=[],semanticPredicate=f'Exact ID {i} is an activity-only internal item with no bank-retained transport/supply role.',rationale=why,evidence=[cite(idx,i,marker)],identityLinks=[])
 out=a.output/'decisions.jsonl';a.output.mkdir(parents=True,exist_ok=True);out.write_text(''.join(json.dumps(d,ensure_ascii=False,sort_keys=True)+'\n' for d in ds),encoding='utf8')
 result={'version':'transport-review-v6','previousSha256':'sha256:'+sha(a.previous),'articleIndexSha256':'sha256:'+sha(a.index),'packetSha256':'sha256:'+sha(a.packets),'recordCount':len(ds),'changedCount':len(cases),'changedItemIds':sorted(cases),'activityOnlyPortalTalismanIds':list(range(26887,26899)),'barbarianAssaultRuneIds':ba_ids,'decisions':dict(collections.Counter(d['decision'] for d in ds)),'notes':'Moves ephemeral minigame state out of retained transport/supply categories, based on explicit exact-item retention limits. Earlier versions remain unchanged.'}
 (a.output/'summary.json').write_text(json.dumps(result,ensure_ascii=False,indent=2,sort_keys=True)+'\n',encoding='utf8');print(json.dumps(result,indent=2))
if __name__=='__main__':main()
