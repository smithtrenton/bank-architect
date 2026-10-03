#!/usr/bin/env python3
"""Consolidate exact-ID local groups and domain research; never mutates plugin data."""
import argparse, collections, csv, hashlib, json, pathlib
from audit import ROOT, normalize, listify, ids, save, utc, wiki_url

def table(path):
 with path.open(encoding='utf-8-sig',newline='') as f:return list(csv.DictReader(f))
def emit(path,rows):
 if not rows:return
 with path.open('w',encoding='utf-8-sig',newline='') as f:
  w=csv.DictWriter(f,fieldnames=rows[0].keys());w.writeheader();w.writerows(rows)
def tsv(path):
 return [line.split('\t') for line in path.read_text(encoding='utf-8-sig').splitlines() if line and not line.startswith('#')]
def run(args):
 out=args.output;out.mkdir(parents=True,exist_ok=True)
 joined=[json.loads(s) for s in (out/'joined.jsonl').read_text(encoding='utf-8').splitlines()]
 by_id={r['item_id']:r for r in joined};members=collections.defaultdict(list);groups=[]
 source_root=ROOT/'src/main/resources/com/pkoka5/ironmanbankarchitect'
 def add(key,kind,sequence,source,confidence,source_urls='',scope='LOCAL_EXACT_ID_BASELINE'):
  sequence=list(dict.fromkeys(sequence))
  for rank,i in enumerate(sequence):members[i].append({'group_key':key,'group_type':kind,'rank':rank,'confidence':confidence,'source':source,'source_urls':source_urls,'evidence_scope':scope})
  groups.append({'group_key':key,'group_type':kind,'member_ids':' | '.join(map(str,sequence)),'member_names':' | '.join(by_id[i]['name'] if i in by_id else '[outside effective]' for i in sequence),'member_count':len(sequence),'current_tags':' | '.join(sorted({by_id[i]['preset_tag'] for i in sequence if i in by_id})),'outside_effective_count':sum(i not in by_id for i in sequence),'confidence':confidence,'source':source,'source_urls':source_urls,'evidence_scope':scope})
 for path in sorted((source_root/'catalog').glob('*-layout-families.tsv')):
  for key,values in tsv(path):add('local-layout:'+path.stem+':'+key,'CURATED_LAYOUT_FAMILY',[int(x) for x in values.split(',')],str(path.relative_to(ROOT)),'BASELINE_NOT_INDEPENDENT_WIKI_VERIFICATION')
 sets=collections.defaultdict(list)
 for domain,key,name,slot,i in tsv(source_root/'organize/item-set-catalog.tsv'):sets[(domain,key,name)].append((int(slot),int(i)))
 for (domain,key,name),seq in sets.items():add('local-set:'+key,'CURATED_SET_'+domain,[i for _,i in sorted(seq)],'src/main/resources/com/pkoka5/ironmanbankarchitect/organize/item-set-catalog.tsv','BASELINE_NOT_INDEPENDENT_WIKI_VERIFICATION')
 supplied=out/'reviews/supplies-herblore/group-candidates.json'
 if supplied.exists():
  data=json.loads(supplied.read_text(encoding='utf-8-sig'))
  for bucket in ('potion_dose_families','additional_wiki_dose_families','food_families'):
   for g in data.get(bucket,[]):
    seq=g.get('member_ids',[int(m['item_id']) for m in g.get('members',[])])
    if seq:add('sourced:'+g['group_key'],g.get('group_type',bucket),seq,str(supplied.relative_to(ROOT)),g.get('confidence','REVIEW'),g.get('evidence_url',' | '.join(g.get('evidence_urls',[]))),g.get('basis','SOURCED_LOCAL_METADATA'))
 farming=out/'reviews/farming-materials/proposed-families.csv'
 if farming.exists():
  for g in table(farming):
   sequence=[int(i.strip()) for i in g['item_ids'].split('|') if i.strip()]
   add('proposed:'+g['candidate_group'],'PROPOSED_FARMING_MATERIAL_WORKFLOW',sequence,str(farming.relative_to(ROOT)),'PROPOSED_'+g['confidence'].upper(),g['source_urls'],g['evidence_limit'])
 gear=out/'reviews/gear-cosmetics/verified-groups.json'
 if not gear.exists():gear=pathlib.Path(__file__).with_name('gear-group-proposals.json')
 if gear.exists():
  for g in json.loads(gear.read_text(encoding='utf-8'))['proposals']:
   add('proposed:'+g['key'],'PROPOSED_GEAR_OUTFIT_ACTIVITY_GROUP',g['member_ids'],str(gear.relative_to(ROOT)),'PROPOSED_'+g['confidence'].upper(),' | '.join(g['sources']),g['evidence']+' '+g.get('caveat',''))
 utility=out/'reviews/utilities-containers/state-families.json'
 if utility.exists():
  for g in json.loads(utility.read_text(encoding='utf-8')):
   add('proposed:'+g['family_key'],'PROPOSED_UTILITY_STATE_FAMILY',[int(i) for i in g['member_ids'].split('|')],str(utility.relative_to(ROOT)),'PROPOSED_'+g['confidence'],g['source_url'],g['state_relation']+' Role: '+g['candidate_role'])
 edges=[dict(item_id=i,item_name=by_id.get(i,{}).get('name',''),**edge) for i,rr in sorted(members.items()) for edge in rr]
 emit(out/'grouping-groups.csv',groups);emit(out/'grouping-edges.csv',edges)
 # Domain rows preserve their original evidence/uncertainty rather than resolving by majority vote.
 domain_files={'gear-cosmetics':'reviewed-items.csv','supplies-herblore':'item-review.csv','farming-materials':'candidate-universe.csv','utilities-containers':'per-id-review.csv','loot-quests-clues':'review-candidates.csv','coverage-variants':'effective-id-coverage.csv'}
 domain_by_id=collections.defaultdict(list);domain_counts={};source_hashes={}
 with (out/'domain-evidence.jsonl').open('w',encoding='utf-8') as f:
  for domain,name in domain_files.items():
   path=out/'reviews'/domain/name
   if not path.exists():raise ValueError(f'Missing domain research: {path}')
   rows=table(path);domain_counts[domain]=len(rows);source_hashes[str(path.relative_to(out))]=hashlib.sha256(path.read_bytes()).hexdigest()
   for row in rows:
    i=int(row.get('item_id',row.get('itemId')));domain_by_id[i].append(domain)
    f.write(json.dumps({'item_id':i,'domain':domain,'review':row},ensure_ascii=False)+'\n')
 flat=table(out/'catalog-semantic-audit.csv')
 for row in flat:
  i=int(row['item_id']);row['review_domains']=' | '.join(domain_by_id[i]);row['exact_group_keys']=' | '.join(g['group_key'] for g in members.get(i,[]));row['group_membership_count']=len(members.get(i,[]))
 emit(out/'full-grouping-audit.csv',flat)
 # All recipe outputs remain discoverable as title-level workflow candidates.
 wiki=json.loads((args.cache/'infobox_item.json').read_text(encoding='utf-8'))['rows'];title_ids=collections.defaultdict(set)
 for r in wiki:
  for title in (r['page_name'],r.get('page_name_sub')):title_ids[normalize(title)].update(i for i in ids(r) if i in by_id)
 recipes=json.loads((args.cache/'recipe.json').read_text(encoding='utf-8'))['rows'];recipe_edges=[]
 for r in recipes:
  for field,role in (('uses_material','material'),('uses_tool','tool'),('uses_facility','facility')):
   for title in listify(r.get(field)):
    recipe_edges.append({'output_page':r['page_name'],'output_page_sub':r.get('page_name_sub',''),'relation':role,'input_title':title,'input_candidate_ids':' | '.join(map(str,sorted(title_ids[normalize(title)]))),'output_candidate_ids':' | '.join(map(str,sorted(title_ids[normalize(r.get('page_name_sub') or r['page_name'])]))),'skills':' | '.join(map(str,listify(r.get('uses_skill')))),'source_url':wiki_url(r['page_name']),'confidence':'TITLE_RELATION_CANDIDATE','evidence_scope':'Wiki recipe relation; candidate ID pools are NOT exact variant input/output proof'})
 emit(out/'recipe-workflow-edges.csv',recipe_edges)
 # Weak catalog family/name clusters aid review only; they never propagate Wiki facts.
 clusters=collections.defaultdict(list)
 for r in joined:
  if r['family_hint']:clusters[normalize(r['family_hint'])].append(r)
 candidates=[]
 for hint,rr in sorted(clusters.items()):
  if len(rr)<2:continue
  candidates.append({'family_hint':hint,'member_count':len(rr),'member_ids':' | '.join(str(r['item_id']) for r in rr),'member_names':' | '.join(r['name'] for r in rr),'current_tags':' | '.join(sorted({r['preset_tag'] for r in rr})),'exact_wiki_match_count':sum(r['wiki_join_status']!='NO_EXACT_ID_FACT' for r in rr),'unverified_count':sum(r['wiki_join_status']=='NO_EXACT_ID_FACT' for r in rr),'confidence':'UNVERIFIED_NAME_FAMILY_CANDIDATE','evidence_scope':'Catalog family hint only; no typed variant, relationship, or shared Wiki fact is established'})
 emit(out/'unverified-family-candidates.csv',candidates)
 source_pools=collections.defaultdict(list)
 for r in joined:
  for f in r['wiki_records']:
   if f.get('version_anchor'):
    source_pools[f['page_name']].append({'item_id':r['item_id'],'name':r['name'],'preset_tag':r['preset_tag'],'subpage':f.get('page_name_sub'),'version_anchor':f['version_anchor'],'default_version':f.get('default_version'),'removal_date':f.get('removal_date'),'join_status':r['wiki_join_status']})
 version_groups=[]
 for page,rr in sorted(source_pools.items()):
  member_ids=sorted({r['item_id'] for r in rr});anchors={r['version_anchor'] for r in rr}
  if len(member_ids)<2 or len(anchors)<2:continue
  version_groups.append({'wiki_page':page,'source_url':wiki_url(page),'member_count':len(member_ids),'member_ids':' | '.join(map(str,member_ids)),'version_anchors':' | '.join(sorted(anchors)),'current_tags':' | '.join(sorted({r['preset_tag'] for r in rr})),'member_source_records':json.dumps(rr,ensure_ascii=False),'confidence':'EXPLICIT_WIKI_VERSION_POOL_CANDIDATE','evidence_scope':'Exact IDs and explicit source version anchors on the same Wiki article; not proof of identical function, bank suitability, typed state transitions, or member order'})
 emit(out/'wiki-version-family-candidates.csv',version_groups)
 summary={'generated_at':utc(),'effective_ids':len(joined),'domain_row_counts':domain_counts,'domain_unique_ids':len(domain_by_id),'ids_with_semantic_domain_review':len(set().union(*(set(i for i,ds in domain_by_id.items() if d in ds) for d in domain_files if d!='coverage-variants'))),'local_and_sourced_groups':len(groups),'group_edges':len(edges),'distinct_grouped_effective_ids':len({i for i,rr in members.items() if rr}&set(by_id)),'wiki_explicit_version_pools':len(version_groups),'wiki_version_pool_distinct_ids':len({i for g in version_groups for i in map(int,g['member_ids'].split(' | '))}),'weak_name_family_clusters':len(candidates),'recipe_workflow_edges':len(recipe_edges),'recipe_rows':len(recipes),'source_hashes':source_hashes,'limits':['Domain review rows are mechanical evidence extraction and policy analysis, not manual validation of each item.','Existing local layout/set groups are the preset baseline; source-backed dose/food groups are labeled separately.','Recipe ID pools retain title-scope ambiguity. No same-name or canonical-ID propagation.','Overlapping roles are preserved; no production reclassification is implied.']}
 save(out/'grouping-summary.json',summary);print(json.dumps(summary,indent=2))
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--output',type=pathlib.Path,default=ROOT/'tmp/semantic-audit');p.add_argument('--cache',type=pathlib.Path,default=ROOT/'tmp/semantic-audit/cache');run(p.parse_args())
