#!/usr/bin/env python3
"""Create a new full CLUE/UNIQUE ledger correcting source-citation and variant-role findings."""
import hashlib,json,re
from pathlib import Path
ROOT=Path(__file__).resolve().parents[4]
BASE=ROOT/'tmp/category-certification/reviews/collections/clue-unique-second-pass.jsonl'
INDEX=ROOT/'tmp/category-certification/wiki-articles/article-index.json'
OUT=ROOT/'tmp/category-certification/reviews/collections/clue-unique-third-pass.jsonl'
DELTA=ROOT/'tmp/category-certification/reviews/collections/clue-unique-third-pass-delta.jsonl'
POLICY=ROOT/'tools/research/semantic-grouping-audit/certification/clue-unique-third-pass-policy.json'
QUOTE_NEEDLES={
 13227:'When used with a pair of [[infinity boots]], [[eternal boots]] will be created.',
 13229:'When used with a pair of [[ranger boots]], [[Pegasian boots]] will be created.',
 13231:'When used with a pair of [[dragon boots]], [[primordial boots]] will be created.',
 23953:"The '''crystal tool seed''' is an [[elves|elven]] [[crystal]] that can be turned into the [[crystal axe]], [[crystal harpoon]], or [[crystal pickaxe]]",
 31732:'The key opens a [[Chest (Pandemonium Cave)|chest]] found in [[Pandemonium Cave]]',
 31744:"The key opens a [[Chest (Anglers' Retreat)|chest]] found on [[Anglers' Retreat]]",
 31756:'The key opens a [[Chest (Laguna Aurorae)|chest]] found on [[Laguna Aurorae]]',
 7981:'It can be stuffed at the [[Taxidermist]] in [[Canifis]] by using the item on her',
}

def rows(p): return [json.loads(x) for x in p.read_text(encoding='utf8').splitlines() if x.strip()]
def exact_pages(index):
 out={}
 for title,a in index.items():
  for i in a.get('exactInfoboxItemIds',[]): out.setdefault(int(i),[]).append((title,a))
 return out

