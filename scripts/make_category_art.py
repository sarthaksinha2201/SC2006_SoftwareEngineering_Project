"""Generate the eight event-category banners used when a venue has no photograph.

One ink-line sketch per category over a single offset pastel shape, drawn on the warm
canvas the rest of the UI uses, so a card with artwork sits beside a card with a
photograph without either looking out of place.

    python scripts/make_category_art.py

Writes gowhere/web/static/img/category/<slug>.svg. Committed, so a clean clone has
them; regenerate after editing this file. The slug must match
gowhere.lepak.images.slugify(category).
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from gowhere.lepak.categories import CATEGORIES          # noqa: E402
from gowhere.lepak.images import slugify                 # noqa: E402

OUT_DIR = ROOT / "gowhere" / "web" / "static" / "img" / "category"
ICON_DIR = OUT_DIR / "icon"
W, H = 800, 450
CANVAS = "#FBFBFA"
INK = "#1F1F1D"

# Each category gets the pastel its .cat-tag uses in app.css, so the artwork and the
# tag sitting on top of it agree.
PASTEL = {
    "Food & Markets":       "#FBF3DB",
    "Arts & Culture":       "#F4F0F9",
    "Music & Performances": "#FDEBEC",
    "Sports & Fitness":     "#E1F3FE",
    "Family & Kids":        "#FAEBDD",
    "Workshops & Classes":  "#EDF3EC",
    "Community":            "#E6F2F1",
    "Sales & Pop-ups":      "#FAF1F5",
}

# The single offset geometric shape behind the sketch. Deliberately cropped by the
# frame on one side so the composition reads as a detail, not a centred icon.
SHAPE = {
    "Food & Markets":       '<circle cx="612" cy="140" r="150"/>',
    "Arts & Culture":       '<rect x="470" y="40" width="300" height="300" rx="8"/>',
    "Music & Performances": '<circle cx="640" cy="330" r="165"/>',
    "Sports & Fitness":     '<rect x="500" y="-40" width="330" height="330" '
                            'transform="rotate(14 665 125)" rx="10"/>',
    "Family & Kids":        '<circle cx="180" cy="86" r="140"/>',
    "Workshops & Classes":  '<rect x="40" y="210" width="300" height="300" rx="8"/>',
    "Community":            '<circle cx="648" cy="118" r="152"/>',
    "Sales & Pop-ups":      '<rect x="560" y="150" width="310" height="310" '
                            'transform="rotate(-12 715 305)" rx="10"/>',
}

# Line sketches, drawn in a 320x240 box whose top-left is placed at (240, 108).
# Continuous strokes, no fills: an ink drawing, not an icon.
SKETCH = {
    "Food & Markets": """
      <path d="M22 118 q138 -34 276 0 q-16 86 -138 86 q-122 0 -138 -86 Z"/>
      <path d="M8 118 h304"/>
      <path d="M96 96 q8 -30 -10 -48 q-18 -18 -8 -44"/>
      <path d="M152 92 q9 -33 -11 -53 q-20 -20 -9 -48"/>
      <path d="M208 96 q8 -30 -10 -48 q-18 -18 -8 -44"/>
      <path d="M60 228 h200"/>
    """,
    "Arts & Culture": """
      <rect x="30" y="26" width="260" height="192" rx="4"/>
      <path d="M30 170 l72 -74 l56 56 l44 -40 l88 78"/>
      <circle cx="214" cy="80" r="22"/>
      <path d="M96 240 h128"/>
      <path d="M160 218 v22"/>
    """,
    "Music & Performances": """
      <path d="M166 176 V34 l108 -24 v142"/>
      <path d="M166 62 l108 -24"/>
      <ellipse cx="140" cy="182" rx="29" ry="22" transform="rotate(-18 140 182)"/>
      <ellipse cx="248" cy="158" rx="29" ry="22" transform="rotate(-18 248 158)"/>
      <path d="M26 126 q20 -46 40 0 q20 46 40 0"/>
      <path d="M8 126 q9 -23 18 0"/>
    """,
    "Sports & Fitness": """
      <circle cx="196" cy="42" r="26"/>
      <path d="M186 80 l-40 62 l-52 24"/>
      <path d="M186 80 l44 48 l-18 66 l54 44"/>
      <path d="M212 194 l-74 46"/>
      <path d="M146 142 l40 10"/>
      <path d="M14 120 h58"/>
      <path d="M22 160 h42"/>
    """,
    "Family & Kids": """
      <path d="M160 36 l66 66 l-66 66 l-66 -66 Z"/>
      <path d="M160 36 v132"/>
      <path d="M94 102 h132"/>
      <path d="M160 168 q-26 36 0 60 q26 24 0 52"/>
      <path d="M160 196 l34 -12"/>
      <path d="M160 232 l-34 -12"/>
    """,
    "Workshops & Classes": """
      <path d="M44 212 l24 -70 l132 -132 l46 46 l-132 132 Z"/>
      <path d="M176 56 l46 46"/>
      <path d="M68 142 l46 46"/>
      <path d="M44 212 l30 -30"/>
      <path d="M16 244 h288"/>
    """,
    "Community": """
      <circle cx="160" cy="64" r="30"/>
      <circle cx="62" cy="134" r="26"/>
      <circle cx="258" cy="134" r="26"/>
      <path d="M110 170 q50 -46 100 0"/>
      <path d="M20 224 q42 -44 84 -10"/>
      <path d="M300 224 q-42 -44 -84 -10"/>
      <path d="M160 94 v46"/>
      <path d="M88 134 h44"/>
      <path d="M188 134 h44"/>
    """,
    "Sales & Pop-ups": """
      <path d="M36 128 l92 -92 h110 v110 l-92 92 Z"/>
      <circle cx="202" cy="72" r="17"/>
      <path d="M36 128 l110 110"/>
      <path d="M16 206 q56 -28 112 0 q56 28 112 0"/>
      <path d="M68 240 h200"/>
    """,
}

TEMPLATE = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" \
width="{w}" height="{h}" role="img" aria-label="{label}">
  <title>{label}</title>
  <rect width="{w}" height="{h}" fill="{canvas}"/>
  <g fill="{pastel}">{shape}</g>
  <g transform="translate(240 108)" fill="none" stroke="{ink}" stroke-width="5"
     stroke-linecap="round" stroke-linejoin="round" opacity="0.88">{sketch}</g>
</svg>
"""


