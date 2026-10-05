#!/usr/bin/env python3
# Strict source entailment audit for the frozen gear-v2 certify cohort.
from __future__ import annotations
import argparse, collections, hashlib, json, re
from pathlib import Path
from typing import Any
ROOT=Path(__file__).resolve().parents[4]
PACKET=ROOT/'tmp/category-certification/reviewer-packets/gear.jsonl'
DECISIONS=ROOT/'tmp/category-certification/reviews/gear-v2/decisions.jsonl'
JOINED=ROOT/'tmp/semantic-audit/joined.jsonl'
INDEX=ROOT/'tmp/category-certification/wiki-articles/article-index.json'
BONUS_PROOF=ROOT/'tmp/category-certification/reviews/gear-v2/bonus-source-proof.json'
OUT=ROOT/'tmp/category-certification/reviews/gear-cohort-entailment-v2'
ACTIVE={'wear','wield','equip'}
SLOT_SUB={'weapon':{'weapon','thrown-weapon'},'2h':{'2h'},'2h weapon':{'2h'},'head':{'head'},'body':{'body'},'legs':{'legs'},'feet':{'feet'},'hands':{'hands'},'ring':{'ring'},'neck':{'neck'},'shield':{'shield','magic-offhand'},'cape':{'cape'},'ammo':{'ammo','thrown-weapon'}}
WEAPON_RE=re.compile(r'\b(?:sword|axe|bow|staff|crossbow|dagger|mace|spear|flail|scimitar|whip|claw|lance|halberd|javelin|dart|knife|thrownaxe|thrown axe|throwing knife|ballista|trident|throwing weapons?|(?:melee|ranged|magic|two[- ]handed|one[- ]handed|throwing) weapons?)\b',re.I)
AMMO_RE=re.compile(r'\b(?:ammunition|arrows?|bolts?|projectile|fired from|fired by|used as ammunition|used with (?:a |the )?(?:bow|crossbow|ballista))\b',re.I)
ARMOUR_RE=re.compile(r'\b(?:armou?r|protective|helmet|helm|kiteshield|shield|platebody|platelegs|plateskirt|chainbody|chainmail|scale body|body slot equipment|head slot equipment|leg slot equipment|shield slot equipment)\b',re.I)
ACCESSORY_COMBAT_RE=re.compile(r'\b(?:combat|attack|damage|strength|prayer bonus|defence bonus|defense bonus|protect(?:s|ion)|reduces? .*damage|increases? .*damage)\b',re.I)
COMPETING=[('cosmetic_only',re.compile(r'\b(?:cosmetic|ornamental|decorative|fashionscape)\b',re.I)),('fun_social',re.compile(r'\b(?:fun weapon|social weapon|play[- ]fighting|whack(?:ing)?|for fun)\b',re.I)),('activity_only',re.compile(r'\b(?:minigame[- ]exclusive|only (?:usable|used|works?) (?:in|during|within) (?:the )?(?:boxing ring|arena|minigame|pvp|player[- ]versus[- ]player|last man standing|castle wars|deadman|bounty hunter)|boxing ring|activity[- ]only)\b',re.I)),('skilling_primary',re.compile(r'\b(?:used (?:only )?for|used to|can be used for|tool for|worn for|worn to)\b.{0,140}\b(?:fishing|woodcutting|mining|hunter|farming|construction|runecraft|agility|smithing|crafting|herblore|thieving|firemaking)\b',re.I))]
def read_jsonl(path:Path)->list[dict[str,Any]]:return [json.loads(x) for x in path.read_text(encoding='utf-8-sig').splitlines() if x.strip()]
def sha(path:Path)->str:return hashlib.sha256(path.read_bytes()).hexdigest()
def norm(text:str)->str:
 text=re.sub(r'\[\[([^]|]+)\|([^]]+)\]\]',r'\2',text);text=re.sub(r'\[\[([^]]+)\]\]',r'\1',text);text=text.replace("'''",'').replace("''",'');text=re.sub(r'\{\{[^{}]*\}\}',' ',text);return re.sub(r'[^a-z0-9]+','',text.lower())
