import json,pathlib,hashlib,glob,collections,re
ROOT=pathlib.Path.cwd(); RR=ROOT/'tmp/category-certification/root-review'; REV=ROOT/'tmp/category-certification/reviews/root-review'; CO=REV/'clue-cosmetic-semantic-240-v1'; CAND=REV/'clue-residual284-root-draft-v1/candidates.jsonl'; INDEX=ROOT/'tmp/category-certification/wiki-articles/article-index.json'; OUT=RR/'clue-cosmetic240-independent-adversarial-v1.json'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
norm=lambda s:s.replace('\r\n','\n').replace('\r','\n')
idx=json.loads(INDEX.read_text(encoding='utf-8')); candidates=[json.loads(x) for x in CAND.read_text(encoding='utf-8').splitlines() if x]; scope={x['itemId']:x for x in candidates if x['currentPrimaryRoute']=={'category':'CLUE','subcategory':'cosmetic','ironmanTabKey':'clues-cosmetics'}}
read_files=sorted(glob.glob(str(RR/'clue-cosmetic240-main-thread-read-*-v1.json')),key=lambda x:min(json.loads(pathlib.Path(x).read_text(encoding='utf-8'))['readPacketPositions']))
read_packets=[json.loads(pathlib.Path(x).read_text(encoding='utf-8')) for x in read_files]; read_cases={c['itemId']:c for p in read_packets for c in p['cases']}
readpos={c['itemId']:c['cosmeticPacketPosition'] for p in read_packets for c in p['cases']}
root230=json.loads((RR/'clue-cosmetic230-immutable-root-policy-draft-v1.json').read_text(encoding='utf-8')); root10=json.loads((RR/'clue-cosmetic10-immutable-root-policy-draft-v1.json').read_text(encoding='utf-8'))
policies={c['itemId']:c for c in root230['cases']+root10['cases']}
findings={json.loads(x)['itemId']:json.loads(x) for x in (CO/'findings.jsonl').read_text(encoding='utf-8').splitlines() if x}; follow={json.loads(x)['itemId']:json.loads(x) for x in (CO/'followup-16.jsonl').read_text(encoding='utf-8').splitlines() if x}; integrated={json.loads(x)['itemId']:json.loads(x) for x in (CO/'integration-corrections-10.jsonl').read_text(encoding='utf-8').splitlines() if x}
errors=[]; audits=[]
for i,cand in sorted(scope.items(),key=lambda z:readpos.get(z[0],999)):
 rr=read_cases.get(i); pol=policies.get(i); f=findings.get(i); fo=follow.get(i); integ=integrated.get(i)
 if not all([rr,pol,f]):errors.append({'itemId':i,'failure':'missing candidate/read/policy/finding'});continue
 src=rr; ent=idx.get(src['title']);
 if not ent:errors.append({'itemId':i,'failure':'article-index title missing'});continue
 rawpath=ROOT/ent['path']; raw=rawpath.read_text(encoding='utf-8'); raw_norm=norm(raw)
 def check_quote(q,label):
  if not q or norm(q) not in raw_norm:errors.append({'itemId':i,'failure':'literal not exact raw substring','field':label})
 sourcehash=sha(rawpath); sh=src['sourceSha256']; rev=src['sourceRevision']; variant=ent.get('variants',{}).get(str(i))
 if sourcehash!=sh or ent['sha256']!=sh or ent['revid']!=rev:errors.append({'itemId':i,'failure':'source SHA/revision/index mismatch'})
 if variant is None or i not in ent.get('exactInfoboxItemIds',[]):errors.append({'itemId':i,'failure':'exact item variant or infobox ID absent'})
 for q in src.get('ownDefinitionAndUniqueContextsRead',[]):check_quote(q,'rootReadExcerpt')
 for q in [pol.get('semanticExcerpt',''),pol.get('positiveFunctionExcerpt','')]:check_quote(q,'draftPredicateExcerpt')
 for q in pol.get('secondaryExcerpts',[]):check_quote(q,'draftCompetingContext')
 for q in src.get('ownDefinitionAndUniqueContextsRead',[]):
  if not q:errors.append({'itemId':i,'failure':'empty own-source excerpt'})
 # Independently bind every read state field to this exact parsed Item variant.
 params=variant.get('params',{}) if variant else {}; readfacts={x['field']:x['value'] for x in src.get('exactVariantFactsRead',[])}
 for k,v in readfacts.items():
  if str(params.get(k,''))!=str(v):errors.append({'itemId':i,'failure':'exact state differs from pinned variant facts','field':k,'read':v,'source':params.get(k)})
 # Immutable proposal and source-read record must agree with frozen candidate ID, source pin, and exact route.
 if cand['exactSource']['title']!=pol['title'] or cand['exactSource']['revision']!=pol['sourceRevision'] or cand['exactSource']['sha256'].removeprefix('sha256:')!=pol['sourceSha256'] or cand['exactSource']['title']!=src['title']:errors.append({'itemId':i,'failure':'candidate/policy/read source binding mismatch'})
 expected_root_decision='revise' if integ else 'certify'
 if f['currentPrimaryRoute']!=cand['currentPrimaryRoute'] or pol['expectedDecision']!=expected_root_decision:errors.append({'itemId':i,'failure':'frozen current route or root decision mismatch'})
 finaldecision=fo['decision'] if fo else f['decision']; finalroute=integ['proposedRoute'] if integ else pol['proposedCategory']
 if finaldecision=='support':
  target={'category':'CLUE','subcategory':'cosmetic','ironmanTabKey':'clues-cosmetics'}
  if pol['proposedCategory']!='CLUE' or pol['proposedSubcategory']!='cosmetic' or pol['proposedIronmanTabKey']!='clues-cosmetics':errors.append({'itemId':i,'failure':'support draft route mismatch'})
  positive=norm(pol.get('positiveFunctionExcerpt','')).lower(); modal=any(x in positive for x in ['would have','would be','proposed reward','failed poll','unobtainable','cache-only'])
  # Function is the item itself presented/worn or actively applied to change the named item appearance.
  direct_cosmetic=any(x in positive for x in ['cosmetic','appearance','decorat','headwear','clothing','wear','ornament kit','outfit'])
  exact_state={z['field']:z['value'] for z in pol.get('exactVariantFacts',[])}
  if modal or not direct_cosmetic:errors.append({'itemId':i,'failure':'support predicate is counterfactual or not a direct appearance function','excerpt':pol.get('positiveFunctionExcerpt','')[:220]})
  if 'equipable' in exact_state and exact_state['equipable']=='Yes' and 'wear' not in str(exact_state.get('options','')).lower() and 'ornament kit' not in positive.lower():errors.append({'itemId':i,'failure':'wearable claim lacks exact Wear option'})
  disposition='RETAIN_CLUE_COSMETIC'
 elif integ:
  target=integ['proposedRoute']; disposition='CORRECT_'+target['category']+'_'+target['subcategory']
 else:errors.append({'itemId':i,'failure':'non-support row lacks final correction packet'});target=None;disposition='UNRESOLVED'
 quote=pol.get('positiveFunctionExcerpt') or pol.get('semanticExcerpt')
 audit={'packetPosition':readpos.get(i),'itemId':i,'title':pol['title'],'sourceRevision':rev,'sourceSha256':sh,'currentRoute':cand['currentPrimaryRoute'],'decision':finaldecision,'proposedRoute':target,'positiveFunctionLiteral':quote,'exactVariantFacts':pol.get('exactVariantFacts',[]),'sourceReadExcerpts':src.get('ownDefinitionAndUniqueContextsRead',[]),'competingContexts':pol.get('secondaryExcerpts',[]),'rootReadLabel':src.get('rootSemanticJudgement'),'independentDisposition':disposition,'notes':pol.get('rationale')}
 audits.append(audit)
