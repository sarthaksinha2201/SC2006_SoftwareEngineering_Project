"""Draws the use case diagram for the deliverable: use_case_diagram.svg.

Run from this directory, then convert to PNG for the Word document:
    python3 gen_usecase.py && qlmanage -t -s 1540 -o . use_case_diagram.svg
"""
import math

W, H = 1860, 1860
out = []
def add(s): out.append(s)

UC = {
    "UC-1":  (400, 240, 120, 42, ["Find Events"]),
    "UC-2":  (810, 168, 120, 42, ["View Event Route"]),
    "UC-3":  (810, 310, 120, 42, ["Check Parking", "Availability"]),
    "UC-4":  (400, 595, 120, 42, ["Compare", "Neighbourhoods"]),
    "UC-5":  (810, 520, 120, 42, ["View Score", "Breakdown"]),
    "UC-6":  (810, 670, 120, 42, ["Estimate", "Commute Time"]),
    "UC-11": (400, 930, 120, 42, ["Find Places to Eat"]),
    "UC-12": (810, 900, 120, 42, ["View Place Details"]),
    "UC-7":  (1127, 620, 105, 42, ["Plan Route"]),
    "UC-8":  (1127, 1000, 105, 42, ["Resolve Location"]),
    "UC-9":  (400, 1230, 120, 42, ["Refresh Static", "Data"]),
    "UC-10": (780, 1230, 120, 42, ["Ingest Events"]),
    "UC-13": (590, 1430, 120, 42, ["Build Place List"]),
}

ACT = {
    "User":        (110, 520, "L", ["User"], None),
    "Maintainer":  (110, 1300, "L", ["Maintainer"], None),
    "LTA":         (1680, 220, "R", ["LTA DataMall"], "«external system»"),
    "OneMap":      (1680, 800, "R", ["OneMap API"], "«external system»"),
    "Google":      (1680, 1180, "R", ["Google Places"], "«external system»"),
    "OpenData":    (420, 1725, "B", ["Data Sources"], "«external system»"),
    "Telegram":    (790, 1725, "B", ["Telegram"], "«external system»"),
    "LLM":         (1040, 1725, "B", ["LLM Service"], "«external system»"),
}

def edge(uc, px, py):
    cx, cy, rx, ry, _ = UC[uc]
    dx, dy = px - cx, py - cy
    t = 1 / math.sqrt((dx / rx) ** 2 + (dy / ry) ** 2)
    return cx + dx * t, cy + dy * t

def attach(a):
    x, y, side, _, _ = ACT[a]
    return {"L": (x + 32, y - 15), "R": (x - 32, y - 15), "B": (x, y - 80)}[side]

add(f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}" font-family="Helvetica, Arial, sans-serif">')
add('''<defs>
<marker id="open" viewBox="0 0 12 12" refX="11" refY="6" markerWidth="12" markerHeight="12" orient="auto-start-reverse" markerUnits="userSpaceOnUse">
<path d="M1,1 L11,6 L1,11" fill="none" stroke="#000" stroke-width="1.4"/></marker>
<style>
.uc{fill:#fff;stroke:#000;stroke-width:1.4}
.ucname{font-size:15px;text-anchor:middle}
.ucid{font-size:12px;text-anchor:middle}
.lbl{font-size:12.5px;text-anchor:middle;paint-order:stroke;stroke:#fff;stroke-width:5px;stroke-linejoin:round}
.cond{font-size:12px;text-anchor:middle;font-style:italic;paint-order:stroke;stroke:#fff;stroke-width:5px;stroke-linejoin:round}
.act{font-size:14px;font-weight:bold;text-anchor:middle}
.stereo{font-size:12px;text-anchor:middle}
.pkg{fill:none;stroke:#000;stroke-width:1.2}
.pkgname{font-size:14px;font-weight:bold}
</style></defs>''')
add(f'<rect x="0" y="0" width="{W}" height="{H}" fill="#fff"/>')

add('<rect x="230" y="20" width="1060" height="1560" fill="none" stroke="#000" stroke-width="2"/>')
add('<text x="760" y="56" font-size="22" font-weight="bold" text-anchor="middle">GoWhere</text>')

def package(x, y, w, h, name, tabw):
    add(f'<path class="pkg" d="M{x},{y} h{tabw} v24 h{w-tabw} v{h-24} h{-w} Z M{x},{y+24} h{tabw}"/>')
    add(f'<text class="pkgname" x="{x+10}" y="{y+17}">{name}</text>')

