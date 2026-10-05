#!/usr/bin/env python3
"""Build a source-bound review packet for non-clue CLUE/UNIQUE certificates."""
import argparse, collections, hashlib, json, re
from pathlib import Path
ROOT=Path(__file__).resolve().parents[4]
FULL=ROOT/'tmp/category-certification/reviews/collections/clue-unique-corrected.jsonl'
ROOT_DEC=ROOT/'tmp/category-certification/reviews/root-clue-scrolls/decisions.jsonl'
INDEX=ROOT/'tmp/category-certification/wiki-articles/article-index.json'
OUT=ROOT/'tmp/category-certification/reviews/collections/root-review-packet.json'

def read_jsonl(p): return [json.loads(x) for x in p.read_text(encoding='utf-8').splitlines() if x.strip()]
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def param_id_binding(params,item_id):
 return [(k,str(v)) for k,v in params.items() if re.fullmatch(r'id\d*',k,re.I) and str(v).isdigit() and int(v)==item_id]
def article_map(index):
 m=collections.defaultdict(list)
 for title,a in index.items():
  for i in a.get('exactInfoboxItemIds',[]): m[int(i)].append((title,a))
 return m

def excerpts(text):
 # Keep representative exact source lines; every excerpt is copied verbatim.
 needles=re.compile(r"(?i)(?:used to|used on|used with|can be used|opens?|contains?|unlocks?|is a .*? clue|obtained from .*?treasure trails|treasure trails|collection log items|display|mounted|stuffed|cosmetic|decorative|no combat bonuses|follows the player|can follow the player|rewarded upon|key opens|reward bag|upgrade items|can be turned into|used alongside|combine|charges|read(?:ing)? .*? unlock|quest item|warm clothing|protect(?:s|ion)? .*?heat|enhance .*?emote)")
 return [line.strip() for line in text.splitlines() if len(line.strip())<850 and needles.search(line)][:5]

FUNCTION=re.compile(r"(?i)\b(?:used|use|opens?|opening|contains?|unlocks?|unlock|allows?|allow|can be|can follow|follow the player|is a clue|is (?:an? )?(?:cryptic|coordinate|emote|map|anagram|music|cipher) clue|equipable|equipped|worn|wear|display|mounted|stuffed|restored|combine|created|crafted|required to|enhance|decorative|cosmetic|protect|summon|consume|consumed|reward bag|reward chest|chest opens|key opens|charges|follower|pet companion)\b")
FACET=re.compile(r"(?i)\[\[Category:(?:Collection log items|Upgrade items|Texts and tomes)|Category:Collection log items|Category:Upgrade items")
ACQ=re.compile(r"(?i)\b(?:possible )?reward(?:ed)?|obtained from|drop from|completing .*?treasure trails|category:collection log items")

