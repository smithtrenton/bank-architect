#!/usr/bin/env python3
"""Certify exact readable Treasure Trails steps using a root-reviewed positive rule."""
import argparse,collections,hashlib,json,pathlib,re
ROOT=pathlib.Path(__file__).resolve().parents[4]
HERE=pathlib.Path(__file__).resolve().parent
PACKET=ROOT/'tmp/category-certification/reviewer-packets/clue-unique.jsonl'
INDEX=ROOT/'tmp/category-certification/wiki-articles/article-index.json'
POLICY=HERE/'clue-scroll-approved-rule.json'
ITEM_BOX=re.compile(r'\{\{Infobox Item[ \t]*\r?\n(.*?)\r?\n\}\}',re.S)
NAME=re.compile(r'Clue scroll \((beginner|easy|medium|hard|elite|master)\)')
TYPE=r'cryptic clue|anagram clue|coordinate clue|emote clue|cipher clue|map clue|hot/cold clue|music clue'
def digest(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def candidates():
 index=json.loads(INDEX.read_text(encoding='utf-8'));byid=collections.defaultdict(list)
 for article in index.values():
  for ident in article['exactInfoboxItemIds']:byid[ident].append(article)
 packets=[json.loads(s) for s in PACKET.read_text(encoding='utf-8').splitlines() if s]
 rows=[];selected=[];reasons=collections.Counter()
 for packet in packets:
  ident=packet['itemId'];current=packet['current']
  row=dict(itemId=ident,shard='clue-unique',decision='unresolved',reviewer='root',proposedRoles=None,roleClaimScope='unassessed',proposedTags=list(current['tags']),evidence=[],identityLinks=[],semanticPredicate='No root-approved primary function decision from this clue-scroll rule.',rationale='This rule certifies only directly defined, exact readable Treasure Trails steps; every other record needs another semantic review.')
  def reject(reason):reasons[reason]+=1;row['rationale']=reason;rows.append(row)
  if (current['category'],current['subcategory'],current['ironmanTabKey'])!=('CLUE','treasure-trail','clues-cosmetics'):
   reject('The current primary assignment is outside this clue-scroll rule.');continue
  if packet['auditScope'] not in ['NAMED_EFFECTIVE','SUPPLEMENTAL']:
   reject('The frozen packet does not establish a named effective assignment.');continue
  matches=byid[ident]
  if len(matches)!=1:
   reject('The exact ID does not have one unambiguous pinned article binding.');continue
  article=matches[0];text_path=ROOT/article['path'];text=text_path.read_text(encoding='utf-8')
  if digest(text_path)!=article['sha256']:raise ValueError('Article bytes changed: '+article['title'])
  if re.search(r'unobtainable|unused item|interface item|unavailable item',text,re.I):
   reject('The article contains a state/research warning that requires individual review.');continue
  raw_boxes=[]
  for raw in ITEM_BOX.findall(text):
   if '{{' in raw:continue
   pairs=re.findall(r'^\|[ \t]*([A-Za-z][A-Za-z0-9]*)[ \t]*=[ \t]*(.*)$',raw,re.M)
   fields={key.lower():value.strip() for key,value in pairs}
   if len(fields)!=len(pairs):continue
   if fields.get('id')==str(ident):raw_boxes.append(fields)
  if len(raw_boxes)!=1:
   reject('The source has no single plain item infobox independently binding this numeric ID.');continue
  fields=raw_boxes[0];name=fields.get('name','')
  if not NAME.fullmatch(name):
   reject('The source infobox is outside the standard named clue-scroll types.');continue
  variant=article['variants'][str(ident)]['params']
  if any(str(variant.get(k,''))!=fields[k] for k in ['id','name','options','equipable']):raise ValueError('Parsed item fields differ from literal raw source: '+str(ident))
  if fields.get('equipable','').casefold()!='no' or 'read' not in [x.strip().casefold() for x in fields.get('options','').split(',')]:
   reject('The exact source item does not establish a readable non-equipment state.');continue
  prefix="'''"+name+"'''";at=text.find(prefix)
  if at<0:
   reject('There is no literal subject-specific definition for this exact named item.');continue
  quote=text[at:].split('\n\n',1)[0]
  lead=re.escape(prefix)+r' is (?:a|an) \[\[(?:[^]|]*\|)?(?:'+TYPE+r')\]\] obtained from '
  if not re.match(lead,quote,re.I) or not re.search(r'\[\[Treasure Trails?\]\]',quote,re.I) or '{{Clue info' not in text:
   reject('The subject definition and actual clue-step content do not directly establish this Treasure Trails function.');continue
  facts=[dict(field=k,value=fields[k]) for k in ['id','name','options','equipable']]
  row.update(decision='certify',proposedCategory='CLUE',proposedSubcategory='treasure-trail',proposedIronmanTabKey='clues-cosmetics',proposedRoles=['treasure_trail_step'],roleClaimScope='supplemental_only',semanticPredicate='The exact readable non-equipment item is explicitly defined as a Treasure Trails clue and has source clue-step content.',rationale='The pinned raw item infobox independently binds the exact ID, name and Read action. Its named subject definition identifies a Treasure Trails clue, so the current clue-solving category, subcategory and tab are supported.',evidence=[dict(kind='direct_variant',itemId=ident,sourceTitle=article['title'],source=article['sourceUrl'],sourceRevision=article['revid'],sourceHash=article['sha256'],quote=quote,structuredFacts=facts,claim='Exact readable Treasure Trails step identity and directly defined primary function.')])
  rows.append(row);selected.append(ident)
 return rows,selected,reasons

def main():
 parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',type=pathlib.Path,default=ROOT/'tmp/category-certification/reviews/root-clue-scrolls');args=parser.parse_args()
 policy=json.loads(POLICY.read_text(encoding='utf-8'))
 for key,path in [('packetSha256',PACKET),('articleIndexSha256',INDEX)]:
  if digest(path)!=policy[key]:raise ValueError('Frozen input hash changed: '+key)
 rows,ids,reasons=candidates()
 if sorted(ids)!=policy['approvedItemIds']:raise ValueError('Rule-selected IDs differ from the root-approved exact cohort')
 if len(rows)!=1761:raise ValueError('Clue/Unique ownership scope changed')
 args.output.mkdir(parents=True,exist_ok=True)
 (args.output/'decisions.jsonl').write_text(''.join(json.dumps(row,ensure_ascii=False)+'\n' for row in rows),encoding='utf-8')
 summary=dict(total=len(rows),certify=len(ids),unresolved=len(rows)-len(ids),policySha256=digest(POLICY),scriptSha256=digest(pathlib.Path(__file__)),packetSha256=digest(PACKET),articleIndexSha256=digest(INDEX),unresolvedReasons=dict(reasons))
 (args.output/'summary.json').write_text(json.dumps(summary,indent=2)+'\n',encoding='utf-8');print(json.dumps(summary,indent=2))
if __name__=='__main__':main()
