#!/usr/bin/env python3
"""Offline-only Wiki semantic audit. Never imported or shipped by the RuneLite plugin."""
import argparse, collections, csv, datetime, hashlib, json, pathlib, re, time, urllib.parse, urllib.request

API = "https://oldschool.runescape.wiki/api.php"
UA = "BankArchitectResearch/1.0 (offline full-catalog semantic grouping audit)"
ROOT = pathlib.Path(__file__).resolve().parents[3]
CATEGORIES = [
 "Equipable items", "Edible items", "Quest items", "Tools", "Skilling equipment",
 "Food", "Drinks", "Cooking ingredients", "Farming produce", "Herblore secondaries",
 "Herblore", "Potions", "Herbs", "Seeds", "Saplings", "Runes", "Currency",
 "Teleportation items", "Containers", "Storage items", "Light sources",
 "Magic armour", "Melee armour", "Ranged armour", "Ammunition", "Arrows", "Bolts",
 "Thrown weapons", "Cosmetic items", "Cosmetic clothing", "Random event rewards",
 "Clue scrolls", "Treasure Trails rewards", "Items used in emote clues",
 "Collection log items", "Pets", "Minigame items", "Tutorial Island", "Unobtainable items",
 "Discontinued items", "Leagues items", "Blighted items", "Sailing",
 "Crafting materials", "Fletching materials", "Construction materials", "Firemaking",
 "Ores", "Metal bars", "Logs", "Gems", "Leather", "Bones", "Textiles",
 "Skilling supplies", "Slayer equipment", "Farming", "Cooking", "Crafting",
 "Construction", "Fletching", "Mining", "Smithing", "Hunter", "Agility",
 "Runecraft", "Clothing", "Skillcapes", "Teleportation jewellery",
 "Treasure Trails emote items", "Herblore ingredients", "Item storage",
]
ITEM_FIELDS = ["page_name", "page_name_sub", "item_name", "item_id", "default_version",
 "quest", "tradeable", "is_members_only", "examine", "release_date", "removal_date",
 "version_anchor", "high_alchemy_value", "weight"]
BONUS_FIELDS = ["page_name", "page_name_sub", "equipment_slot", "stab_attack_bonus",
 "slash_attack_bonus", "crush_attack_bonus", "range_attack_bonus", "magic_attack_bonus",
 "stab_defence_bonus", "slash_defence_bonus", "crush_defence_bonus", "range_defence_bonus",
 "magic_defence_bonus", "strength_bonus", "ranged_strength_bonus", "prayer_bonus",
 "magic_damage_bonus", "weapon_attack_speed", "weapon_attack_range", "combat_style"]
RECIPE_FIELDS = ["page_name", "page_name_sub", "uses_material", "uses_tool", "uses_facility",
 "uses_skill", "source_template", "production_json", "is_members_only"]
_last_request = 0.0

def utc():
 return datetime.datetime.now(datetime.timezone.utc).isoformat()

def request(params):
 global _last_request
 time.sleep(max(0.0, 1.0-(time.monotonic()-_last_request)))
 url = API + "?" + urllib.parse.urlencode(dict(format="json", formatversion=2, **params))
 req = urllib.request.Request(url, headers={"User-Agent":UA})
 for attempt in range(3):
  _last_request = time.monotonic()
  try:
   with urllib.request.urlopen(req, timeout=45) as response:
    data=json.load(response)
   if data.get("error"): raise RuntimeError(str(data["error"]))
   return data, url
  except Exception:
   if attempt == 2: raise
   time.sleep(2 * (attempt+1))

def save(path, data):
 path.parent.mkdir(parents=True,exist_ok=True)
 path.write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding="utf-8")

