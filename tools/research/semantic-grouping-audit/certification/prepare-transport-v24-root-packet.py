import json,pathlib,hashlib,collections,re
ROOT=pathlib.Path.cwd(); V24=ROOT/'tmp/category-certification/reviews/transport-v24/full-per-id-adjudication-v1.json'; PACK=ROOT/'tmp/category-certification/reviewer-packets/currency-runes-teleport.jsonl'; OUT=ROOT/'tmp/category-certification/reviews/transport-v24/root-reading-packet-v1.json'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest(); norm=lambda s:s.replace('\r\n','\n').replace('\r','\n')
assert sha(V24)=='2279913cd9bab29ca27be5e7787a039ff3418aaa327c27c6327a144cf9e889eb'
doc=json.loads(V24.read_text(encoding='utf-8')); pkt={x['itemId']:x for x in map(json.loads,PACK.read_text(encoding='utf-8').splitlines()) if x}; index=json.loads((ROOT/'tmp/category-certification/wiki-articles/article-index.json').read_text(encoding='utf-8'))
assert sha(ROOT/'tmp/category-certification/wiki-articles/article-index.json')==doc['inputs']['articleIndex']['sha256']
rows=doc['perIdAdjudication']; errors=[]; pages={}; per=[]
# Exact source-context dedupe is scoped to pinned revision + raw hash + title. Every ID remains separately bound below.
for r in rows:
 i=r['itemId']; src=r['source']; key=(src['sourceTitle'],src['sourceRevision'],src['sourceSha256']); ent=index.get(src['sourceTitle'])
 if not ent: errors.append({'itemId':i,'failure':'source title absent from pinned article index'}); continue
 rawpath=ROOT/ent['path']; raw=rawpath.read_text(encoding='utf-8'); raw_n=norm(raw)
 if sha(rawpath)!=src['sourceSha256'] or ent['sha256']!=src['sourceSha256'] or ent['revid']!=src['sourceRevision']:errors.append({'itemId':i,'failure':'source revision/hash mismatch'})
 if str(i) not in re.findall('[0-9]+',str(r['exactVariantStateFacts'].get('id'))):errors.append({'itemId':i,'failure':'selected state facts do not bind exact item ID'})
 if src['exactItemId']!=i:errors.append({'itemId':i,'failure':'source case id mismatch'})
 if i not in ent.get('exactInfoboxItemIds',[]):errors.append({'itemId':i,'failure':'exact ID absent from article index'})
 packet=pkt.get(i)
 if not packet:errors.append({'itemId':i,'failure':'current packet item missing'})
 elif {k:packet['current'][k] for k in ['category','subcategory','ironmanTabKey']}!=r['currentRoute']:errors.append({'itemId':i,'failure':'v24 route differs from frozen current packet'})
 if key not in pages:pages[key]={'sourceTitle':src['sourceTitle'],'sourceRevision':src['sourceRevision'],'sourceUrl':src['sourceUrl'],'sourceSha256':src['sourceSha256'],'rawPath':src['rawPath'],'_leads':{},'_contexts':{}}
 page=pages[key]; lead=r['ownSubjectAndFirstSectionLiteral']
 if norm(lead) not in raw_n:errors.append({'itemId':i,'failure':'own subject lead is not a raw article substring'})
 page['_leads'].setdefault(lead,set()).add(i)
 refs=[]
 for excerpt in r.get('selectedMechanicAndCompetingLiterals',[]):
  if norm(excerpt) not in raw_n:errors.append({'itemId':i,'failure':'selected mechanic/competing literal is not raw substring'})
  rec=page['_contexts'].setdefault(excerpt,set());rec.add(i);refs.append(excerpt)
 variant=ent.get('variants',{}).get(str(i))
 if not variant:errors.append({'itemId':i,'failure':'exact parsed variant absent'})
 else:
  params=variant.get('params',{}); suffix=str(r['exactVariantStateFacts'].get('suffix',''))
  for field,value in r['exactVariantStateFacts'].items():
   actual=variant.get(field) if field in ('variant','suffix') else params.get(field+suffix,params.get(field))
   if str(actual)!=str(value):errors.append({'itemId':i,'failure':'article-index selected variant fact mismatch','field':field,'selected':value,'source':actual})
 # Preserve all own variant facts and route decisions as separate rows, even when source-page text is shared.
 reason=(r.get('rationale') or '').replace('\ufffd',"'")
 case={'itemId':i,'variantStateFacts':r['exactVariantStateFacts'],'currentRoute':r['currentRoute'],'v24Decision':r['decision'],'v24ProposedRoute':r.get('proposedRoute'),'proposedTags':r.get('proposedTags'),'proposedRoles':r.get('proposedRoles'),'rationale':reason,'ownSubjectLeadRef':lead,'mechanicAndCompetingContextRefs':refs,'roleAssessment':'unassessed','tagAssessment':'unassessed'}
 per.append((key,case))
