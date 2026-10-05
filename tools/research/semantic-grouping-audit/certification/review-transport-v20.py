from __future__ import annotations
import hashlib, json, pathlib, re, csv, sys
from collections import Counter, defaultdict
ROOT = pathlib.Path.cwd()
OUT = ROOT / 'tmp/category-certification/reviews/transport-v20'
OUT.mkdir(parents=True, exist_ok=True)
packet_path = ROOT/'tmp/category-certification/reviewer-packets/currency-runes-teleport.jsonl'
decisions_path = ROOT/'tmp/category-certification/reviews/transport/decisions.jsonl'
index_path = ROOT/'tmp/category-certification/wiki-articles/article-index.json'
coverage_path = ROOT/'tmp/category-certification/current-coverage.tsv'
approvals_path = ROOT/'tools/research/semantic-grouping-audit/certification/root-policy-approvals.json'
tele_path = ROOT/'tools/research/semantic-grouping-audit/certification/teleport-primary-approved-policy.json'
rune_path = ROOT/'tools/research/semantic-grouping-audit/certification/rune-primary-approved-policy.json'

def sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()
def jsonl(path): return [json.loads(line) for line in path.read_text(encoding='utf-8').splitlines() if line.strip()]
def paragraph(text, anchor):
    ix=text.find(anchor)
    if ix < 0: raise ValueError(f'anchor not found: {anchor}')
    lo=text.rfind('\n\n',0,ix)+2
    hi=text.find('\n\n',ix)
    if hi < 0: hi=len(text)
    value=text[lo:hi].strip()
    if anchor not in value: raise AssertionError(anchor)
    return value

packets=jsonl(packet_path)
prior={int(x['itemId']):x for x in jsonl(decisions_path)}
article_index=json.loads(index_path.read_text(encoding='utf-8'))
coverage={}
with coverage_path.open(encoding='utf-8-sig',newline='') as f:
    for row in csv.DictReader(f,delimiter='\t'):
        iid=int(row['itemId']);
        if iid in coverage: raise ValueError(f'duplicate current coverage id {iid}')
        coverage[iid]=row
if len(coverage)!=34085: raise ValueError(f'expected 34085 current rows, got {len(coverage)}')
if len(packets)!=1138 or len({int(p['itemId']) for p in packets})!=1138: raise ValueError('transport shard is not 1,138 unique IDs')
if set(prior)!=set(int(p['itemId']) for p in packets): raise ValueError('prior decisions do not cover frozen shard exactly')
if not set(coverage).issuperset(set(prior)): raise ValueError('some transport IDs absent from current authoritative coverage')

approvals=json.loads(approvals_path.read_text(encoding='utf-8'))['approvedPolicies']
approved={}
for policy_file, policy_path in [('teleport-primary-approved-policy.json',tele_path),('rune-primary-approved-policy.json',rune_path)]:
    policy=json.loads(policy_path.read_text(encoding='utf-8'))
    pin=approvals.get(policy_file)
    if not pin or sha(policy_path)!=pin['sha256']: raise ValueError(f'approval pin mismatch for {policy_file}')
    if len(policy['cases'])!=policy['expectedCaseCount']: raise ValueError(f'case count mismatch {policy_file}')
    for c in policy['cases']:
        iid=int(c['itemId'])
        if iid in approved: raise ValueError(f'duplicate approved item {iid}')
        approved[iid]={'policy':policy_file,'proposedCategory':c['proposedCategory'],'proposedSubcategory':c['proposedSubcategory'],'proposedIronmanTabKey':c.get('proposedIronmanTabKey','currency-utilities')}
        current=coverage[iid]
        target=(c['proposedCategory'], c['proposedSubcategory'], c.get('proposedIronmanTabKey','currency-utilities'))
        actual=(current['itemCategory'],current['subcategory'],current['ironmanTabKey'])
        if target!=actual: raise ValueError(f'root-approved current route mismatch {iid}: {target} vs {actual}')