def lead_block(text:str)->str:
 m=re.search(r"'''([^\n]*?)'''",text)
 if not m:return ''
 end=re.search(r'\n\s*\n',text[m.start():]);return text[m.start():m.start()+end.start()] if end else text[m.start():m.start()+1600]
def first_sentence(lead:str)->str:
 m=re.search(r'\.(?:\s|$)',lead);return lead[:m.start()+1] if m else lead[:800]
def article_for(idx:dict[str,Any],i:int)->dict[str,Any]|None:return next((a for a in idx.values() if i in [int(v) for v in a.get('exactInfoboxItemIds',[])] and str(i) in a.get('variants',{})),None)
def selected_params(a:dict[str,Any],i:int)->dict[str,Any]:
 raw=a['variants'][str(i)].get('params',{});out=dict(raw)
 for key,value in raw.items():
  if re.fullmatch(r'id\d*',key,re.I) and str(value)==str(i):
   suffix=key[2:]
   for f in ('name','options','equipable','examine'):
    if f+suffix in raw:out[f]=raw[f+suffix]
 return out
def exact_slot(proof:dict[str,Any])->str|None:return proof.get('joined',{}).get('record',{}).get('equipment_slot')
def word_tokens(text:str)->list[str]:
 text=re.sub(r"'''|''",'',text.lower())
 return re.findall(r'[a-z0-9]+',text)
def exact_variant_facts(article:dict[str,Any],item_id:int)->list[dict[str,str]]:
 raw=article.get('variants',{}).get(str(item_id),{}).get('params',{});facts=[]
 for idkey,value in raw.items():
  if re.fullmatch(r'id\d*',idkey,re.I) and str(value)==str(item_id):
   suffix=idkey[2:]
   for f in (idkey,'name'+suffix,'options'+suffix,'equipable'+suffix,'examine'+suffix):
    if f in raw:facts.append({'field':f,'value':str(raw[f])})
 for f in ('name','options','equipable','examine'):
  if f in raw and not any(q['field']==f for q in facts):facts.append({'field':f,'value':str(raw[f])})
 return facts
def lead_template_audit(text:str)->dict[str,Any]:
 m=re.search(r"'''([^\n]*?)'''",text)
 if not m:return {'templateTypes':[],'subjectInsideTemplate':False}
 prefix=text[:m.start()]; types=sorted(set(re.findall(r'\{\{\s*([a-zA-Z0-9 _-]+)',prefix)))
 notes={'about','other uses','otheruses','redirect','hatnote','distinguish','for','main','see also'}
 note_types=[x.strip().lower() for x in types if x.strip().lower() in notes or x.strip().lower().startswith(('redirect','about','other uses','distinguish'))]
 first_open=max(prefix.rfind('{{'),0); first_close=prefix.rfind('}}')
 inside=bool(note_types and first_open>first_close and first_open>prefix.rfind('}}'))
 return {'templateTypes':note_types,'subjectInsideTemplate':inside}
