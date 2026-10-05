#!/usr/bin/env python3
"""Review exact-ID currency, rune, and teleport placement from pinned Wiki mechanics."""
import argparse, csv, hashlib, json, re
from collections import Counter
from pathlib import Path
ROOT=Path(__file__).resolve().parents[4]
PACKETS=ROOT/'tmp/category-certification/reviewer-packets/currency-runes-teleport.jsonl'
INDEX=ROOT/'tmp/category-certification/wiki-articles/article-index.json'
OUT=ROOT/'tmp/category-certification/reviews/transport'
POLICY=Path(__file__).with_name('transport-policy.json')

def rx(*xs): return [re.compile(x,re.I) for x in xs]
CURRENCY=rx(r'\b(?:is|are) (?:a form of |the main )?currenc(?:y|ies)\b',r'\bcurrency of\b',r'\b(?:can|may|could) be exchanged for\b',r'\b(?:can|may) exchange (?:it|them|these|those|the tokens?|tokens?)\b.{0,160}\bfor\b',r'\b(?:used|spent|redeemed|exchanged) (?:to|for|at|with|in)\b.{0,120}\b(?:buy|purchase|shop|reward|item|entry|access|charge|exchange|obtain)\b',r'\b(?:exchange|exchanged|redeem|redeemed|trade in|traded in)\b.{0,100}\b(?:items?|rewards?|shop|experience|entry|access|charges?)\b',r'\b(?:used to enter|used to gain entry|used to purchase|used to buy|used to pay for|used to charge)\b',r'\b(?:allows?|permits?) (?:a player|players)?\s*.{0,100}\b(?:passage|entry|access|rest|ride)\b',r'\btrade (?:three|\d+) of them to\b.{0,80}\bfor\b')
RUNE=rx(r'\b(?:rune|runes)\b.{0,180}\bused (?:to cast|for)\b.{0,120}\b(?:spells?|teleportation)\b',r'\bused in every combat spell\b',r'\b(?:used|needed|required) to cast\b.{0,120}\bspells?\b',r'\bused to cast\b.{0,120}\bspells?\b',r'\b(?:used|needed|required) for casting (?:magic|spells?)\b',r'\bplayers can cast spells? using the runes stored\b',r'\bfunction like runes\b.{0,100}\bcast\b',r'\ballows? players to cast\b.{0,140}\bspell\b')
FOCUS=rx(r'\b(?:talisman|tiara|focus)\b.{0,300}\b(?:allows?|enables?|lets?) (?:a player|the player|players)?\s*(?:to )?(?:enter|use)\b.{0,100}\baltar\b',r'\b(?:talisman|tiara|focus)\b.{0,300}\b(?:enter|access|locate)\b.{0,100}\b(?:altar|runecraft)\b',r'\b(?:enter|access)\b.{0,100}\b(?:altar|runecraft altar)\b.{0,160}\b(?:talisman|tiara|focus)\b',r'\b(?:worn|used) to enter the? ?\w* altar\b')
CONTAINER=rx(r'\b(?:store|stores|hold|holds)\b.{0,80}\brunes?\b',r'\bcast spells? using the runes stored\b')
BINDING=rx(r'\b(?:bind|binding) (?:combination )?runes\b',r'\bincreases? (?:the )?(?:chance|success rate)\b.{0,100}\bbind\b',r'\b(?:guarantees?|gives?|grants?)\b.{0,50}\b100% (?:chance|success rate)\b.{0,100}\b(?:bind|making|crafting)\b',r'\b100% success rate in (?:making|crafting) combination runes\b',r'\b100% (?:chance|success rate) in (?:making|crafting) combination runes\b')
TELEPORT=rx(r'\bteleports? (?:the player|players|you|a player)?\s*(?:to|between|away|out)\b',r'\bteleported (?:into|to|out of)\b',r'\bcan transport you out of\b',r'\b(?:provides?|offers?|grants?|allows?|enables?)\b.{0,120}\bteleports?\b',r'\b(?:used|usable) to teleport\b.{0,100}\b(?:to|between)\b',r'\bteleport to [A-Z][\w -]{1,80}',r'\bmove their boat to the nearest docking point\b')
ACCESS=rx(r'\b(?:portal nexus|portal|spirit tree|fairy ring|teleport focus|transport network)\b.{0,180}\b(?:teleport|transport|destination|access)\b',r'\b(?:used to build|used to install|built in a player-owned house|installed in a player-owned house)\b.{0,180}\b(?:portal|transport|teleport)\b')
# Exact-ID corrections: no name, family, or variant propagation.
MANUAL={
3706:('CLEANUP','quest-item','storage-cleanup','Quest-only token for a one-off Fremennik Trials step, not repeatable currency.'),4691:('CLEANUP','quest-item','storage-cleanup','Sphinx token requests help during one quest and is not bank currency.'),7478:('CLEANUP','quest-item','storage-cleanup','Dragon token summons an NPC for a Recipe for Disaster quest step, not currency.'),5606:('CLEANUP','quest-item','storage-cleanup','Makeover voucher is removed and no longer usable as current currency.'),9768:('TOOL','skilling-outfit','skilling-tools','Hitpoints cape is wearable skillcape gear, not currency.'),9769:('TOOL','skilling-outfit','skilling-tools','Trimmed Hitpoints cape is wearable skillcape gear, not currency.'),
13141:('GEAR','weapon','combat-gear','Western banner is a spear-like combat weapon, not currency.'),13142:('GEAR','weapon','combat-gear','Western banner is a spear-like combat weapon, not currency.'),13143:('GEAR','weapon','combat-gear','Western banner is a spear-like combat weapon, not currency.'),13144:('GEAR','weapon','combat-gear','Western banner is a spear-like combat weapon, not currency.'),4485:('POTION','food','potions-food','White pearl is edible and heals Hitpoints; it is food, not currency.'),20017:('CLUE','cosmetic','clues-cosmetics','Master Treasure Trails disguise ring is a cosmetic model-change reward with no combat stats; classify it with clue cosmetics, not spendable currency.'),22346:('GEAR','minigame-gear','combat-gear','Attacker icon is worn jaw-slot Barbarian Assault gear, not currency.'),31770:('UNIQUE','valuable-loot','slayer-boss-loot','Tiny pearl is an alchable encounter reward with no exchange role; it is loot, not currency.'),32517:('SKILLING','task-item','resources','Crate of tokens is courier cargo delivered by boat, not currency or a teleport.'),6819:('CLEANUP','quest-item','storage-cleanup','This large pouch quest variant is a teleport beacon, not a usable rune container.'),
9690:('CLEANUP','quest-item','storage-cleanup','Blank water rune is a quest intermediate and cannot cast spells in its blank state.'),9692:('CLEANUP','quest-item','storage-cleanup','Blank air rune is a quest intermediate, not a usable spellcasting rune.'),9694:('CLEANUP','quest-item','storage-cleanup','Blank earth rune is a quest intermediate, not a usable spellcasting rune.'),9696:('CLEANUP','quest-item','storage-cleanup','Blank mind rune is a quest intermediate, not a usable spellcasting rune.'),9698:('CLEANUP','quest-item','storage-cleanup','Blank fire rune is a quest intermediate, not a usable spellcasting rune.'),28375:('CLEANUP','quest-item','storage-cleanup','Anima portal schematic is handed to Ketla during Desert Treasure II; it does not transport the player.'),
29251:('SKILLING','construction-material','resources','Blueprint is used to craft a quetzal whistle, not an active teleport.'),29253:('SKILLING','construction-material','resources','Blueprint is used to craft an enhanced quetzal whistle, not an active teleport.'),29256:('SKILLING','construction-material','resources','Blueprint is used to craft a perfected quetzal whistle, not an active teleport.'),29259:('SKILLING','construction-material','resources','Torn blueprint is used to craft an enhanced quetzal whistle, not an active teleport.'),29261:('SKILLING','construction-material','resources','Torn blueprint is used to craft a perfected quetzal whistle, not an active teleport.'),
25938:('CLEANUP','cleanup','storage-cleanup','Animation offhand is temporarily wielded during a teleport animation; it cannot transport the player.'),25941:('CLEANUP','cleanup','storage-cleanup','Animation offhand is temporarily wielded during a teleport animation; it cannot transport the player.'),25944:('CLEANUP','cleanup','storage-cleanup','Animation offhand is temporarily wielded during a teleport animation; it cannot transport the player.'),25947:('CLEANUP','cleanup','storage-cleanup','Animation offhand is temporarily wielded during a teleport animation; it cannot transport the player.'),25950:('CLEANUP','cleanup','storage-cleanup','Animation offhand is temporarily wielded during a teleport animation; it cannot transport the player.'),25953:('CLEANUP','cleanup','storage-cleanup','Animation offhand is temporarily wielded during a teleport animation; it cannot transport the player.'),27546:('CLEANUP','cleanup','storage-cleanup','Animation offhand is temporarily wielded during a teleport animation; it cannot transport the player.'),27548:('CLEANUP','cleanup','storage-cleanup','Animation offhand is temporarily wielded during a teleport animation; it cannot transport the player.'),
28438:('CLEANUP','quest-item','storage-cleanup','Old tablet is a Desert Treasure II transcript collectible; article documents no teleport function.'),28439:('CLEANUP','quest-item','storage-cleanup','Damp tablet is a Desert Treasure II transcript collectible; article documents no teleport function.'),28440:('CLEANUP','quest-item','storage-cleanup','Damp tablet is a Desert Treasure II transcript collectible; article documents no teleport function.'),28465:('CLEANUP','quest-item','storage-cleanup','Slimy tablet is a Desert Treasure II transcript collectible; article documents no teleport function.'),28466:('CLEANUP','quest-item','storage-cleanup','Slimy tablet is a Desert Treasure II transcript collectible; article documents no teleport function.'),28467:('CLEANUP','quest-item','storage-cleanup','Slimy tablet is a Desert Treasure II transcript collectible; article documents no teleport function.'),
617:('CLEANUP','quest-item','storage-cleanup','These are fake, untradeable coins found only in the Shilo quest tomb, not spendable currency.'),620:('CLEANUP','cleanup','storage-cleanup','This Paramaya ticket version has never been obtainable in OSRS; it is a historical discontinued ticket object.'),6964:('CLEANUP','cleanup','storage-cleanup','These are fake, untradeable coins shown only in a cutscene and have no spend value.'),7774:('CLEANUP','cleanup','storage-cleanup','These historical reward tokens were superseded before OSRS and have never been obtainable in OSRS.'),7775:('CLEANUP','cleanup','storage-cleanup','These historical reward tokens were superseded before OSRS and have never been obtainable in OSRS.'),7776:('CLEANUP','cleanup','storage-cleanup','These historical reward tokens were superseded before OSRS and have never been obtainable in OSRS.'),
  22803:('GEAR','ammo','combat-gear',"Rada blessing is wearable achievement diary gear in the ammo slot, not currency."),22941:('GEAR','ammo','combat-gear',"Rada blessing is wearable achievement diary gear in the ammo slot, not currency."),22943:('GEAR','ammo','combat-gear',"Rada blessing is wearable achievement diary gear in the ammo slot, not currency."),22945:('GEAR','ammo','combat-gear',"Rada blessing is wearable achievement diary gear in the ammo slot, not currency."),22947:('GEAR','ammo','combat-gear',"Rada blessing is wearable achievement diary gear in the ammo slot, not currency."),
  25926:('TELEPORT','teleport','currency-utilities',"Ghommal's hilt is a teleportation item; currency misses its movement function."),25928:('TELEPORT','teleport','currency-utilities',"Ghommal's hilt is a teleportation item; currency misses its movement function."),25930:('TELEPORT','teleport','currency-utilities',"Ghommal's hilt is a teleportation item; currency misses its movement function."),25932:('TELEPORT','teleport','currency-utilities',"Ghommal's hilt is a teleportation item; currency misses its movement function."),25934:('TELEPORT','teleport','currency-utilities',"Ghommal's hilt is a teleportation item; currency misses its movement function."),25936:('TELEPORT','teleport','currency-utilities',"Ghommal's hilt is a teleportation item; currency misses its movement function."),
  1505:('CLEANUP','quest-item','storage-cleanup','This Plague City scroll is a one-time quest reward that unlocks the Ardougne Teleport spell; reading it does not transport the player.'),20238:('TELEPORT','teleport-charge','currency-utilities','This consumable recharges teleport jewellery; its role is teleport charges, not a direct teleport.'),21764:('TELEPORT','transport-access','currency-utilities',"This page is added to Kharedst's memoirs to unlock a Port Piscarilius teleport; it grants access rather than moving the player itself."),21768:('TELEPORT','transport-access','currency-utilities',"This page is added to Kharedst's memoirs to unlock a Lovakengj teleport; it grants access rather than moving the player itself."),29455:('TOOL','pvm-utility','skilling-tools','The anchoring scroll protects against teleport attacks; it does not move the player.'),11177:('CLEANUP','cleanup','storage-cleanup','The exact Jewellery object is a dusty Varrock Museum minigame artefact with no usable transport function.'),
  699:('CLEANUP','quest-item','storage-cleanup','The exact Stone tablet is a one-time Dig Site quest object delivered to Terry Balando, not transport.'),22991:('CLEANUP','quest-item','storage-cleanup','The exact Lizardman Temple tablet is a read-only construction record, not transport.'),26954:('CLEANUP','quest-item','storage-cleanup','The exact Beneath Cursed Sands tablet is quest lore containing a chest code, not transport.'),27519:('CLEANUP','quest-item','storage-cleanup','This Garden of Death tablet is a quest inscription, not transport.'),27520:('CLEANUP','quest-item','storage-cleanup','This Garden of Death tablet is a quest inscription, not transport.'),27521:('CLEANUP','quest-item','storage-cleanup','This Garden of Death tablet is a quest inscription, not transport.'),27522:('CLEANUP','quest-item','storage-cleanup','This Garden of Death tablet is a quest inscription, not transport.'),28816:('CLEANUP','quest-item','storage-cleanup','The exact Curse of Arrav tablet is a read-only quest inscription, not transport.'),28817:('CLEANUP','quest-item','storage-cleanup','The exact Curse of Arrav tablet is a read-only quest inscription, not transport.'),28818:('CLEANUP','quest-item','storage-cleanup','The exact Curse of Arrav tablet is a read-only quest inscription, not transport.'),28819:('CLEANUP','quest-item','storage-cleanup','The exact Curse of Arrav tablet is a read-only quest inscription, not transport.'),29876:('CLEANUP','quest-item','storage-cleanup','The exact Stone tablet is a read-only story collectible, not a teleport.'),30952:('CLEANUP','quest-item','storage-cleanup','This Final Dawn tablet records Old Ones history and a puzzle, not transport.'),30953:('CLEANUP','quest-item','storage-cleanup','This Final Dawn tablet records Old Ones history and a puzzle, not transport.'),30954:('CLEANUP','quest-item','storage-cleanup','This Final Dawn tablet records Old Ones history and a puzzle, not transport.')
}
MANUAL[619]=('CLEANUP','cleanup','storage-cleanup','The exact ticket only grants a decorative dormitory-access feature; the article says players cannot sleep there, so there is no usable currency or travel function.')
MANUAL_QUOTES={
 **{i:r'With all 7 tokens in the inventory, the player will be given' for i in range(29388,29408)},
 619:r'Gaining access to the dormitory is a purely aesthetic feature which has no function',617:r'coins turn to dust',620:r'unobtainable version of the',699:r'Giving it to \[\[Terry Balando\]\] finishes the quest',1505:r'When read, players will be able to cast',4485:r'white pearl can be eaten, healing 2',
 20238:r'scroll allows a player to charge any',21764:r'used on \[\[Kharedst.s memoirs\]\] to allow teleportation',21768:r'used on \[\[Kharedst.s memoirs\]\] or the \[\[Book of the Dead\]\] to allow teleportation',
 22941:r'When worn:',22943:r'When worn:',22945:r'When worn:',22947:r'When worn',
 25926:r'Three daily teleports to the \[\[God Wars Dungeon\]\] entrance',25928:r'Three daily teleports to the \[\[God Wars Dungeon\]\] entrance',25930:r'Three daily teleports to the \[\[God Wars Dungeon\]\] entrance',25932:r'Three daily teleports to the \[\[God Wars Dungeon\]\] entrance',25934:r'Three daily teleports to the \[\[God Wars Dungeon\]\] entrance',25936:r'Three daily teleports to the \[\[God Wars Dungeon\]\] entrance',
 9474:r'It can be used at any time to summon a',
 22991:r'records the construction of the temple',29455:r'It can be read to become permanently impervious to teleport attacks',31770:r'Aside from an entry in the \[\[collection log\]\]',32517:r'courier task, which must then be delivered',
}
def semantic_quote(text,item):
    pattern=MANUAL_QUOTES.get(item)
    if not pattern:return subject_quote(text)
    flat=re.sub(r'\s+',' ',' '.join(text.split()))
    m=re.search(pattern,flat,re.I)
    if not m:return subject_quote(text)
    start=m.start()
    end=flat.find('. ',m.end())
    if end<0:end=min(len(flat),m.end()+300)
    else:end+=1
    return flat[start:min(end,start+700)].strip()