# The same sketch again with no banner around it, for the category wheel on the Where
# to Lepak search. currentColor, so each one takes the colour of the chip it sits in.
ICON_TEMPLATE = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="-10 -10 340 270" \
fill="none" stroke="currentColor" stroke-width="11" stroke-linecap="round" \
stroke-linejoin="round" role="img" aria-label="{label}"><title>{label}</title>{sketch}</svg>
"""


def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    ICON_DIR.mkdir(parents=True, exist_ok=True)
    for category in CATEGORIES:
        svg = TEMPLATE.format(
            w=W, h=H, canvas=CANVAS, ink=INK,
            label=category.replace("&", "and"),
            pastel=PASTEL[category],
            shape=SHAPE[category],
            sketch="".join(line.strip() for line in SKETCH[category].splitlines()),
        )
        sketch = "".join(line.strip() for line in SKETCH[category].splitlines())
        path = OUT_DIR / f"{slugify(category)}.svg"
        path.write_text(svg, encoding="utf-8")
        icon = ICON_TEMPLATE.format(label=category.replace("&", "and"), sketch=sketch)
        icon_path = ICON_DIR / f"{slugify(category)}.svg"
        icon_path.write_text(icon, encoding="utf-8")
        print(f"{path.relative_to(ROOT)}  {len(svg)}b   icon {len(icon)}b")


if __name__ == "__main__":
    main()