package(255, 80, 710, 300, "Where to Lepak", 140)
package(255, 410, 710, 340, "Where to Live", 130)
package(255, 780, 710, 260, "Where to Eat", 125)
package(255, 1070, 710, 460, "Maintain Data", 130)
package(990, 80, 275, 1450, "Shared Services", 150)

def line(x1, y1, x2, y2, dashed=False, arrow=False):
    d = ' stroke-dasharray="8 6"' if dashed else ''
    m = ' marker-end="url(#open)"' if arrow else ''
    add(f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" stroke="#000" stroke-width="1.3"{d}{m}/>')

for a, u in [("User", "UC-1"), ("User", "UC-4"), ("User", "UC-11"),
             ("Maintainer", "UC-9"), ("Maintainer", "UC-13"), ("LTA", "UC-3"),
             ("OneMap", "UC-7"), ("OneMap", "UC-8"), ("Google", "UC-11"),
             ("OpenData", "UC-9"), ("OpenData", "UC-13"),
             ("Telegram", "UC-10"), ("LLM", "UC-10")]:
    ax, ay = attach(a)
    ex, ey = edge(u, ax, ay)
    line(ax, ay, ex, ey)

def dep(src, dst, kind, cond=None, t=0.5):
    sx, sy = UC[src][0], UC[src][1]
    tx, ty = UC[dst][0], UC[dst][1]
    x1, y1 = edge(src, tx, ty)
    x2, y2 = edge(dst, sx, sy)
    line(x1, y1, x2, y2, dashed=True, arrow=True)
    mx, my = x1 + (x2 - x1) * t, y1 + (y2 - y1) * t
    add(f'<text class="lbl" x="{mx:.0f}" y="{my - 9:.0f}">«{kind}»</text>')
    if cond:
        add(f'<text class="cond" x="{mx:.0f}" y="{my + 18:.0f}">[{cond}]</text>')

dep("UC-2", "UC-1", "extend", "user selects an event")
dep("UC-3", "UC-1", "extend", "travel mode = Drive")
dep("UC-3", "UC-11", "extend", "travel mode = Drive", t=0.64)
dep("UC-5", "UC-4", "extend", "user requests breakdown")
dep("UC-6", "UC-4", "extend", "Commute factor included")
dep("UC-12", "UC-11", "extend", "user selects a place")
dep("UC-1", "UC-7", "include", t=0.55)
dep("UC-6", "UC-7", "include", t=0.5)
dep("UC-11", "UC-7", "include", t=0.58)
dep("UC-7", "UC-8", "include")
dep("UC-9", "UC-8", "include", t=0.42)
dep("UC-10", "UC-8", "include", t=0.45)
dep("UC-13", "UC-8", "include", t=0.52)

for uid, (cx, cy, rx, ry, lines) in UC.items():
    add(f'<ellipse class="uc" cx="{cx}" cy="{cy}" rx="{rx}" ry="{ry}"/>')
    idy = cy + ry + 17 if uid in ("UC-8", "UC-12") else cy - ry - 7
    add(f'<text class="ucid" x="{cx}" y="{idy}">{uid}</text>')
    if len(lines) == 1:
        add(f'<text class="ucname" x="{cx}" y="{cy + 5}">{lines[0]}</text>')
    else:
        add(f'<text class="ucname" x="{cx}" y="{cy - 4}">{lines[0]}</text>')
        add(f'<text class="ucname" x="{cx}" y="{cy + 15}">{lines[1]}</text>')

for a, (x, y, side, labels, stereo) in ACT.items():
    add(f'<circle cx="{x}" cy="{y-56}" r="17" fill="#fff" stroke="#000" stroke-width="1.6"/>')
    add(f'<line x1="{x}" y1="{y-39}" x2="{x}" y2="{y+12}" stroke="#000" stroke-width="1.6"/>')
    add(f'<line x1="{x-28}" y1="{y-20}" x2="{x+28}" y2="{y-20}" stroke="#000" stroke-width="1.6"/>')
    add(f'<line x1="{x}" y1="{y+12}" x2="{x-24}" y2="{y+52}" stroke="#000" stroke-width="1.6"/>')
    add(f'<line x1="{x}" y1="{y+12}" x2="{x+24}" y2="{y+52}" stroke="#000" stroke-width="1.6"/>')
    add(f'<text class="act" x="{x}" y="{y+74}">{labels[0]}</text>')
    if stereo:
        add(f'<text class="stereo" x="{x}" y="{y+91}">{stereo}</text>')
    if a == "OpenData":
        add(f'<text class="stereo" x="{x}" y="{y+107}">(data.gov.sg · LTA DataMall · OpenStreetMap · Wikipedia)</text>')

add('</svg>')
open("use_case_diagram.svg", "w").write("\n".join(out))
print("ok")