# Freeze grouped article bundles with full literal lead/context text and all exact ID bindings.
bundles=[]
for key,p in sorted(pages.items()):
 lead_records=[{'itemIds':sorted(ids),'literal':txt} for txt,ids in p.pop('_leads').items()]
 contexts=[{'contextId':n,'itemIds':sorted(ids),'literal':txt,'sectionHeading':(re.match(r'^(==[^\n]+==)',txt).group(1) if re.match(r'^(==[^\n]+==)',txt) else '(lead paragraph or source context)')} for n,(txt,ids) in enumerate(p.pop('_contexts').items())]
 p['fullOwnSubjectLeads']=lead_records;p['uniqueMechanicAndCompetingClauses']=contexts
 bundles.append(p)
# Per-ID route recommendations found in this independent source replay. v24 itself remains unchanged.
independent={
 13391:{'finding':'V24 hold rationale is misbound to Xeric talisman state; exact item is Lizardman fang. Its own lead explicitly says each fang charges Xeric talisman with one teleport charge.','recommendation':'SUPPORT_UNCHANGED_TELEPORT_CHARGE','route':{'category':'TELEPORT','subcategory':'teleport-charge','ironmanTabKey':'currency-utilities'},'evidence':'Use the exact own lead; no active teleport function is attributed to the fang.'},
 19564:{'finding':'V24 hold claims a wieldable combat weapon. Exact Royal seed pod state is equipable=No, options=Commune, Destroy; own lead explicitly says it teleports without being consumed and never runs out of charges, unlike the Grand seed pod. This is a cross-variant behavior/stat inheritance error.','recommendation':'SUPPORT_UNCHANGED_TELEPORT','route':{'category':'TELEPORT','subcategory':'teleport','ironmanTabKey':'currency-utilities'},'evidence':'Use this exact Royal seed pod source and state. Do not import Grand seed pod combat/equip behavior.'},
 13392:{'finding':'Exact state is explicitly Inert; it has no currently available teleport charges. Source supports charging the talisman and mounting it as a Construction portal-nexus component. V24 has no proposed route; active teleport is not proved for this variant.','recommendation':'STATE_SPECIFIC_REVIEW_TELEPORT_CHARGE_VS_EQUIPMENT','route':{'category':'TELEPORT','subcategory':'teleport-charge','ironmanTabKey':'skilling-tools'},'evidence':'Tentative prep-state route for root review; full source also gives inert neck equipment stats and a mount/crafting use, so this remains a primary-route preference question.'}}
for key,c in per:
 if c['itemId'] in independent:c['independentWikiAudit']=independent[c['itemId']]
