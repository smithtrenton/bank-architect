"""Build the farming/materials domain audit from the root Wiki join (no network calls)."""
import csv
import json
import os
from collections import Counter, defaultdict

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..'))
JOINED = os.path.join(ROOT, 'tmp', 'semantic-audit', 'joined.jsonl')
CATALOG = os.path.join(ROOT, 'src', 'main', 'resources', 'com', 'pkoka5', 'ironmanbankarchitect', 'catalog')
OUT = os.path.join(ROOT, 'tmp', 'semantic-audit', 'reviews', 'farming-materials')
os.makedirs(OUT,exist_ok=True)
TARGET_CATEGORIES = [
    'Farming', 'Crops', 'Seeds', 'Saplings', 'Mining', 'Ores', 'Metal bars', 'Smithing', 'Logs',
    'Crafting', 'Gems', 'Leather', 'Construction', 'Fletching', 'Arrows', 'Bolts', 'Firemaking', 'Sailing'
]
EQUIPMENT_CATEGORIES = {'Equipable items', 'Clothing', 'Magic armour', 'Melee armour', 'Ranged armour'}
MATERIAL_TAGS = {'raw-resources', 'gems', 'ammo-components'}
RECIPE_SKILLS = {'Farming', 'Mining', 'Smithing', 'Woodcutting', 'Crafting', 'Construction', 'Fletching', 'Firemaking', 'Sailing'}


def true_categories(row):
    out = set()
    for fact in row.get('wiki_records') or []:
        for key, value in fact.items():
            if key.startswith('Category:') and value is True:
                out.add(key[len('Category:'):])
    return out


def item_facts(row):
    facts = []
    for w in row.get('wiki_records') or []:
        for key in ('examine', 'quest', 'page_name_sub'):
            value = w.get(key)
            if value not in (None, '', False, []):
                value = str(value).replace('\n', ' ').strip()
                if value and value not in facts:
                    facts.append(key + '=' + value[:320])
    return ' | '.join(facts)


def relevant_recipe_titles(row):
    values = []
    for rel in row.get('recipe_relations') or []:
        skills = rel.get('skills') or []
        page = rel.get('page', '')
        if any(skill in RECIPE_SKILLS for skill in skills):
            values.append(page)
    return sorted(set(values))


def read_rows():
    return [json.loads(line) for line in open(JOINED, encoding='utf-8')]


all_rows = read_rows()
by_id = {str(r['item_id']): r for r in all_rows}

