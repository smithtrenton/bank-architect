import argparse,hashlib,json,re
from pathlib import Path
ROOT=Path(__file__).resolve().parents[4];BASE=ROOT/'tmp/category-certification'
PREV=BASE/'reviews/transport-v3/decisions.jsonl';PACKET=BASE/'reviewer-packets/currency-runes-teleport.jsonl';INDEX=BASE/'wiki-articles/article-index.json';OUT=BASE/'reviews/transport-v4'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def exact(index,i):
 h=[(t,e) for t,e in index.items() if i in e.get('exactInfoboxItemIds',[]) and str(i) in e.get('variants',{})]
 return h[0] if len(h)==1 else None
def after_infobox(text):
 a=text.find('{{Infobox Item');dep=0
 if a<0:return 0
 for j in range(a,len(text)-1):
  if text[j:j+2]=='{{':dep+=1
  elif text[j:j+2]=='}}':
   dep-=1
   if dep==0:return j+2
 return 0
def sentence(index,i,marker):
 hit=exact(index,i);title,e=hit;path=ROOT/e['path'];txt=path.read_text(encoding='utf-8');body=after_infobox(txt);p=txt.find(marker,body)
 if p<0:raise ValueError(f'marker absent {i}: {marker}')
 l=max(body,txt.rfind('\n\n',body,p)+2);r=txt.find('\n\n',p);r=len(txt) if r<0 else r;para=' '.join(txt[l:r].split());m=para.find(marker)
 prev=[x.end() for x in re.finditer(r'[.!?](?:\s|$)',para[:m])];start=prev[-1] if prev else (para.rfind(']]',0,m)+2 if ']]' in para[:m] else 0)
 z=re.search(r'[.!?](?:\s|$)',para[m:]);end=m+z.end() if z else min(len(para),m+400);q=para[start:end].strip()
 params=e['variants'][str(i)].get('params',{});ids={x.strip() for k,v in params.items() if k=='id' or re.fullmatch(r'id[1-9][0-9]*',k) for val in (v if isinstance(v,list) else [v]) for x in str(val or '').split(',')}
 if str(i) not in ids:raise ValueError(f'variant lacks exact ID {i}')
 if sha(path)!=e['sha256']:raise ValueError(f'hash mismatch {i}')
 return {'kind':'exact_wiki','source':e['sourceUrl'],'sourceTitle':title,'sourceRevision':e['revid'],'sourceHash':'sha256:'+e['sha256'],'itemId':i,'quote':q}
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--previous',type=Path,default=PREV);ap.add_argument('--packets',type=Path,default=PACKET);ap.add_argument('--index',type=Path,default=INDEX);ap.add_argument('--output',type=Path,default=OUT);a=ap.parse_args()
 ds=[json.loads(x) for x in a.previous.read_text(encoding='utf-8').splitlines() if x.strip()];by={x['itemId']:x for x in ds};pack={x['itemId']:x for x in (json.loads(l) for l in a.packets.read_text(encoding='utf-8-sig').splitlines() if l.strip())};index=json.loads(a.index.read_text(encoding='utf-8'))
 cases={
 9691:('Unlike normal water runes, this cannot be used to cast a spell.','used to unlock a mysterious door','The exact Water rune (The Slug Menace) is a quest key for the Witchaven shrine door and is explicitly unusable for spellcasting; it is not the normal water-rune supply.'),
 9695:('Unlike normal earth runes, this cannot be used to cast a spell.','used to unlock a mysterious door','The exact Earth rune (The Slug Menace) is a quest key for the Witchaven shrine door and is explicitly unusable for spellcasting; it is not the normal earth-rune supply.'),
 9697:('Unlike normal mind runes, this cannot be used to cast a spell.','used to unlock a mysterious door','The exact Mind rune (The Slug Menace) is a quest key for the Witchaven shrine door and is explicitly unusable for spellcasting; it is not the normal mind-rune supply.'),
 9699:('Unlike normal fire runes, this cannot be used to cast a spell.','used to unlock a mysterious door','The exact Fire rune (The Slug Menace) is a quest key for the Witchaven shrine door and is explicitly unusable for spellcasting; it is not the normal fire-rune supply.')}
 for i,(negative,positive,why) in cases.items():
  d=by[i]
  if d['decision']!='certify':raise ValueError(f'Expected false certificate on {i}, got {d["decision"]}')
  proof=[sentence(index,i,positive),sentence(index,i,negative)]
  d.update(decision='revise',proposedCategory='CLEANUP',proposedSubcategory='quest-item',proposedIronmanTabKey='storage-cleanup',proposedRoles=['quest_item'],proposedTags=['quest-use'],semanticPredicate=f'Exact ID {i} is a quest-only shrine-door key, not a spellcasting rune.',rationale=why,evidence=proof,identityLinks=[])
 out=a.output/'decisions.jsonl';a.output.mkdir(parents=True,exist_ok=True);out.write_text(''.join(json.dumps(x,ensure_ascii=False,sort_keys=True)+'\n' for x in ds),encoding='utf-8')
 import collections
 result={'version':'transport-review-v4','previousSha256':'sha256:'+sha(a.previous),'articleIndexSha256':'sha256:'+sha(a.index),'packetSha256':'sha256:'+sha(a.packets),'recordCount':len(ds),'changedItemIds':sorted(cases),'changedCount':len(cases),'decisions':dict(collections.Counter(x['decision'] for x in ds)),'notes':'Semantic correction of four false Slug Menace rune certificates; 9693 was already corrected to the same quest-item destination in v3.'}
 (a.output/'summary.json').write_text(json.dumps(result,indent=2,ensure_ascii=False,sort_keys=True)+'\n',encoding='utf-8');print(json.dumps(result,indent=2))
if __name__=='__main__':main()
