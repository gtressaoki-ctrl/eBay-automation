"""Static guide pages: one page per list pin, every product with its own Amazon affiliate link.

A pin can carry one link only, so list pins (gift guides, essentials) point at a guide page
instead, where each product is a separate link. Run `python guides.py` to write site/.
"""

import html
import os
import shutil

from PIL import Image

from generate_pins import PINS
from products import PRODUCTS, pin_tag, product_url

HERE = os.path.dirname(os.path.abspath(__file__))
SITE = os.path.join(HERE, "site")
SITE_NAME = "Desk Posture Guides"

BLURBS = {
    "lumbar_ec": "Memory-foam pillow that straps to the chair and fills the gap behind your lower back.",
    "seat_ec": "Firm memory-foam cushion; raises a low chair and takes pressure off a hard seat.",
    "footrest_ec": "Angled under-desk footrest for when your feet don't sit flat on the floor.",
    "sihoo_m57": "Mesh ergonomic chair with adjustable lumbar, armrests and recline, a common first upgrade.",
    "steelcase_s1": "Lightweight task chair with adjustable seat depth, arms and lumbar from a long-running office brand.",
    "flexispot_e7": "Electric sit-stand desk with two motors and memory presets for your sitting and standing heights.",
    "flexispot_conv": "Sits on the desk you already have and lifts keyboard and screen to standing height.",
    "topo_mat": "Contoured anti-fatigue mat that gives you places to shift your feet while standing.",
    "vivo_arm": "Clamp-on monitor arm that lifts the screen to eye level and frees up desk space.",
    "huanuo_dual": "Gas-spring arm for two monitors so both sit at the same height.",
    "nulaxy": "Adjustable laptop stand that raises the screen; pair it with an external keyboard and mouse.",
    "k860": "Split, curved keyboard that keeps the wrists straighter than a flat board.",
    "mx_vertical": "Vertical mouse that holds your hand in a handshake position instead of palm-down.",
    "gimars": "Gel wrist rests for the keyboard and mouse, so wrists aren't on a hard desk edge.",
    "timetimer": "Visual desk timer, handy for breaks or sit-stand switches without checking your phone.",
    "theraband": "Light resistance bands for shoulder and upper-back exercises between meetings.",
    "chirp": "Foam roller wheel for the upper back after a long day at the desk.",
    "chirp_neck": "Small roller sized for the neck and upper shoulders.",
    "restcloud": "Neck and shoulder rest for a few minutes of decompression after work.",
}

# Which pins get a guide page: list pins whose items map to several products.
GUIDE_PINS = [39, 48, 52, 59, 74, 81, 82, 87, 91, 92, 96, 100]
DISCLOSURE = "As an Amazon Associate I earn from qualifying purchases. Prices and availability change; check on Amazon."

CSS = """
:root{--paper:#F2EDE4;--card:#FBF8F3;--ink:#1D2330;--muted:#5E6070;--line:#D8D0C2;--accent:#C4553B;--btn-ink:#fff}
@media (prefers-color-scheme:dark){:root:not([data-theme="light"]){--paper:#16181D;--card:#1F232A;--ink:#ECE7DE;--muted:#A8A39A;--line:#343842;--accent:#E07A5F;--btn-ink:#16181D}}
:root[data-theme="dark"]{--paper:#16181D;--card:#1F232A;--ink:#ECE7DE;--muted:#A8A39A;--line:#343842;--accent:#E07A5F;--btn-ink:#16181D}
*{box-sizing:border-box}body{margin:0;background:var(--paper);color:var(--ink);font:16px/1.6 "Instrument Sans",system-ui,sans-serif}
.wrap{max-width:720px;margin:0 auto;padding:24px 16px 56px}
.eyebrow{font:500 12px "DM Mono",ui-monospace,monospace;letter-spacing:.14em;text-transform:uppercase;color:var(--accent)}
h1{font:400 2.6rem/1.05 "Instrument Serif",Georgia,serif;margin:.3rem 0 .6rem;text-wrap:balance}
h2{font:400 1.6rem/1.15 "Instrument Serif",Georgia,serif;margin:0}
p.lede{color:var(--muted);margin:0 0 1.2rem}
.hero{display:block;width:100%;max-width:360px;border-radius:12px;border:1px solid var(--line);margin:0 0 1.5rem}
.item{background:var(--card);border:1px solid var(--line);border-radius:14px;padding:16px;margin:0 0 12px;display:flex;flex-direction:column;gap:8px}
.item .n{font:500 12px "DM Mono",monospace;color:var(--accent)}
.item p{margin:0;color:var(--muted)}
a.btn{align-self:flex-start;background:var(--accent);color:var(--btn-ink);text-decoration:none;font-weight:600;padding:9px 16px;border-radius:999px}
a.btn:focus-visible,a:focus-visible{outline:2px solid var(--ink);outline-offset:2px}
.list a{color:var(--ink)}.list li{margin:.4rem 0}
footer{margin-top:2rem;font-size:.85rem;color:var(--muted)}
"""

