"""Monthly change report. Changes never bypass the verified source lock or E2E gate."""
from __future__ import annotations
import json
import os
import re
import urllib.request
from ci.common import ROOT, config, write_json

def get(url):
    headers = {"User-Agent": "mysqlclient-static-watch"}
    if url.startswith("https://api.github.com/") and os.environ.get("GITHUB_TOKEN"):
        headers["Authorization"] = "Bearer " + os.environ["GITHUB_TOKEN"]
    with urllib.request.urlopen(urllib.request.Request(url, headers=headers), timeout=60) as r:
        return json.load(r)

def latest(values, prefix=None):
    candidates = []
    for value in values:
        if prefix and not value.startswith(prefix + "."):
            continue
        if re.fullmatch(r"\d+(?:\.\d+){1,3}", value):
            candidates.append(value)
    return max(candidates, key=lambda v: tuple(map(int, v.split('.')))) if candidates else "not found"

def main():
    c = config()
    rows = []
    def check(component, locked, lookup):
        try:
            newest = lookup()
            rows.append(dict(component=component, pinned=locked, available=newest,
                             status="UNCHANGED" if newest == locked else "REVIEW"))
        except Exception as exc:
            rows.append(dict(component=component, pinned=locked, available="unknown", status="LOOKUP_FAILED", detail=str(exc)))
    check("mysqlclient", c["upstream"]["current"]["version"], lambda: get("https://pypi.org/pypi/mysqlclient/json")["info"]["version"])
    django = get("https://pypi.org/pypi/Django/json")
    for series in sorted({p["version"].rsplit('.', 1)[0] for p in c["django"]}):
        pinned = next(p["version"] for p in c["django"] if p["version"].startswith(series + '.'))
        check("Django " + series, pinned, lambda series=series: latest(django["releases"], series))
    for name, d in c["native"].items():
        def lookup(d=d, name=name):
            tags = get(f"https://api.github.com/repos/{d['repository']}/tags?per_page=100")
            names = [x['name'].removeprefix('openssl-').removeprefix('v') for x in tags]
            series = '.'.join(d['version'].split('.')[:2]) if name in ('openssl','connector') else None
            return latest(names, series)
        check(name, d["version"], lookup)
    for series in ('8.0','8.4'):
        pinned = max((x['version'] for x in c['mysql'] if x['version'].startswith(series + '.')),
                     key=lambda x: tuple(map(int,x.split('.'))))
        check('MySQL ' + series, pinned,
              lambda series=series: latest([x['name'] for x in get('https://hub.docker.com/v2/repositories/library/mysql/tags?page_size=100&name=' + series)['results']], series))
    write_json(ROOT / 'reports/upstream.json', rows)
    text = '# Upstream version watch\n\n| Component | Pinned | Available | Status |\n|---|---|---|---|\n'
    text += ''.join(f"| {r['component']} | {r['pinned']} | {r['available']} | {r['status']} |\n" for r in rows)
    text += '\nUpdates require explicit lock changes, source verification, and a passing full E2E run.\n'
    (ROOT / 'reports/upstream.md').write_text(text)
    print(text)

if __name__ == '__main__':
    main()