def fetch_bucket(name, fields, cache, refresh=False, size=5000, label=None):
 label=label or name
 pages=[]; offset=0; after_page_name=None
 while True:
  dest=cache/f"{label}-{offset:06d}.json"
  query=f"bucket('{name}').select("+",".join(json.dumps(f) if "'" in f else "'"+f+"'" for f in fields)+")"
  if after_page_name is not None:
   query+=f".where('page_name','>',{json.dumps(after_page_name,ensure_ascii=False)})"
  query+=f".orderBy('page_name','asc').limit({size}).run()"
  if dest.exists() and not refresh:
   packet=json.loads(dest.read_text(encoding="utf-8"))
   if packet["query"] != query: raise ValueError(f"Cached query or pagination schema differs at {dest}; use a new cache directory or --refresh to fetch a consistent snapshot")
  else:
   data,url=request({"action":"bucket","query":query})
   packet={"retrieved_at":utc(),"query":query,"source_url":url,"rows":data["bucket"]}
   save(dest,packet)
  batch=packet["rows"]
  if len(batch)<size:
   pages.extend(batch)
   print(f"{label}: {len(pages)} rows",flush=True)
   break
  last_page_name=batch[-1].get("page_name")
  if not last_page_name: raise ValueError(f"{label}: page_name missing from a full Bucket batch; cannot paginate safely")
  boundary_start=next((i for i,row in enumerate(batch) if row.get("page_name")==last_page_name),None)
  if boundary_start is None or boundary_start==0:
   raise ValueError(f"{label}: page {last_page_name!r} fills the {size}-row batch; cannot safely determine or advance past the complete page")
  # Keep the entire final page group out of this batch. The next query starts
  # after the last accepted page and fetches this group again in full.
  accepted=batch[:boundary_start]
  pages.extend(accepted)
  print(f"{label}: {len(pages)} rows",flush=True)
  after_page_name=accepted[-1].get("page_name")
  if not after_page_name: raise ValueError(f"{label}: page_name missing from accepted Bucket rows; cannot paginate safely")
  offset += len(accepted)
 exact_rows=[json.dumps(row,sort_keys=True,ensure_ascii=False,separators=(",",":")) for row in pages]
 unique_exact_rows=len(set(exact_rows))
 duplicate_exact_rows=len(exact_rows)-unique_exact_rows
 if duplicate_exact_rows:
  raise ValueError(f"{label}: {duplicate_exact_rows} exact duplicate Bucket rows across {len(pages)} fetched rows; inspect snapshot consistency before joining")
 save(cache/(label+".json"),{"rows":pages,"retrieved_at":utc(),"fields":fields,
  "row_count":len(pages),"unique_exact_row_count":unique_exact_rows,"duplicate_exact_row_count":duplicate_exact_rows})
 return pages

def fetch(args):
 cache=args.cache;cache.mkdir(parents=True,exist_ok=True)
 cats_file=cache/"category-schema.json"
 if cats_file.exists() and not args.refresh: cats=json.loads(cats_file.read_text(encoding="utf-8"))
 else:
  present=[];missing=[]
  for offset in range(0,len(CATEGORIES),40):
   data,url=request({"action":"query","prop":"info","titles":"|".join("Category:"+c for c in CATEGORIES[offset:offset+40])})
   for page in data["query"]["pages"]:
    (missing if page.get("missing",False) else present).append(page["title"].removeprefix("Category:"))
  cats={"present":sorted(present),"missing":sorted(missing),"retrieved_at":utc()}
  save(cats_file,cats)
 print(f"Category fields: {len(cats['present'])} existing, {len(cats['missing'])} requested names unavailable",flush=True)
 item_rows=fetch_bucket("infobox_item",ITEM_FIELDS,cache,args.refresh)
 # Category predicates each add SQL joins; narrow passes avoid database join limits.
 def key(r):return (r["page_name"],r.get("page_name_sub"),tuple(sorted(map(str,listify(r.get("item_id"))))))
 item_index=collections.defaultdict(list)
 for r in item_rows:item_index[key(r)].append(r)
 mismatches=[]
 for offset in range(0,len(cats["present"]),12):
  names=cats["present"][offset:offset+12]
  category_rows=fetch_bucket("infobox_item",["page_name","page_name_sub","item_id"]+["Category:"+c for c in names],cache,args.refresh,label=f"item_categories_{offset:02d}")
  for r in category_rows:
   if key(r) not in item_index:mismatches.append({"pass":offset,"key":key(r)})
   for target in item_index.get(key(r),[]):
    target.update({f:v for f,v in r.items() if f.startswith("Category:")})
 save(cache/"category-merge-mismatches.json",mismatches)
 if mismatches:raise ValueError(f"Category snapshot drift: {len(mismatches)} unmatched rows")
 save(cache/"infobox_item.json",{"rows":item_rows,"retrieved_at":utc(),"fields":ITEM_FIELDS+["Category:"+c for c in cats["present"]],"category_merge_unmatched_rows":len(mismatches)})
 fetch_bucket("infobox_bonuses",BONUS_FIELDS,cache,args.refresh)
 fetch_bucket("recipe",RECIPE_FIELDS,cache,args.refresh)
 fetch_bucket("item_id",["page_name","page_name_sub","id"],cache,args.refresh)
 manifest={"retrieved_at":utc(),"api":API,"user_agent":UA,"license":"CC BY-NC-SA 3.0",
  "categories":cats,"files":[{"path":str(x.relative_to(cache)),"sha256":hashlib.sha256(x.read_bytes()).hexdigest(),"bytes":x.stat().st_size} for x in sorted(cache.glob("*.json")) if x.name != "manifest.json"]}
 save(cache/"manifest.json",manifest)