FONTS = ('<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="stylesheet" '
         'href="https://fonts.googleapis.com/css2?family=Instrument+Serif&family=Instrument+Sans:wght@400;600'
         '&family=DM+Mono:wght@500&display=swap">')


def page(title, body, desc):
    e = html.escape
    return (f'<!doctype html><html lang="en"><head><meta charset="utf-8">'
            f'<meta name="viewport" content="width=device-width,initial-scale=1">'
            f'<title>{e(title)}</title><meta name="description" content="{e(desc)}">{FONTS}<style>{CSS}</style></head>'
            f'<body><div class="wrap">{body}<footer>{e(DISCLOSURE)}</footer></div></body></html>')


def guide_items(pin):
    """Products shown on a guide: the pin's products plus any item kinds that map to known products."""
    kind_to_product = {"lumbar": "lumbar_ec", "seat_cushion": "seat_ec", "footrest": "footrest_ec",
                       "monitor_arm": "vivo_arm", "laptop_stand": "nulaxy", "wrist_rest": "gimars",
                       "vmouse": "mx_vertical", "timer": "timetimer", "band": "theraband", "mat": "topo_mat",
                       "chair": "sihoo_m57", "desk": "flexispot_e7"}
    keys = []
    for kind, label in pin.get("items", []):
        k = kind_to_product.get(kind)
        if pin["n"] in (52, 74, 100) and kind == "wrist_rest" and "keyboard" in label.lower():
            k = "k860"
        if k and k not in keys:
            keys.append(k)
    for k in pin["products"]:
        if k in BLURBS and k not in keys:
            keys.append(k)
    return keys


def build():
    if os.path.isdir(SITE):
        shutil.rmtree(SITE)
    os.makedirs(os.path.join(SITE, "img"))
    e = html.escape
    links = []
    by_n = {p["n"]: p for p in PINS}
    for n in GUIDE_PINS:
        pin = by_n[n]
        slug = pin["slug"]
        Image.open(os.path.join(HERE, "images", f"{n:02d}-{slug}.png")).convert("RGB").resize((600, 900)).save(
            os.path.join(SITE, "img", f"{slug}.jpg"), quality=85)
        tag = pin_tag(pin)
        cards = []
        for i, k in enumerate(guide_items(pin), 1):
            cards.append(f'<div class="item"><span class="n">{i:02d}</span><h2>{e(PRODUCTS[k]["name"])}</h2>'
                         f'<p>{e(BLURBS[k])}</p><a class="btn" href="{e(product_url(k, tag))}" '
                         f'rel="sponsored noopener" target="_blank">See it on Amazon</a></div>')
        body = (f'<a class="eyebrow" href="./" style="text-decoration:none">← {e(SITE_NAME)}</a>'
                f'<h1>{e(pin["title"])}</h1><p class="lede">{e(pin["sub"])}</p>'
                + "".join(cards)
                + f'<img class="hero" src="img/{slug}.jpg" alt="{e(pin["title"])}" width="600" height="900">')
        with open(os.path.join(SITE, f"{slug}.html"), "w", encoding="utf-8") as f:
            f.write(page(pin["title"], body, pin["desc"].split(". ", 1)[-1]))
        links.append(f'<li><a href="{slug}.html">{e(pin["title"])}</a></li>')
    body = (f'<span class="eyebrow">Desk setup &amp; posture</span><h1>{e(SITE_NAME)}</h1>'
            f'<p class="lede">Simple, illustrated guides to a more comfortable desk, and the products in them.</p>'
            f'<ul class="list">{"".join(links)}</ul>')
    with open(os.path.join(SITE, "index.html"), "w", encoding="utf-8") as f:
        f.write(page(SITE_NAME, body, "Illustrated guides to desk setup, posture and home office upgrades."))
    return SITE


if __name__ == "__main__":
    print("wrote", build())
