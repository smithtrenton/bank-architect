#!/usr/bin/env python3
"""Read-only adversarial replay for the v17 23-rune root-review cohort."""
from __future__ import annotations
import hashlib,json,re
from pathlib import Path
ROOT=Path(__file__).resolve().parents[4]
PROPOSAL=ROOT/'tmp/category-certification/reviews/transport-v17/ordinary-spellcasting-runes-review.json'
DECISIONS=ROOT/'tmp/category-certification/reviews/transport-v15/decisions.jsonl'
PACKET=ROOT/'tmp/category-certification/reviewer-packets/currency-runes-teleport.jsonl'
INDEX=ROOT/'tmp/category-certification/wiki-articles/article-index.json'
OUT=ROOT/'tmp/category-certification/reviews/transport-v18/exact23-rune-adversarial-review.json'
EXPECTED=[554,555,556,557,558,559,560,561,562,563,564,565,566,4694,4695,4696,4697,4698,4699,9075,21880,28929,30843]
MECHANIC_NEEDLES={
 554:['used to cast fire-based combat spells'],555:['used to cast water-based combat spells'],556:['used in every combat spell'],557:['used to cast earth-based combat spells'],
 558:['mind rune','strike spells'],559:['body runes','used for'],560:['used to cast spells'],561:['transmutation spells'],562:['low level missile spells'],563:['law rune','teleportation','spells'],564:['cosmic rune','enchanting spells'],565:['used to cast spells'],566:['used to cast spells'],
 4694:['any spell requiring one fire rune, one water rune, or both will spend only one steam rune'],
 4695:['any spell requiring one water rune, one air rune, or both will spend only one mist rune'],
 4696:['any spell requiring one earth rune, one air rune, or both will spend only one dust rune'],
 4697:['any spell requiring one fire rune, one air rune, or both will cost only one smoke rune'],
 4698:['any spell requiring one water rune, one earth rune, or both will spend only one mud rune'],
 4699:['any spell requiring one fire rune, one earth rune, or both will spend only one lava rune'],
 9075:['astral runes','lunar spells'],21880:['used for surge spells','offering spells'],
 28929:['used in place of fire runes for non-combat spells'],
 30843:['used to cast','death charge','dark demonbane','summon thralls'],
}
SLUG={9691:555,9693:556,9695:557,9697:558,9699:554}
BA={11686:554,11687:555,11688:556,11689:557,11690:558,11691:559,11692:560,11693:561,11694:562,11695:563,11696:564,11697:565,11698:566,11699:9075,22208:21880}
NZ={11712:562,11713:560,11714:565,11715:556,11716:555,11717:557,11718:554}


def sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()
def read_jsonl(path): return [json.loads(s) for s in path.read_text(encoding='utf-8-sig').splitlines() if s.strip()]
def infobox(raw):
    p=raw.find('{{Infobox Item')
    if p<0: raise ValueError('Infobox Item absent')
    m=re.search(r'\n}}\s*\n',raw[p:])
    if not m: raise ValueError('Infobox Item close absent')
    block=raw[p:p+m.end()]
    fields={}
    for line in block.splitlines()[1:]:
        m=re.match(r'\s*\|\s*([^=]+?)\s*=\s*(.*?)\s*$',line)
        if m: fields[m.group(1).strip().lower()]=m.group(2).strip()
    return fields

def lead(raw):
    p=raw.find('{{Infobox Item'); m=re.search(r'\n}}\s*\n',raw[p:])
    return raw[p+m.end():].split('\n==',1)[0].strip()
def paras(s): return [x.strip() for x in re.split(r'\n\s*\n',s) if x.strip()]
def page_for(index,iid):
    matches=[(title,a) for title,a in index.items() if iid in a.get('exactInfoboxItemIds',[])]
    if len(matches)!=1: raise ValueError(f'{iid}: expected one exact page, got {len(matches)}')
    return matches[0]