def enrich(args):
 cache=args.cache
 schema_path=cache/"category-extra-schema.json"
 if schema_path.exists() and not args.refresh:
  schema=json.loads(schema_path.read_text(encoding="utf-8"))
 else:
  names=["Items needed for an emote clue","Warm clothing","Items storable in the costume room","Unfinished potions","Crops","Keys","Champions' Challenge"]
  data,url=request({"action":"query","prop":"info","titles":"|".join("Category:"+c for c in names)})
  schema={"present":[],"missing":[],"retrieved_at":utc(),"source_url":url}
  for p in data["query"]["pages"]:schema["missing" if p.get("missing",False) else "present"].append(p["title"].removeprefix("Category:"))
  save(schema_path,schema)
 packet=json.loads((cache/"infobox_item.json").read_text(encoding="utf-8"));index=collections.defaultdict(list)
 def key(r):return(r["page_name"],r.get("page_name_sub"),tuple(sorted(map(str,listify(r.get("item_id"))))))
 for r in packet["rows"]:index[key(r)].append(r)
 mismatches=[]
 for offset in range(0,len(schema["present"]),10):
  label=f"item_extra_categories_{offset:02d}"
  cached=cache/(label+".json")
  # Preserve the original query's field order when resuming a cached snapshot.
  fields=json.loads(cached.read_text(encoding="utf-8"))["fields"] if cached.exists() and not args.refresh else ["page_name","page_name_sub","item_id"]+["Category:"+c for c in schema["present"][offset:offset+10]]
  rows=fetch_bucket("infobox_item",fields,cache,args.refresh,label=label)
  for r in rows:
   if key(r) not in index:mismatches.append(key(r))
   for target in index.get(key(r),[]):target.update({k:v for k,v in r.items() if k.startswith("Category:")})
 if mismatches:raise ValueError(f"Category enrichment snapshot drift: {len(mismatches)} unmatched rows")
 packet["additional_category_fields"]=schema["present"];save(cache/"infobox_item.json",packet)
 save(cache/"manifest.json",{"retrieved_at":utc(),"api":API,"user_agent":UA,"license":"CC BY-NC-SA 3.0","files":[{"path":str(x.relative_to(cache)),"sha256":hashlib.sha256(x.read_bytes()).hexdigest(),"bytes":x.stat().st_size} for x in sorted(cache.glob("*.json")) if x.name!="manifest.json"]})

def normalize(s):
 return re.sub(r"\s+"," ",str(s or "").strip()).casefold()

def listify(v):
 return v if isinstance(v,list) else ([] if v is None else [v])

def ids(row):
 out=[]
 for value in listify(row.get("item_id")):
  if re.fullmatch(r"[1-9][0-9]*",str(value).strip()): out.append(int(str(value).strip()))
 return out

def wiki_url(title):
 return "https://oldschool.runescape.wiki/w/"+urllib.parse.quote(str(title).replace(" ","_"),safe="/")

def flag(facts,category):
 # False is never evidence of absence: only record positive page-scoped claims.
 return any(f.get("Category:"+category) is True for f in facts)

