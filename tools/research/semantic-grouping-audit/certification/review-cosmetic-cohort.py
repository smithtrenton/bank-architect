#!/usr/bin/env python3
"""Review every frozen CLUE/cosmetic certificate against its exact pinned item page."""
import argparse,collections,hashlib,json,re
from pathlib import Path
ROOT=Path(__file__).resolve().parents[4]
LEDGER=ROOT/'tmp/category-certification/reviews/collections/clue-unique-third-pass.jsonl'
INDEX=ROOT/'tmp/category-certification/wiki-articles/article-index.json'
OUT=ROOT/'tmp/category-certification/reviews/collections/cosmetic-strict-review.json'
POLICY=ROOT/'tools/research/semantic-grouping-audit/certification/cosmetic-strict-rule.json'
COSMETIC=re.compile(r'(?i)\b(?:purely cosmetic|cosmetic (?:item|reward|piece|variant)|decorative|changes? the appearance|appearance of|recolou?rs? (?:the|an?)|worn for show|does not (?:provide|offer|give) (?:any )?(?:combat )?bonuses|do not (?:provide|offer|give) (?:any )?(?:combat )?bonuses|no combat bonuses|no bonuses when worn|no stat bonuses|cosmetic only|vanity item)\b')
PET=re.compile(r'(?i)\b(?:is a pet|are pet cats|pet companion|can follow the player|follows the player|will follow the player|as their follower|pet kitten|puppy)\b')
COMPETING=re.compile(r'(?i)\b(?:prayer bonus|magic attack bonus|ranged attack bonus|strength bonus|warm clothing|desert heat|protect(?:s|ion)? (?:the player|from)|used as .*?(?:weapon|tool|warm clothing)|can be used to (?:attack|kill|heal|protect|open|teleport|carry|store|dye|make|create|craft|upgrade)|used to (?:attack|kill|heal|protect|open|teleport|store|dye|make|create|craft|upgrade)|required to (?:enter|access|complete)|used in the quest|quest item|enhance.{0,50}emote|holds? (?:a|an|items)|can be eaten|heals? \d+|restores? \d+|teleports? the player|is used to charge|used to charge|imbue.{0,50}(?:weapon|armour|armor|cape|boots|ring))')
STAT_FIELDS={'astab','aslash','acrush','amagic','arange','dstab','dslash','dcrush','dmagic','drange','str','rstr','mdmg','prayer','damage','defence','defense'}

def read_jsonl(p):return [json.loads(x) for x in p.read_text(encoding='utf-8').splitlines() if x.strip()]
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def exact_id_fields(params,i):
 return [{'field':k,'value':str(v)} for k,v in params.items() if re.fullmatch(r'id\d*',k,re.I) and str(v).isdigit() and int(v)==i]
def line_snippets(text,pattern,limit=20):
 out=[]
 for line in text.splitlines():
  q=line.strip()
  # Section labels such as ==Combat stats== do not themselves assert a mechanic.
  if q and not q.startswith('==') and len(q)<=1200 and pattern.search(q): out.append(q)
 return list(dict.fromkeys(out))[:limit]
def subject_lead(text,name):
 # Intro prose before the first section heading. Keep raw wikitext for auditable quotes.
 intro=re.split(r'(?m)^\s*==',text,maxsplit=1)[0]
 lines=[line.strip() for line in intro.splitlines() if line.strip()]
 # Most item articles begin with a bolded canonical name. Ignore leading templates,
 # but retain the complete intro so a reviewer can see direct subject binding.
 prose=[line for line in lines if not line.startswith('{{') and not line.startswith('|')]
 return '\n'.join(prose[:8])[:2400]