def wiki_plain(body):
    body=re.sub(r'\[\[([^]|]+)\|([^]]+)\]\]',r'\2',body)
    return re.sub(r'\[\[([^]]+)\]\]',r'\1',body)
def evidence_paras(body,terms):
    out=[]
    for p in paras(body):
        plain=' '.join(wiki_plain(p).split()).casefold()
        if all(term.casefold() in plain for term in terms): out.append(p)
    return out

def exception(iid,title,index,mode):
    if title not in index: raise ValueError(f'exception page absent: {title}')
    art=index[title]
    if iid not in art.get('exactInfoboxItemIds',[]): raise ValueError(f'exception {iid} not bound to {title}')
    path=ROOT/Path(art['path']); raw=path.read_text(encoding='utf-8-sig')
    if sha(path)!=art['sha256']: raise ValueError(f'exception page hash mismatch {iid}')
    fields=infobox(raw)
    if fields.get('id')!=str(iid): raise ValueError(f'exception raw ID mismatch {iid}')
    if mode=='slug': pats=[r'cannot be used to cast a spell',r'cannot replace a normal.*during spells']
    elif mode=='ba': pats=[r'variant of normal',r'disappear if the player attempts to take.*outside',r'unobtainable runes']
    else: pats=[r'cannot be taken outside of the Nightmare Zone',r'cannot be used to cast non-combat spells']
    matches=[]
    for para in paras(raw):
        if any(re.search(p,para,re.I) for p in pats): matches.append(para)
    if not matches: raise ValueError(f'exception quote absent for {iid}')
    conflicts=[]
    if mode=='ba' and fields.get('tradeable')=='Yes' and any('untradeable' in q.casefold() for q in matches):
        conflicts.append('Raw Infobox Item says tradeable=Yes, while the exact-page prose says this BA variant is untradeable. Treat the field as conflicting evidence; the mode-only conclusion rests on the page-specific acquisition/outside-mode mechanics, not this infobox flag.')
    return {'itemId':iid,'sourceTitle':title,'sourceRevision':art['revid'],'sourceUrl':art['sourceUrl'],'sourceHash':'sha256:'+art['sha256'],'rawInfoboxState':{k:fields.get(k) for k in ('id','name','options','examine','quest','tradeable','equipable','stackable','noteable','value') if k in fields},'literalExceptionEvidence':matches,'sourceFieldConflicts':conflicts}

