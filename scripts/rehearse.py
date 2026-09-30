"""Rehearse the demo path (docs/demo.md section 3) against a real server.

    python scripts/rehearse.py <checkout> online
    python scripts/rehearse.py <checkout> offline   # every outbound connection fails

The checkout needs data/snapshot.db, .env and events. Prints each step, its time and
the key lines, then counts the demo postal codes and coordinates in the server log
(they must be 0).
"""
import html
import os
import re
import subprocess
import sys
import time

import requests

root, mode = sys.argv[1], sys.argv[2]
PORT = 5055 if mode == "online" else 5056
LOG = f"{root}/data/logs/rehearsal_{mode}.log"
DEST, START = "119077", "238801"            # NUS Kent Ridge (commute), ION Orchard (Lepak)
env = {**os.environ, "GOWHERE_SECRET_KEY": "rehearsal"}
if mode == "offline":   # every outbound connection fails, as with wifi off
    env.update(HTTP_PROXY="http://127.0.0.1:9", HTTPS_PROXY="http://127.0.0.1:9",
               http_proxy="http://127.0.0.1:9", https_proxy="http://127.0.0.1:9", NO_PROXY="")
server = subprocess.Popen([f"{root}/.venv/bin/flask", "--app", "gowhere.web:create_app()", "run",
                           "--port", str(PORT)], cwd=root, env=env,
                          stdout=open(LOG, "w"), stderr=subprocess.STDOUT)
b = requests.Session(); b.trust_env = False       # the browser itself is local
base = f"http://127.0.0.1:{PORT}"
for _ in range(50):
    try:
        b.get(base + "/"); break
    except requests.ConnectionError:
        time.sleep(0.2)

def step(name, method, path, **kw):
    t0 = time.time()
    r = getattr(b, method)(base + path, allow_redirects=True, timeout=180, **kw)
    text = html.unescape(r.text)
    print(f"\n## {name}: HTTP {r.status_code} in {time.time() - t0:.1f}s")
    return text

def show(text, *patterns):
    for p in patterns:
        for m in re.findall(p, text, re.S)[:6]:
            print("   ", re.sub(r"\s+", " ", m if isinstance(m, str) else " | ".join(m)).strip()[:160])

live = {"include_public_transport": "1", "weight_public_transport": "6",
        "include_housing_affordability": "1", "weight_housing_affordability": "8",
        "flat_type": "4 ROOM", "budget_min": "400000", "budget_max": "700000",
        "min_remaining_lease_years": "60",
        "include_amenities": "1", "weight_amenities": "5", "amenity_types": ["supermarket", "hawker_centre"],
        "include_greenery": "1", "weight_greenery": "4",
        "include_healthcare": "1", "weight_healthcare": "5", "facility_type": "polyclinic"}
t = step("Home", "get", "/")
t = b.post(base + "/live/check", data={**live, "areas": ["QUEENSTOWN", "TAMPINES", "PUNGGOL", "CHANGI"]}).json()
print("\n## Selection-time check with Changi:", t)
t = b.post(base + "/live/check", data={**live, "areas": ["QUEENSTOWN", "TAMPINES", "PUNGGOL", "BEDOK"]}).json()
print("## ...after swapping Changi for Bedok:", t)
t = step("Where to Live results (with Commute to 119077 by public transport)", "post", "/live",
         data={**live, "areas": ["QUEENSTOWN", "TAMPINES", "PUNGGOL", "BEDOK"],
               "include_commute": "1", "weight_commute": "7", "destination_postal": DEST, "mode": "pt"})
show(t, r"<h2>(.*?)</h2>", r'<p role="alert">(.*?)</p>', r"<p><strong>(.*?)</strong></p>")
show(t, r"<tr><td>([^<]*)</td><td>([A-Za-z ]+)<br>.*?</td><td>([\d.]+)</td>")
show(t, r"0\.0<br><small>([^<]*)</small>", r"<td>[\d.]+<br><small>(\d[\d.]* min by[^<]*)</small>")
t = step("Where to Live results again (reload)", "get", "/live/results")

lepak = {"categories": ["Arts & Culture", "Music & Performances", "Family & Kids"], "date_option": "week",
         "origin": "postal", "postal": START, "mode": "pt", "max_minutes": "45"}
t = step("Lepak search, public transport from 238801", "post", "/lepak", data=lepak)
show(t, r"<h1>(.*?)</h1>", r'role="alert">(.*?)<', r"<h2><a[^>]*>(.*?)</a></h2>.*?<p>([^<]*(?:min |About )[^<]*)</p>")
first = re.search(r'/lepak/events/(\d+)', t)
t2 = step("Sort soonest", "get", "/lepak/results?sort=soonest"); show(t2, r"<h2><a[^>]*>(.*?)</a></h2>")
t2 = step("Chip Family & Kids", "get", "/lepak/results?category=Family+%26+Kids"); show(t2, r"<h2><a[^>]*>(.*?)</a></h2>")
if first:
    t2 = step("Event detail", "get", f"/lepak/events/{first.group(1)}")
    show(t2, r"<h1>(.*?)</h1>", r"<p>([^<]*(?:min |About )[^<]*)</p>")
t = step("Lepak search, drive", "post", "/lepak", data={**lepak, "mode": "drive"})
show(t, r"<h1>(.*?)</h1>", r'role="alert">(.*?)<', r"<p>(Parking[^<]*|[\d,]+ car lots[^<]*)</p>")
t = step("Lepak search, use my location", "post", "/lepak",
         data={**lepak, "origin": "here", "lat": "1.3040", "lon": "103.8318", "postal": ""})
show(t, r"<h1>(.*?)</h1>", r'role="alert">(.*?)<', r"<h2><a[^>]*>(.*?)</a></h2>.*?<p>([^<]*(?:min |About )[^<]*)</p>")
server.terminate(); server.wait()
log = open(LOG).read()
print(f"\n## Server log: {len(log.splitlines())} lines; '{DEST}' x{log.count(DEST)}, '{START}' x{log.count(START)}, "
      f"'1.3040' x{log.count('1.3040')}; tracebacks x{log.count('Traceback')}")