def subject_attributed(lead:str,article:dict[str,Any],item_id:int,exact_name:str)->tuple[bool,str,str,list[int]]:
 m=re.search(r"'''([^\n]*?)'''",lead)
 if not m:return False,'','no_bold_subject',[]
 bold=m.group(1);bt=word_tokens(bold);nt=word_tokens(exact_name)
 def sequence(a:list[str],b:list[str])->bool:return bool(a) and any(b[k:k+len(a)]==a for k in range(max(0,len(b)-len(a)+1)))
 if sequence(nt,bt):return True,bold,'exact_infobox_name',[]
 if nt and len(nt)==len(bt) and nt[:-1]==bt[:-1] and (bt[-1]==nt[-1]+'s' or (nt[-1].endswith('s') and bt[-1]==nt[-1][:-1])):return True,bold,'bounded_plural',[]
 # The title is tied to this exact-ID infobox mapping; accept exact full-token equivalence only.
 title_tokens=word_tokens(str(article.get('title','')))
 if sorted(bt)==sorted(title_tokens):return True,bold,'exact_pinned_article_title',[]
 # State-family evidence must come from this page's explicit ID/name variant table.
 def strip_state(name:str)->list[str]:
  words=word_tokens(name);return [x for x in words if x not in {'p','poison','inactive','broken','unbroken','degraded','100','75','50','25','0','active'}]
 siblings=[];target_base=strip_state(exact_name)
 for sibling_id in map(int,article.get('exactInfoboxItemIds',[])):
  if sibling_id==item_id:continue
  sibling_name=str(selected_params(article,sibling_id).get('name',''))
  st=word_tokens(sibling_name);plural=bool(st and bt and st[:-1]==bt[:len(st)-1] and (bt[len(st)-1:len(st)]==[st[-1]+'s'] or (st[-1].endswith('s') and bt[len(st)-1:len(st)]==[st[-1][:-1]])))
  if strip_state(sibling_name)==target_base and (sequence(st,bt) or plural):siblings.append(sibling_id)
 if siblings:return True,bold,'bounded_infobox_family_variant',siblings
 return False,bold,'unmatched_subject_lead',[]

def explicit_mechanic(sentence:str,sub:str,proof:dict[str,Any]|None)->list[str]:
 # Restrict type evidence to the grammatical complement of the exact subject's first predicate.
 plain=re.sub(r'\[\[([^]|]+)\|([^]]+)\]\]',r'\2',sentence);plain=re.sub(r'\[\[([^]]+)\]\]',r'\1',plain);plain=plain.replace("'''",'').replace("''",'')
 m=re.search(r'\b(?:is|are|can be|serves as|functions as)\s+(.*)',plain,re.I);comp=m.group(1) if m else ''
 # Stop before later functions, acquisition, ingredients, and comparisons to avoid attributing words like "weapon scroll" to the subject.
 comp=re.split(r'\b(?:made by|obtained by|obtained from|used by|which |that |who |requiring |requires |and a quest|and an item|from opening)\b|[;.]',comp,maxsplit=1,flags=re.I)[0]
 flags=[]
 if WEAPON_RE.search(comp):flags.append('weapon_function')
 if AMMO_RE.search(comp):flags.append('ammunition_function')
 if re.search(r'\b(?:piece of|type of|form of|item of)\b.{0,90}\b(?:armou?r|protection)\b|\b(?:helmet|helm|kiteshield|shield|platebody|platelegs|plateskirt|chainbody|chainmail)\b',comp,re.I):flags.append('armour_or_protection')
 if sub in {'neck','ring','cape','hands','feet','gear'} and ACCESSORY_COMBAT_RE.search(comp):flags.append('subject_combat_effect')
 # Cosmetic/decorated variants keep their own combat identity only when this exact page has its own active, positive stats.
 variant=bool(re.search(r'\b(?:cosmetic variant|decorated version|decorative variant|ornamented version) of\b',plain,re.I))
 if variant and proof:
  stats=proof.get('joined',{}).get('record',{});positive=any(isinstance(v,(int,float)) and v>0 for k,v in stats.items() if k in {'stab_attack_bonus','slash_attack_bonus','crush_attack_bonus','range_attack_bonus','magic_attack_bonus','stab_defence_bonus','slash_defence_bonus','crush_defence_bonus','range_defence_bonus','magic_defence_bonus','strength_bonus','ranged_strength_bonus','prayer_bonus','magic_damage_bonus'})
  if positive and proof.get('activeEquipmentOptions',{}).get('status')=='explicit_active_equipment_action':flags.append('exact_variant_retains_combat_stats')
 return list(dict.fromkeys(flags))
