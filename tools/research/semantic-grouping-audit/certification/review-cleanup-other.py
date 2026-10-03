#!/usr/bin/env python3
"""Emit honest per-ID Cleanup decisions from exact pinned, manually reviewed policies."""
import argparse, collections, csv, hashlib, json, pathlib
ROOT=pathlib.Path(__file__).resolve().parents[4]
HERE=pathlib.Path(__file__).resolve().parent

def run(args):
 policy=json.loads(args.policy.read_text(encoding='utf-8'))
 articles=json.loads(args.articles.read_text(encoding='utf-8'))
 cases={p['itemId']:p for p in policy['cases']}
 if len(cases)!=len(policy['cases']):raise ValueError('Duplicate policy ID')
 with args.coverage.open(encoding='utf-8-sig',newline='') as stream:
  coverage={int(r['itemId']):r for r in csv.DictReader(stream,delimiter='\t')}
 rows=[]
 for ident,current in sorted(coverage.items()):
  if current['itemCategory']!='CLEANUP' or current['subcategory']!='cleanup':continue
  decision=dict(itemId=ident,decision='unresolved',reviewer='root',shard='cleanup-other',
                rationale='No approved semantic decision yet. Generic Cleanup fallback and missing Wiki facts are not certification.',
                semanticPredicate='Unproven function and placement; no claim of absence.', proposedRoles=None,proposedTags=[],evidence=[],identityLinks=[])
  if ident in cases:
   case=cases[ident];source=articles[case['title']]
   if source['revid']!=case['sourceRevision'] or source['sha256']!=case['sourceSha256']:raise ValueError('Source changed: '+case['title'])
   text_path=ROOT/source['path'] if not pathlib.Path(source['path']).is_absolute() else pathlib.Path(source['path'])
   text=text_path.read_text(encoding='utf-8')
   if hashlib.sha256(text_path.read_bytes()).hexdigest()!=case['sourceSha256']:raise ValueError('Text digest differs')
   if ident not in source['exactInfoboxItemIds'] or str(ident) not in source['variants'] or case['semanticExcerpt'] not in text:raise ValueError('Exact ID or semantic evidence absent')
   roles=sorted(set(filter(None,current['tags'].split(',')))|set(case['addedRoles']))
   destination={'HERBLORE':'herblore','SKILLING':'resources','POTION':'potions-food','CLUE':'clues-cosmetics','GEAR':'combat-gear'}[case['proposedCategory']]
   decision.update(decision='revise',proposedCategory=case['proposedCategory'],proposedSubcategory=case['proposedSubcategory'],proposedRoles=sorted(case['addedRoles']),proposedTags=roles,
                   semanticPredicate=case['rationale'],
                   proposedIronmanTabKey=destination,rationale=case['rationale'],
                   evidence=[dict(kind='direct_variant',itemId=ident,source=source['sourceUrl'],sourceRevision=source['revid'],
                                  sourceHash=source['sha256'],quote=case['semanticExcerpt'])])
  rows.append(decision)
 if set(cases)-{r['itemId'] for r in rows}:raise ValueError('Policy contains IDs outside frozen ownership')
 args.output.mkdir(parents=True,exist_ok=True)
 with (args.output/'decisions.jsonl').open('w',encoding='utf-8',newline='') as stream:
  for row in rows:stream.write(json.dumps(row,ensure_ascii=False)+'\n')
 (args.output/'summary.json').write_text(json.dumps(dict(total=len(rows),decisions=dict(collections.Counter(r['decision'] for r in rows)),coverageSha256=hashlib.sha256(args.coverage.read_bytes()).hexdigest()),indent=2)+'\n',encoding='utf-8')
 print(json.dumps(dict(total=len(rows),decisions=dict(collections.Counter(r['decision'] for r in rows)))))
if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__)
 p.add_argument('--coverage',type=pathlib.Path,default=ROOT/'tmp/category-certification/current-coverage.tsv')
 p.add_argument('--articles',type=pathlib.Path,default=ROOT/'tmp/category-certification/wiki-articles/article-index.json')
 p.add_argument('--policy',type=pathlib.Path,default=HERE/'cleanup-other-policy.json')
 p.add_argument('--output',type=pathlib.Path,default=ROOT/'tmp/category-certification/reviews/cleanup-other')
 run(p.parse_args())
