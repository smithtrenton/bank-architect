#!/usr/bin/env python3
"""Verify provenance and detached approval for the exact supplemental66 cohort."""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
CERT = Path(__file__).resolve().parent
NAME = 'farming-supplemental-approved-policy.json'
HERBS = set(range(5291, 5305))
SPECIAL = {5317,13657,22875,22881,22883,22885}
SEEDLINGS = {5358,5359,5360,5361,5362,5363,5364,5365,5366,5367,5368,5369,5480,5481,5482,5483,5484,5485,5486,5487,5488,5489,5490,5491,5492,5493,5494,5495,21469,21471,21473,21475,22848,22850,22852,22854,22862,22864,23655,23657,31490,31492,31494,31496,31498,31500}
IDS = HERBS | SPECIAL | SEEDLINGS
PATHS = {
 'articleIndex':'tmp/category-certification/wiki-articles/article-index.json',
 'materialsPacket':'tmp/category-certification/reviewer-packets/skilling-farming.jsonl',
 'literalPacket':'tmp/category-certification/reviews/materials-positive-cohorts/20261003-farming-seed-literal-v2/root-review-packet.json',
 'immutableSourceDraft':'tmp/root-review/farming-supplemental-66-unchanged-primary-draft.json',
 'rootReadRecord':'tmp/category-certification/root-review/farming-supplemental66-root-source-read.json',
 'immutableRootPolicyDraft':'tmp/category-certification/root-review/farming-supplemental66-root-policy-draft.json',
 'independentReview':'tmp/root-review/farming-supplemental-66-independent-review-v1.json',
}

def digest(p):
 return hashlib.sha256(p.read_bytes()).hexdigest()

def read(p):
 return json.loads(p.read_text(encoding='utf-8-sig'))

def require(condition,message):
 if not condition: raise ValueError(message)

