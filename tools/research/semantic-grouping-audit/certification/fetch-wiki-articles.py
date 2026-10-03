#!/usr/bin/env python3
"""Acquire full exact-ID Wiki articles. Acquisition alone is not certification."""
import argparse, csv, hashlib, importlib.util, json, pathlib, re, sys
RESEARCH = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RESEARCH))
import audit
spec = importlib.util.spec_from_file_location('missing_review', RESEARCH / 'review-missing-items.py')
missing_review = importlib.util.module_from_spec(spec)
spec.loader.exec_module(missing_review)

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def save_index(path, value):
    temporary = path.with_suffix(path.suffix + ".partial")
    audit.save(temporary, value)
    temporary.replace(path)

def run(args):
    coverage = {}
    with args.coverage.open(encoding='utf-8-sig', newline='') as stream:
        for row in csv.DictReader(stream, delimiter='\t'):
            ident = int(row['itemId'])
            if ident <= 0 or ident in coverage:
                raise ValueError('Invalid or duplicate current ID')
            coverage[ident] = row
    bucket = json.loads(args.bucket.read_text(encoding='utf-8'))
    plan = {}
    for row in bucket['rows']:
        ids = [int(str(i).strip()) for i in audit.listify(row.get('item_id'))
               if re.fullmatch(r'[1-9][0-9]*', str(i).strip())]
        matched = sorted(set(ids) & coverage.keys())
        if matched:
            plan.setdefault(row['page_name'], set()).update(matched)
    titles = sorted(plan)
    args.output.mkdir(parents=True, exist_ok=True)
    source_plan = dict(coverageSha256=sha(args.coverage), bucketSha256=sha(args.bucket),
                       pages=[dict(title=t, itemIds=sorted(plan[t])) for t in titles])
    plan_path = args.output / 'source-plan.json'
    if plan_path.exists() and json.loads(plan_path.read_text(encoding='utf-8')) != source_plan:
        raise ValueError('Source plan changed; use a separate acquisition directory')
    audit.save(plan_path, source_plan)
    index_path = args.output / 'article-index.json'
    index = json.loads(index_path.read_text(encoding='utf-8')) if index_path.exists() else {}
    if set(index) - set(titles):
        raise ValueError('Cached index contains pages outside frozen source plan')
    errors = []
    for offset in range(0, len(titles), 40):
        requested = titles[offset:offset+40]
        packet_path = args.output / 'packets' / f'{offset:06d}.json'
        if packet_path.exists():
            packet = json.loads(packet_path.read_text(encoding='utf-8'))
            if packet['requestedTitles'] != requested:
                raise ValueError('Cached source request differs')
        else:
            data, url = audit.request(dict(action='query', prop='revisions', rvprop='ids|timestamp|content',
                                            rvslots='main', titles='|'.join(requested), redirects=1))
            packet = dict(retrievedAt=audit.utc(), sourceUrl=url, requestedTitles=requested, data=data)
            audit.save(packet_path, packet)
        query = packet['data'].get('query', {})
        aliases = {r['from']:r['to'] for r in query.get('redirects', [])}
        aliases.update({r['from']:r['to'] for r in query.get('normalized', [])})
        by_title = {p['title']:p for p in query.get('pages', [])}
        for title in requested:
            resolved, seen = title, set()
            while resolved in aliases and resolved not in seen:
                seen.add(resolved)
                resolved = aliases[resolved]
            page = by_title.get(resolved)
            if not page or not page.get('revisions'):
                errors.append(dict(title=title, itemIds=sorted(plan[title]), error='Missing article revision'))
                continue
            revision = page['revisions'][0]
            text = revision['slots']['main']['content']
            text_path = args.output / 'text' / f"{revision['revid']}.txt"
            text_path.parent.mkdir(parents=True, exist_ok=True)
            text_path.write_text(text, encoding='utf-8')
            try:
                variants = missing_review.variants(text)
                parser_error = ''
            except ValueError as error:
                variants, parser_error = {}, str(error)
            expected = sorted(plan[title])
            index[title] = dict(title=resolved, requestedTitle=title, revid=revision['revid'],
                                revisionTimestamp=revision.get('timestamp'), retrievedAt=packet['retrievedAt'],
                                sourceUrl=f"https://oldschool.runescape.wiki/w/Special:Redirect/revision/{revision['revid']}",
                                path=str(text_path), sha256=sha(text_path), packetPath=str(packet_path),
                                packetSha256=sha(packet_path), requestedItemIds=expected,
                                exactInfoboxItemIds=sorted(variants), variants={str(i):v for i,v in variants.items()},
                                absentRequestedIds=sorted(set(expected)-variants.keys()), parserError=parser_error)
        save_index(args.output / 'article-index.json', index)
        audit.save(args.output / 'acquisition-summary.json',
                   dict(generatedAt=audit.utc(), coverageSha256=source_plan['coverageSha256'],
                        bucketSha256=source_plan['bucketSha256'], acquiredPages=len(index), plannedPages=len(titles),
                        errors=errors, parserErrorPages=sum(bool(v['parserError']) for v in index.values()),
                        absentExactIds=sum(len(v['absentRequestedIds']) for v in index.values()),
                        limitation='Full article acquisition and exact ID checks do not certify semantic assignments.'))
        print(f'Acquired {len(index)}/{len(titles)} source pages; {len(errors)} acquisition gaps', flush=True)

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--coverage', type=pathlib.Path, default=pathlib.Path('tmp/category-certification/current-coverage.tsv'))
    parser.add_argument('--bucket', type=pathlib.Path, default=pathlib.Path('tmp/missing-item-audit/cache/infobox_item.json'))
    parser.add_argument('--output', type=pathlib.Path, default=pathlib.Path('tmp/category-certification/wiki-articles'))
    run(parser.parse_args())