# Independent exact-page positive cases. Each quote below is copied verbatim from this pinned raw revision.
case_specs=[
 {'id':1464,'kind':'currency_exchange','targetSubcategory':'currency','definitionAnchor':"An '''archery ticket''' is the reward given for using the [[Target (Ranging Guild)|target range]] at the [[Ranging Guild]]. The quantity received varies from 0-100 tickets per 10 shots at the cost of 200 coins. They can be exchanged with the [[Ticket Merchant]] within the guild for prizes, most notably rune arrows and green d'hide bodies.",'mechanicAnchors':["{{StoreTableHead|currency=Archery ticket|hidecaption=y|hidestock=y|hiderestock=y|hidebuy=y|hidege=y|column1={{plinkp|Coins}}/{{plinkp|Archery ticket}}|bucket=No}}"], 'acquisitionAnchors':[], 'competingAnchors':[], 'rationale':'Exact item article directly says tickets exchange with the Ticket Merchant for prizes and supplies its own shop table keyed to Archery ticket; this is spendable exchange value rather than a reward container.'},
 {'id':22820,'kind':'currency_exchange','targetSubcategory':'currency','definitionAnchor':"'''Molch pearls''' are a stackable item which can be obtained while [[Aerial fishing]]. Each catch has a 1/66.6 to 1/50 chance of giving Molch pearls in addition to the player's catch, which scales based on the player's [[Fishing]] and [[Hunter]] levels. Players can also exchange a [[golden tench]] with [[Alry the Angler]] for 100 Molch pearls. They can be stored in a [[tackle box]].",'mechanicAnchors':['Molch pearls can be traded to Alry in his shop, [[Alry the Angler\'s Angling Accessories]] on [[Molch Island]] for equipable versions of fishing rods, pieces of the [[Angler\'s outfit]], as well as for the [[fish sack]].'], 'acquisitionAnchors':[], 'competingAnchors':[], 'rationale':'The exact page names a shop redemption mechanic with a named merchant and reward prices. Minigame/skilling acquisition does not make the held pearls activity-only.'},
 {'id':25527,'kind':'currency_exchange','targetSubcategory':'currency','definitionAnchor':"'''Stardust''' can be mined during the [[Shooting Stars]] activity. It is used as currency in [[Dusuri's Star Shop]] or to add charges to the [[celestial ring]] and [[celestial signet]].",'mechanicAnchors':['Free-to-play players may acquire stardust, but will not be able to use them as [[Dusuri\'s Star Shop]] is only available to members.','Each piece of stardust is valued at'], 'acquisitionAnchors':[], 'competingAnchors':[], 'rationale':'Own exact article explicitly gives both currency use and charge use. The F2P access limitation is recorded as competing context; it does not negate use for an eligible member.'},
 {'id':30038,'kind':'currency_exchange','targetSubcategory':'currency','definitionAnchor':"'''Termites''' are insects in a jar which are obtained while training [[Agility]] at the [[Colossal Wyrm Agility Course]]. They are scooped up from small circles of [[Termites (NPC)|termites]] that occasionally spawn on the course, which are picked up automatically without need for additional input from the player, in contrast to [[marks of grace]].",'mechanicAnchors':['Termites serve as the currency for [[Worm Tongue\'s Wares]], and are eaten by [[Worm Tongue]], an anteater.','! colspan="2" |Reward\n! style="white-space:nowrap;" |Cost'], 'acquisitionAnchors':[], 'competingAnchors':['Termites serve as the currency for [[Worm Tongue\'s Wares]], and are eaten by [[Worm Tongue]], an anteater.'], 'rationale':'Exact shop role and explicit reward-cost table establish recurring exchange value. The article also records an NPC-food interaction, kept as competing context without replacing the player-facing currency function.'},
 {'id':2996,'kind':'currency_exchange','targetSubcategory':'currency','definitionAnchor':"'''Agility arena tickets''' were earned from tagging [[ticket dispenser]]s within the [[Brimhaven Agility Arena]] minigame. Each ticket was rewarded after tagging more than one dispenser in a row.",'mechanicAnchors':['The discontinued tickets, as well as the former shop, are still available in-game for players who have the discontinued tickets to redeem.'], 'acquisitionAnchors':[], 'competingAnchors':['The item was discontinued and a [[Agility arena ticket|new version]] was introduced following the 9 May 2024'], 'rationale':'This exact discontinued ID remains redeemable for existing holders per its own page; its acquisition status is not treated as proof of current availability. Proposal classifies extant redeemable stock by actual exchange function.'},
 {'id':563,'kind':'spell_rune','targetSubcategory':'rune','definitionAnchor':"The '''law rune''' is a [[Runes|rune]] used in all [[Teleportation spells|teleportation]] and [[Telekinetic Grab|telekinesis]] [[spells]], as well as in many of the supportive and utility spells on the [[Lunar Spellbook]].",'mechanicAnchors':[], 'acquisitionAnchors':['Law runes may be crafted at the [[Law Altar]]'], 'competingAnchors':[], 'rationale':'The exact Law rune page directly states use in teleportation, telekinesis, and utility spells; the exact variant is stackable and has no separate state suffix. Runecrafting is recorded as a secondary function, not a reason to change the primary.'},
 {'id':9469,'kind':'player_teleport_consumable','targetSubcategory':'teleport','definitionAnchor':"The '''grand seed pod''' is a single-use teleport item that can be obtained as a rare reward from [[Wingstone]], [[Penwie]], [[Brambickle]], and [[Professor Manglethorp]] in the [[Gnome Restaurant]] [[minigame]].",'mechanicAnchors':['Unlike most teleports, which stop working above level 20 Wilderness, the Grand seed pod is among the'], 'acquisitionAnchors':[], 'competingAnchors':['The upgraded version of this item, the [[Royal seed pod]], is obtained upon completion of [[Monkey Madness II]], and has unlimited charges.'], 'rationale':'The exact item is expressly single-use player teleportation; the minigame is its source, not an activity-use restriction. Its finite use and Wilderness exception belong to this ID.'},
 {'id':10972,'kind':'player_teleport_consumable','targetSubcategory':'teleport','definitionAnchor':"The '''Dorgesh-kaan sphere''' [[teleport]]s the player to a random location within [[Dorgesh-Kaan]]. They can be purchased and used upon completion of the [[Death to the Dorgeshuun]] [[quest]]. The sphere is consumed upon use and does not work beyond level 20 [[Wilderness]].",'mechanicAnchors':[], 'acquisitionAnchors':["[[Oldak]], the cave goblin professor, will construct these spheres for the player if they provide him with 2 [[law rune]]s and 1 [[molten glass]]"], 'competingAnchors':[], 'rationale':'The own exact item definition states actual player teleportation, consumption on use, and the exact wilderness limit. Quest completion is an access condition, not evidence that an item copy is activity-restricted.'},
 {'id':11060,'kind':'player_teleport_consumable','targetSubcategory':'teleport','definitionAnchor':"The '''goblin village sphere''' sphere [[teleport]]s the player to a random location within the [[Goblin Village]]. They can be purchased and used upon completion of the [[Another Slice of H.A.M.]] [[quest]], and are identical in appearance to [[plain of mud sphere]]s. The sphere is consumed upon use and does not work beyond level 20 [[Wilderness]].",'mechanicAnchors':[], 'acquisitionAnchors':["[[Oldak]], the cave goblin professor, will construct these spheres for the player if they provide him with 2 [[law rune]]s and 1 [[molten glass]]"], 'competingAnchors':[], 'rationale':'Exact subject text states the sphere teleports the player and is consumed on use. Quest prerequisite and same-appearance warning are not used to infer state or identity.'},
 {'id':13658,'kind':'transport_component','targetCategory':'TELEPORT','targetSubcategory':'teleport-charge','definitionAnchor':"A '''teleport card''' is used to charge the [[Chronicle]], a book that teleports the player just outside the [[Champions' Guild]].",'mechanicAnchors':['Noted teleport cards cannot be used to charge the Chronicle.'], 'acquisitionAnchors':["They can be purchased from [[Diango's Toy Store]], for 150 [[coins]] each."], 'competingAnchors':[], 'rationale':'The physical exact card directly charges a player-teleport book, but does not itself teleport the player. Proposal changes the subcategory from teleport to teleport-charge; the article’s noted-item restriction is preserved.'},
]