expected_ids=set(scope); final_ids={x["itemId"] for x in audits}
for label,expected,actual in [('read',expected_ids,set(read_cases)),('policy',expected_ids,set(policies)),('finding',expected_ids,set(findings))]:
 if expected!=actual:errors.append({'failure':label+' set mismatch','missing':sorted(expected-actual),'extra':sorted(actual-expected)})
if len(audits)!=240 or len(final_ids)!=240:errors.append({'failure':'case total/unique count mismatch','audits':len(audits),'unique':len(final_ids)})
if set(follow)!={2639,2641,2643,12321,12323,12325,7581,7582,7583,7584,7585,26707,26709,26713,26717,27121}:errors.append({'failure':'followup scope mismatch','ids':sorted(follow)})
if set(integrated)!={7581,7582,7583,7584,7585,26707,26709,26713,26717,27121}:errors.append({'failure':'integration correction scope mismatch','ids':sorted(integrated)})
for i in [7581,7582,7583,7584,7585]:
 c=policies.get(i,{}); q=' '.join(c.get('secondaryExcerpts',[]));
 hraw=(ROOT/read_cases[i]['sourcePath']).read_text(encoding='utf-8')
 if '|text1 = Follower' not in hraw or not any(f'|id{n} = {i}' in hraw for n in range(1,6)):errors.append({'itemId':i,'failure':'hellcat exact item/follower infobox binding absent'})
 if 'No Collection Log membership is claimed' not in c.get('rationale',''):errors.append({'itemId':i,'failure':'Collection Log caveat absent'})
