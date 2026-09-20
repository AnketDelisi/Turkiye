import glob, re, sys
sys.path.insert(0, 'scrapers')
import importlib.util
spec = importlib.util.spec_from_file_location('w', 'scrapers/wikipedia.py')
w = importlib.util.module_from_spec(spec)
spec.loader.exec_module(w)
# collect all uppercase cell names in 2018 aggregate tables
seen = {}
for f in glob.glob('data/raw/wiki/*2018*.txt'):
    wt = open(f, encoding='utf8').read()
    a = wt.find('| Çevre oyu')
    if a < 0: continue
    seg = wt[a:]
    nxt = seg.find('\n==')
    seg = seg[:nxt] if nxt > 0 else seg
    for ln in seg.split('\n'):
        cell = ln.strip().lstrip('|').strip()
        cell = re.sub(r'^align="(?:center|right)"\s*\|\s*', '', cell)
        if re.match(r'^[A-ZÇĞİÖŞÜÂ][A-ZÇĞİÖŞÜÂ \.]{1,25}$', cell):
            seen[cell] = seen.get(cell, 0) + 1
missing = {c: n for c, n in seen.items() if c.upper() not in w.PARTY_ABBREV}
print('cell names not in PARTY_ABBREV:', missing)