def main():
 baseline=rows(BASE); byid={int(x['itemId']):x for x in baseline}; original={i:json.dumps(x,ensure_ascii=False,sort_keys=True) for i,x in byid.items()}
 index=json.loads(INDEX.read_text(encoding='utf8')); pages=exact_pages(index); applied=[]
 for i,needle in QUOTE_NEEDLES.items():
  m=[(t,a) for t,a in pages.get(i,[]) if str(i) in a.get('variants',{})]
  if len(m)!=1: raise ValueError(f'exact source ambiguity for {i}: {[t for t,a in m]}')
  title,a=m[0]; text=(ROOT/a['path']).read_text(encoding='utf8')
  if needle not in text: raise ValueError(f'quoted mechanic not found for {i}: {needle}')
  ev={'kind':'exact_wiki','sourceTitle':title,'source':a['sourceUrl'],'sourceRevision':a['revid'],'sourceHash':'sha256:'+a['sha256'],'itemId':i,'quote':needle}
  byid[i].setdefault('evidence',[]).append(ev); applied.append({'itemId':i,'sourceTitle':title,'revision':a['revid'],'hash':'sha256:'+a['sha256'],'quote':needle})
 # Multi-ID page categories/facets do not make Collection Log claims per variant.
 remove_log_role=[20275,20278,20693,24483,24484,24485,24486]
 for i in remove_log_role:
  r=byid[i]; roles=list(r.get('proposedRoles') or []); r['proposedRoles']=[x for x in roles if x!='collection_log_member']
  r['rationale']=(r.get('rationale','')+' Collection Log membership was removed: the only cited page facet is shared by multiple item IDs and does not bind this role to this variant.')
 # Correct a non-pet combat headgear role caused by a lexical false match.
 r=byid[12271]; r['proposedRoles']=[x for x in (r.get('proposedRoles') or []) if x!='pet_companion']
 r['rationale']=(r.get('rationale','')+' Removed unsupported pet-companion role: exact ID 12271 is the equipable Bandos mitre in a singleton item infobox, not a pet item.')
 # Direct item mechanics expose multiple primary uses; hold this trophy assignment for taxonomy review.
 r=byid[7981]; r['decision']='unresolved'; roles=set(r.get('proposedRoles') or []); roles.update(['display_trophy','equipment_upgrade_material']); r['proposedRoles']=sorted(roles)
 r['rationale']='Exact item page documents both stuffing/mounting the KQ head as a player-owned-house trophy and combining it with a Slayer helmet to create a green Slayer helmet. The current cited source excerpt did not establish either function; the primary category is held unresolved because this exact item has a direct display use and a functional gear-upgrade use.'
 r['semanticPredicate']='Preserve exact item-specific display-trophy and equipment-upgrade functions independently; resolve primary placement under the approved role-precedence policy.'
 # Quest-specific clue scrolls are not established Treasure Trails steps by their direct page.
 for i in [23814,23815,23816,23817]:
  r=byid[i]; r['decision']='unresolved'; r['proposedRoles']=sorted(set(r.get('proposedRoles') or [])|{'quest_required_item'})
  r['rationale']='The exact page defines this numeric ID as a quest item in Song of the Elves and says it leads to Lady Meilyr. That proves quest use, but not a Treasure Trails clue function; the current CLUE/treasure-trail assignment remains unresolved.'
  r['semanticPredicate']='Assign a quest clue item only when direct exact-ID evidence establishes the preset-relevant function, not from the shared phrase “clue scroll”.'
 for i in [7280,19764,21524,19770,7255]:
  r=byid[i]; r['decision']='unresolved'; r['rationale']='This row was previously certified under a broad clue-scroll grouping. The root-reviewed strict rule did not select it because its exact source lacks one of the required raw item-ID binding, named direct Treasure Trails subject definition, standard readable state, or actual clue-step proof checks; keep it open for separate per-ID review.'
  r['semanticPredicate']='Do not transfer clue-scroll item identity/function across source titles or variants; require exact source binding and direct step definition.'
 for i in [27427]:
  r=byid[i]; r['decision']='unresolved'; r['proposedRoles']=sorted(set(r.get('proposedRoles') or [])|{'event_clue_interface'})
  r['rationale']='The exact page says this is only shown in a chatbox interface during Crack the Clue III and has no known acquisition method. It does not establish a retained bank-item state; category certification is withheld.'
  r['semanticPredicate']='A chatbox/event interface representation is not treated as an obtainable bank item without direct item-state evidence.'
 delta=[byid[i] for i in sorted(byid) if original[i]!=json.dumps(byid[i],ensure_ascii=False,sort_keys=True)]
 OUT.parent.mkdir(parents=True,exist_ok=True); OUT.write_text(''.join(json.dumps(byid[i],ensure_ascii=False,separators=(',',':'))+'\n' for i in sorted(byid)),encoding='utf8')
 DELTA.write_text(''.join(json.dumps(x,ensure_ascii=False,separators=(',',':'))+'\n' for x in delta),encoding='utf8')
 policy={'version':3,'inputSha256':hashlib.sha256(BASE.read_bytes()).hexdigest(),'articleIndexSha256':hashlib.sha256(INDEX.read_bytes()).hexdigest(),'rules':['Exact direct facts attach only to the exact item numeric ID and pinned article hash.','Collection Log page categories on multi-ID variant articles are unresolved at variant scope unless the exact variant is directly bound to the facet.','Do not infer companion function from lexical mentions of pets/animals on combat equipment pages.','When one item has documented display and functional upgrade uses, preserve both and leave primary placement unresolved until role precedence is approved.','Quest/event/interface clue strings do not establish Treasure Trails item function or inventory state.'],'citationRepairs':applied,'removedCollectionLogRoleFromMultiIdPages':remove_log_role,'removedPetRoleFromNonPetItem':[12271],'newlyUnresolvedForSourceOrPrecedence':[7981,23814,23815,23816,23817,7280,19764,21524,19770,7255,27427],'outputRows':len(byid),'deltaRows':len(delta),'outputSha256':hashlib.sha256(OUT.read_bytes()).hexdigest(),'deltaSha256':hashlib.sha256(DELTA.read_bytes()).hexdigest()}
 POLICY.write_text(json.dumps(policy,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
 print(json.dumps({'rows':len(byid),'delta':len(delta),'unresolved':sum(r['decision']=='unresolved' for r in byid.values()),'output':str(OUT),'deltaPath':str(DELTA),'policy':str(POLICY)},indent=2))
if __name__=='__main__':main()