def main():
    proposal=json.loads(PROPOSAL.read_text(encoding='utf-8-sig'))
    if sorted(p['itemId'] for p in proposal['positiveProposals'])!=EXPECTED: raise ValueError('v17 positive set changed')
    index=json.loads(INDEX.read_text(encoding='utf-8-sig'))
    decisions={d['itemId']:d for d in read_jsonl(DECISIONS)}
    packets={p['itemId']:p for p in read_jsonl(PACKET)}
    audited=[]
    for iid in EXPECTED:
        row=next(r for r in proposal['positiveProposals'] if r['itemId']==iid)
        decision=decisions[iid]; packet=packets[iid]; current=packet['current']
        title,art=page_for(index,iid); path=ROOT/Path(art['path']); raw=path.read_text(encoding='utf-8-sig')
        if sha(path)!=art['sha256']: raise ValueError(f'{iid}: body SHA mismatch')
        if row['sourceHash']!='sha256:'+art['sha256'] or int(row['sourceRevision'])!=int(art['revid']): raise ValueError(f'{iid}: proposal citation mismatch')
        if title!=row['exactSourceTitle'] or title!=decision['evidence'][0]['sourceTitle'] or int(decision['evidence'][0]['sourceRevision'])!=int(art['revid']) or decision['evidence'][0]['sourceHash'].removeprefix('sha256:')!=art['sha256']: raise ValueError(f'{iid}: frozen v15/index/citation mismatch')
        fields=infobox(raw)
        if fields.get('id')!=str(iid): raise ValueError(f'{iid}: raw infobox id mismatch')
        if fields.get('name','').casefold()!=row['itemName'].casefold(): raise ValueError(f'{iid}: raw infobox name mismatch')
        if fields.get('equipable')!='No' or fields.get('stackable')!='Yes': raise ValueError(f'{iid}: item state contradicted')
        route={k:current[k] for k in ('category','subcategory','ironmanTabKey')}
        if route!=row['frozenCurrentPrimaryRoute'] or route!=row['proposedPrimaryRoute']: raise ValueError(f'{iid}: primary route changed')
        if decision.get('decision')!='certify' or decision.get('proposedCategory')!='RUNE' or (decision.get('proposedSubcategory'),decision.get('proposedIronmanTabKey'))!=(current['subcategory'],current['ironmanTabKey']): raise ValueError(f'{iid}: v15 certification not unchanged')
        fulllead=lead(raw)
        lead_paras=paras(fulllead)
        body_lower=raw.casefold()
        proof=[]
        # Direct source positives. For ID 28929, also accept and separately
        # report the page's explicit non-combat spell substitution passage.
        for term in MECHANIC_NEEDLES[iid]:
            matches=evidence_paras(fulllead,[term])
            if not matches and iid in (28929,): matches=evidence_paras(raw,[term])
            if not matches: raise ValueError(f'{iid}: direct mechanic phrase absent: {term}')
            proof.extend(matches[:1])
        negative_hits=[p for p in paras(fulllead) if re.search(r'\b(?:cannot|can not|not)\b.{0,100}\b(?:cast|spell)\b',p,re.I)]
        variant_qualified_negatives=[p for p in negative_hits if re.search(r'Barbarian Assault|Nightmare Zone|\(nz\)|variant',p,re.I)]
        direct_negative_hits=[p for p in negative_hits if p not in variant_qualified_negatives]
        if direct_negative_hits: raise ValueError(f'{iid}: positive lead contains adverse spell-use claim: {direct_negative_hits}')
        # Secondary facts are not treated as negative role evidence. Save exact
        # passages that point to crafting, markets, charges, or other uses.
        secondary=[]
        for para in paras(raw):
            if re.search(r'\b(?:runecraft|runic altar|runecrafting|shop|purchase|coins|currency|traded|trade|exchange|searing page|oathplate|offering spells|alchemy|charge|crafting)\b',para,re.I):
                flat=' '.join(para.split())
                if flat not in ['{{'+row['itemName']+' Rune Spells}}']:
                    secondary.append(para)
        # Source article exact index should not merge any mode/quest variants.
        exact_ids=art['exactInfoboxItemIds']
        if exact_ids!=[iid]: raise ValueError(f'{iid}: source page groups additional item IDs unexpectedly: {exact_ids}')
        audited.append({'itemId':iid,'itemName':row['itemName'],'sourceTitle':title,'sourceRevision':art['revid'],'sourceUrl':art['sourceUrl'],'sourceHash':'sha256:'+art['sha256'],'exactNumericIdInRawInfobox':fields['id'],'rawInfoboxState':{k:fields.get(k) for k in ('id','name','members','quest','tradeable','bankable','equipable','stackable','noteable','options','examine','value','weight') if k in fields},'fullOwnSubjectLead':fulllead,'literalSpellPaymentMechanicEvidence':list(dict.fromkeys(proof)),'wholePageSecondaryOrCompetingContexts':secondary,'sectionHeadings':[line.strip() for line in raw.splitlines() if line.lstrip().startswith('==')],'frozenCurrentPrimaryRoute':route,'proposedPrimaryRoute':route,'variantQualifiedNegativeSpellUseMentionsInLead':variant_qualified_negatives,'directNegativeSpellUseMentionsInLead':direct_negative_hits})
    slug_titles={9691:'Water rune (The Slug Menace)',9693:'Air rune (The Slug Menace)',9695:'Earth rune (The Slug Menace)',9697:'Mind rune (The Slug Menace)',9699:'Fire rune (The Slug Menace)'}
    ba_names={'Fire':'Fire','Water':'Water','Air':'Air','Earth':'Earth','Mind':'Mind','Body':'Body','Death':'Death','Nature':'Nature','Chaos':'Chaos','Law':'Law','Cosmic':'Cosmic','Blood':'Blood','Soul':'Soul','Astral':'Astral','Wrath':'Wrath'}
    ba_titles={11686:'Fire rune (Barbarian Assault)',11687:'Water rune (Barbarian Assault)',11688:'Air rune (Barbarian Assault)',11689:'Earth rune (Barbarian Assault)',11690:'Mind rune (Barbarian Assault)',11691:'Body rune (Barbarian Assault)',11692:'Death rune (Barbarian Assault)',11693:'Nature rune (Barbarian Assault)',11694:'Chaos rune (Barbarian Assault)',11695:'Law rune (Barbarian Assault)',11696:'Cosmic rune (Barbarian Assault)',11697:'Blood rune (Barbarian Assault)',11698:'Soul rune (Barbarian Assault)',11699:'Astral rune (Barbarian Assault)',22208:'Wrath rune (Barbarian Assault)'}
    nz_titles={11712:'Chaos rune (nz)',11713:'Death rune (nz)',11714:'Blood rune (nz)',11715:'Air rune (nz)',11716:'Water rune (nz)',11717:'Earth rune (nz)',11718:'Fire rune (nz)'}
    exceptions={'slugMenace':[exception(i,t,index,'slug') for i,t in slug_titles.items()],'barbarianAssault':[exception(i,t,index,'ba') for i,t in ba_titles.items()],'nightmareZone':[exception(i,t,index,'nz') for i,t in nz_titles.items()]}
    comparison_maps={'slugMenace':SLUG,'barbarianAssault':BA,'nightmareZone':NZ}
    ordinary_by_id={r['itemId']:r for r in audited}
    for group, mapping in comparison_maps.items():
        for ex in exceptions[group]:
            ordinary_id=mapping[ex['itemId']]
            ordinary=ordinary_by_id[ordinary_id]
            ex['ordinaryRuneIdForComparisonOnly']=ordinary_id
            ex['ordinaryRuneSourceForComparisonOnly']={k:ordinary[k] for k in ('sourceTitle','sourceRevision','sourceUrl','sourceHash')}
            ex['comparisonRule']='Direct source for this distinct variant and direct source for the ordinary item were reviewed separately; no family/name fact was propagated.'
    counts={'ordinaryExactIdsExamined':len(audited),'slugMenaceImitations':len(exceptions['slugMenace']),'barbarianAssaultCopies':len(exceptions['barbarianAssault']),'nightmareZoneCopies':len(exceptions['nightmareZone'])}
    inputs={}
    for name,p in [('proposalPacket',PROPOSAL),('v15Decisions',DECISIONS),('reviewerPacket',PACKET),('articleIndex',INDEX),('auditor',Path(__file__))]: inputs[name]={'path':p.relative_to(ROOT).as_posix(),'sha256':'sha256:'+sha(p)}
    report={'schemaVersion':1,'purpose':'Independent, read-only exact-23 source/state/route replay. No root policy, proposal packet, production preset, or approved ledger was changed.', 'examinedExactItemIds':EXPECTED,'inputs':inputs,'checks':['Recomputed each exact source body SHA from local raw revision text','Reparsed the raw Infobox Item and required the exact item ID/name/state','Compared pinned source title/revision/hash across v15 decision, article index, and v17 proposal','Rechecked frozen current category/subcategory/tab against the unchanged proposal route','Found direct spell-payment mechanics in each exact item source','Scanned full articles for Runecraft, trade/shop/currency and competing consumption contexts','Compared normal IDs with direct exact-ID BA, NZ, and Slug Menace variant pages'],'ordinaryRuneCases':audited,'confirmedExceptions':exceptions,'counts':counts}
    OUT.parent.mkdir(parents=True,exist_ok=True); OUT.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(counts,indent=2)); print('output',OUT.relative_to(ROOT))
if __name__=='__main__': main()
