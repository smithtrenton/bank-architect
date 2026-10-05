#!/usr/bin/env python3
"""Reproducible source-role and role-precedence pass for the frozen CLUE/UNIQUE ledger."""
from __future__ import annotations
import argparse, hashlib, json, re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
DEFAULT_INPUT = ROOT / "tmp/category-certification/reviews/collections/clue-unique-corrected.jsonl"
DEFAULT_INDEX = ROOT / "tmp/category-certification/wiki-articles/article-index.json"
DEFAULT_OUT = ROOT / "tmp/category-certification/reviews/collections/clue-unique-second-pass.jsonl"
DEFAULT_DELTA = ROOT / "tmp/category-certification/reviews/collections/clue-unique-second-pass-delta.jsonl"
DEFAULT_POLICY = ROOT / "tools/research/semantic-grouping-audit/certification/clue-unique-second-pass-policy.json"

# Exact IDs are deliberately enumerated. A member never inherits another variant's role.
CASES = {
 "clue_container_or_locator": {
  "ids": [13648,13649,13650,13651,19712,19714,19716,19718,23127,23129,20358,20360,20362,20364,23442,24361,24362,24363,24364,24365,24366,19939,23183],
  "role":"functional_clue_utility", "targetCategory":"CLUE", "targetSubcategory":"treasure-trail",
  "quotePattern":r"(?i)(?:opening|searching|open|used)\b[^.!?]{0,180}(?:clue scroll|hot.?cold|clue)"
 },
 "upgrade_or_weapon_component": {
  "ids":[4082,12783,23956,25635,25637,25639,30628,30631],
  "role":"equipment_upgrade_material", "targetCategory":"UNIQUE", "targetSubcategory":None,
  "allowedSubcategories":["equipment-upgrade","weapon-upgrade"],
  "quotePattern":r"(?i)(?:used to craft|used on|can be turned into|used alongside|one of the three parts|used to create)[^.!?]{0,190}"
 },
 "boss_access_component": {
  "ids":[19679,19681,19683], "role":"boss_access_material", "targetCategory":"UNIQUE", "targetSubcategory":"boss-access-key",
  "quotePattern":r"(?i)(?:combined|combine)[^.!?]{0,190}(?:used to reach|reach)"
 },
 "achievement_gallery_display": {
  "ids":[12007,23064], "role":"display_trophy", "targetCategory":"CLUE", "targetSubcategory":"collection-trophy",
  "quotePattern":r"(?i)(?:used on|use on)[^.!?]{0,190}boss lair display"
 },
 "single_use_ability_unlock": {
  "ids":[21034,21047,21079,30626,30627], "role":"single_use_ability_unlock", "targetCategory":"UNIQUE", "targetSubcategory":None,
  "quotePattern":r"(?i)(?:reading it allows|reading it requires)[^.!?]{0,190}(?:unlock|consum|prayer)"
 },
 "clue_reward_gear_components": {
  "ids":[3827,3828,3829,3830,3831,3832,3833,3834,3835,3836,3837,3838,12613,12614,12615,12616,12617,12618,12619,12620,12621,12622,12623,12624],
  "role":"equipment_upgrade_material", "targetCategory":"CLUE", "targetSubcategory":"treasure-trail",
  "quotePattern":r"(?i)all four[^.!?]{0,220}equipable in the \[\[shield slot\]\]"
 },
 "upgrade_material_components": {
  "ids":[11931,11932,11933], "role":"equipment_upgrade_material", "targetCategory":"UNIQUE", "targetSubcategory":"equipment-upgrade",
  "quotePattern":r"(?i)can be forged into a \[\[malediction ward\]\]"
 },
 "key_components": {
  "ids":[985,987], "role":"key_material", "targetCategory":"UNIQUE", "targetSubcategory":"key-material",
  "quotePattern":r"(?i)is used with a \[\[(?:loop|tooth) half of key\]\] to make a \[\[crystal key\]\]"
 },
 "other_function_conflict": {
  "ids":[11258,21275,30640], "role":None, "targetCategory":None, "targetSubcategory":None,
  "quotePattern":r"(?i)(?:can be used to create|can be combined with|can be brought to)[^.!?]{0,190}",
  "rolesById":{"11258":"functional_tool","21275":"equipment_upgrade_material","30640":"functional_material"}
 }
}