def stat_facts(text):
 out=[]
 for match in re.finditer(r'\{\{Infobox Bonuses(.*?)\n\}\}',text,re.S|re.I):
  for key,value in re.findall(r'^\|\s*([A-Za-z]+)\s*=\s*([^\r\n]+)',match.group(1),re.M):
   if key.lower() in STAT_FIELDS and value.strip() not in ('','0','+0','-0','0.0','0.00'):
    out.append({'field':key.lower(),'value':value.strip()})
 return out

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--output',type=Path,default=OUT);a=ap.parse_args()
 rows=read_jsonl(LEDGER);index=json.loads(INDEX.read_text(encoding='utf-8')); targets=[r for r in rows if r['proposedCategory']=='CLUE' and r['proposedSubcategory']=='cosmetic' and r['decision']=='certify']
 byid=collections.defaultdict(list)
 for title,art in index.items():
  for i in art.get('exactInfoboxItemIds',[]):byid[int(i)].append((title,art))
 result=[];status=collections.Counter();support_counts=collections.Counter();competing_counts=collections.Counter();pet_ids=[];weak=[]
 for r in targets:
  i=int(r['itemId']); arts=byid.get(i,[]); exact=[]
  for title,art in arts:
   v=art.get('variants',{}).get(str(i),{});params=v.get('params',{})
   if exact_id_fields(params,i):exact.append((title,art,v,params))
  if len(exact)!=1:
   result.append({'itemId':i,'reviewStatus':'ambiguous','reason':'no unique source variant with an exact numeric infobox ID field','candidateTitles':[t for t,a in arts]});status['ambiguous']+=1;continue
  title,art,v,params=exact[0];path=ROOT/art['path'];text=path.read_text(encoding='utf-8')
  lead=subject_lead(text,params.get('name') or title)
  cosmetics=line_snippets(text,COSMETIC,30)
  intro=re.split(r'(?m)^\s*==',text,maxsplit=1)[0]
  intro_cosmetics=line_snippets(intro,COSMETIC,10)
  competing=line_snippets(text,COMPETING,50)
  stats=stat_facts(text)
  pet_lines=line_snippets(text,PET,20)
  pet_direct=('pet_companion' in (r.get('proposedRoles') or [])) or bool(PET.search(lead))
  state={'itemId':i,'idFields':exact_id_fields(params,i),'name':params.get('name'),'variant':v.get('variant'),'suffix':v.get('suffix'),'options':params.get('options'),'equipable':params.get('equipable'),'tradeable':params.get('tradeable'),'bankable':params.get('bankable'),'bankability':'explicit_'+str(params.get('bankable')) if 'bankable' in params else 'unknown_absent_field'}
  src={'sourceTitle':title,'source':art['sourceUrl'],'sourceRevision':art['revid'],'sourceHash':'sha256:'+art['sha256'],'articleExactInfoboxItemIds':art.get('exactInfoboxItemIds',[]),'subjectSpecificLead':lead,'cosmeticClauses':cosmetics,'introCosmeticClauses':intro_cosmetics,'competingUseClauses':competing,'nonzeroStatFacts':stats,'petOrFollowerClauses':pet_lines,'articleHasCollectionLogFacet':'[[Category:Collection log items]]' in text}
  row={'itemId':i,'currentCategory':r['proposedCategory'],'currentSubcategory':r['proposedSubcategory'],'currentTab':r['proposedIronmanTabKey'],'currentRoles':r.get('proposedRoles'),'currentTags':r.get('proposedTags',[]),'sourceState':state,'sourceEvidence':src}
  if pet_direct:
   row.update(reviewStatus='excluded_pet_companion',reason='Exact source/role evidence identifies a pet or follower; review primary placement under pet policy, not cosmetic policy.')
   pet_ids.append(row)
  elif stats:
   row.update(reviewStatus='contradicted',reason='Exact item source variant has one or more nonzero equipment bonus facts; a cosmetic-only primary classification is contradicted, though style use may coexist.')
  elif intro_cosmetics and any((params.get('name') or title).casefold() in c.casefold() for c in intro_cosmetics):
   if competing:
    row.update(reviewStatus='ambiguous',reason='The exact ID-bound variant has direct cosmetic/appearance evidence, but the article also documents a candidate competing mechanic; full-page context is retained for primary-placement review.')
   else:
    row.update(reviewStatus='strict_supported',reason='The exact ID-bound variant has an intro clause that names the item and directly documents cosmetic/decorative/appearance use, with no nonzero stat facts or scanned competing mechanic. Full-page clauses are retained for reviewer inspection.')
  elif competing:
   row.update(reviewStatus='ambiguous',reason='The exact article documents a competing non-appearance mechanic or required quest/activity use; cosmetic retention may coexist, but primary placement is unresolved.')
  else:
   row.update(reviewStatus='ambiguous',reason='Exact source does not contain a subject-specific cosmetic/decorative/appearance/no-bonus clause; equipability, collection log, reward origin, descriptive examine, or absent bonuses alone are insufficient.')
  status[row['reviewStatus']]+=1
  support_counts['has_cosmetic_clause' if cosmetics else 'no_explicit_cosmetic_clause']+=1
  if stats:competing_counts['nonzero_stats']+=1
  if competing:competing_counts['competing_mechanic_clause']+=1
  result.append(row)
 # Every decision is per ID and retains pinned source metadata. No family-level propagation.
 policy={'schema':1,'status':'review proposal only; root approval required','rule':'Strict-support requires one pinned article, exact numeric item ID binding to the selected variant, a subject-specific literal clause explicitly calling the exact item cosmetic/decorative/purely cosmetic, explicitly appearance-changing, worn for show, or explicitly bonus-free; and no directly documented competing functional mechanic on that exact page. Nonzero stat facts contradict cosmetic-only placement. A direct competing utility, quest-access, warmth, clue-tool, emote, storage, food, or transformation use is ambiguous unless root policy determines primary precedence. Pet/follower subjects are excluded for separate review. No inference from missing stats/fields, item titles, reward origin, or Collection Log page category.',
 'inputs':{'v3LedgerSha256':sha(LEDGER),'articleIndexSha256':sha(INDEX)},'totalCosmeticCertificates':len(targets),'statusCounts':dict(status),'evidenceCounts':dict(support_counts),'competingEvidenceCounts':dict(competing_counts),'petCompanionExcludedCount':len(pet_ids),'perItemReviews':result,'petCompanionExcludedRows':pet_ids}
 a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(policy,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
 print(json.dumps({'output':str(a.output),'total':len(targets),'statusCounts':dict(status),'evidenceCounts':dict(support_counts),'competing':dict(competing_counts),'petsExcluded':len(pet_ids)},ensure_ascii=False,indent=2))
if __name__=='__main__':main()
