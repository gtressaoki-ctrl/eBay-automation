"""Plate template (HTML + inline SVG) and Chromium rendering."""

import json
import os
import subprocess

from svgkit import INK, INK_SOFT, LINE, MONO, PAPER, SANS, SERIF, TERRA

HERE = os.path.dirname(os.path.abspath(__file__))
FONTS = os.path.join(HERE, "fonts")
W, H = 1000, 1500
MARGIN = 64
ART_TOP = 470  # default top of the illustration field
ART_BOTTOM = 1380

CSS = f"""
@font-face {{ font-family: '{SERIF}'; src: url('file://{FONTS}/InstrumentSerif-Regular.ttf'); }}
@font-face {{ font-family: '{SERIF}'; font-style: italic; src: url('file://{FONTS}/InstrumentSerif-Italic.ttf'); }}
@font-face {{ font-family: '{SANS}'; src: url('file://{FONTS}/InstrumentSans-Regular.ttf'); font-weight: 400; }}
@font-face {{ font-family: '{SANS}'; src: url('file://{FONTS}/InstrumentSans-Bold.ttf'); font-weight: 700; }}
@font-face {{ font-family: '{MONO}'; src: url('file://{FONTS}/DMMono-Regular.ttf'); }}
html, body {{ margin: 0; padding: 0; background: {PAPER}; }}
.plate {{ position: relative; width: {W}px; height: {H}px; overflow: hidden; background: {PAPER}; }}
.plate svg.art {{ position: absolute; left: 0; top: 0; }}
.head {{ position: absolute; left: {MARGIN}px; right: {MARGIN}px; top: 0; }}
.meta {{ position: absolute; top: 58px; left: 0; right: 0; display: flex; justify-content: space-between;
        font-family: '{MONO}'; font-size: 15px; letter-spacing: 3px; color: {INK_SOFT}; text-transform: uppercase; }}
.meta b {{ color: {TERRA}; font-weight: 400; }}
.rule {{ position: absolute; left: 0; right: 0; height: 1px; background: {LINE}; opacity: .55; }}
h1 {{ position: absolute; top: 118px; left: 0; right: 0; margin: 0; font-family: '{SERIF}'; font-weight: 400;
      font-size: var(--hs, 104px); line-height: .98; letter-spacing: -1.5px; color: {INK}; }}
h1 em {{ color: {TERRA}; }}
.sub {{ position: absolute; left: 0; right: 0; font-family: '{SANS}'; font-size: 27px; line-height: 1.3;
        color: #4E5260; }}
.band {{ position: absolute; left: 0; right: 0; top: 0; background: {INK}; }}
.b .meta {{ color: #A9A395; }}
.b .meta b {{ color: #F2926F; }}
.b .head .rule {{ background: {PAPER}; opacity: .28; }}
.b h1 {{ color: {PAPER}; letter-spacing: -2px; }}
.b h1 em {{ color: #F2926F; }}
.b .sub {{ color: #D6D0C4; }}
.badge {{ position: absolute; right: {MARGIN}px; width: 152px; height: 152px; border-radius: 50%; background: {TERRA};
          display: flex; flex-direction: column; align-items: center; justify-content: center; color: {PAPER};
          box-shadow: 0 0 0 6px {PAPER}; }}
.badge .n {{ font-family: '{SERIF}'; font-size: 76px; line-height: .9; }}
.badge .c {{ font-family: '{MONO}'; font-size: 13px; letter-spacing: 2.5px; text-transform: uppercase; margin-top: 4px; }}
.foot {{ position: absolute; left: {MARGIN}px; right: {MARGIN}px; top: 1418px; display: flex; justify-content: space-between;
        font-family: '{MONO}'; font-size: 15px; letter-spacing: 3px; color: {INK_SOFT}; text-transform: uppercase; }}
"""

GRAIN = """
<filter id="grain" x="0" y="0" width="100%" height="100%">
  <feTurbulence type="fractalNoise" baseFrequency="0.9" numOctaves="2" seed="7" result="n"/>
  <feColorMatrix type="matrix" values="0 0 0 0 0.12  0 0 0 0 0.10  0 0 0 0 0.08  0 0 0 0.55 0"/>
</filter>
"""


def plate_html(pin, art_svg, sub_top, variant="a"):
    head_size = pin.get("head_size", 104)
    band = badge = ""
    if variant == "b":
        head_size = 124
        band_h = sub_top + 62
        band = f'<div class="band" style="height:{band_h}px"></div>'
        if pin.get("badge_b"):
            n, c = pin["badge_b"]
            badge = f'<div class="badge" style="top:{band_h - 82}px"><div class="n">{n}</div><div class="c">{c}</div></div>'

    return f"""<!doctype html><html><head><meta charset="utf-8"><style>{CSS}</style></head>
<body><div class="plate {variant}">
<svg class="art" width="{W}" height="{H}" viewBox="0 0 {W} {H}" xmlns="http://www.w3.org/2000/svg">
<defs>{GRAIN}</defs>
{art_svg}
<rect width="{W}" height="{H}" filter="url(#grain)" opacity=".16"/>
</svg>
{band}
<div class="head">
  <div class="meta"><span><b>No.{pin['n']:02d}</b> &nbsp;{pin['kicker']}</span><span>{pin.get('meta_right', 'Posture Atlas')}</span></div>
  <div class="rule" style="top:92px"></div>
  <h1 style="--hs:{head_size}px">{pin['headline_html']}</h1>
  <div class="sub" style="top:{sub_top}px">{pin['sub']}</div>
</div>
{badge}
<div class="rule" style="top:1398px; left:{MARGIN}px; right:{MARGIN}px"></div>
<div class="foot"><span>Save for your next work session</span><span>Fig. {pin['n']:02d}</span></div>
</div></body></html>"""


def render_all(jobs, out_dir, scale=2):
    """jobs: list of (html_path, png_path). Renders with Playwright/Chromium."""
    js = os.path.join(HERE, "render.mjs")
    spec = os.path.join(out_dir, "_jobs.json")
    with open(spec, "w") as fh:
        json.dump([{"html": h, "png": p} for h, p in jobs], fh)
    env = dict(os.environ)
    env.setdefault("NODE_PATH", "/opt/node22/lib/node_modules")
    subprocess.run(["node", js, spec, str(scale)], check=True, env=env)
    os.remove(spec)
