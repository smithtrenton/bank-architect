import argparse,collections,hashlib,json,re
from pathlib import Path
ROOT=Path(__file__).resolve().parents[4];BASE=ROOT/'tmp/category-certification';PREV=BASE/'reviews/transport-v6/decisions.jsonl';PACKET=BASE/'reviewer-packets/currency-runes-teleport.jsonl';INDEX=BASE/'wiki-articles/article-index.json';OUT=BASE/'reviews/transport-v7'
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
 stops=[x.end() for x in re.finditer(r'[.!?](?:\s|$)',para[:m])];start=stops[-1] if stops else (para.rfind(']]',0,m)+2 if ']]' in para[:m] else 0);z=re.search(r'[.!?](?:\s|$)',para[m:]);end=m+z.end() if z else min(len(para),m+400)
 return {'kind':'exact_wiki','source':e['sourceUrl'],'sourceTitle':title,'sourceRevision':e['revid'],'sourceHash':'sha256:'+e['sha256'],'itemId':i,'quote':para[start:end].strip()}
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--previous',type=Path,default=PREV);ap.add_argument('--packets',type=Path,default=PACKET);ap.add_argument('--index',type=Path,default=INDEX);ap.add_argument('--output',type=Path,default=OUT);a=ap.parse_args();ds=[json.loads(x) for x in a.previous.read_text(encoding='utf8').splitlines() if x.strip()];by={d['itemId']:d for d in ds};idx=json.loads(a.index.read_text(encoding='utf8'))
 # Exact spell-icon inventory IDs are unobtainable interface artifacts, not usable transport devices.
 spell_ids=[3286,3289,3292,3296,3301,3306,3312,4555,4631,4634,4637,4640,4643,4646,4649,4652,7619,8828,9712]
 for i in spell_ids:
  d=by[i]
  if d['decision']!='certify':raise ValueError(f'expected false spell-icon cert {i}, got {d["decision"]}')
  d.update(decision='revise',proposedCategory='CLEANUP',proposedSubcategory='cleanup',proposedIronmanTabKey='storage-cleanup',proposedRoles=['unobtainable_internal_item'],proposedTags=[],semanticPredicate=f'Exact ID {i} is an unobtainable spellbook interface artifact, not a teleport item.',rationale='The exact article identifies this spell icon as an unobtainable cache item used by the spellbook interface; it cannot be retained or activated as a player teleport.',evidence=[cite(idx,i,'series of unobtainable items that exist in the game cache')],identityLinks=[])
 # A spell unlock and a location tablet have different transport roles; retain the correct subcategory for the tablet.
 target=by[24336]
 if target['decision']!='certify':raise ValueError('expected target tablet certificate')
 target.update(decision='revise',proposedCategory='TELEPORT',proposedSubcategory='teleport-tablet',proposedIronmanTabKey='currency-utilities',proposedRoles=['teleport_consumable'],proposedTags=[],semanticPredicate='Exact ID 24336 is a consumed target-location tablet.',rationale='This exact item is a magic tablet that breaks to teleport to the assigned target; classify it with teleport tablets rather than the broad teleport-device subcategory.',evidence=[cite(idx,24336,'is a [[magic tablet]] that can be broken by players to')],identityLinks=[])
 # Direct mechanic excerpts replace old spell-nav, footer, and disambiguation-only snippets.
 repairs={13660:'is an equipable book that can be used to [[Teleportation|teleport]] the player',22400:'is a reward from the quest [[A Taste of Hope]]. It allows unlimited',31443:'is a [[magic tablet]] that can be broken by players to [[teleport]] to their [[boat]]',31441:'is a [[magic tablet]] that can be broken by players to move their [[boat]]',24441:'tablet is actually used to teleport to the bakery',981:'the player is teleported into the [[Blackhole]]',556:'They are used in every combat spell and most teleportation spells',564:'Cosmic runes are also used for the [[Lunar spells]]',
 }
 for i,marker in repairs.items():
  if by[i]['decision']!='certify':raise ValueError(f'expected kept certificate {i}')
  by[i]['evidence']=[cite(idx,i,marker)]
 # The boat and Target tablets already have the correct taxonomy; replace weak evidence and retain certification.
 for i in (24336,31441,31443):
  d=by[i]
  d.update(decision='certify',proposedCategory='TELEPORT',proposedSubcategory='teleport-tablet',proposedIronmanTabKey='currency-utilities',proposedRoles=['teleport_consumable'],proposedTags=[],semanticPredicate=f'Exact ID {i} is a consumed transport tablet.',rationale='The exact item article says this tablet breaks to perform the transport. The current tablet subcategory is supported by its consumption and movement mechanic.',evidence=[cite(idx,i,{24336:'is a [[magic tablet]] that can be broken by players to',31443:'is a [[magic tablet]] that can be broken by players to [[teleport]] to their [[boat]]',31441:'is a [[magic tablet]] that can be broken by players to move their [[boat]'}[i])],identityLinks=[])
 # Scaperune also has a confirmed tablet form and therefore needs the tablet subcategory.
 i=24441; d=by[i]
 d.update(decision='revise',proposedCategory='TELEPORT',proposedSubcategory='teleport-tablet',proposedIronmanTabKey='currency-utilities',proposedRoles=['teleport_consumable'],proposedTags=[],semanticPredicate='Exact ID 24441 is a consumed transport tablet.',rationale='The exact item is a teleport tablet used to leave ScapeRune; the tablet-specific placement reflects its consumable movement mechanic.',evidence=[cite(idx,i,'tablet is actually used to teleport to the bakery')],identityLinks=[])
 out=a.output/'decisions.jsonl';a.output.mkdir(parents=True,exist_ok=True);out.write_text(''.join(json.dumps(d,ensure_ascii=False,sort_keys=True)+'\n' for d in ds),encoding='utf8')
 result={'version':'transport-review-v7','previousSha256':'sha256:'+sha(a.previous),'articleIndexSha256':'sha256:'+sha(a.index),'packetSha256':'sha256:'+sha(a.packets),'recordCount':len(ds),'changedCount':len(spell_ids)+1+len(repairs)+2,'spellIconIds':spell_ids,'transportRoleCorrections':[24336,31441,31443,24441],'citationRepairs':sorted(repairs),'decisions':dict(collections.Counter(d['decision'] for d in ds)),'notes':'Removes unobtainable spellbook cache icons from TELEPORT and strengthens exact functional evidence for multiple teleport items. V1-v6 remain unchanged.'}
 (a.output/'summary.json').write_text(json.dumps(result,ensure_ascii=False,indent=2,sort_keys=True)+'\n',encoding='utf8');print(json.dumps(result,indent=2))
if __name__=='__main__':main()