# Broad but bounded coverage: all present resource/Farming destinations and every exact item-page
# membership in the requested skills/material families, plus cleanup rows with a relevant recipe edge.
rows = []
for r in all_rows:
    cats = true_categories(r)
    preset_cat = r.get('preset_category', '') or ''
    preset_tag = r.get('preset_tag', '') or ''
    catalog_cat = r.get('catalog_category', '') or ''
    recipe_titles = relevant_recipe_titles(r)
    in_scope = (preset_cat in {'resources', 'seeds-farming'} or catalog_cat == 'FARMING'
                or bool(cats.intersection(TARGET_CATEGORIES))
                or (preset_cat == 'storage-cleanup' and recipe_titles and r.get('wiki_join_status') == 'EXACT_ID_SINGLE'))
    if not in_scope:
        continue

    facts = r.get('wiki_records') or []
    exact_categories = sorted(cats)
    domain_roles = []
    if cats.intersection({'Seeds', 'Saplings', 'Crops'}): domain_roles.append('planting-or-crop-item')
    if 'Farming' in cats: domain_roles.append('farming-associated')
    if cats.intersection({'Mining', 'Ores'}): domain_roles.append('mining-associated')
    if cats.intersection({'Metal bars', 'Smithing'}): domain_roles.append('smithing-associated')
    if 'Logs' in cats: domain_roles.append('wood-associated')
    if cats.intersection({'Crafting', 'Gems', 'Leather'}): domain_roles.append('crafting-associated')
    if cats.intersection({'Fletching', 'Arrows', 'Bolts'}): domain_roles.append('fletching-or-ammunition-associated')
    if 'Construction' in cats: domain_roles.append('construction-associated')
    if 'Firemaking' in cats: domain_roles.append('firemaking-associated')
    if 'Sailing' in cats: domain_roles.append('sailing-associated')
    equip = bool(cats.intersection(EQUIPMENT_CATEGORIES))
    tags = r.get('tags') or []
    recipe_count = len(r.get('recipe_relations') or [])
    notes = []
    if cats.intersection({'Seeds', 'Saplings', 'Crops'}) and preset_tag not in {'seeds', 'herb-seeds', 'produce'}:
        notes.append('direct crop/seed category cross-tabs outside current seed or produce tags; inspect quest, herb, or tool role before any change')
    if equip and preset_tag in MATERIAL_TAGS:
        notes.append('page-scoped equipment category appears under a material tag; exact variant can still be an ingredient or ammo, so inspect mechanics')
    if preset_cat == 'storage-cleanup' and recipe_titles:
        notes.append('recipe relation intersects a requested skill; recipe title edge does not prove this exact item variant is a material')
    if 'Farming' in cats and preset_cat not in {'seeds-farming', 'herblore'} and catalog_cat != 'TOOL':
        notes.append('Farming category indicates association only; verify actual harvest/planting source and downstream use')
    rows.append({
        'item_id': r.get('item_id'), 'name': r.get('name'), 'catalog_category': catalog_cat,
        'subcategory': r.get('subcategory', ''), 'preset_category': preset_cat, 'preset_tag': preset_tag,
        'preset_tag_by_family': r.get('preset_tag_by_family', ''), 'family_hint': r.get('family_hint', ''),
        'constant': r.get('constant', ''), 'variant_flags': ' | '.join(r.get('variant_flags') or []),
        'wiki_join_status': r.get('wiki_join_status', ''), 'wiki_fact_count': len(facts),
        'wiki_categories_positive': ' | '.join(exact_categories), 'wiki_roles': ' | '.join(r.get('roles') or []), 'candidate_roles': ' | '.join(domain_roles),
        'wiki_url': ' | '.join(r.get('wiki_urls') or []), 'wiki_fact_snippets': item_facts(r),
        'recipe_relation_count': recipe_count, 'relevant_recipe_pages': ' | '.join(recipe_titles[:50]),
        'evidence_scope': 'Positive item-page category or exact-ID page fields only; category flags are page-scoped; recipe title edges are not exact item-variant proof; absence is not evidence.',
        'review_note': ' | '.join(notes)
    })

columns = list(rows[0]) if rows else []
with open(os.path.join(OUT, 'candidate-universe.csv'), 'w', newline='', encoding='utf-8-sig') as f:
    writer = csv.DictWriter(f, fieldnames=columns); writer.writeheader(); writer.writerows(rows)

review = [r for r in rows if r['review_note']]
with open(os.path.join(OUT, 'review-queue.csv'), 'w', newline='', encoding='utf-8-sig') as f:
    writer = csv.DictWriter(f, fieldnames=columns); writer.writeheader(); writer.writerows(review)

# Cross-tabs include positive exact page facts only. A category absent from a page is not counted as a negative.
current_dest = Counter()
cat_dest = Counter()
status = Counter()
role_counts = Counter()
overlap = Counter()
cat_totals = Counter()
for row in rows:
    current_dest[(row['preset_category'], row['preset_tag'])] += 1
    status[row['wiki_join_status']] += 1
    for role in filter(None, row['candidate_roles'].split(' | ')): role_counts[role] += 1
    cats = set(filter(None, row['wiki_categories_positive'].split(' | ')))
    for cat in cats.intersection(TARGET_CATEGORIES):
        cat_dest[(cat, row['preset_category'], row['preset_tag'])] += 1
        cat_totals[cat] += 1
    if cats.intersection({'Seeds', 'Saplings', 'Crops'}) and row['preset_tag'] not in {'seeds', 'herb-seeds', 'produce'}:
        overlap['crop_category_outside_seed_produce'] += 1
    if cats.intersection(EQUIPMENT_CATEGORIES) and row['preset_tag'] in MATERIAL_TAGS:
        overlap['equipment_category_inside_material_tag'] += 1
    if 'Farming' in cats and 'recipe_material' in row['wiki_roles'].split(' | '):
        overlap['farming_plus_recipe_material_role'] += 1