proposals=[]
source_rechecks=[]
for spec in case_specs:
    iid=spec['id']; packet=next(x for x in packets if int(x['itemId'])==iid); row=coverage[iid]
    if packet['current']['category']!=row['itemCategory'] or packet['current']['subcategory']!=row['subcategory'] or packet['current']['ironmanTabKey']!=row['ironmanTabKey']:
        raise ValueError(f'packet/current-coverage disagreement for {iid}')
    # Find exact own item source from index, and verify own variant ID.
    hits=[(title,entry) for title,entry in article_index.items() if str(iid) in entry.get('variants',{})]
    if len(hits)!=1: raise ValueError(f'{iid}: expected one exact-ID page, got {len(hits)}')
    title,entry=hits[0]; var=entry['variants'][str(iid)]
    source_path=ROOT/entry['path']
    raw=source_path.read_text(encoding='utf-8')
    actual_hash=sha(source_path)
    if actual_hash!=entry['sha256']: raise ValueError(f'{iid}: raw hash mismatch')
    def getq(anchor):
        q=paragraph(raw,anchor)
        if not q: raise AssertionError(iid)
        return q
    definition=getq(spec['definitionAnchor'])
    mechanics=[getq(a) for a in spec.get('mechanicAnchors',[])]
    acquisition=[getq(a) for a in spec.get('acquisitionAnchors',[])]
    competing=[getq(a) for a in spec.get('competingAnchors',[])]
    facts=var['params']
    if str(facts.get('id','')).split(',').__contains__(str(iid)) is False and facts.get('id')!=str(iid):
        raise ValueError(f'{iid}: infobox ID mismatch {facts.get("id")}')
    target_category=spec.get('targetCategory',row['itemCategory'])
    target_sub=spec['targetSubcategory']
    target_tab=row['ironmanTabKey']
    reviewed_case={'itemId':iid,'title':title,'status':'PROPOSED_SOURCE_BACKED_PRIMARY','kind':spec['kind'],'currentRoute':{'category':row['itemCategory'],'subcategory':row['subcategory'],'ironmanTabKey':row['ironmanTabKey']},'proposedRoute':{'category':target_category,'subcategory':target_sub,'ironmanTabKey':target_tab},'currentTags':packet['current'].get('tags',[]),'tagsClaimed':False,'rolesClaimed':None,'rationale':spec['rationale'],'source':{'sourceTitle':title,'sourceRevision':entry['revid'],'sourceUrl':entry['sourceUrl'],'sourceSha256':actual_hash,'rawPath':entry['path'],'exactItemId':iid},'exactVariantStateFacts':{k:facts.get(k) for k in ['id','name','options','wornoptions','equipable','stackable','tradeable','quest','noteable','bankable','examine'] if k in facts},'ownSubjectLeadLiteral':definition,'mechanicLiterals':mechanics,'acquisitionLiterals':acquisition,'competingContextLiterals':competing,'priorDecision':{'decision':prior[iid]['decision'],'rationale':prior[iid]['rationale']}}
    if iid in approved:
        source_rechecks.append(reviewed_case)
    else:
        proposals.append(reviewed_case)