TAB={32083:'resources',32085:'resources'}

def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def snippet(text, patterns, limit=260):
    for pat in patterns:
        m=pat.search(text)
        if m:
            start=max(0,text.rfind('\n',0,m.start())+1); end=text.find('\n',m.end()); end=len(text) if end<0 else end
            s=re.sub(r'\s+',' ',text[start:end]).strip()
            if len(s)>limit: s=s[max(0,m.start()-start-70):][:limit]
            return s
    return ''
def exact(index,item):
    hits=[(t,e) for t,e in index.items() if item in e.get('exactInfoboxItemIds',[])]
    if len(hits)!=1:return None
    title,e=hits[0]
    if str(item) not in e.get('variants',{}):return None
    return title,e

def subject_quote(text, limit=700):
    # Cite the item's own lead paragraph, not a matching category footer or a later trivia/update section.
    close=text.find('}}')
    start=text.find("'''", close + 2 if close >= 0 else 0)
    if start < 0: start=0
    end=text.find('\n\n', start)
    heading=text.find('\n==', start)
    if end < 0 or (heading >= 0 and heading < end): end=heading
    if end < 0: end=len(text)
    paragraph=re.sub(r'\s+',' ',text[start:end]).strip()
    # Keep the first complete sentence(s) so each short excerpt remains contiguous and meaningful.
    sentences=re.split(r'(?<=[.!?])\s+(?=[A-Z\'])',paragraph)
    quote=' '.join(sentences[:3]).strip()
    if len(quote)>limit:
        quote=quote[:limit].rsplit(' ',1)[0]
    return quote