# Audit every existing exact-ID family membership in both current family data files.
existing = []
for filename in ('farming-layout-families.tsv', 'resource-layout-families.tsv'):
    path = os.path.join(CATALOG, filename)
    if not os.path.exists(path):
        continue
    for line in open(path, encoding='utf-8-sig'):
        line = line.strip()
        if not line or line.startswith('#') or '\t' not in line: continue
        group, raw_ids = line.split('\t', 1)
        ids = [v.strip() for v in raw_ids.split(',') if v.strip()]
        members = [by_id[i] for i in ids if i in by_id]
        existing.append({
            'catalog_file': filename, 'group_key': group, 'listed_item_ids': ' | '.join(ids),
            'listed_count': len(ids), 'joined_count': len(members),
            'exact_id_single_count': sum(m.get('wiki_join_status') == 'EXACT_ID_SINGLE' for m in members),
            'no_exact_id_fact_count': sum(m.get('wiki_join_status') == 'NO_EXACT_ID_FACT' for m in members),
            'current_destinations': ' | '.join(sorted(set((m.get('preset_category','')+'/'+m.get('preset_tag','')) for m in members))),
            'positive_wiki_categories': ' | '.join(sorted(set(c for m in members for c in true_categories(m)))),
            'member_wiki_urls': ' | '.join(sorted(set(u for m in members for u in (m.get('wiki_urls') or [])))),
            'review_note': 'Existing grouping is a curated baseline; category agreement and exact-ID page facts support review, but no group is universal across all content states.'
        })
with open(os.path.join(OUT, 'existing-groups.csv'), 'w', newline='', encoding='utf-8-sig') as f:
    writer = csv.DictWriter(f, fieldnames=list(existing[0]) if existing else [])
    writer.writeheader(); writer.writerows(existing)

# Explicit, source-backed family suggestions. All item data is read from the root join, not inferred by name alone.
proposals = []
def add_group(key, role, ids, confidence, recommendation, source_urls=None):
    members = [by_id[str(i)] for i in ids if str(i) in by_id]
    evidence = []
    urls = set(source_urls or [])
    for m in members:
        facts = m.get('wiki_records') or []
        snippets = []
        for w in facts:
            for k in ('examine', 'quest'):
                v = w.get(k)
                if v not in (None, '', False, []): snippets.append(k+'='+str(v).replace('\n',' ')[:220])
        evidence.append(f"{m['item_id']}:{m['name']} [{m.get('preset_category','')}/{m.get('preset_tag','')}; {m.get('wiki_join_status','')}] {'; '.join(snippets)}")
        urls.update(m.get('wiki_urls') or [])
    proposals.append({
        'candidate_group': key, 'functional_role': role, 'item_ids': ' | '.join(str(i) for i in ids),
        'member_evidence': ' || '.join(evidence), 'member_count': len(members), 'confidence': confidence,
        'recommendation': recommendation, 'source_urls': ' | '.join(sorted(urls)),
        'evidence_limit': 'Direct Wiki item pages are exact-ID joined where noted; skill/category association alone does not prove harvest or recipe stage.'
    })

# Tree-seed-to-sapling processing pairs: the current seed families hold the seed stage only.
seed_sapling_pairs = [
 ('oak/acorn to oak sapling',5312,5370),('willow seed to willow sapling',5313,5371),('maple seed to maple sapling',5314,5372),
 ('yew seed to yew sapling',5315,5373),('magic seed to magic sapling',5316,5374),('spirit seed to spirit sapling',5317,5375),
 ('apple tree seed to apple sapling',5283,5496),('banana tree seed to banana sapling',5284,5497),('orange tree seed to orange sapling',5285,5498),
 ('curry tree seed to curry sapling',5286,5499),('pineapple seed to pineapple sapling',5287,5500),('papaya tree seed to papaya sapling',5288,5501),
 ('palm tree seed to palm sapling',5289,5502),('calquat tree seed to calquat sapling',5290,5503),('teak seed to teak sapling',21486,21477),
 ('mahogany seed to mahogany sapling',21488,21480),('celastrus seed to celastrus sapling',22869,22856),('redwood seed to redwood sapling',22871,22859),
 ('dragonfruit seed to dragonfruit sapling',22877,22866),('crystal acorn to crystal sapling',23661,23659),
 ('camphor seed to camphor sapling',31547,31502),('ironwood seed to ironwood sapling',31549,31505),('rosewood seed to rosewood sapling',31551,31508)
]
for name, seed, sapling in seed_sapling_pairs:
    add_group('farming.tree-stage.'+name.replace(' ','-').replace('/','-'), 'same-species seed → sapling stage pair', [seed,sapling], 'high',
              'Candidate to extend the existing species seed families with the exact next-stage sapling; keep quest-only saplings separate.')