def classify(d:dict[str,Any],p:dict[str,Any],article:dict[str,Any]|None,proof:dict[str,Any]|None)->dict[str,Any]:
 i=int(d['itemId']);sub=p['current']['subcategory'];base={'itemId':i,'status':'ambiguous','reasonCodes':[],'article':None,'subjectLabel':None,'subjectAttributed':False,'subjectAttributionBasis':None,'boundedSiblingIds':[],'mechanics':[],'activeOption':None,'exactSlot':None,'slotCompatible':False,'competitionFlags':[],'primaryExcerpt':'','competitionExcerpts':[],'fullArticlePurposeHits':[],'exactVariantFacts':[],'leadTemplateAudit':None,'bonusSourceProof':None,'decision':d['decision']}
 if not article:return {**base,'reasonCodes':['no_exact_pinned_article']}
 raw=(ROOT/article['path']).read_text(encoding='utf-8',errors='replace');lead=lead_block(raw);sentence=first_sentence(lead);params=selected_params(article,i);exact_name=str(params.get('name',''));attributed,label,attribution_basis,sibling_ids=subject_attributed(lead,article,i,exact_name)
 opts={x.strip().lower() for x in str(params.get('options','')).split(',')};active=sorted(opts&ACTIVE);slot=exact_slot(proof) if proof else None;name_text=' '.join([str(params.get('name','')),str(p.get('registryName',''))]).lower()
 flags=[];snippets=[];all_hits=[]
 for code,pattern in COMPETING:
  for m in pattern.finditer(raw):
   all_hits.append({'kind':code,'quote':raw[max(0,m.start()-100):min(len(raw),m.end()+140)]})
  m=pattern.search(sentence)
  if m:flags.append(code);snippets.append({'kind':code,'quote':sentence[max(0,m.start()-100):min(len(sentence),m.end()+140)]})
 mechanics=explicit_mechanic(sentence,sub,proof);compatible=bool(slot and (sub=='gear' or sub in SLOT_SUB.get(str(slot).lower(),set()) or (sub=='ammo' and str(slot).lower()=='weapon' and 'dart' in name_text and 'weapon_function' in mechanics)));reason=[]
 if not attributed:reason.append('subject_lead_not_exactly_attributed')
 if not mechanics:reason.append('no_explicit_subject_weapon_armour_ammo_or_combat_function_in_lead')
 if len(active)!=1 or str(params.get('equipable','')).strip().lower()!='yes':reason.append('exact_variant_has_no_single_explicit_active_wear_wield_equip_option')
 if not slot:reason.append('no_unique_exact_id_primary_slot')
 if slot and not compatible:reason.append('exact_primary_slot_conflicts_with_current_subcategory')
 hard=[x for x in flags if x in {'fun_social','activity_only','skilling_primary'}]
 if hard and not (mechanics and ACCESSORY_COMBAT_RE.search(sentence)):reason.append('competing_noncombat_primary_purpose')
 if 'cosmetic_only' in flags and not mechanics:reason.append('cosmetic_variant_without_direct_retained_function')
 status='strict_supported' if not reason else ('contradicted' if hard else 'ambiguous')
 ainfo={'title':article['title'],'sourceUrl':article['sourceUrl'],'sourceRevision':article['revid'],'sourceHash':'sha256:'+article['sha256'],'path':article['path']}
 facts=exact_variant_facts(article,i);template_audit=lead_template_audit(raw)
 if template_audit['subjectInsideTemplate'] and 'subject_lead_inside_hatnote_template' not in reason:reason.append('subject_lead_inside_hatnote_template');status='ambiguous'
 bonus_evidence=None
 if proof:
  rec=proof.get('joined',{}).get('record',{})
  bonus_evidence={'proofArtifact':'tmp/category-certification/reviews/gear-v2/bonus-source-proof.json','proofArtifactRowSha256':hashlib.sha256(json.dumps(proof,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()).hexdigest(),'sourceTitle':proof.get('article',{}).get('title'),'sourceUrl':proof.get('article',{}).get('sourceUrl'),'sourceRevision':proof.get('article',{}).get('revision'),'sourceHash':'sha256:'+str(proof.get('article',{}).get('sha256','')),'itemId':i,'itemVariant':proof.get('itemVariant'),'activeEquipmentOptions':proof.get('activeEquipmentOptions'),'equipmentSlot':rec.get('equipment_slot'),'combatValues':{k:v for k,v in rec.items() if k in {'stab_attack_bonus','slash_attack_bonus','crush_attack_bonus','range_attack_bonus','magic_attack_bonus','stab_defence_bonus','slash_defence_bonus','crush_defence_bonus','range_defence_bonus','magic_defence_bonus','strength_bonus','ranged_strength_bonus','prayer_bonus','magic_damage_bonus'}}}
 return {**base,'status':status,'reasonCodes':list(dict.fromkeys(reason)),'article':ainfo,'subjectLabel':label,'subjectAttributed':attributed,'subjectAttributionBasis':attribution_basis,'boundedSiblingIds':sibling_ids,'mechanics':mechanics,'activeOption':active,'exactSlot':slot,'slotCompatible':compatible,'competitionFlags':flags,'primaryExcerpt':lead[:360],'competitionExcerpts':snippets,'fullArticlePurposeHits':all_hits,'exactVariantFacts':facts,'leadTemplateAudit':template_audit,'bonusSourceProof':bonus_evidence}
def main()->None:
 ap=argparse.ArgumentParser();ap.add_argument('--output',type=Path,default=OUT);args=ap.parse_args();packet=read_jsonl(PACKET);pmap={int(x['itemId']):x for x in packet};decisions=[x for x in read_jsonl(DECISIONS) if x.get('decision')=='certify']
 if len(decisions)!=2184:raise ValueError(f'frozen v2 cohort changed: {len(decisions)}')
 idx=json.loads(INDEX.read_text(encoding='utf-8-sig'));proof=json.loads(BONUS_PROOF.read_text(encoding='utf-8-sig'))
 if proof['inputs']['decisionSha256']!=sha(DECISIONS) or proof['inputs']['articleIndexSha256']!=sha(INDEX):raise ValueError('bonus-source proof is not pinned to v2 and current article index')
 by_proof={int(x['itemId']):x for x in proof.get('consistent',[]) if x.get('decision')=='certify'};rows=[]
 for d in decisions:
  i=int(d['itemId']);rows.append(classify(d,pmap[i],article_for(idx,i),by_proof.get(i)))
 if any(x['status']=='strict_supported' and not x.get('bonusSourceProof') for x in rows):raise ValueError('strict cohort row lacks exact item source proof')
 counts=collections.Counter(x['status'] for x in rows);reasons=collections.Counter(r for x in rows for r in x['reasonCodes']);clusters=collections.defaultdict(list)
 basis_counts=collections.Counter(x['subjectAttributionBasis'] for x in rows);template_counts=collections.Counter(t for x in rows for t in (x.get('leadTemplateAudit') or {}).get('templateTypes',[]));direct_flags=collections.Counter(f for x in rows for f in x['competitionFlags']);strict=[x for x in rows if x['status']=='strict_supported'];strict_hits=collections.Counter(h['kind'] for x in strict for h in x['fullArticlePurposeHits'])
 for x in rows:
  key=' '.join(x['primaryExcerpt'].split())
  if key:clusters[key].append(x['itemId'])
 excerpts=[{'count':len(ids),'itemIds':sorted(ids),'normalizedPrimaryExcerpt':ex} for ex,ids in sorted(clusters.items(),key=lambda z:(-len(z[1]),z[0]))]
 args.output.mkdir(parents=True,exist_ok=True);(args.output/'review.jsonl').write_text(''.join(json.dumps(x,ensure_ascii=False,sort_keys=True)+'\n' for x in rows),encoding='utf-8')
 summary={'schema':'gear-cohort-entailment-v2','sourceCohort':'gear-v2 decisions where decision=certify','reviewStatus':'candidate_for_root_review_not_approved','rowCount':len(rows),'statusCounts':dict(sorted(counts.items())),'reasonCounts':dict(sorted(reasons.items())),'idsByReason':{r:[x['itemId'] for x in rows if r in x['reasonCodes']] for r in sorted(reasons)},'explicitSemanticSubsetCount':counts['strict_supported'],'subjectAttributionBasisCounts':dict(sorted(basis_counts.items())),'leadTemplateCounts':dict(sorted(template_counts.items())),'directCompetingPurposeCounts':dict(sorted(direct_flags.items())),'strictFullArticlePurposeHitCounts':dict(sorted(strict_hits.items())),'strictVariantOnlyEvidenceIds':[x['itemId'] for x in strict if 'exact_variant_retains_combat_stats' in x['mechanics']],'strictBoundedFamilyVariantIds':[x['itemId'] for x in strict if x.get('boundedSiblingIds')],'contradictionIds':[x['itemId'] for x in rows if x['status']=='contradicted'],'ambiguityIds':[x['itemId'] for x in rows if x['status']=='ambiguous'],'directCompetingPurposeIds':{k:[x['itemId'] for x in rows if k in x['competitionFlags']] for k,_ in COMPETING},'fullArticlePurposeHitIds':{k:[x['itemId'] for x in rows if any(h['kind']==k for h in x['fullArticlePurposeHits'])] for k,_ in COMPETING},'primaryExcerptClusters':excerpts,'inputs':{'packetSha256':sha(PACKET),'decisionSha256':sha(DECISIONS),'joinedSha256':sha(JOINED),'articleIndexSha256':sha(INDEX),'bonusSourceProofSha256':sha(BONUS_PROOF),'bonusSourceProofScope':proof['scope'],'bonusSourceProofConsistentRows':len(proof['consistent'])},'productionPolicy':{'subcategoryPrecedencePath':'src/main/java/com/pkoka5/ironmanbankarchitect/catalog/ItemClassificationRefiner.java','subcategoryPrecedenceSha256':sha(ROOT/'src/main/java/com/pkoka5/ironmanbankarchitect/catalog/ItemClassificationRefiner.java'),'ammoNameGroupPath':'src/main/resources/com/pkoka5/ironmanbankarchitect/catalog/classification-names.tsv','ammoNameGroupSha256':sha(ROOT/'src/main/resources/com/pkoka5/ironmanbankarchitect/catalog/classification-names.tsv'),'ironmanMappingPath':'src/main/java/com/pkoka5/ironmanbankarchitect/organize/BankTags.java','ironmanMappingSha256':sha(ROOT/'src/main/java/com/pkoka5/ironmanbankarchitect/organize/BankTags.java'),'ironmanPresetPath':'src/main/java/com/pkoka5/ironmanbankarchitect/organize/PresetCategoryMapper.java','ironmanPresetSha256':sha(ROOT/'src/main/java/com/pkoka5/ironmanbankarchitect/organize/PresetCategoryMapper.java'),'interpretation':'Production maps group 29 names containing dart to GEAR/ammo; the Ironman combat-gear Ammunition split accepts ammo and thrown-weapon. Thus a direct throwing-dart function with exact primary slot weapon remains compatible with the current ammo storage assignment.'},'limitations':['Strict-supported rows require exact page subject attribution, an explicit opening-sentence function, one exact-item Wear/Wield/Equip action, a source-proof-backed primary slot, and compatibility with the current subcategory; generic gear accepts any exact primary slot; the production ammo policy also accepts exact throwing darts with weapon slot.','Strict rows are candidate evidence for root review, not root-approved certification.' ,'Contradicted is reserved for explicit competing primary-purpose phrases; other failed gates are ambiguous.','Only direct opening-sentence purpose phrases affect strict status; all purpose-pattern hits elsewhere in the pinned article are separately retained with literal context to expose potential competing or variant-specific mechanics without treating incidental mentions as contradictions.','This is a conservative semantic subset; it does not change production or claim unresolved rows are incorrectly assigned.']}
 (args.output/'summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2,sort_keys=True)+'\n',encoding='utf-8');print(json.dumps({k:v for k,v in summary.items() if k!='primaryExcerptClusters'},ensure_ascii=False,indent=2))
if __name__=='__main__':main()
