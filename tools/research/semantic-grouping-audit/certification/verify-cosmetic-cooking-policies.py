#!/usr/bin/env python3
"""Verify exact primary approvals, pinned own-source evidence and staged workflows."""
from __future__ import annotations
import argparse, hashlib, json, re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
CERT = ROOT / 'tools/research/semantic-grouping-audit/certification'
BASE = ROOT / 'tmp/category-certification'
REVIEW = BASE / 'root-review'
CONFIG = {
 'clue-residual44-primary-approved-policy.json': ('clue-residual44-immutable-root-policy-draft-v2.json','1094d48744d2aff91a7effc65040e373604ae4a243bc0f4d9fadd29b1035e2c6',44,'certify','0ab2de5f469815d41fa52709fd4a92bf0ebb31fa984fa86e4724fbb394b68ac2'),
 'clue-cosmetic-primary-approved-policy.json': ('clue-cosmetic230-immutable-root-policy-draft-v1.json','b6d107dd406118b4bc6133e16fbb455c3a9437fcacbfbcb62599dd8bbb56785c',230,'certify','71b525ea8b851b6d3163d40e7cdfc9e4b66b2bb393dff44146b4681232c536a4'),
 'clue-cosmetic-corrections-approved-policy.json': ('clue-cosmetic10-immutable-root-policy-draft-v1.json','26e37e534cef9a493d2d762d18f2c13f1f0fb064d15905e9e30c710599a3f60c',10,'revise','e88a53833e9e42646626b61a8bbc13aa5b3f42ffd601d8ced254943adcd1923d'),
 'cooking-stage-primary-approved-policy.json': ('cooking-stage9-immutable-root-policy-draft-v2.json','90d361a232c4eddddd01b513e61b6810dc5374e123e8b15ba1462603e16cf688',4,'certify','7564aa7b0f6773e0634e96e6527e67f5e2f5c0c299871a4a2f2d701232cf3ac5'),
 'cooking-stage-corrections-approved-policy.json': ('cooking-stage9-immutable-root-policy-draft-v2.json','90d361a232c4eddddd01b513e61b6810dc5374e123e8b15ba1462603e16cf688',5,'revise','c425d50a4f8f32db6eee3ba2bad444f952e3283dbe969f5050ea136c5c94134b'),
}
PACKET_284 = BASE / 'reviews/root-review/clue-residual284-root-draft-v1/candidates.jsonl'
ARTICLE_INDEX = BASE / 'wiki-articles/article-index.json'