def verify_policy(policy, *, draft=False):
 require(policy.get('schema')==1 and policy.get('expectedCaseCount')==66,'Wrong schema/count')
 require(policy.get('status')=='root-reviewed primary assignments only','No explicit root approval status')
 if not draft:
  path=CERT/NAME
  require(read(path)==policy,'Passed policy is not saved approved policy')
  approvals=read(CERT/'root-policy-approvals.json')
  require(approvals.get('schema')==1 and approvals.get('status')=='root-reviewed exact policy pins','Bad detached approvals')
  approval=approvals['approvedPolicies'][NAME]
  canonical=hashlib.sha256(json.dumps(policy,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()).hexdigest()
  require(digest(path)==approval['sha256'] and canonical==approval['canonicalSha256'],'Detached policy content differs')
  require(approval['approvedItemIds']==sorted(IDS) and approval['caseCount']==66 and approval['decision']=='certify','Detached cohort differs')
 require(policy.get('sourceInputPaths')==PATHS,'Changed fixed source input paths')
 require(set(policy.get('sourceHashes',{}))==set(PATHS),'Changed source pin keys')
 for key,path in PATHS.items():
  require(digest(ROOT/path)==policy['sourceHashes'][key],'Pinned input changed: '+key)
 immutable=read(ROOT/PATHS['immutableRootPolicyDraft'])
 require(policy['cases']==immutable['cases'],'Reviewed case contents changed')
 source_draft=read(ROOT/PATHS['immutableSourceDraft'])
 drafts={r['itemId']:r for r in source_draft['cases']}
 require(len(drafts)==66 and set(drafts)==IDS,'Source draft cohort changed')
 ids=[r['itemId'] for r in policy['cases']]
 require(len(ids)==66 and set(ids)==IDS,'Approved exact cohort changed')
 index=read(ROOT/PATHS['articleIndex'])
 packets={r['itemId']:r for r in map(json.loads,(ROOT/PATHS['materialsPacket']).read_text(encoding='utf-8-sig').splitlines())}
 rows=read(ROOT/PATHS['literalPacket'])['rows']
 require(len(rows)==150 and len({r['itemId'] for r in rows})==150,'Literal packet scope changed')
 read_record=read(ROOT/PATHS['rootReadRecord'])
 require(set(read_record['exactIds'])==IDS and read_record['ownCaseDefinitionsAndSelectedStateFactsRead']==66,'Root read record changed')
 independent=read(ROOT/PATHS['independentReview'])
 require(set(independent['examinedIds'])==IDS and independent['proposalSha256']==policy['sourceHashes']['immutableSourceDraft'] and not independent['confirmedRouteExceptions'],'Independent review boundary changed')
 require(len(independent['candidateFindings'])==66 and {r['itemId'] for r in independent['candidateFindings']}==IDS,'Independent review rows changed')
 secondary=0
 for case in policy['cases']:
  ident=case['itemId']; d=drafts[ident]; source=index[case['title']]
  require(ident in source['exactInfoboxItemIds'] and str(ident) in source['variants'],'Missing exact own ID')
  require((case['title'],case['sourceRevision'],case['sourceSha256'])==(d['title'],source['revid'],source['sha256']),'Own source binding changed')
  path=ROOT/source['path'];require(digest(path)==source['sha256'],'Raw source changed')
  raw=path.read_bytes().decode('utf-8'); variant=source['variants'][str(ident)]; params=variant['params']
  require(str(variant.get('suffix') or '')==str(d['variantSuffix'] or ''),'Exact variant suffix changed')
  require(d['exactRawIdField'] in raw,'Exact raw ID line missing')
  st,en=d['ownDefinitionSourceOffsets']; require(raw[st:en]==case['semanticExcerpt']==d['ownDefinitionExcerpt'],'Own definition slice changed')
  selected=d['selectedActiveStateFacts']; expected=[]
  for key in ['id','name','version','examine','options','equipable','stackable','tradeable','quest','noteable']:
   field=selected['selectedFields'].get(key,key)
   if field and selected.get(key) is not None:
    require(str(params.get(field))==str(selected[key]),'Selected exact fact differs: '+str(ident)+'/'+key)
    expected.append({'field':field,'value':str(selected[key])})
  require(case['exactVariantFacts']==expected,'Exact facts differ from reviewed draft')
  require(selected['id']==str(ident) and selected['equipable']=='No' and selected['quest']=='No' and selected['options']=='Drop','Selected own active state changed')
  require(selected['stackable']==('No' if ident in SEEDLINGS else 'Yes'),'Seed/seedling stack state changed')
  quotes=[q['text'] for q in d['competingContextCitations']]
  require(case['secondaryExcerpts']==quotes,'Material contexts changed')
  for q in d['competingContextCitations']:
   require(raw[q['sourceStartChar']:q['sourceEndChar']]==q['text'],'Material context is not literal')
  secondary+=len(quotes)
  positive=case['positiveFunctionExcerpt'];require(positive in [case['semanticExcerpt']]+quotes,'Positive function not own-source citation')
  require('farming' in positive.casefold(),'No own Farming function clause')
  target={'category':'FARMING','subcategory':'herb-seed' if ident in HERBS else 'farming','ironmanTabKey':'herblore' if ident in HERBS else 'seeds-farming'}
  require(d['currentPrimaryRoute']==d['proposedPrimaryRoute']=={k:packets[ident]['current'][k] for k in target}==target,'Only reviewed unchanged primary route allowed')
  require((case['proposedCategory'],case['proposedSubcategory'])==(target['category'],target['subcategory']),'Approved target differs')
  require(not case.get('addedRoles') and not case.get('proposedTags') and not case.get('tagEvidence'),'Secondary roles/tags not approved')
 return {'technicalGate':'passed','recordedRootApproval':not draft,'exactIdsVerified':66,'secondaryLiteralCitationsVerified':secondary,'scope':'Primary assignments only; existing tags retained, supplemental roles unassessed'}

def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('policy',type=Path);p.add_argument('--draft',action='store_true');a=p.parse_args()
 print(json.dumps(verify_policy(read(a.policy),draft=a.draft),sort_keys=True))

if __name__=='__main__':main()
