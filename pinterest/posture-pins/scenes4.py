"""Batch 4 scenes: laptops, keyboards and the sit-stand rhythm."""

from plate import ART_BOTTOM, W
from scenes import BODY, L, R, SIT, STAND, caption, floor, hair, kb_plan, pose, rows, seated, standing
from svgkit import (INK, INK_FAR, LINE, MONO, PAPER, SAGE, SAGE_SOFT, SERIF, TERRA, TERRA_SOFT, arc_arrow, callout,
                    capsule, chair_side, check, cross, fmt, line, path, rect, strain, text, top_figure)


def _laptop_plan(cx, cy, w, h):
    """Laptop open on a stand, seen from above: base plus the screen edge."""
    return (rect(cx - w / 2, cy, w, h, rx=6, fill=PAPER, stroke=LINE, sw=1.8)
            + rect(cx - w / 2 + 10, cy + 10, w - 20, h - 26, rx=3, stroke=LINE, sw=0.8, extra='opacity=".6"')
            + rect(cx - w / 2, cy - 16, w, 14, rx=3, fill=INK))


def sc_laptop_monitor(pin, top):
    out = []
    u = 66
    cx = W / 2
    dtop = top + 120
    dbot = dtop + 430
    out.append(rect(L + 10, dtop, R - L - 20, dbot - dtop, rx=8, fill=PAPER, stroke=LINE, sw=2))
    out.append(rect(cx - 30 - 165, dtop + 59, 330, 22, rx=4, fill=INK))
    out.append(rect(cx - 85, dtop + 82, 110, 40, rx=8, stroke=LINE, sw=1.6))
    lx = L + 115
    out.append(_laptop_plan(lx, dtop + 80, 180, 120))
    out.append(kb_plan(cx - 190, dtop + 270, 300, 96))
    out.append(f'<ellipse cx="{fmt(cx + 160)}" cy="{fmt(dtop + 318)}" rx="24" ry="36" fill="{PAPER}" stroke="{LINE}" stroke-width="1.8"/>')
    hc = (cx - 40, dbot + 110)
    out.append(top_figure(hc, u, arms_to=[(cx - 120, dtop + 350), (cx + 160, dtop + 350)]))
    out.append(line((cx - 40, dtop + 85), (cx - 40, hc[1] - 50), stroke=TERRA, sw=1.3, dash="3 6"))
    out.append(callout((cx + 135, dtop + 70), (R - 290, top + 40), "Monitor straight ahead", num=1))
    out.append(callout((lx - 90, dtop + 70), (L, top + 40), "Laptop raised to the side", num=2))
    out.append(callout((cx - 190, dtop + 340), (L, dbot + 70), "Separate keyboard + mouse", num=3))
    out.append(rows(L, ART_BOTTOM - 150, R - L, pin["tips"], gap=48, size=22, two_col=True))
    return "".join(out)


def _hands(c, u, wrists, hands, col):
    out = []
    for s, w, h in zip((-1, 1), wrists, hands):
        el = (c[0] + s * 1.02 * u, c[1] - 0.55 * u)
        sh = (c[0] + s * 0.86 * u, c[1] + 0.3 * u)
        out.append(path(capsule(sh, 0.2 * u, el, 0.14 * u), fill=col))
        out.append(path(capsule(el, 0.14 * u, w, 0.1 * u), fill=col))
        out.append(path(capsule(w, 0.11 * u, h, 0.09 * u), fill=col))
    return "".join(out)