for i in [26707,26709,26713,26717,27121]:
 c=policies.get(i,{}); q=norm(c.get('semanticExcerpt','')).lower(); pos=norm(c.get('positiveFunctionExcerpt','')).lower()
 if not any(x in q for x in ['was a proposed reward','would have been']) or 'failed poll' not in pos:errors.append({'itemId':i,'failure':'cached kit missing counterfactual/failed-poll proof'})
counts=collections.Counter(x['independentDisposition'] for x in audits)
# Every final quote, state, competing context, and source pin above is retained per case for audit replay.
report={'schema':'clue-cosmetic240-independent-adversarial-readonly-v1','status':'independent candidate audit; no policy approval, ledger application, production edit, or Git change','sourceInputs':{
 'candidatePacket':{'path':str(CAND.relative_to(ROOT)),'sha256':sha(CAND)},'articleIndex':{'path':'tmp/category-certification/wiki-articles/article-index.json','sha256':sha(INDEX)},
 'immutableDraft230':{'path':'tmp/category-certification/root-review/clue-cosmetic230-immutable-root-policy-draft-v1.json','sha256':sha(RR/'clue-cosmetic230-immutable-root-policy-draft-v1.json')},'immutableDraft10':{'path':'tmp/category-certification/root-review/clue-cosmetic10-immutable-root-policy-draft-v1.json','sha256':sha(RR/'clue-cosmetic10-immutable-root-policy-draft-v1.json')},
 'readRecordFiles':[{'path':str(pathlib.Path(x).relative_to(ROOT)),'sha256':sha(pathlib.Path(x))} for x in read_files], 'findings':{'path':str((CO/'findings.jsonl').relative_to(ROOT)),'sha256':sha(CO/'findings.jsonl')},'followup16':{'path':str((CO/'followup-16.jsonl').relative_to(ROOT)),'sha256':sha(CO/'followup-16.jsonl')},'integrationCorrections10':{'path':str((CO/'integration-corrections-10.jsonl').relative_to(ROOT)),'sha256':sha(CO/'integration-corrections-10.jsonl')}},
 'scope':{'frozenCandidateRows':284,'exactCLUECosmeticRows':240,'uniqueExaminedIds':len(final_ids),'sourceReadCases':len(read_cases),'finalRootDraftCases':len(policies),'candidateCurrentRoute':'CLUE/cosmetic -> clues-cosmetics','finalDecisionCounts':dict(collections.Counter((fo['decision'] if (fo:=follow.get(i)) else findings[i]['decision']) for i in expected_ids)),'independentDispositionCounts':dict(counts),'expectedFinalPartition':{'CLUE/cosmetic':230,'CLUE/collection-pet':5,'CLEANUP/cleanup':5}},
 'auditMethod':'For every packet position, replayed the pinned exact numeric item ID against raw revision bytes, exact article-index variant and selected state; checked root full-page excerpts, positive function quote, and all competing contexts as literal substrings. Tested active appearance predicate against counterfactual language; checked frozen current route and final proposed route. No source excerpt, category facet, reward origin, role, or tag is treated as proof by itself.',
 'exceptionFindings':{'hellcatIds':[7581,7582,7583,7584,7585],'disposition':'CLUE/collection-pet candidate; exact item variant maps to the same-index NPC follower form; article also documents cosmetic morphing, age, quest/rathunting and interaction context. No collection-log membership, NPC combat stats, or cross-form behavior inherited.','failedPollKitIds':[26707,26709,26713,26717,27121],'disposition':'CLEANUP/cleanup candidate; own pages mark the entries cached/failed-poll, with proposed/would-have ornament behavior. That is counterfactual, not a live item function; do not inherit actual ornament behavior from other kits or base equipment.'},
 'confirmedPrimaryExceptions':[],'unresolvedPrimaryCases':[],'integrityFailures':errors,'integrityFailureCount':len(errors),'caseAudits':audits}
OUT.parent.mkdir(parents=True,exist_ok=True); OUT.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8');print(json.dumps({'output':str(OUT),'sha256':sha(OUT),'caseCount':len(audits),'integrityFailureCount':len(errors),'counts':dict(counts),'errors':errors[:20]},ensure_ascii=False,indent=2))