def evidence(item,title,e,text,quote):
    return {'kind':'exact_wiki','source':e['sourceUrl'],'sourceTitle':title,'sourceRevision':e['revid'],'sourceHash':'sha256:'+e['sha256'],'itemId':item,'quote':quote,'sourceDescription':f'Exact item_id={item} Infobox Item variant on {title}; raw revision {e["revid"]}.'}
def decide(p,index):
    i=p['itemId']; cur=p['current']; cat,sub,tab=cur['category'],cur['subcategory'],cur['ironmanTabKey']
    d={'itemId':i,'shard':p['shard'],'reviewer':'transport','decision':'unresolved','proposedCategory':cat,'proposedSubcategory':sub,'proposedRoles':None,'proposedTags':cur.get('tags',[]),'proposedIronmanTabKey':tab,'semanticPredicate':f'Exact article evidence for item {i} does not yet establish the primary mechanic needed to certify {cat}/{sub}.','rationale':'','evidence':[],'identityLinks':[]}
    hit=exact(index,i)
    if not hit:
        d['rationale']='No exact numeric item_id article variant is available. A name, title, family, or alternate lookup match cannot certify this item.'; return d
    title,e=hit; path=ROOT/Path(e['path'].replace('\\','/'))
    if not path.is_file() or sha(path)!=e['sha256']:
        d['rationale']='The exact article text is missing or its SHA-256 differs from article-index.json; source identity cannot be checked.'; return d
    text=path.read_text(encoding='utf-8'); params=e['variants'][str(i)].get('params',{})
    rawid=params.get('id')
    if rawid is None: rawid=next((v for k,v in params.items() if re.fullmatch(r'id[1-9][0-9]*',k) and str(v)==str(i)),None)
    if str(i) not in {part.strip() for part in str(rawid or '').split(',')}:
        d['rationale']=f'Article page is associated with item {i}, but its exact variant parameters do not name that ID.'; return d
    if i in MANUAL:
        nc,ns,nt,why=MANUAL[i]
        proof=snippet(text,rx(r'quest item',r'unobtainable',r'cape of accomplishment',r'skillcape',r'spear',r'eaten',r'healing',r'change the model',r'worn in the jaw slot',r'alchemised',r'courier task',r'delivered',r'used to craft',r'blueprint',r'temporarily wielded',r'transcript',r'experience',r'teleport beacon',r'teleportation item',r'teleport',r'currency',r'exchange',r'passage',r'fake item',r'no spend value',r'ability unlock',r'added to',r'ammo slot',r'achievement diary',r'teleport attacks',r'quest item',r'quest reward',r'never been obtainable',r'never been obtainable in OSRS',r'used to add',r'used on',r'found in',r'texts and tomes'))
        if proof:
            d.update(decision='revise',proposedCategory=nc,proposedSubcategory=ns,proposedIronmanTabKey=nt,proposedRoles=[ns.replace('-','_')],semanticPredicate='Exact-ID article mechanics establish a primary role that differs from the compiled assignment.',rationale=why)
            d['evidence']=[evidence(i,title,e,text,semantic_quote(text,i))]; return d
    if i in TAB and cat=='CURRENCY':
        proof=snippet(text,CURRENCY)
        if proof:
            d.update(decision='revise',proposedIronmanTabKey=TAB[i],proposedRoles=['resource_exchange_coupon'],semanticPredicate='The exact coupon exchanges for a specific resource and should group with the resource output.',rationale='The exact sawmill coupon is redeemed for a named plank resource; its resources tab matches the first-party resource-placement rule.')
            d['evidence']=[evidence(i,title,e,text,proof)]; return d
    lower=text.casefold()
    if cat=='CURRENCY' and 29388 <= i <= 29407:
        proof=semantic_quote(text,i)
        d.update(decision='unresolved',proposedRoles=None,semanticPredicate='The exact item is one member of a daily collectathon token set redeemed together for a one-time key/reward; whether this belongs in repeatable currency or quest/reward-token storage is unresolved.',rationale='The exact article confirms a group redemption for a key and one-time reward, but does not establish repeatable spendable currency value for this individual collection token. The current CURRENCY assignment cannot certify it under the spendable-value policy.')
        d['evidence']=[evidence(i,title,e,text,proof)]; return d
    if cat=='CURRENCY' and i==9474:
        proof=semantic_quote(text,i)
        d.update(decision='unresolved',proposedRoles=None,semanticPredicate='The exact item is a reward-claim token that summons a food-bearing NPC; the source does not establish spendable/exchangeable currency or an appropriate target category.',rationale='The direct mechanic is a reusable reward-claim interface for Gnome Restaurant credits and food, not a purchase, access fee, or reward-shop exchange. Keep the category unresolved pending the taxonomy for reward-claim tokens.')
        d['evidence']=[evidence(i,title,e,text,proof)]; return d
    if cat=='CURRENCY' and i==2996:
        proof=semantic_quote(text,i)
        d.update(decision='certify',proposedRoles=['redeemable_experience_reward'],semanticPredicate='The exact discontinued ticket remains redeemable for Agility experience/rewards at its named exchange, so it retains a spendable reward-exchange role.',rationale='The exact article states the tickets can be redeemed for Agility experience and rewards at the Brimhaven Agility Arena Ticket Exchange; discontinued status does not erase that retained exchange function.')
        d['evidence']=[evidence(i,title,e,text,proof)]; return d
    if cat=='CURRENCY' and re.search(r'\b(?:series of )?unobtainable items\b|track the status of players',lower):
        q=semantic_quote(text,i)
        d.update(decision='revise',proposedCategory='CLEANUP',proposedSubcategory='cleanup',proposedIronmanTabKey='storage-cleanup',proposedRoles=['inert_purchase_state_marker'],semanticPredicate='The exact article identifies an unobtainable purchase-state marker, not spendable currency.',rationale='The exact item is an internal/unobtainable purchase-state marker with no documented bankable exchange value.')
        d['evidence']=[evidence(i,title,e,text,q)]; return d
    if cat=='CURRENCY':
        if re.search(r'\bquest item\b',lower) and not re.search(r'\b(?:currency|can be exchanged for|used to purchase|used to buy|reward shop)\b',lower):
            q=snippet(text,rx(r'quest item'))
            if q:
                d.update(decision='revise',proposedCategory='CLEANUP',proposedSubcategory='quest-item',proposedIronmanTabKey='storage-cleanup',proposedRoles=['quest_item'],semanticPredicate='Exact article identifies a quest-only item and no repeatable spend/exchange mechanic.',rationale='This exact item is described as a quest item, and its article supplies no repeatable currency mechanic.')
                d['evidence']=[evidence(i,title,e,text,q)]; return d
        proof=snippet(text,CURRENCY)
        if proof and (cat,sub,tab)==('CURRENCY','currency','currency-utilities'):
            d.update(decision='certify',proposedRoles=['spendable_exchange_value'],semanticPredicate='The exact article documents spendable/exchangeable value for a purchase, service, access, charge, or reward exchange.',rationale='Exact variant mechanics establish repeatable exchange value, matching the currency subcategory and Ironman currency/utilities tab.')
            d['evidence']=[evidence(i,title,e,text,semantic_quote(text,i))]; return d
        if re.search(r'\b(?:series of )?unobtainable items\b|track the status of players',lower):
            q=snippet(text,rx(r'unobtainable items',r'track the status'))
            if q:
                d.update(decision='revise',proposedCategory='CLEANUP',proposedSubcategory='cleanup',proposedIronmanTabKey='storage-cleanup',proposedRoles=['inert_purchase_state_marker'],semanticPredicate='Exact article describes an unobtainable purchase-state marker, not spendable currency.',rationale='The exact item is an internal/unobtainable purchase-state marker with no documented bankable exchange value.')
                d['evidence']=[evidence(i,title,e,text,q)]; return d
        d['rationale']='The exact article is available, but its mechanics do not establish spendable/exchangeable currency value; it may instead be a reward, quest item, container, or utility.'; return d
    if cat=='RUNE':
        rules={'rune':RUNE,'runecrafting-focus':FOCUS,'rune-container':CONTAINER,'runecrafting-utility':BINDING}
        proof=snippet(text,rules.get(sub,[])); expected='skilling-tools' if sub in {'runecrafting-focus','runecrafting-utility'} else 'currency-utilities'
        if proof and tab==expected:
            roles={'rune':'spellcasting_supply','runecrafting-focus':'runecrafting_focus','rune-container':'rune_storage_container','runecrafting-utility':'runecrafting_production_utility'}
            d.update(decision='certify',proposedRoles=[roles.get(sub,sub.replace('-','_'))],semanticPredicate='Exact article mechanics establish this spell rune, altar focus, rune-storage container, or Runecraft production utility.',rationale='The exact article documents the specific rune-related mechanic and its subcategory keeps consumables, altar tools, and containers distinct under the Ironman tab policy.')
            d['evidence']=[evidence(i,title,e,text,proof)]; return d
        q=snippet(text,rx(r'\bquest item\b',r'\b(?:ornament|heraldic|shield|animation item|collection log|keel part)\b'))
        if q and re.search(r'\bquest item\b|\b(?:ornament|heraldic|shield|animation item|collection log|keel part)\b',lower):
            d['rationale']='The exact article suggests a quest, cosmetic, construction, or minigame role, but does not establish a spell rune, altar focus, pouch, or Runecraft utility; the target subcategory needs more evidence.'
            d['evidence']=[evidence(i,title,e,text,q)]; return d
        d['rationale']='The exact article does not establish whether this is a usable spell rune, altar focus, rune container, or Runecraft utility.'; return d
    if cat=='TELEPORT':
        opt=str(params.get('options','')).casefold(); ex=str(params.get('examine','')).casefold()
        proof=snippet(text,(ACCESS if sub=='transport-access' else [])+TELEPORT+ACCESS)
        direct=bool(re.search(r'\bteleport\b',opt) or re.search(r'\bteleports? (?:you|the player|players)?\s*(?:to|between)\b',ex))
        if proof and (direct or any(x.search(text) for x in TELEPORT+ACCESS)) and tab=='currency-utilities':
            role='transport_network_access' if sub=='transport-access' else 'teleport_device'
            d.update(decision='certify',proposedRoles=[role],semanticPredicate='Exact article mechanics document active/rechargeable movement or installed transport access.',rationale='The exact item is an active transport device or transport-network access item; rechargeable depleted devices remain useful gear when the article documents restoration.')
            d['evidence']=[evidence(i,title,e,text,proof)]; return d
        d['rationale']='The exact article is available, but does not conclusively establish a usable/rechargeable teleport or transport-access role; related animation, container, or quest context is insufficient.'; return d
    return d

