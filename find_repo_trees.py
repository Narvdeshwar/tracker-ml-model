import requests, json

api_url = 'https://api.github.com/repos/bebhuvan/ipo-performance-verification/git/trees/main?recursive=1'
r = requests.get(api_url, timeout=10)
if r.status_code == 200:
    tree = r.json().get('tree', [])
    for item in tree:
        path = item.get('path')
        if any(w in path.lower() for w in ['sub', 'gmp', 'date', 'issue', 'nifty', 'vix', 'bse', 'nse', 'market']):
            print(path)