def join(args):
 out=args.output;out.mkdir(parents=True,exist_ok=True)
 item_rows=json.loads((args.cache/"infobox_item.json").read_text(encoding="utf-8"))["rows"]
 bonus_rows=json.loads((args.cache/"infobox_bonuses.json").read_text(encoding="utf-8"))["rows"]
 recipes=json.loads((args.cache/"recipe.json").read_text(encoding="utf-8"))["rows"]
 lookup_by_id=collections.defaultdict(list);infobox_by_source_key=collections.defaultdict(list)
 lookup_path=args.cache/"item_id.json"
 if lookup_path.exists():
  for r in json.loads(lookup_path.read_text(encoding="utf-8"))["rows"]:
   for ident in ids(dict(item_id=r.get("id"))):lookup_by_id[ident].append(r)
 for r in item_rows:infobox_by_source_key[(r["page_name"],r.get("page_name_sub"))].append(r)
 wiki_by_id=collections.defaultdict(list);bonuses_by_key=collections.defaultdict(list);bonuses_by_page=collections.defaultdict(list)
 for r in item_rows:
  for ident in ids(r): wiki_by_id[ident].append(r)
 for r in bonus_rows:
  key=(normalize(r["page_name"]),normalize(r.get("page_name_sub")))
  bonuses_by_key[key].append(r);bonuses_by_page[key[0]].append(r)
 recipe_roles=collections.defaultdict(lambda:collections.defaultdict(list))
 for r in recipes:
  for field,role in (("uses_material","recipe_material"),("uses_tool","recipe_tool"),("uses_facility","recipe_facility")):
   for title in listify(r.get(field)):
    recipe_roles[normalize(title)][role].append({"page":r["page_name"],"page_sub":r.get("page_name_sub"),"skills":listify(r.get("uses_skill"))})
 effective=list(csv.DictReader(args.effective.open(encoding="utf-8-sig"),delimiter="\t"))
 registry=[]
 for line in args.registry.read_text(encoding="utf-8-sig").splitlines():
  cells=line.split("\t")
  if len(cells)==4:
   registry.append({"id":cells[0],"name":cells[1],"category":cells[2],"constant":cells[3]})
 excluded=list(csv.DictReader(args.excluded.open(encoding="utf-8-sig"),delimiter="\t"))
 stats=collections.Counter();joined=[];flat=[];findings=[]
 tag_rows=list(csv.DictReader(args.tag_map.open(encoding="utf-8-sig"),delimiter="\t"))
 tagmap={int(r["item_id"]):r for r in tag_rows}
 if len(tagmap)!=len(tag_rows):raise ValueError("Duplicate exact IDs in preset export")
 if set(tagmap)!={int(r["itemId"]) for r in effective}:raise ValueError("Preset and effective export ID sets differ")
 for item in effective:
  ident=int(item["itemId"]);facts=wiki_by_id.get(ident,[])
  unique_facts={json.dumps(f,sort_keys=True):f for f in facts}
  facts=list(unique_facts.values())
  record={"item_id":ident,"name":item["name"],"catalog_category":item["itemCategory"],"subcategory":item["subcategory"],"preset_category":item["ironmanTabKey"],"constant":item["constantName"],"variant_flags":item["variantFlags"].split(",") if item["variantFlags"] else [],"family_hint":item["variantFamilyKey"],
   "wiki_join_status":"NO_EXACT_ID_FACT" if not facts else ("EXACT_ID_SINGLE" if len(facts)==1 else "EXACT_ID_MULTIPLE"),
   "wiki_records":facts,"wiki_urls":sorted({wiki_url(f["page_name"]) for f in facts})}
  links=lookup_by_id.get(ident,[]);link_warnings=[]
  for link in links:
   same_key=infobox_by_source_key.get((link['page_name'],link.get('page_name_sub')),[])
   if not same_key:link_warnings.append({'page':link['page_name'],'subpage':link.get('page_name_sub'),'reason':'NO_ITEM_INFOBOX_FOR_LOOKUP_KEY'})
   for source in same_key:
    raw_ids=listify(source.get('item_id'))
    nonnumeric=[str(v) for v in raw_ids if not re.fullmatch(r'[1-9][0-9]*',str(v).strip()) and re.search(r'(?<![0-9])'+str(ident)+r'$',str(v).strip())]
    if nonnumeric:link_warnings.append({'page':link['page_name'],'subpage':link.get('page_name_sub'),'reason':'NONNUMERIC_INFOBOX_ID_NAMESPACE','raw_ids':nonnumeric})
    elif ident not in ids(source):link_warnings.append({'page':link['page_name'],'subpage':link.get('page_name_sub'),'reason':'SAME_SOURCE_KEY_DIFFERENT_ITEM_ID','raw_ids':raw_ids})
  record['wiki_lookup_links']=links;record['wiki_lookup_warnings']=link_warnings
  record['wiki_lookup_status']='PRIMARY_INFOBOX_FACT_PRESENT' if facts else ('LOOKUP_LINK_ONLY_UNVERIFIED_NAMESPACE' if links else 'NO_WIKI_ID_LINK')
  if links:stats['with_alternate_lookup_link']+=1
  if links and not facts:stats['lookup_only_unverified']+=1
  if link_warnings:stats['with_lookup_namespace_or_source_key_warning']+=1
  cat=item["ironmanTabKey"];sub=item["subcategory"];baseline=tagmap[ident]
  if baseline["preset_category"]!=cat:raise ValueError(f"Preset category differs at {ident}")
  tag=baseline["preset_tag"]
  record["preset_tag"]=tag
  record["preset_tag_by_family"]=baseline["preset_tag_by_family"]
  roles=set();bonus_matches=[];recipe_evidence=[]
  for f in facts:
   key=(normalize(f["page_name"]),normalize(f.get("page_name_sub")))
   matches=bonuses_by_key.get(key,[])
   method="EXACT_PAGE_SUB" if matches else "NONE"
   if not matches and len(bonuses_by_page.get(key[0],[]))==1:
    matches=bonuses_by_page[key[0]];method="UNIQUE_PAGE_FALLBACK"
   if matches:
    bonus_matches.append({"item_page":f["page_name"],"item_page_sub":f.get("page_name_sub"),"method":method,"status":"UNIQUE" if len(matches)==1 else "AMBIGUOUS","records":matches})
   for title in {normalize(f["page_name"]),normalize(f.get("page_name_sub"))}:
    if title in recipe_roles:
     for role,ev in recipe_roles[title].items():
      roles.add(role);recipe_evidence.extend(dict(e,role=role,join_scope="WIKI_TITLE_RELATION_NOT_VARIANT_PROOF") for e in ev)
   for category in sorted(args.category_names):
    if f.get("Category:"+category) is True:roles.add("wiki_category:"+category)
   if f.get("quest") and normalize(f["quest"])!="no":roles.add("quest_associated")
  record.update(roles=sorted(roles),bonus_matches=bonus_matches,recipe_relations=recipe_evidence)
  stats[record["wiki_join_status"]]+=1
  if bonus_matches: stats["with_bonus_match"]+=1
  if recipe_evidence:stats["with_recipe_relation"]+=1
  stats["effective_records"]+=1
  detectors=[]
  def add(code,target,reason,confidence="CANDIDATE"):
   detectors.append(code);findings.append({"item_id":ident,"name":item["name"],"detector":code,"current_tag":tag,"candidate_tag":target,"confidence":confidence,"reason":reason,"source_urls":" | ".join(record["wiki_urls"]),"evidence_scope":"EXACT_ITEM_ID + PAGE_SCOPED_CATEGORIES; REVIEW VARIANT/OVERLAPS"})
  if facts:
   if flag(facts,"Currency") and tag!="currency":add("CURRENCY_ROLE_OUTSIDE_CURRENCY","currency","Wiki currency membership conflicts with the preset tag; activity reward grouping may explain policy.")
   if flag(facts,"Runes") and tag!="runes":add("RUNE_ROLE_OUTSIDE_RUNES","runes","Wiki rune role conflicts with preset tag; exact variant and consumable restrictions need review.")
   if flag(facts,"Edible items") and tag in {"cleanup","gear","tools","quest-items"}:add("EDIBLE_ROLE_IN_UNRELATED_TAG","food / produce / ingredients","Edibility is recorded; food versus ingredient, poison, novelty, and quest role remains to determine.")
   if flag(facts,"Equipable items") and tag in {"raw-resources","gems","ammo-components","produce","seeds","secondaries"}:add("EQUIPMENT_ROLE_IN_MATERIAL_TAG","gear / tools / cosmetics","Wiki page records equipability; verify row variant and actual use, not merely a wearable name.")
   if flag(facts,"Tools") and tag=="cleanup":add("TOOL_ROLE_IN_CLEANUP","tools / containers","Wiki tool role exists but catalog keeps cleanup; quest and restricted tools require review.")
   if flag(facts,"Teleportation items") and tag=="cleanup":add("TELEPORT_ROLE_IN_CLEANUP","teleports","Wiki teleport use exists but catalog keeps cleanup; charge and retained-function states require review.")
   if flag(facts,"Skilling equipment") and tag in {"cleanup","raw-resources","clues"}:add("SKILLING_EQUIPMENT_OUTSIDE_TOOLS","tools / skilling-outfits","Wiki skilling-equipment role exists; activity cosmetics and non-default states require review.")
   if flag(facts,"Herblore secondaries") and tag not in {"secondaries","herblore-other"}:add("SECONDARY_ROLE_OUTSIDE_HERBLORE","secondaries","Wiki secondary role indicates recipe use; preserve other Crafting/Farming uses.")
   if flag(facts,"Crops") and tag in {"cleanup","gear","tools"}:add("PRODUCE_ROLE_IN_UNRELATED_TAG","produce / Herblore inputs","Wiki produce role disagrees with apparent item identity; downstream use requires review.")
   if tag=="cleanup" and roles & {"recipe_material","recipe_tool"}:add("RECIPE_ROLE_IN_CLEANUP","material / tool / quest workflow","Wiki recipe graph contains this page/name as an input or tool; title relationship is not exact variant proof.")
   if "quest_associated" in roles and tag not in {"quest-items","cleanup"}:add("QUEST_FUNCTION_OVERLAP","retain function or quest-items","Quest association overlaps an assigned functional role; no automatic move to cleanup.", "OVERLAP_REVIEW")
   if record["variant_flags"] and facts:stats["variant_flagged_wiki_records"]+=1
  else:
   detectors.append("WIKI_ID_COVERAGE_GAP")
  record["detectors"]=detectors;joined.append(record)
  flat.append({"item_id":ident,"name":item["name"],"catalog_category":item["itemCategory"],"subcategory":sub,"preset_category":cat,"preset_tag":tag,"preset_tag_by_family":record["preset_tag_by_family"],"constant":item["constantName"],"variant_flags":item["variantFlags"],"family_hint":item["variantFamilyKey"],"wiki_join_status":record["wiki_join_status"],"wiki_fact_count":len(facts),"wiki_lookup_status":record["wiki_lookup_status"],"wiki_lookup_pages":" | ".join(sorted({r["page_name"] for r in links})),"wiki_lookup_warning_codes":" | ".join(sorted({r["reason"] for r in link_warnings})),"wiki_pages":" | ".join(sorted({f["page_name"] for f in facts})),"wiki_urls":" | ".join(record["wiki_urls"]),"roles":" | ".join(sorted(roles)),"detectors":" | ".join(detectors),"bonus_join_methods":" | ".join(sorted({m["method"] for m in bonus_matches})),"recipe_relation_count":len(recipe_evidence)})
 with (out/"joined.jsonl").open("w",encoding="utf-8") as f:
  for r in joined:f.write(json.dumps(r,ensure_ascii=False)+"\n")
 for name,rr in (("catalog-semantic-audit.csv",flat),("mechanical-findings.csv",findings),("excluded-cache-records.csv",excluded)):
  if rr:
   with (out/name).open("w",encoding="utf-8-sig",newline="") as f:
    w=csv.DictWriter(f,fieldnames=rr[0].keys());w.writeheader();w.writerows(rr)
 statuses={}
 for r in registry:
  ident=int(r["id"]) if r["id"].isdigit() else None
  statuses[r["id"]]=r
 effective_by_id={r["item_id"]:r for r in flat}
 excluded_by_id={int(r["itemId"]):r for r in excluded}
 universe=[]
 for r in registry:
  ident=int(r["id"]) if r["id"].isdigit() and int(r["id"])>0 else None
  current=effective_by_id.get(ident);ex=excluded_by_id.get(ident)
  universe.append({"item_id":r["id"],"registry_name":r["name"],"constant":r["constant"],"audit_status":"EFFECTIVE_NAMED_ITEM" if current else ("EXCLUDED_CACHE_RECORD" if ex else "OMITTED_INVALID_OR_NULL_NAME"),"exclusion_reason":ex["reason"] if ex else "","wiki_join_status":current["wiki_join_status"] if current else "OUTSIDE_EFFECTIVE_EXPORT"})
 with (out/"registry-universe.csv").open("w",encoding="utf-8-sig",newline="") as f:
  w=csv.DictWriter(f,fieldnames=universe[0].keys());w.writeheader();w.writerows(universe)
 if len(effective_by_id)!=len(effective):raise ValueError("Duplicate effective item IDs")
 if set(effective_by_id)&set(excluded_by_id):raise ValueError("Effective/excluded ID overlap")
 if len(registry)!=len(effective)+len(excluded)+sum(r["audit_status"]=="OMITTED_INVALID_OR_NULL_NAME" for r in universe):raise ValueError("Universe accounting mismatch")
 summary={"generated_at":utc(),"scope":"Offline catalog/preset baseline; no live account/bank reads; no production changes",
  "registry_rows":len(registry),"registry_distinct_positive_ids":sum(k.isdigit() and int(k)>0 for k in statuses),"excluded_cache_records":len(excluded),"omitted_invalid_or_null_name_rows":len(registry)-len(effective)-len(excluded),
  "counts":dict(stats),"mechanical_finding_count":len(findings),"mechanically_flagged_distinct_items":len({r["item_id"] for r in findings}),"finding_detector_counts":dict(collections.Counter(r["detector"] for r in findings)),
  "categories":json.loads((args.cache/"category-schema.json").read_text(encoding="utf-8")),
  "additional_categories":json.loads((args.cache/"category-extra-schema.json").read_text(encoding="utf-8")) if (args.cache/"category-extra-schema.json").exists() else {},
  "preset_export_sha256":hashlib.sha256(args.tag_map.read_bytes()).hexdigest(),
  "limitations":["No missing Wiki/category/bonus data is treated as proof of absence.","Categories are page-scoped, not necessarily row-variant properties; false flags are not negative facts.","All exact-ID rows are preserved, including non-default versions and multi-match conflicts.","Recipe relationships are exact Wiki title/name edges, not evidence for every item-ID variant.","Preset tag mapping is an offline baseline; runtime gear stats, owned-tool selection and account options are contextual.","Alternate item_id bucket links remain separate: bare numeric links may correspond to historical/interface/beta namespaces or construction definitions, and never propagate item facts.","No proposed tag automatically changes production classifications."]}
 save(out/"summary.json",summary)
 print(json.dumps(summary,indent=2),flush=True)