def main():
    ap=argparse.ArgumentParser(description=__doc__); ap.add_argument('--packets',type=Path,default=PACKETS); ap.add_argument('--index',type=Path,default=INDEX); ap.add_argument('--output',type=Path,default=OUT); a=ap.parse_args()
    packets=[json.loads(x) for x in a.packets.read_text(encoding='utf-8-sig').splitlines() if x.strip()]; index=json.loads(a.index.read_text(encoding='utf-8'))
    target=[p for p in packets if p['current']['category'] in {'CURRENCY','RUNE','TELEPORT'}]; cats=Counter(p['current']['category'] for p in target)
    if dict(cats)!={'CURRENCY':302,'RUNE':191,'TELEPORT':645}: raise ValueError(f'Frozen input counts changed: {dict(cats)}')
    ds=[decide(p,index) for p in target]; ids=[d['itemId'] for d in ds]
    if len(ids)!=len(set(ids)): raise ValueError('Duplicate IDs')
    a.output.mkdir(parents=True,exist_ok=True); out=a.output/'decisions.jsonl'
    out.write_text(''.join(json.dumps(d,ensure_ascii=False,sort_keys=True)+'\n' for d in ds),encoding='utf-8')
    counts=Counter(d['decision'] for d in ds); by={}
    for c in ('CURRENCY','RUNE','TELEPORT'):
        by[c]=dict(Counter(d['decision'] for d,p in zip(ds,target) if p['current']['category']==c))
    summary={'inputs':{str(a.packets.relative_to(ROOT)):sha(a.packets),str(a.index.relative_to(ROOT)):sha(a.index),str(POLICY.relative_to(ROOT)):sha(POLICY)},'recordCount':len(ds),'categories':dict(sorted(cats.items())),'decisions':dict(sorted(counts.items())),'byCategory':by,'exactArticleEvidenceCount':sum(bool(d['evidence']) for d in ds),'unresolvedExamples':[{'itemId':d['itemId'],'rationale':d['rationale']} for d in ds if d['decision']=='unresolved'][:30],'correctionExamples':[{'itemId':d['itemId'],'proposedCategory':d['proposedCategory'],'proposedSubcategory':d['proposedSubcategory'],'proposedIronmanTabKey':d['proposedIronmanTabKey'],'rationale':d['rationale']} for d in ds if d['decision']=='revise'][:50],'limitations':['A decision is emitted only when an exact-ID mechanic or curated exact-ID exception supports the placement. Ambiguous exact articles remain unresolved.','No fact transfers by display name, title similarity, family membership, or unrelated variant.']}
    (a.output/'summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2,sort_keys=True)+'\n',encoding='utf-8')
    print(f'Wrote {len(ds)} exact-ID reviews: {dict(counts)}')
if __name__=='__main__': main()