def sha_bytes(data): return hashlib.sha256(data).hexdigest()
def sha(path): return sha_bytes(path.read_bytes())
def read_json(path): return json.loads(path.read_bytes().decode('utf-8-sig', errors='strict'))
def canon_sha(obj): return sha_bytes(json.dumps(obj,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode('utf-8'))
def require(ok,msg):
 if not ok: raise ValueError(msg)
def norm(s): return ' '.join(s.split())
def id_sha(ids): return sha_bytes(json.dumps(sorted(map(int,ids)),separators=(',',':')).encode('ascii'))
def read_jsonl(path):
 out=[]
 for n,line in enumerate(path.read_bytes().decode('utf-8-sig',errors='strict').splitlines(),1):
  if line.strip():
   try: out.append(json.loads(line))
   except json.JSONDecodeError as e: raise ValueError(f'{path}:{n}: invalid JSONL: {e}')
 return out
def rows(value):
 if isinstance(value,dict):
  if 'itemId' in value: yield value
  for x in value.values(): yield from rows(x)
 elif isinstance(value,list):
  for x in value: yield from rows(x)
def packet_map(path):
 rs=read_jsonl(path) if path.suffix.lower()=='.jsonl' else list(rows(read_json(path)))
 out={}
 for r in rs:
  if 'itemId' in r:
   i=int(r['itemId']); require(i not in out,f'{path}: duplicate item #{i}'); out[i]=r
 return out
def input_map(d):
 p,h=d.get('sourceInputPaths'),d.get('sourceHashes')
 require(isinstance(p,dict) and isinstance(h,dict) and set(p)==set(h),'Immutable source path/hash maps differ')
 return p,h
def verify_partition():
 drafts={n:read_json(REVIEW/file) for n,(file,_,_,_,_) in CONFIG.items()}
 clue=[]
 for n in ['clue-residual44-primary-approved-policy.json','clue-cosmetic-primary-approved-policy.json','clue-cosmetic-corrections-approved-policy.json']:
  clue.extend(int(c['itemId']) for c in drafts[n]['cases'])
 packet=packet_map(PACKET_284)
 require(len(packet)==284 and len(set(packet))==284 and len(clue)==284 and len(set(clue))==284 and set(clue)==set(packet),'44+230+10 fail exact frozen-284 partition')
 cook=drafts['cooking-stage-primary-approved-policy.json']; cp=packet_map(ROOT/cook['sourceInputPaths']['candidatePacket']); ci={int(c['itemId']) for c in cook['cases']}
 require(len(cp)==21 and len(ci)==9 and ci<set(cp),'Cooking stage draft is not exact nine-case subset of frozen source packet')
 rootread=read_json(ROOT/cook['sourceInputPaths']['rootReadRecord']); read_ids={int(x['itemId']) for x in rootread['cases']}
 require(len(read_ids)==10 and ci<read_ids and read_ids-ci=={6004},'Cooking ten-ID root-read boundary changed; only Mushroom #6004 may be omitted')
def src_objects(path):
 return read_jsonl(path) if path.suffix.lower()=='.jsonl' else list(rows(read_json(path)))
def verify_bob(d):
 c=next((x for x in d['cases'] if int(x['itemId'])==3436),None); require(c is not None,'Missing Sacred oil(1) exact state')
 proof=c.get('variantFunctionProof',{}); m=proof.get('mechanicSource',{})
 rawrel='tmp/category-certification/sacred-oil-decanting-source-v1/15353359.txt'; apirel='tmp/category-certification/sacred-oil-decanting-source-v1/api-packet.json'
 rawpath,apipath=ROOT/rawrel,ROOT/apirel
 require(proof.get('kind')=='explicit-own-material-decant-workflow' and m.get('sourceTitle')=='Bob Barter (herbs)' and int(m.get('sourceRevision',-1))==15353359,'Sacred oil Bob proof identity changed')
 require(m.get('sourcePath')==rawrel and m.get('sourceApiPacketPath')==apirel and sha(rawpath)==m.get('sourceSha256') and sha(apipath)==m.get('sourceApiPacketSha256'),'Sacred oil Bob raw/API pins differ')
 raw=rawpath.read_bytes().decode('utf-8',errors='strict'); quote=m.get('literalQuote','')
 require(norm(quote) in norm(raw) and 'specified number of doses (1-4)' in quote and '[[sacred oil]]' in quote,'Bob exact decant quote does not prove own Sacred oil 1-4 dose route')
 api=read_json(apipath); page=api['data']['query']['pages'][0]; rev=page['revisions'][0]
 require(page['title']=='Bob Barter (herbs)' and int(rev['revid'])==15353359 and rev['slots']['main']['content']==raw,'Bob API packet content/revision does not match raw source')
 require(proof.get('exactOwnState')=={'itemId':3436,'dose':1,'requiredMinimumPyreLogDose':2},'Sacred oil(1) threshold facts changed')
 require('one dose alone' in proof.get('interpretation','').casefold(),'Sacred oil proof fails to limit the claim to a transformed >=2-dose state')
def verify_sources(d,cases):
 index=read_json(ARTICLE_INDEX); nfact=nquote=0
 for c in cases:
  i=int(c['itemId']); src=index.get(c['title']); require(src is not None,f'#{i}: missing exact indexed title')
  require(i in {int(v) for v in src.get('exactInfoboxItemIds',[])} and str(i) in src.get('variants',{}),f'#{i}: exact numeric variant is not bound')
  require(int(src['revid'])==int(c['sourceRevision']) and src['sha256']==c['sourceSha256'],f'#{i}: pinned revision/hash differs')
  rawbytes=(ROOT/str(src['path']).replace('\\','/')).read_bytes(); require(sha_bytes(rawbytes)==src['sha256'],f'#{i}: raw Wiki byte SHA mismatch')
  raw=rawbytes.decode('utf-8',errors='strict'); variant=src['variants'][str(i)]; params=variant.get('params',{}); suffix=str(variant.get('suffix') or '')
  for f in c.get('exactVariantFacts',[]):
   field,val=str(f['field']),str(f['value']); base_match=re.fullmatch(r'(id|name|version|examine|options|quest|equipable)(\d+)',field)
   if base_match and suffix and suffix.isdigit(): require(base_match.group(2)==suffix,f'#{i}: field {field} belongs to a sibling variant, expected suffix {suffix}')
   suffixed=field+suffix if suffix and not (base_match and base_match.group(2)==suffix) else field; actual=suffixed if suffixed in params else field
   require(str(params.get(actual,''))==val,f'#{i}: exact variant field {actual} differs')
   if field.startswith('id'):
    require(val==str(i),f'#{i}: selected ID field does not bind this exact item')
    require(re.search(r'^\s*\|\s*'+re.escape(actual)+r'\s*=\s*'+re.escape(val)+r'\s*$',raw,re.M) is not None,f'#{i}: exact raw ID field absent')
   nfact+=1
  quotes=[('own',c.get('semanticExcerpt','')),('primary',c.get('positiveFunctionExcerpt',''))]+[(f'secondary {j}',q) for j,q in enumerate(c.get('secondaryExcerpts',[]))]
  for label,q in quotes:
   require(isinstance(q,str) and q.strip() and norm(q) in norm(raw),f'#{i}: {label} quote not literal in strict UTF-8 raw source'); nquote+=1
  require(not c.get('addedRoles') and not c.get('proposedTags') and not c.get('tagEvidence'),f'#{i}: primary-only policy adds roles/tags')
 return nfact,nquote
def verify_policy(policy, *, draft=False):
 verify_partition()
 name=policy.get('policyFile'); require(name in CONFIG,'Policy file is outside fixed five-name allowlist')
 draft_name,draft_hash,count,decision,expected_ids_sha=CONFIG[name]; dp=REVIEW/draft_name; d=read_json(dp)
 require(sha(dp)==draft_hash and d.get('status')=='IMMUTABLE_ROOT_CASE_APPROVED_DRAFT_AWAITING_LEDGER_INTEGRATION' and d.get('ledgerAppliedCount')==0,'Immutable root draft bytes/status changed')
 chosen=[c for c in d['cases'] if c['expectedDecision']==decision]; ids=[int(c['itemId']) for c in chosen]
 require(len(ids)==count and len(set(ids))==count and id_sha(ids)==expected_ids_sha and len(policy.get('cases',[]))==count,'Exact fixed case count/ID set changed')
 require(policy.get('schema')==1 and policy.get('status')=='root-reviewed primary assignments only' and policy.get('expectedCaseCount')==count and policy.get('expectedDecision')==decision,'Policy metadata/decision is not the fixed uniform cohort')
 require(policy['cases']==chosen and all(c['expectedDecision']==decision for c in policy['cases']),'Policy cases differ from exact immutable uniform-decision subset')
 policy_ids=[int(c['itemId']) for c in policy['cases']]
 require(id_sha(policy_ids)==id_sha(ids),'Exact ID set changed')
 paths,hashes=input_map(d); expect_paths={**paths,'immutableRootPolicyDraft':dp.relative_to(ROOT).as_posix()}; expect_hashes={**hashes,'immutableRootPolicyDraft':draft_hash}
 require(policy.get('sourceInputPaths')==expect_paths and policy.get('sourceHashes')==expect_hashes,'Fixed source path/hash manifest differs from root draft')
 for k,rel in expect_paths.items(): require(sha(ROOT/rel)==expect_hashes[k],f'Pinned source changed: {k}')
 if not draft:
  audits=policy.get('independentAudits')
  require(isinstance(audits,list) and audits,'Detached independent audit pins are required')
  for audit in audits:
   require(isinstance(audit,dict) and set(audit)=={'path','sha256'},'Independent audit pin shape changed')
   ap=ROOT/audit['path']; require(ap.is_file() and sha(ap)==audit['sha256'],f'Independent audit pin mismatch: {audit.get("path")}')
 if not draft:
  pp=CERT/name; require(pp.is_file() and read_json(pp)==policy,'Normal mode requires exact policy saved under fixed certification path')
  approvals=read_json(CERT/'root-policy-approvals.json'); require(approvals.get('schema')==1 and approvals.get('status')=='root-reviewed exact policy pins','Detached approval manifest malformed')
  a=approvals.get('approvedPolicies',{}).get(name); require(isinstance(a,dict),'Detached approval entry missing')
  require(a.get('sha256')==sha(pp) and a.get('canonicalSha256')==canon_sha(policy),'Detached policy byte/canonical hash mismatch')
  require(a.get('approvedItemIds')==sorted(policy_ids) and a.get('caseCount')==count and a.get('decision')==decision,'Detached exact IDs/count/decision mismatch')
 verify_support(d,policy['cases'])
 nfact,nquote=verify_sources(d,policy['cases'])
 if name.startswith('cooking-stage-'): verify_bob(d)
 return {'policyFile':name,'mode':'draft candidate' if draft else 'detached approved','count':count,'decision':decision,'exactIdSetSha256':id_sha(policy_ids),'variantFactsChecked':nfact,'literalExcerptsChecked':nquote,'detachedApprovalVerified':not draft}
def verify_support(d,cases):
 paths=d['sourceInputPaths']; packet=packet_map(ROOT/paths['candidatePacket'])
 rkeys=[k for k in paths if k=='rootReadRecord' or k.startswith('rootRead')]
 ikeys=[k for k in paths if any(z in k.lower() for z in ('independent','finding','followup'))]
 rr=sum((src_objects(ROOT/paths[k]) for k in rkeys),[]); ir=sum((src_objects(ROOT/paths[k]) for k in ikeys),[])
 for c in cases:
  i=int(c['itemId']); require(i in packet,f'#{i}: not in exact candidate packet')
  p=packet[i]; route=p.get('currentPrimaryRoute') or p.get('currentRoute') or p.get('current') or p.get('currentAssignment')
  require(isinstance(route,dict),f'#{i}: frozen current route missing')
  old=(route.get('category',route.get('itemCategory')),route.get('subcategory'),route.get('ironmanTabKey')); new=(c.get('proposedCategory'),c.get('proposedSubcategory'),c.get('proposedIronmanTabKey'))
  require(old==new if c['expectedDecision']=='certify' else old!=new,f'#{i}: target/current route disagrees with expected decision')
  roots=[x for x in rr if int(x.get('itemId',-1))==i]
  require(any(x.get('sourceTitle',x.get('title'))==c['title'] and int(x.get('revision',x.get('sourceRevision',-1)))==int(c['sourceRevision']) and x.get('sourceSha256')==c['sourceSha256'] for x in roots),f'#{i}: root source-read record does not pin own page')
  require(any(int(x.get('itemId',-1))==i for x in ir),f'#{i}: no exact-ID independent-review record')
def make_draft_policy(name):
 draft_name,_,count,decision,_=CONFIG[name]; dp=REVIEW/draft_name; d=read_json(dp)
 return {'policyFile':name,'schema':1,'status':'root-reviewed primary assignments only','expectedCaseCount':count,'expectedDecision':decision,'sourceInputPaths':{**d['sourceInputPaths'],'immutableRootPolicyDraft':dp.relative_to(ROOT).as_posix()},'sourceHashes':{**d['sourceHashes'],'immutableRootPolicyDraft':sha(dp)},'cases':[c for c in d['cases'] if c['expectedDecision']==decision]}
def main():
 p=argparse.ArgumentParser(description=__doc__); p.add_argument('policyFile',choices=sorted(CONFIG)); p.add_argument('--draft',action='store_true'); p.add_argument('--all-drafts',action='store_true'); a=p.parse_args()
 verify_partition(); names=sorted(CONFIG) if a.all_drafts else [a.policyFile]
 result=[verify_policy(make_draft_policy(n) if a.draft or a.all_drafts else read_json(CERT/n),draft=a.draft or a.all_drafts) for n in names]
 print(json.dumps({'technicalGate':'passed','results':result,'semanticApprovalGranted':False},ensure_ascii=False,sort_keys=True))
if __name__=='__main__': main()
