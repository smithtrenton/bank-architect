#!/usr/bin/env python3
"""Acquire explicitly planned public articles for reviewed mechanics and log provenance."""
import argparse,json,pathlib
from audit import ROOT,request,save,utc

def run(args):
 plan=json.loads(args.plan.read_text(encoding='utf-8'))
 for entry in plan:
  name=entry['file']
  if pathlib.Path(name).name!=name:raise ValueError('Plan files must be plain basenames')
  path=args.cache/name
  if path.exists() and not args.refresh:
   print('Reusing',path);continue
  params={'action':'query','prop':'revisions','rvprop':'ids|timestamp|content','rvslots':'main'}
  if 'revision' in entry:params['revids']=entry['revision']
  else:params.update(titles='|'.join(entry['titles']),redirects=1)
  data,url=request(params)
  meta={'retrieved_at':utc(),'source_url':url,'requested_titles':entry.get('titles',[]),'requested_revision':entry.get('revision')}
  # Collection Log parser expects the API query shape; article readers expect packet.data.
  save(path,dict(data,source_metadata=meta) if name=='collection-log-page.json' else dict(meta,data=data))
  print('Fetched',path)
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--plan',type=pathlib.Path,default=pathlib.Path(__file__).with_name('article-plan.json'));p.add_argument('--cache',type=pathlib.Path,default=ROOT/'tmp/semantic-audit/cache');p.add_argument('--refresh',action='store_true');run(p.parse_args())