def support_class(quote):
 if FACET.search(quote): return 'facet_or_template_only_citation'
 if FUNCTION.search(quote): return 'direct_mechanic_or_subject_function_excerpt'
 if ACQ.search(quote): return 'acquisition_or_reward_only_excerpt'
 return 'generic_examine_or_descriptive_excerpt_needs_context'

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--output',type=Path,default=OUT);a=ap.parse_args()
 rows=read_jsonl(FULL); rootrows=read_jsonl(ROOT_DEC); rootids={r['itemId'] for r in rootrows if r['decision']=='certify'}
 index=json.loads(INDEX.read_text(encoding='utf-8')); byid=article_map(index)
 cert=[r for r in rows if r['decision']=='certify']; candidates=[r for r in cert if r['itemId'] not in rootids]
 allcounts=collections.Counter((r['proposedCategory'],r['proposedSubcategory']) for r in cert)
 candcounts=collections.Counter((r['proposedCategory'],r['proposedSubcategory']) for r in candidates)
 item_rows=[];weak=[];facet_only=[];pet=[]
 weak_token_re=re.compile(r'\b(?:used|use|opens?|opening|contains?|unlocks?|unlock|allows?|allow|can be|can follow|is a clue|is an? (?:cryptic|coordinate|emote|map|anagram|music|cipher) clue|equipable|equipped|worn|wear|display|mounted|stuffed|restored|combine|created|crafted|required to|enhance|decorative|cosmetic|protect|summon|consume|consumed|reward bag|reward chest|rewards?|drop|obtained|obtaining|pet)\b',re.I)
 forced_weak_ids={31732,31744,31756,7981}
 for r in candidates:
  i=int(r['itemId']); evs=[e for e in r.get('evidence',[]) if e['kind']=='exact_wiki']; evid=[]
  for e in evs:
   matches=[(t,art) for t,art in byid.get(i,[]) if t==e.get('sourceTitle') and art.get('revid')==e.get('sourceRevision')]
   info={k:e.get(k) for k in ('sourceTitle','source','sourceRevision','sourceHash','quote')}
   info['citationSupportClass']=support_class(e.get('quote',''))
   if len(matches)==1:
    t,art=matches[0]; params=art.get('variants',{}).get(str(i),{}).get('params',{})
    text=(ROOT/art['path']).read_text(encoding='utf-8')
    info['exactInfoboxBinding']={'itemId':i,'boundIdFields':param_id_binding(params,i),'name':params.get('name'),'variant':art.get('variants',{}).get(str(i),{}).get('variant'),'suffix':art.get('variants',{}).get(str(i),{}).get('suffix'),'options':params.get('options'),'equipable':params.get('equipable'),'tradeable':params.get('tradeable'),'explicitBankableField':params.get('bankable')}
    info['articleSupportExcerpts']=excerpts(text)
    info['exactPageItemIds']=list(art.get('exactInfoboxItemIds',[]))
    info['collectionLogAttribution']='exact_single_id_page_facet' if len(art.get('exactInfoboxItemIds',[]))==1 and '[[Category:Collection log items]]' in text else ('shared_multi_id_page_facet_unresolved' if '[[Category:Collection log items]]' in text else 'no_page_facet_found')
    info['sourceContainsCollectionLogFacet']='[[Category:Collection log items]]' in text
    info['sourceContainsUpgradeFacet']='[[Category:Upgrade items]]' in text
   evid.append(info)
  record={'itemId':i,'category':r['proposedCategory'],'subcategory':r['proposedSubcategory'],'tab':r['proposedIronmanTabKey'],'tags':r.get('proposedTags',[]),'roles':r.get('proposedRoles'),'semanticPredicate':r.get('semanticPredicate'),'rationale':r.get('rationale'),'evidence':evid}
  item_rows.append(record)
  classes=[e['citationSupportClass'] for e in evid]
  if classes and (i in forced_weak_ids or not weak_token_re.search(evid[0].get('quote',''))): weak.append(record)
  if any(e['citationSupportClass']=='facet_or_template_only_citation' for e in evid): facet_only.append(record)
  if any(role in (r.get('proposedRoles') or []) for role in ('pet_companion','pet_stage_adult','pet_stage_puppy')):
   pet.append(record)
 rule_defs=[
  {'category':'CLUE/treasure-trail','predicate':'Exact item page directly defines a clue scroll or step, clue tool, or trail-specific mechanical use; reward source, title resemblance, or footer/template alone is not a function.','exceptions':['Quest-scoped or event/interface scrolls require exact state review.','A named clue-step rule requires exact own infobox ID and an item-specific subject lead.']},
  {'category':'CLUE/cosmetic','predicate':'Exact item page establishes a wearable/style/emote appearance function or explicit cosmetic status; zero bonuses, collection-log membership, or treasure-trail origin alone do not establish style retention.','exceptions':['Any stat/prayer/protection/heat/tool/emote/storage function is a separate role and can create primary-placement conflict.','Quest-only wearables remain unresolved under the open retention policy.']},
  {'category':'CLUE/collection-trophy','predicate':'Exact item page documents mounting/stuffing/display as a trophy, or exact collection-log facet only supports a collection-log role.','exceptions':['Category:Collection log items never proves trophy display or primary CLUE placement.','Generic “I should get it stuffed” examine text is insufficient without the direct taxidermy/display mechanic.']},
  {'category':'UNIQUE/reward-container','predicate':'Exact page documents a container that can be opened/searched to yield contents, with current subcategory as container/reward grouping.','exceptions':['Reward origin alone is not proof the item contains/open yields anything.']},
  {'category':'UNIQUE/boss-access-key or reward-key','predicate':'Exact page states the key opens a named chest/access point or is used to enter a challenge.','exceptions':['A key described only as a reward/time threshold needs the page’s actual opens/entry mechanic.']},
  {'category':'UNIQUE/equipment-upgrade or weapon-upgrade','predicate':'Exact page states this exact component transforms/creates/upgrades a named piece of equipment.','exceptions':['[[Category:Upgrade items]] alone is a facet, not a mechanic.']},
  {'category':'UNIQUE/equipment-charge','predicate':'Exact page states charging/imbuing/refilling or a direct charge-consumption relation.','exceptions':['Death behavior of stored charges does not prove primary charge function by itself.']},
  {'category':'CLUE/collection-pet','predicate':'Exact page says this exact item variant is a pet/companion that follows or is summoned; explicit stage/variant state is attached via exact item ID.','exceptions':['Do not propagate companion state, collection-log category or bankability across morph variants. Missing bankable field means unknown.']},
  {'category':'UNIQUE/reward-drop','predicate':'The exact item is an openable reward object and the page directly documents the opening/contents mechanic.','exceptions':['A reward name or reward origin without an opening/contents mechanic is insufficient.']},
  {'category':'UNIQUE/salvaging-relic','predicate':'The exact item page identifies it as a relic recovered by a named salvage activity.','exceptions':['Collection Log facet alone does not establish salvage/relic role; cite the direct salvage relation.']},
 ]
 # Per-ID strict clue rule binding proof, copied from root's direct-variant evidence.
 clueout=[r for r in rootrows if r['decision']=='certify']
 strict_bindings=[]
 for rr in clueout:
  ident=int(rr['itemId']); ev=rr['evidence'][0]
  found=[(t,art) for t,art in byid.get(ident,[]) if t==ev['sourceTitle'] and art['revid']==ev['sourceRevision']]
  if len(found)!=1:
   strict_bindings.append({'itemId':ident,'integrity':'binding_missing_or_ambiguous','evidence':ev}); continue
  title,art=found[0]; text=(ROOT/art['path']).read_text(encoding='utf-8')
  params=art.get('variants',{}).get(str(ident),{}).get('params',{})
  name=params.get('name',''); subject="'''"+name+"'''"; pos=text.find(subject)
  lead=text[pos:].split('\n\n',1)[0] if pos>=0 else ''
  strict_bindings.append({'itemId':ident,'integrity':'exact_article_id_and_raw_infobox_bound','sourceTitle':title,'source':art['sourceUrl'],'sourceRevision':art['revid'],'sourceHash':'sha256:'+art['sha256'],'exactInfoboxItemIds':art.get('exactInfoboxItemIds',[]),'rawBoundIdFields':param_id_binding(params,ident),'rawInfoboxFacts':{k:params.get(k) for k in ['id','name','options','equipable']},'directNamedLead':lead,'hasClueInfoStepContent':'{{Clue info' in text,'rootDecisionEvidence':ev})

 approved_ids=sorted(rootids)
 old_clue=[r for r in cert if 'clue_scroll_item' in (r.get('proposedRoles') or [])]
 rejected_clue=[r for r in old_clue if r['itemId'] not in rootids]
 pet_role_rows=[r for r in pet if 'pet_companion' in (r.get('roles') or [])]
 pet_placement=[r for r in pet_role_rows if r['subcategory']!='collection-pet' and r['itemId']!=12271]
 pet_mismatch=[r for r in pet_role_rows if r['itemId']==12271]
 pet_groups=collections.defaultdict(list)
 for r in pet_placement:
  binding=r['evidence'][0].get('exactInfoboxBinding',{}) if r.get('evidence') else {}
  pet_groups[binding.get('name') or 'unknown'].append(r['itemId'])
 for rule in rule_defs:
  cat,sub=rule['category'].split('/',1)
  subs=[part.strip() for part in sub.split(' or ')]
  rule['frozenCorrectedCertifiedCount']=sum(allcounts.get((cat,part),0) for part in subs)
  rule['otherCandidateCount']=sum(candcounts.get((cat,part),0) for part in subs)
  examples=[]
  for rec in item_rows:
   if rec['category']!=cat or rec['subcategory'] not in subs: continue
   for e in rec['evidence']:
    q=e.get('quote') or ''
    if q and e.get('citationSupportClass')=='direct_mechanic_or_subject_function_excerpt':
     examples.append({'itemId':rec['itemId'],'sourceTitle':e.get('sourceTitle'),'source':e.get('source'),'sourceRevision':e.get('sourceRevision'),'sourceHash':e.get('sourceHash'),'quote':q})
     if len(examples)>=3: break
   if len(examples)>=3: break
  if not examples:
   for rec in item_rows:
    if rec['category']!=cat or rec['subcategory'] not in subs: continue
    for e in rec['evidence']:
     if e.get('quote'):
      examples.append({'itemId':rec['itemId'],'sourceTitle':e.get('sourceTitle'),'source':e.get('source'),'sourceRevision':e.get('sourceRevision'),'sourceHash':e.get('sourceHash'),'quote':e.get('quote')}); break
    if examples: break
  rule['representativeExactItemEvidence']=examples
 packet={'schema':1,'purpose':'Root review of the 1,255 frozen corrected certifications, focusing on the 618 not in the root-approved strict clue-scroll cohort, with exact article and citation context. This packet is research only and changes no production data.','inputHashes':{'correctedFullLedgerSha256':sha(FULL),'rootClueDecisionsSha256':sha(ROOT_DEC),'articleIndexSha256':sha(INDEX)},'totals':{'frozenCorrectedCertified':len(cert),'rootStrictClueCertified':len(clueout),'otherCandidateRows':len(candidates),'otherCandidateCountsByCategorySubcategory':{f'{k[0]}/{k[1]}':v for k,v in sorted(candcounts.items())},'weakCitedExcerpts':len(weak),'facetOrTemplateOnlyCitedExcerpts':len(facet_only),'petRelatedOtherCandidateRows':len(pet),'previousClueRoleRows':len(old_clue),'previousClueRoleRowsOutsideStrictRootRule':len(rejected_clue)},'ruleGroups':rule_defs,'priorFullCertCountsByCategorySubcategory':{f'{k[0]}/{k[1]}':v for k,v in sorted(allcounts.items())},'weakCitationDefinition':'The original 62-row conservative citation scan plus four root-identified cases (#31732, #31744, #31756, #7981). The scan is a citation-strength queue, not a claim that the full article lacks mechanics. Each row includes exact page/revision/hash, exact ID binding, and matching source lines when indexed.','facetOnlyCitationDefinition':'A cited excerpt is itself a collection-log or upgrade-category facet/template. Such a facet can support that one facet role, but does not independently establish primary category or functional use.','strictRootClueBoundRows':strict_bindings,'petRolePlacementReview':{'explicitPetCompanionRowsOutsideCollectionPet':len(pet_placement),'byExactPageSubject':{k:sorted(v) for k,v in sorted(pet_groups.items())},'directRoleButDifferentPrimaryCategoryRows':pet_placement,'falsePetRoleRows':pet_mismatch,'collectionLogFacetCaution':'Phoenix morph item IDs 20693, 24483-24486 share one multi-ID source page categorized as Collection log items; retain companion/morph roles from exact variant evidence but do not attribute the category facet to each variant.'},'weakCitedExcerptRows':weak,'facetOnlyCitedRows':facet_only,'petBindingRows':pet,'other618CandidateRows':item_rows,'previousClueClaimsRejectedByRootRule':[{'itemId':r['itemId'],'sourceTitle':next((e.get('sourceTitle') for e in r.get('evidence',[]) if e['kind']=='exact_wiki'),None),'quote':next((e.get('quote') for e in r.get('evidence',[]) if e['kind']=='exact_wiki'),None),'reason':'Not selected by root’s exact readable named Treasure Trails clue rule; requires independent review.'} for r in rejected_clue]}
 a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(packet,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
 print(json.dumps({'path':str(a.output),'frozenCorrectedCertified':len(cert),'rootStrictClueCertified':len(clueout),'other618CandidateRows':len(candidates),'weakCitedExcerpts':len(weak),'facetOnlyCited':len(facet_only),'petRows':len(pet),'previousClueClaimsRejectedByRootRule':len(rejected_clue),'candidateCounts':packet['totals']['otherCandidateCountsByCategorySubcategory']},ensure_ascii=False,indent=2))
if __name__=='__main__':main()