def sc_keyboard_compare(pin, top):
    """Split vs regular keyboard in plan view: where the wrists bend."""
    out = []
    mid = W / 2
    u = 74
    out.append(line((mid, top + 10), (mid, top + 700), sw=0.9, extra='opacity="0.45"'))
    out.append(caption(L, top + 36, "Split keyboard", "Hands at shoulder width", tag_col=SAGE))
    out.append(caption(mid + 30, top + 36, "Regular keyboard", "Hands pulled together", tag_col=TERRA))
    for k, x0 in enumerate((L, mid + 30)):
        c = (x0 + (mid - 30 - L) / 2, top + 560)
        out.append(rect(x0, top + 160, mid - 30 - L, 330, rx=8, fill=PAPER, stroke=LINE, sw=1.6))
        ky = c[1] - 3.6 * u
        if k == 0:
            for s in (-1, 1):
                kx = c[0] + s * 1.3 * u
                out.append(f'<g transform="rotate({-8 * s} {fmt(kx)} {fmt(ky)})">{kb_plan(kx - 0.75 * u, ky - 0.45 * u, 1.5 * u, 0.9 * u)}</g>')
            wrists = [(c[0] - 1.15 * u, c[1] - 2.3 * u), (c[0] + 1.15 * u, c[1] - 2.3 * u)]
            hands = [(c[0] - 1.2 * u, c[1] - 3.05 * u), (c[0] + 1.2 * u, c[1] - 3.05 * u)]
        else:
            out.append(kb_plan(c[0] - 1.45 * u, ky - 0.45 * u, 2.9 * u, 0.9 * u))
            wrists = [(c[0] - 0.62 * u, c[1] - 2.3 * u), (c[0] + 0.62 * u, c[1] - 2.3 * u)]
            hands = [(c[0] - 0.74 * u, c[1] - 3.05 * u), (c[0] + 0.74 * u, c[1] - 3.05 * u)]
        out.append(top_figure(c, u))
        out.append(_hands(c, u, wrists, hands, INK if k == 0 else INK))
        for s, w in zip((-1, 1), wrists):
            el = (c[0] + s * 1.02 * u, c[1] - 0.55 * u)
            d = (w[0] - el[0], w[1] - el[1])
            out.append(line(el, (w[0] + d[0] * 0.5, w[1] + d[1] * 0.5), stroke=SAGE if k == 0 else TERRA, sw=1.3, dash="3 6"))
            if k == 1:
                out.append(strain(w, 18))
    y0 = top + 770
    for i, (good_txt, bad_txt) in enumerate(pin["compare"]):
        yy = y0 + i * 70
        out.append(check((L + 14, yy - 8), r=12))
        out.append(text(L + 40, yy, good_txt, size=23, fill=INK))
        out.append(cross((mid + 44, yy - 8), r=12))
        out.append(text(mid + 70, yy, bad_txt, size=23, fill=INK))
        out.append(hair(yy + 26, L, R, 0.35))
    out.append(text(W / 2, ART_BOTTOM - 40, pin["verdict"], size=34, family=SERIF, fill=INK, anchor="middle", italic=True))
    return "".join(out)


def sc_rhythm(pin, top):
    """Sit / stand / move figures above a proportional time bar."""
    out = []
    segs = pin["segments"]
    total = sum(m for m, _, _ in segs)
    n = len(segs)
    cw = (R - L) / n
    floor_y = top + 500
    u = 58
    cols = [INK_FAR, SAGE, TERRA]
    for i, (mins, lab, kind) in enumerate(segs):
        cx = L + cw * (i + 0.5)
        out.append(floor(L + cw * i + 20, L + cw * (i + 1) - 20, floor_y))
        if kind == "sit":
            hip = (cx - 0.6 * u, floor_y - 2.1 * u)
            out.append(chair_side(hip, u, floor_y))
            s, j = seated(hip, u, SIT)
        else:
            p = pose(STAND, uarm=200, farm=150, fuarm=160, ffarm=200) if kind == "move" else STAND
            s, j = standing(cx - 0.2 * u, floor_y, u, p)
            if kind == "stand":
                out.append(rect(cx - 1.1 * u, floor_y - 0.12 * u, 1.9 * u, 0.12 * u, rx=4, fill=SAGE_SOFT))
        out.append(s)
        if kind == "move":
            out.append(arc_arrow((cx - 0.2 * u, j["shoulder"][1]), 1.6 * u, 300, 380))
        out.append(text(cx, floor_y + 64, f"{mins} MIN", size=16, family=MONO, fill=cols[i % 3], anchor="middle", ls=3))
        out.append(text(cx, floor_y + 112, lab, size=44, family=SERIF, fill=INK, anchor="middle"))
    by = floor_y + 190
    x = L
    for i, (mins, lab, kind) in enumerate(segs):
        w = (R - L) * mins / total
        out.append(rect(x, by, w - 4, 34, rx=4, fill=cols[i % 3]))
        x += w
    out.append(text(L, by + 70, "0", size=15, family=MONO, fill=BODY))
    out.append(text(R, by + 70, f"{total} MIN, THEN REPEAT", size=15, family=MONO, fill=BODY, anchor="end", ls=2))
    out.append(text(W / 2, ART_BOTTOM - 70, pin["verdict"], size=36, family=SERIF, fill=INK, anchor="middle", italic=True))
    return "".join(out)


SCENES4 = {"laptop_monitor": sc_laptop_monitor, "keyboard_compare": sc_keyboard_compare, "rhythm": sc_rhythm}