def main():
 parser=argparse.ArgumentParser()
 parser.add_argument("command",choices=["fetch","enrich","join"])
 parser.add_argument("--cache",type=pathlib.Path,default=ROOT/"tmp/semantic-audit/cache")
 parser.add_argument("--output",type=pathlib.Path,default=ROOT/"tmp/semantic-audit")
 parser.add_argument("--effective",type=pathlib.Path,default=ROOT/"tmp/semantic-audit/effective.tsv")
 parser.add_argument("--excluded",type=pathlib.Path,default=ROOT/"tmp/semantic-audit/excluded.tsv")
 parser.add_argument("--tag-map",type=pathlib.Path,default=ROOT/"tmp/semantic-audit/preset-tags.tsv")
 parser.add_argument("--registry",type=pathlib.Path,default=ROOT/"src/main/resources/com/pkoka5/ironmanbankarchitect/catalog/item-registry.tsv")
 parser.add_argument("--refresh",action="store_true")
 args=parser.parse_args()
 if args.command=="fetch":fetch(args)
 elif args.command=="enrich":enrich(args)
 else:
  args.category_names=json.loads((args.cache/"category-schema.json").read_text(encoding="utf-8"))["present"]
  extra=args.cache/"category-extra-schema.json"
  if extra.exists():args.category_names+=json.loads(extra.read_text(encoding="utf-8"))["present"]
  join(args)
if __name__=="__main__":main()