add_group('farming.tithe-farm-seeds', 'Tithe Farm seed tier family', [13423,13424,13425], 'high',
          'Keep as a distinct three-tier planting family; all three exact item examines name the Hosidius land strips and the Wiki Tithe Farm page lists the three seed tiers.',
          ['https://oldschool.runescape.wiki/w/Tithe_Farm','https://oldschool.runescape.wiki/w/Tithe_farm_guide'])
add_group('farming.coral-nursery-fragments', 'coral-nursery planting inputs', [31511,31513,31515], 'medium',
          'Candidate family of three propagation inputs; current item pages say they are propagated in a coral nursery. Confirm live content/patch mechanics before merging with ordinary seeds.',
          ['https://oldschool.runescape.wiki/w/Coral_nursery'])
add_group('farming.magical-flower-seeds', 'magical decorative flower seeds', [299,29458], 'medium',
          'Keep separate from crop/harvest families; Wiki pages identify magical flower-seed mechanics, while bank destination may remain Farming seeds or move to a separate utility/cosmetic family.',
          ['https://oldschool.runescape.wiki/w/Mithril_seeds','https://oldschool.runescape.wiki/w/Adamant_seeds'])
add_group('farming.chambers-herb-seeds', 'Chambers of Xeric herb seeds', [20903,20906,20909], 'medium',
          'Group as a distinct raid-only herb-growing seed family, not as ordinary patch seeds; exact Wiki Chambers page documents Farming plots and the three herbs. Keep the Herblore downstream overlap explicit.',
          ['https://oldschool.runescape.wiki/w/Chambers_of_Xeric'])
add_group('farming.huasca-herb-seed', 'Huasca herb-seed extension', [30088], 'high',
          'Candidate extension of herb-seed family: exact item examine says plant in a herb patch; retain Herblore/Farming overlap in destination policy.',
          ['https://oldschool.runescape.wiki/w/Huasca_seed'])
add_group('farming.enriched-snapdragon-variant', 'quest-linked enriched herb seed state', [5300,29538], 'medium',
          'Keep exact IDs distinct; candidate to display together as Snapdragon seed variants. #29538 is quest-linked and promises a more potent herb, so preserve quest/effect notes and do not auto-move it from cleanup.',
          ['https://oldschool.runescape.wiki/w/Snapdragon_seed','https://oldschool.runescape.wiki/w/Enriched_snapdragon_seed'])
add_group('farming.gout-tuber-role-review', 'plantable herb-patch seed vs quest hardy tuber', [6311,4001], 'high',
          'Role correction candidate: #6311 is explicitly planted in a herb patch and currently tagged produce; #4001 is a quest-linked hardy tuber with distinct mechanics. Keep them in separate item-state roles; #6311 fits seed/Herblore workflow.',
          ['https://oldschool.runescape.wiki/w/Gout_tuber','https://oldschool.runescape.wiki/w/Hardy_gout_tuber'])

# Material processing chains missing as explicit species-stage families from resource-layout-families.tsv.
for key, ids in [
 ('metal.bronze', [436,438,2349]), ('metal.steel', [440,453,2353]), ('metal.blurite', [668,9467]),
 ('metal.lovakite', [13356,13354]), ('metal.lead', [31716,32889]), ('metal.cupronickel', [31719,32892])
]:
    add_group('resources.'+key, 'ore(s) → processed bar family', ids, 'high',
              'Candidate extension of ore/bar family rows; verify that the existing row sorter should place input and output stages together without mixing wearable smithing products.')