# Full exact-ID partition, carrying each input row and the current authoritative full-ledger route.
partition=[]
class_counts=Counter(); by_category=Counter(); no_exact_ids=[]; nonnamed=[]; no_page=[]
for p in sorted(packets,key=lambda x:int(x['itemId'])):
    iid=int(p['itemId']); old=prior[iid]; cur=coverage[iid]; ev=p['sourceEvidence']
    exact_pages=[]
    for link in ev.get('wikiLookupLinks',[]):
        ids=[str(x) for x in link.get('id',[])]
        if str(iid) in ids:
            exact_pages.append({'pageName':link.get('page_name'),'pageNameSub':link.get('page_name_sub')})
    exact_index=[]
    for title,e in article_index.items():
        if str(iid) in e.get('variants',{}):
            exact_index.append({'sourceTitle':title,'revision':e['revid'],'url':e['sourceUrl'],'sha256':e['sha256']})
    if len(exact_index)>1: raise ValueError(f'{iid}: multiple exact page index records')
    approval=approved.get(iid)
    if approval: cls='ROOT_APPROVED_UNCHANGED'
    elif 8014<=iid<=8022: cls='USER_POLICY_HOLD_NONTELEPORT_SPELL_TABLET'
    elif any(c['itemId']==iid for c in proposals): cls='NEW_SOURCE_BACKED_PROPOSAL'
    elif old['decision']=='revise': cls='LEGACY_CORRECTION_PROPOSAL_UNAPPROVED'
    elif exact_index: cls='EXACT_WIKI_ID_PRESENT_NEEDS_INDEPENDENT_MECHANIC_REVIEW'
    else: cls='NO_EXACT_ID_EVIDENCE_HOLD'
    class_counts[cls]+=1; by_category[cur['itemCategory']]+=1
    if not exact_index: no_exact_ids.append(iid)
    if p['auditScope']!='NAMED_EFFECTIVE': nonnamed.append({'itemId':iid,'auditScope':p['auditScope'],'registryName':p['registryName'],'catalogName':p.get('catalogName')})
    if not ev.get('wikiLookupLinks') and not exact_index: no_page.append(iid)
    partition.append({'itemId':iid,'registryName':p['registryName'],'catalogName':p.get('catalogName'),'constantName':p.get('constantName'),'auditScope':p['auditScope'],'sourceAuditStatus':{'wikiJoinStatus':ev.get('wikiJoinStatus'),'wikiLookupStatus':ev.get('wikiLookupStatus'),'exactLookupPages':exact_pages,'exactNumericIdIndexPages':exact_index,'variantFlags':ev.get('variantFlags',[])},'currentAuthoritativeRoute':{'category':cur['itemCategory'],'subcategory':cur['subcategory'],'ironmanTabKey':cur['ironmanTabKey'],'tags':[x for x in (cur.get('tags','').split(',') if isinstance(cur.get('tags'),str) else cur.get('tags',[])) if x]},'disposition':cls,'priorTransportReview':{'decision':old['decision'],'proposedCategory':old['proposedCategory'],'proposedSubcategory':old['proposedSubcategory'],'proposedIronmanTabKey':old['proposedIronmanTabKey'],'rationale':old['rationale']},'rootApproval':approval})

