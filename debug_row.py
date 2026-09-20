import urllib.request, urllib.parse, json, time
for prov in ['Bitlis', 'Kilis', 'Muş', 'Sivas', 'Şırnak', 'Yozgat', 'Zonguldak']:
    q = urllib.parse.urlencode({
        'action': 'query', 'list': 'search',
        'srsearch': f"intitle:{prov} 2023 genel seçim",
        'srlimit': 5, 'format': 'json', 'formatversion': '2'})
    try:
        req = urllib.request.Request(
            'https://tr.wikipedia.org/w/api.php?' + q,
            headers={'User-Agent': 'test/0.1'})
        j = json.loads(urllib.request.urlopen(req, timeout=15).read().decode())
        titles = [s['title'] for s in j['query']['search']]
        print(prov, '->', titles[:3])
    except urllib.error.HTTPError as e:
        if e.code == 429:
            print(prov, '429 (rate limited)')
        else:
            print(prov, 'ERR', e)
    except Exception as e:
        print(prov, 'ERR', e)
    time.sleep(2)