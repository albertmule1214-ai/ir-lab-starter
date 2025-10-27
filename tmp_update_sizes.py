import json, pathlib
root = pathlib.Path('.').resolve()
idx = root / 'index_json'
res = root / 'results'
with open(res / 'dict_compression_sizes.json', 'r', encoding='utf-8') as f:
    s = json.load(f)
postings = (idx / 'postings.json').stat().st_size if (idx / 'postings.json').exists() else 0
orig_total = s['original_lexicon.json'] + postings
block_total_index = s['block_total'] + postings
front_total_index = s['front_total'] + postings
s['original_index_total_bytes'] = orig_total
s['block_index_total_bytes'] = block_total_index
s['front_index_total_bytes'] = front_total_index
s['block_index_saving_bytes'] = orig_total - block_total_index
s['front_index_saving_bytes'] = orig_total - front_total_index
s['block_index_saving_pct'] = round((s['block_index_saving_bytes']/orig_total*100.0) if orig_total else 0.0, 3)
s['front_index_saving_pct'] = round((s['front_index_saving_bytes']/orig_total*100.0) if orig_total else 0.0, 3)
with open(res / 'dict_compression_sizes.json', 'w', encoding='utf-8') as f:
    json.dump(s, f, ensure_ascii=False, indent=2)
print('updated')