def load_rows(path): return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
def write_jsonl(path, rows): path.parent.mkdir(parents=True,exist_ok=True); path.write_text("".join(json.dumps(r,ensure_ascii=False,separators=(",",":"))+"\n" for r in rows),encoding="utf-8")
def exact_pages(index):
 out={}
 for title,article in index.items():
  for item_id in article.get("exactInfoboxItemIds",[]):
   out.setdefault(int(item_id),[]).append((title,article))
 return out

def quote_for(path,pattern):
 text=Path(path).read_text(encoding="utf-8")
 m=re.search(pattern,text)
 if not m: return None
 # Evidence excerpts are exact source substrings; markup is kept intact for verifier fidelity.
 start=max(text.rfind(".",0,m.start()),text.rfind("|",0,m.start()),text.rfind("\n",0,m.start()))+1
 ends=[x for x in (text.find(".",m.end()),text.find("|",m.end()),text.find("\n",m.end())) if x>=0]
 end=min(ends) if ends else min(len(text),m.end()+190)
 q=text[start:end].strip()
 if len(q)>240: q=text[m.start():min(len(text),m.end()+80)].strip()
 return q if q and q in text else None

def wiki_evidence(item_id, title, article, quote):
 return {"kind":"exact_wiki","sourceTitle":title,"source":article["sourceUrl"],"sourceRevision":article["revid"],"sourceHash":"sha256:"+article["sha256"],"itemId":item_id,"quote":quote}