for wood, log_id, plank_id in [
 ('normal',1511,960),('oak',1521,8778),('teak',6333,8780),('mahogany',6332,8782),
 ('camphor',32904,31432),('ironwood',32907,31435),('rosewood',32910,31438)
]:
    add_group('resources.wood.'+wood+'.log-to-plank', 'log → plank processing pair', [log_id,plank_id], 'high',
              'Candidate species-stage pair; the Wiki Plank Make table documents exact log-to-plank conversions. Keep raw log and processed plank state explicit.',
              ['https://oldschool.runescape.wiki/w/Plank_Make'])
for gem, uncut, cut in [('jade',1627,1611),('red-topaz',1629,1613),('onyx',6571,6573),('zenyte',19496,19493)]:
    add_group('resources.gem.'+gem, 'uncut → cut gem pair', [uncut,cut], 'high',
              'Candidate extension of gem families; exact Wiki item pages distinguish uncut/cut stages. Preserve state-specific IDs and do not include finished jewellery.',
              ['https://oldschool.runescape.wiki/w/Gem'])

with open(os.path.join(OUT, 'proposed-families.csv'), 'w', newline='', encoding='utf-8-sig') as f:
    writer = csv.DictWriter(f, fieldnames=list(proposals[0])); writer.writeheader(); writer.writerows(proposals)

summary = {
    'domain': 'farming-produce-and-skill-materials',
    'generated_from': 'tmp/semantic-audit/joined.jsonl',
    'effective_catalog_records': len(all_rows), 'candidate_universe_records': len(rows), 'review_queue_records': len(review),
    'candidate_inclusion': 'All actual preset resources and seeds-farming tags, all current FARMING category rows, every positive exact Wiki category in target skills/materials, and exact-ID cleanup rows with recipe edges to requested skills.',
    'wiki_join_status_in_candidate_universe': dict(status),
    'current_destination_counts': {f'{k[0]}/{k[1]}': v for k,v in sorted(current_dest.items())},
    'positive_wiki_category_counts': dict(sorted(cat_totals.items())),
    'positive_wiki_category_to_current_destination': {f'{k[0]} -> {k[1]}/{k[2]}':v for k,v in sorted(cat_dest.items())},
    'overlap_counts': dict(overlap),
    'existing_curated_group_rows': len(existing), 'proposed_source_backed_group_rows': len(proposals),
    'limitations': [
       'Wiki category membership is page-scoped; broad skill membership does not prove primary bank role.',
       'Recipe relationships are title-level and not proof for every item-ID variant.',
       'No absent category, recipe edge, source field, or fixture presence is treated as evidence of absence.',
       'Current tags in joined rows are the actual Java preset-tag baseline. Candidate rows and families are review recommendations, never automatic moves.',
       'The query must not treat the entire Farming category or the entire Smithing/Construction/Crafting categories as raw materials.',
       'Farming-produced herbs, crops, fibers, logs, and other outputs can have downstream Herblore, Cooking, Crafting, Fletching, Firemaking, or Construction uses; primary grouping follows exact mechanics and current workflow context.'
    ],
    'source_pages': [
       'https://oldschool.runescape.wiki/w/Farming','https://oldschool.runescape.wiki/w/Growth',
       'https://oldschool.runescape.wiki/w/Tithe_Farm','https://oldschool.runescape.wiki/w/Tithe_farm_guide',
       'https://oldschool.runescape.wiki/w/Chambers_of_Xeric','https://oldschool.runescape.wiki/w/Fletching',
       'https://oldschool.runescape.wiki/w/Mining','https://oldschool.runescape.wiki/w/Smithing',
       'https://oldschool.runescape.wiki/w/Plank_Make','https://oldschool.runescape.wiki/w/Construction',
       'https://oldschool.runescape.wiki/w/Crafting','https://oldschool.runescape.wiki/w/Firemaking',
       'https://oldschool.runescape.wiki/w/Sailing'
    ]
}
with open(os.path.join(OUT, 'coverage.json'), 'w', encoding='utf-8') as f: json.dump(summary,f,indent=2,ensure_ascii=False)
print(json.dumps({'effective_catalog_records':len(all_rows),'candidate_universe_records':len(rows),'review_queue_records':len(review),
                  'wiki_join_status':dict(status),'positive_category_counts':dict(sorted(cat_totals.items())),
                  'current_destinations':summary['current_destination_counts'],'group_rows':len(existing),'proposed_families':len(proposals)},indent=2,ensure_ascii=False))