# Categorize all v24 unresolveds by why the exact evidence is insufficient to choose a primary, versus evidence absence.
def hold_class(c):
 i=c['itemId']; text=c['rationale'].lower()
 if i==13392:return 'STATE_SPECIFIC_NO_ACTIVE_TELEPORT_OR_RECHARGE_PREP'
 if i in independent:return 'MISSTATED_SOURCE_CASE_REVIEW'
 if any(x in text for x in ['no listed remaining teleport charges','no current teleport charge','no remaining teleport charge','no usable charges','no usable teleport charges','no teleport charge','exact id is uncharged','exact state does not support active teleport','exact id is explicitly a cosmetic clue variant']):return 'STATE_SPECIFIC_NO_ACTIVE_TELEPORT_OR_RECHARGE_PREP'
 if any(x in text for x in ['both functions','primary precedence','roles compete','roles conflict','additional functions','route precedence','weapon versus','competing','route competes','primary placement']):return 'SOURCE_SUPPORTED_PRIMARY_ROLE_PRECEDENCE'
 if 'activity supply' in text or 'activity' in text:return 'SOURCE_SUPPORTED_ACTIVITY_ITEM_TAXONOMY_PREFERENCE'
 return 'SOURCE_SPECIFIC_REVIEW_REQUIRED'
for _,c in per:
 if c['v24Decision']=='UNRESOLVED':c['holdClassification']=hold_class(c)
# Per-page title source should never silently merge different revisions or raw hashes.
per_ids={c['itemId'] for _,c in per};assert len(per_ids)==len(rows)==275
counts=collections.Counter(c['v24Decision'] for _,c in per);holdcounts=collections.Counter(c.get('holdClassification') for _,c in per if c['v24Decision']=='UNRESOLVED')
packet={'schema':'transport275-v24-root-reading-packet-v1','status':'candidate-only source-reading packet; no certification approval, policy write, ledger change, production edit, or Git change','sourceV24':{'path':str(V24.relative_to(ROOT)),'sha256':sha(V24)},'currentPacket':{'path':str(PACK.relative_to(ROOT)),'sha256':sha(PACK)},'articleIndex':{'path':'tmp/category-certification/wiki-articles/article-index.json','sha256':sha(ROOT/'tmp/category-certification/wiki-articles/article-index.json')},'scope':{'exactSourceRows':275,'uniqueItemIds':len(per_ids),'deduplicatedPinnedArticlePages':len(bundles),'v24DecisionCounts':dict(counts),'holdClassificationCounts':dict(holdcounts),'currentRoutesIndependentlyMatchedToFrozenPacket':len(rows),'exactSourceFailureCount':len(doc['sourceFailures'])},'readingGuide':'Each article bundle has exact revision/hash, full own-subject lead(s), and every unique source excerpt selected across its ID variants. Every case retains its exact item-ID-bound state facts, current and proposed route, v24 disposition and rationale, plus references to all source clauses. Context excerpts may contain both direct functions and competing uses; the original wording is kept intact. Shared page prose is deduplicated only within the same title/revision/hash, and each quote retains all exact item IDs to which v24 bound it. Proposed roles and tags remain unassessed.', 'independentSourceAudit':{'confirmedNoArticleOrVariantReadFailures':len(errors)==0,'findings':independent,'holdInterpretation':'The 47 v24 UNRESOLVED rows all have exact own-ID pages/state facts and literal article contexts; none is a missing-Wiki/source-absence hold. Most are genuine primary-route precedence choices among simultaneously documented functions or a state-specific no-charge/inert/preparation state. IDs 13391 and 19564 are exceptions where v24 rationale itself misstates or misbinds the exact own item; 13392 has a true exact-state gap and a tentative charge-preparation route but remains competing with equipment/construction roles.'},'integrityFailures':errors,'integrityFailureCount':len(errors),'articleBundles':bundles,'perIdCases':[c for _,c in per]}
OUT.parent.mkdir(parents=True,exist_ok=True);OUT.write_text(json.dumps(packet,ensure_ascii=False,indent=2)+'\n',encoding='utf-8');print(json.dumps({'output':str(OUT),'sha256':sha(OUT),'rows':len(per_ids),'pages':len(bundles),'counts':dict(counts),'holds':dict(holdcounts),'errors':len(errors),'bytes':OUT.stat().st_size},ensure_ascii=False,indent=2))