def main():
 ap=argparse.ArgumentParser(); ap.add_argument("--input",type=Path,default=DEFAULT_INPUT); ap.add_argument("--article-index",type=Path,default=DEFAULT_INDEX); ap.add_argument("--output",type=Path,default=DEFAULT_OUT); ap.add_argument("--delta",type=Path,default=DEFAULT_DELTA); ap.add_argument("--policy",type=Path,default=DEFAULT_POLICY); a=ap.parse_args()
 rows=load_rows(a.input); index=json.loads(a.article_index.read_text(encoding="utf-8")); pages=exact_pages(index); by_id={int(r["itemId"]):r for r in rows}; before={i:json.dumps(r,sort_keys=True,ensure_ascii=False) for i,r in by_id.items()}; policy={"version":2,"inputs":{"ledgerSha256":hashlib.sha256(a.input.read_bytes()).hexdigest(),"articleIndexSha256":hashlib.sha256(a.article_index.read_bytes()).hexdigest()},"strictRules":[
  "Exact numeric infobox ID must match the reviewed row; never propagate across a shared article or morph.",
  "Reward/drop provenance and Category:Collection log items do not independently prove primary placement or a semantic role.",
  "Direct item-specific mechanics establish roles independently of origin. If mechanics conflict with the current primary category/subcategory, preserve the roles and keep the row unresolved for taxonomy review.",
  "An ongoing gear/ability/access use takes precedence over reward-origin-only reasoning for role assignment; it does not by itself choose a plugin primary category.",
  "A documented Achievement Gallery boss-lair display is direct display-trophy evidence. Collection-log membership remains a separate fact.",
  "A quest-only label or explicit no-use fact does not disprove retained cosmetic value for an equipable wearable.",
  "Every proposed role addition below requires the exact ID's own pinned page and verbatim quote; no title/family fan-out."],"caseGroups":[]}
 delta=[]
 for case, spec in CASES.items():
  group={"case":case,"ids":spec["ids"],"sourceRule":spec["quotePattern"],"role":spec["role"],"targetCategory":spec["targetCategory"],"targetSubcategory":spec["targetSubcategory"],"reviewed":[]}
  for item_id in spec["ids"]:
   row=by_id.get(item_id)
   if not row: group["reviewed"].append({"itemId":item_id,"status":"not_in_frozen_packet"}); continue
   matches=pages.get(item_id,[])
   exact=[(t,art) for t,art in matches if str(item_id) in art.get("variants",{}) and item_id in [int(v) for k,v in art["variants"][str(item_id)].get("params",{}).items() if re.fullmatch(r"id\d*",k) and str(v).isdigit()]]
   if len(exact)!=1: group["reviewed"].append({"itemId":item_id,"status":"unresolved_exact_page_ambiguous_or_absent","candidateTitles":[t for t,_ in matches]}); continue
   title,art=exact[0]; quote=quote_for(art["path"],spec["quotePattern"])
   if not quote: group["reviewed"].append({"itemId":item_id,"status":"unresolved_no_mechanics_quote","sourceTitle":title,"revision":art["revid"],"sourceHash":"sha256:"+art["sha256"]}); continue
   ev=wiki_evidence(item_id,title,art,quote)
   row.setdefault("evidence",[]).append(ev)
   roles=set(row.get("proposedRoles") or [])
   if spec["role"]: roles.add(spec["role"])
   if item_id in spec.get("rolesById",{}): roles.add(spec["rolesById"][item_id])
   if case=="achievement_gallery_display": roles.add("collection_log_member") if len(art.get("exactInfoboxItemIds", [])) == 1 and "[[Category:Collection log items]]" in Path(art["path"]).read_text(encoding="utf-8") else None
   row["proposedRoles"]=sorted(roles) if roles else []
   if case in ("clue_container_or_locator","boss_access_component","achievement_gallery_display"):
    row["decision"]="certify"; row["proposedCategory"]=spec["targetCategory"]; row["proposedSubcategory"]=spec["targetSubcategory"]
    row["rationale"]=(f"Exact-ID pinned article directly documents the reviewed item's {spec['role'].replace('_',' ')} mechanic. The cited page is bound to item ID {item_id}; category and subcategory match this case's direct primary-function rule. Any Collection Log facet is preserved as an independent role only when present on this exact page.")
    row["semanticPredicate"]=f"The exact item is placed by its directly documented {spec['role'].replace('_',' ')} function, separately from acquisition provenance."
   elif case in ("upgrade_or_weapon_component","single_use_ability_unlock"):
    # Primary category path is either already consistent or taxonomy needs root choice.
    if row.get("proposedCategory")==spec["targetCategory"] and (row.get("proposedSubcategory")==spec["targetSubcategory"] or row.get("proposedSubcategory") in spec.get("allowedSubcategories",[])):
     row["decision"]="certify"; row["rationale"]=f"Exact-ID pinned article directly documents {spec['role'].replace('_',' ')} use. This is a functional use independent of reward provenance."
    else:
     row["decision"]="unresolved"; row["rationale"]=f"Exact-ID pinned article directly documents {spec['role'].replace('_',' ')} use. The source establishes the role, but the current category/subcategory does not encode it cleanly; primary-placement policy is unresolved."
    row["semanticPredicate"]=f"Record direct item-specific {spec['role'].replace('_',' ')} mechanics separately from source/reward provenance."
   elif case=="other_function_conflict":
    row["decision"]="unresolved"; row["rationale"]="Exact-ID page proves a functional use that conflicts with the current collection/cosmetic primary placement; this source establishes role only, and taxonomy requires review."
    row["semanticPredicate"]="Preserve direct ongoing/use mechanics independently; do not infer category from collection-log or reward origin."
   group["reviewed"].append({"itemId":item_id,"status":row["decision"],"sourceTitle":title,"revision":art["revid"],"sourceHash":"sha256:"+art["sha256"],"quote":quote})
  policy["caseGroups"].append(group)
 for item_id,row in by_id.items():
  if before[item_id]!=json.dumps(row,sort_keys=True,ensure_ascii=False): delta.append(row)
 write_jsonl(a.output,[by_id[i] for i in sorted(by_id)])
 write_jsonl(a.delta,delta)
 a.policy.parent.mkdir(parents=True,exist_ok=True); a.policy.write_text(json.dumps(policy,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
 print(json.dumps({"rows":len(by_id),"delta":len(delta),"cases":{g["case"]:sum(1 for r in g["reviewed"] if r["status"] in ("certify","revise","unresolved")) for g in policy["caseGroups"]},"unresolved":sum(1 for r in by_id.values() if r["decision"]=="unresolved"),"output":str(a.output),"deltaPath":str(a.delta),"policy":str(a.policy)},indent=2))
if __name__=="__main__": main()