# Validate all original approved and proposal IDs unique and within exact shard.
if len({x['itemId'] for x in proposals})!=len(proposals): raise ValueError('proposal IDs not unique')
if set(approved)&set(x['itemId'] for x in proposals): raise ValueError('new candidates overlap pinned approvals')
if len(partition)!=1138 or sum(class_counts.values())!=1138: raise ValueError('partition incomplete')
report={'schema':'transport-v20-full-shard-review','status':'candidate review only; no root approval, policy write, ledger change, or production edit','asOf':'2026-10-03','scope':{'shard':'currency-runes-teleport','rowCount':len(partition),'categories':dict(by_category),'expectedCurrentLedgerRows':34085},'inputs':{str(x.relative_to(ROOT)):sha(x) for x in [packet_path,decisions_path,index_path,coverage_path,approvals_path,tele_path,rune_path]},'rootApprovedCohorts':{'teleport':{'policy':'teleport-primary-approved-policy.json','ids':sorted(i for i,x in approved.items() if x['policy']=='teleport-primary-approved-policy.json')},'rune':{'policy':'rune-primary-approved-policy.json','ids':sorted(i for i,x in approved.items() if x['policy']=='rune-primary-approved-policy.json')}},'userPolicyHolds':{'nonteleportSpellTabletIds':list(range(8014,8023))},'newSourceBackedProposals':proposals,'independentSourceRechecksOfPinnedCases':source_rechecks,'partitionCounts':dict(class_counts),'partitionNotes':{'ROOT_APPROVED_UNCHANGED':'Exact pinned approval and current route equality verified; tags/roles are not claimed here.','USER_POLICY_HOLD_NONTELEPORT_SPELL_TABLET':'Preserved exactly as directed, including item 8022 which is an intended but unobtainable Telekinetic Grab tablet.','NEW_SOURCE_BACKED_PROPOSAL':'Independent exact article/state check; proposal only.','LEGACY_CORRECTION_PROPOSAL_UNAPPROVED':'Earlier transport review recommended a correction; this report does not approve it.','EXACT_WIKI_ID_PRESENT_NEEDS_INDEPENDENT_MECHANIC_REVIEW':'Exact source identity exists but no new positive semantic certification made here.','NO_EXACT_ID_EVIDENCE_HOLD':'Exact own numeric Wiki item variant unavailable in packet/index; unresolved, with no same-name propagation.'},'nonNamedEffectiveRows':nonnamed,'noExactIdRows':no_exact_ids,'noPageOrLookupRows':no_page,'fullPartition':partition}
out=OUT/'full-shard-review-v1.json'
out.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps({'output':str(out),'sha256':sha(out),'partitionCounts':dict(class_counts),'nonNamedEffectiveCount':len(nonnamed),'nonNamedEffective':nonnamed,'noExactIdCount':len(no_exact_ids),'noPageOrLookupCount':len(no_page),'proposalIds':[x['itemId'] for x in proposals],'rootApprovedTeleportCount':len(root_ids) if False else len([i for i,x in approved.items() if x['policy']=='teleport-primary-approved-policy.json']),'rootApprovedRuneCount':len([i for i,x in approved.items() if x['policy']=='rune-primary-approved-policy.json'])},ensure_ascii=False,indent=2))


