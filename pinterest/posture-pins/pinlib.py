"""Drawing primitives for the posture pin illustrations.

Everything is drawn on a 2x canvas (2000x3000) and downsampled to the
1000x1500 Pinterest size at the end, which gives smooth anti-aliased edges.

Angle convention used by the figures: degrees measured clockwise from
"straight up".  0 = up, 90 = forward (right when facing right),
180 = down, 270 = backward.
"""

import math
import os

from PIL import Image, ImageDraw, ImageFilter, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
FONT_DIR = os.path.join(HERE, "fonts")

# ---------------------------------------------------------------- palette
NAVY = (31, 42, 68)
INK = (52, 60, 82)
MUTED = (96, 104, 124)
TEAL = (42, 157, 143)
TEAL_LIGHT = (205, 234, 229)
CORAL = (231, 111, 81)
CORAL_LIGHT = (250, 222, 212)
MUSTARD = (233, 196, 106)
SAND = (244, 162, 97)
WHITE = (255, 255, 255)
WOOD = (214, 170, 120)
WOOD_DARK = (176, 132, 86)
STEEL = (74, 82, 100)
STEEL_LIGHT = (140, 148, 164)
SCREEN = (128, 196, 222)
PLANT = (96, 160, 110)

BG = {
    "cream": (247, 241, 232),
    "sage": (229, 239, 231),
    "sky": (228, 238, 247),
    "blush": (250, 235, 229),
    "butter": (252, 243, 219),
    "lavender": (238, 235, 248),
    "mint": (224, 243, 238),
}

SKIN = [(241, 194, 160), (205, 145, 104), (150, 96, 64), (255, 220, 192)]
HAIR = [(58, 40, 30), (30, 30, 36), (140, 86, 48), (92, 60, 40)]


def shade(c, k):
    return tuple(max(0, min(255, int(v * k))) for v in c[:3])


def mix(a, b, t):
    return tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3))


def person(shirt=TEAL, pants=NAVY, skin=0, hair=0, shoe=(44, 48, 60)):
    return dict(shirt=shirt, pants=pants, skin=SKIN[skin], hair=HAIR[hair], shoe=shoe)


# ---------------------------------------------------------------- fonts
_font_cache = {}


def font(weight, size):
    key = (weight, size)
    if key not in _font_cache:
        path = os.path.join(FONT_DIR, f"Poppins-{weight}.ttf")
        _font_cache[key] = ImageFont.truetype(path, int(size))
    return _font_cache[key]


def text_w(fnt, text):
    b = fnt.getbbox(text)
    return b[2] - b[0]


def wrap(text, fnt, maxw):
    words = text.split()
    lines, cur = [], ""
    for w in words:
        t = (cur + " " + w).strip()
        if text_w(fnt, t) <= maxw or not cur:
            cur = t
        else:
            lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return lines


def text_block(img, x, y, text, fnt, fill, maxw, align="center", leading=1.12):
    """Draw wrapped text. x is the centre (align=center) or left edge."""
    d = ImageDraw.Draw(img)
    lines = wrap(text, fnt, maxw)
    asc, desc = fnt.getmetrics()
    lh = int((asc + desc) * leading)
    for i, ln in enumerate(lines):
        if align == "center":
            d.text((x, y + i * lh), ln, font=fnt, fill=fill, anchor="ma")
        else:
            d.text((x, y + i * lh), ln, font=fnt, fill=fill, anchor="la")
    return y + len(lines) * lh


# ---------------------------------------------------------------- geometry
def D(a):
    r = math.radians(a)
    return math.sin(r), -math.cos(r)


def add(p, a, length, f=1):
    v = D(a)
    return (p[0] + f * v[0] * length, p[1] + v[1] * length)


def rot(p, c, a):
    """Rotate point p around c by a degrees clockwise (screen coords)."""
    r = math.radians(a)
    x, y = p[0] - c[0], p[1] - c[1]
    return (c[0] + x * math.cos(r) - y * math.sin(r), c[1] + x * math.sin(r) + y * math.cos(r))


def seg(img, p1, p2, w, col):
    d = ImageDraw.Draw(img)
    d.line([p1, p2], fill=col, width=int(w))
    r = w / 2
    for p in (p1, p2):
        d.ellipse([p[0] - r, p[1] - r, p[0] + r, p[1] + r], fill=col)


def poly_line(img, pts, w, col):
    for a, b in zip(pts, pts[1:]):
        seg(img, a, b, w, col)


def circle(img, c, r, fill=None, outline=None, width=1):
    d = ImageDraw.Draw(img)
    d.ellipse([c[0] - r, c[1] - r, c[0] + r, c[1] + r], fill=fill, outline=outline, width=int(width))


def rrect(img, box, r, fill=None, outline=None, width=1):
    d = ImageDraw.Draw(img)
    x0, y0, x1, y1 = box
    box = [min(x0, x1), min(y0, y1), max(x0, x1), max(y0, y1)]
    r = min(r, (box[2] - box[0]) / 2, (box[3] - box[1]) / 2)
    d.rounded_rectangle(box, radius=max(0, r), fill=fill, outline=outline, width=int(width))


def polygon(img, pts, fill):
    ImageDraw.Draw(img).polygon(pts, fill=fill)


def dashed(img, p1, p2, col, w=6, dash=26, gap=18):
    d = ImageDraw.Draw(img)
    x1, y1 = p1
    x2, y2 = p2
    L = math.hypot(x2 - x1, y2 - y1)
    if L == 0:
        return
    ux, uy = (x2 - x1) / L, (y2 - y1) / L
    t = 0
    while t < L:
        e = min(t + dash, L)
        d.line([(x1 + ux * t, y1 + uy * t), (x1 + ux * e, y1 + uy * e)], fill=col, width=int(w))
        t += dash + gap


def arrow(img, p1, p2, col, w=10, head=34):
    seg(img, p1, p2, w, col)
    ang = math.atan2(p2[1] - p1[1], p2[0] - p1[0])
    a1 = ang + math.radians(150)
    a2 = ang - math.radians(150)
    pts = [p2, (p2[0] + head * math.cos(a1), p2[1] + head * math.sin(a1)),
           (p2[0] + head * math.cos(a2), p2[1] + head * math.sin(a2))]
    polygon(img, pts, col)


def curved_arrow(img, c, r, a0, a1, col, w=10, head=30):
    """Arc arrow using PIL angles (0 = 3 o'clock, clockwise)."""
    d = ImageDraw.Draw(img)
    d.arc([c[0] - r, c[1] - r, c[0] + r, c[1] + r], a0, a1, fill=col, width=int(w))
    t = math.radians(a1)
    tip = (c[0] + r * math.cos(t), c[1] + r * math.sin(t))
    tang = t + math.pi / 2
    back = (tip[0] - head * math.cos(tang), tip[1] - head * math.sin(tang))
    nx, ny = math.cos(t), math.sin(t)
    pts = [(tip[0] + head * 0.2 * math.cos(tang), tip[1] + head * 0.2 * math.sin(tang)),
           (back[0] + nx * head * 0.55, back[1] + ny * head * 0.55),
           (back[0] - nx * head * 0.55, back[1] - ny * head * 0.55)]
    polygon(img, pts, col)


def angle_arc(img, c, r, a0, a1, col, w=6):
    """Arc between two figure-convention angles (0 = up, clockwise)."""
    d = ImageDraw.Draw(img)
    s, e = sorted([a0 - 90, a1 - 90])
    d.arc([c[0] - r, c[1] - r, c[0] + r, c[1] + r], s, e, fill=col, width=int(w))


def check_badge(img, c, r, col=TEAL):
    circle(img, c, r, fill=col)
    pts = [(c[0] - r * 0.45, c[1] + r * 0.02), (c[0] - r * 0.1, c[1] + r * 0.36), (c[0] + r * 0.48, c[1] - r * 0.34)]
    poly_line(img, pts, r * 0.22, WHITE)


def cross_badge(img, c, r, col=CORAL):
    circle(img, c, r, fill=col)
    k = r * 0.38
    seg(img, (c[0] - k, c[1] - k), (c[0] + k, c[1] + k), r * 0.22, WHITE)
    seg(img, (c[0] - k, c[1] + k), (c[0] + k, c[1] - k), r * 0.22, WHITE)


def num_badge(img, c, r, n, col=NAVY, fg=WHITE):
    circle(img, c, r, fill=col)
    ImageDraw.Draw(img).text(c, str(n), font=font("Bold", r * 1.15), fill=fg, anchor="mm")


def pill(img, xy, text, fnt, fg=WHITE, bg=NAVY, anchor="mm", pad=(26, 12), radius=None):
    d = ImageDraw.Draw(img)
    b = d.textbbox((0, 0), text, font=fnt, anchor="lt")
    tw, th = b[2] - b[0], b[3] - b[1]
    asc, desc = fnt.getmetrics()
    th = asc - desc * 0.35
    w, h = tw + pad[0] * 2, th + pad[1] * 2
    x, y = xy
    if anchor[0] == "m":
        x0 = x - w / 2
    elif anchor[0] == "r":
        x0 = x - w
    else:
        x0 = x
    if anchor[1] == "m":
        y0 = y - h / 2
    elif anchor[1] == "b":
        y0 = y - h
    else:
        y0 = y
    rrect(img, (x0, y0, x0 + w, y0 + h), radius if radius is not None else h / 2, fill=bg)
    d.text((x0 + w / 2, y0 + h / 2), text, font=fnt, fill=fg, anchor="mm")
    return (x0, y0, x0 + w, y0 + h)


def callout(img, point, label_xy, text, fnt, col=NAVY, fg=WHITE, dot=16, anchor="mm"):
    seg(img, point, label_xy, 5, col)
    circle(img, point, dot, fill=WHITE, outline=col, width=7)
    return pill(img, label_xy, text, fnt, fg=fg, bg=col, anchor=anchor)


def glow(img, c, r, col=CORAL, alpha=170):
    layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    for i in range(6, 0, -1):
        rr = r * i / 6
        a = int(alpha * (1 - i / 7))
        d.ellipse([c[0] - rr, c[1] - rr, c[0] + rr, c[1] + rr], fill=col + (a,))
    layer = layer.filter(ImageFilter.GaussianBlur(r / 5))
    img.alpha_composite(layer)
    # little "ache" strokes
    for k, a in enumerate((-40, 0, 40)):
        p1 = add(c, a, r * 0.95)
        p2 = add(c, a, r * 1.25)
        seg(img, p1, p2, max(6, r * 0.09), col)


# ---------------------------------------------------------------- figures
SIDE_DEFAULT = dict(lumbar=0, thoracic=0, neck=6, thigh=90, shin=180, foot=90,
                    uarm=172, farm=95, fthigh=None, fshin=None, fuarm=None, ffarm=None,
                    ffoot=None, far_arm=True, hand_obj=None)


def side_figure(img, hip, u, pal, f=1, legs=(1.0, 1.0), **kw):
    """Flat side-view person.  hip = hip joint; f=1 faces right, -1 left.

    Returns a dict of joint positions for annotation.
    """
    p = dict(SIDE_DEFAULT)
    p.update(kw)
    for k in ("thigh", "shin", "uarm", "farm", "foot"):
        if p["f" + k] is None:
            p["f" + k] = p[k]
    lt, ls = 2.1 * u * legs[0], 2.05 * u * legs[1]

    p1 = add(hip, p["lumbar"], 1.35 * u, f)
    sh = add(p1, p["thoracic"], 1.45 * u, f)
    nb = add(sh, p["neck"], 0.32 * u, f)
    hc = add(nb, p["neck"], 0.66 * u, f)
    arm0 = add(sh, p["thoracic"] + 180, 0.12 * u, f)

    pants_far = shade(pal["pants"], 0.78)
    shirt_far = shade(pal["shirt"], 0.8)
    skin_far = shade(pal["skin"], 0.88)

    def leg(th, sn, ft, pants, off):
        h = (hip[0] + off * f, hip[1])
        k = add(h, th, lt, f)
        a = add(k, sn, ls, f)
        toe = add(a, ft, 0.7 * u, f)
        heel = add(a, ft + 180, 0.12 * u, f)
        seg(img, h, k, 0.64 * u, pants)
        seg(img, k, a, 0.5 * u, pants)
        seg(img, heel, toe, 0.3 * u, pal["shoe"])
        return k, a, toe

    def arm(ua, fa, shirt, skin):
        e = add(arm0, ua, 1.45 * u, f)
        w = add(e, fa, 1.35 * u, f)
        seg(img, arm0, e, 0.42 * u, shirt)
        seg(img, e, w, 0.36 * u, skin)
        seg(img, add(e, ua + 180, 0.25 * u, f), e, 0.42 * u, shirt)
        circle(img, add(w, fa, 0.08 * u, f), 0.21 * u, fill=skin)
        return e, w

    # far side limbs
    leg(p["fthigh"], p["fshin"], p["ffoot"], pants_far, -0.08 * u)
    if p["far_arm"]:
        arm(p["fuarm"], p["ffarm"], shirt_far, skin_far)

    # torso + head
    seg(img, nb, add(nb, p["neck"] + 180, 0.2 * u, f), 0.36 * u, pal["skin"])
    poly_line(img, [add(hip, p["lumbar"], 0.15 * u, f), p1, sh], 0.98 * u, pal["shirt"])
    circle(img, hip, 0.52 * u, fill=pal["pants"])
    seg(img, nb, hc, 0.36 * u, pal["skin"])
    hr = 0.56 * u
    circle(img, hc, hr, fill=pal["skin"])
    tilt = p["neck"]
    d = ImageDraw.Draw(img)
    if f == 1:
        a0, a1 = 118 + tilt, 328 + tilt
    else:
        a0, a1 = 212 - tilt, 422 - tilt
    d.pieslice([hc[0] - hr * 1.07, hc[1] - hr * 1.1, hc[0] + hr * 1.07, hc[1] + hr * 1.04], a0, a1, fill=pal["hair"])
    circle(img, add(hc, tilt + 80, hr * 0.42, f), hr * 0.62, fill=pal["skin"])
    eye = add(hc, tilt + 82, 0.3 * u, f)
    ear = add(hc, tilt + 200, 0.08 * u, f)
    circle(img, eye, 0.065 * u, fill=NAVY)
    circle(img, ear, 0.12 * u, fill=shade(pal["skin"], 0.9))

    # near limbs
    knee, ankle, toe = leg(p["thigh"], p["shin"], p["foot"], pal["pants"], 0)
    elbow, wrist = arm(p["uarm"], p["farm"], shade(pal["shirt"], 0.9), pal["skin"])
    return dict(hip=hip, mid=p1, shoulder=sh, neck=nb, head=hc, head_r=hr, eye=eye, ear=ear,
                knee=knee, ankle=ankle, toe=toe, elbow=elbow, wrist=wrist, u=u)


def front_figure(img, cx, hipy, u, pal, seated=False, lean=0, tilt=0,
                 la=(188, 182), ra=(172, 178), back=False, chair=None, legs_visible=True):
    """Front (or back) view person.  la/ra = (upper, fore) angles for the
    image-left / image-right arm.  lean rotates the upper body around the
    pelvis (positive = toward image right)."""
    pel = (cx, hipy)

    def R(pt):
        return rot(pt, pel, lean)

    shl = R((cx - 0.98 * u, hipy - 2.75 * u))
    shr = R((cx + 0.98 * u, hipy - 2.75 * u))
    neck0 = R((cx, hipy - 2.75 * u))
    neck1 = add(neck0, lean, 0.38 * u)
    hc = add(neck1, lean + tilt, 0.62 * u)
    hr = 0.58 * u

    if chair is not None and seated:
        # backrest + seat behind the body
        rrect(img, (cx - 1.3 * u, hipy - 2.7 * u, cx + 1.3 * u, hipy + 0.1 * u), 0.3 * u, fill=chair)
        rrect(img, (cx - 1.45 * u, hipy + 0.1 * u, cx + 1.45 * u, hipy + 0.42 * u), 0.15 * u, fill=shade(chair, 0.85))
        seg(img, (cx, hipy + 0.42 * u), (cx, hipy + 1.6 * u), 0.22 * u, shade(chair, 0.7))
        seg(img, (cx - 1.1 * u, hipy + 1.75 * u), (cx + 1.1 * u, hipy + 1.75 * u), 0.2 * u, shade(chair, 0.7))
        for x in (cx - 1.1 * u, cx + 1.1 * u):
            circle(img, (x, hipy + 1.92 * u), 0.14 * u, fill=NAVY)

    # legs
    if legs_visible:
        if seated:
            for s in (-1, 1):
                h = (cx + s * 0.48 * u, hipy + 0.1 * u)
                k = (cx + s * 0.62 * u, hipy + 0.62 * u)
                a = (cx + s * 0.66 * u, hipy + 2.35 * u)
                seg(img, h, k, 0.72 * u, shade(pal["pants"], 1.08))
                seg(img, k, a, 0.52 * u, pal["pants"])
                seg(img, (a[0] - 0.12 * u, a[1] + 0.12 * u), (a[0] + 0.12 * u, a[1] + 0.12 * u), 0.34 * u, pal["shoe"])
        else:
            for s in (-1, 1):
                h = (cx + s * 0.46 * u, hipy + 0.1 * u)
                k = (cx + s * 0.5 * u, hipy + 2.15 * u)
                a = (cx + s * 0.52 * u, hipy + 4.15 * u)
                seg(img, h, k, 0.66 * u, pal["pants"])
                seg(img, k, a, 0.52 * u, pal["pants"])
                seg(img, a, (a[0] + s * 0.28 * u, a[1] + 0.1 * u), 0.3 * u, pal["shoe"])
        rrect(img, (cx - 0.86 * u, hipy - 0.35 * u, cx + 0.86 * u, hipy + 0.42 * u), 0.3 * u, fill=pal["pants"])

    # torso
    torso = [shl, shr, R((cx + 0.84 * u, hipy - 0.1 * u)), R((cx - 0.84 * u, hipy - 0.1 * u))]
    polygon(img, torso, pal["shirt"])
    circle(img, shl, 0.36 * u, fill=pal["shirt"])
    circle(img, shr, 0.36 * u, fill=pal["shirt"])
    seg(img, R((cx - 0.84 * u, hipy - 0.25 * u)), R((cx + 0.84 * u, hipy - 0.25 * u)), 0.3 * u, pal["shirt"])

    # neck + head
    seg(img, neck0, neck1, 0.4 * u, shade(pal["skin"], 0.92))
    circle(img, hc, hr, fill=pal["skin"])
    d = ImageDraw.Draw(img)
    t = lean + tilt
    if back:
        circle(img, hc, hr * 1.02, fill=pal["hair"])
    else:
        d.pieslice([hc[0] - hr * 1.05, hc[1] - hr * 1.08, hc[0] + hr * 1.05, hc[1] + hr * 1.0],
                   190 + t, 350 + t, fill=pal["hair"])
        circle(img, add(hc, t, hr * 0.62), hr * 0.62, fill=pal["hair"])
        circle(img, add(hc, t + 180, hr * 0.1), hr * 0.72, fill=pal["skin"])
        for s in (-1, 1):
            circle(img, add(add(hc, t + 90 * s, hr * 0.34), t + 180, hr * 0.12), hr * 0.08, fill=NAVY)

    # arms
    def arm(s0, ua, fa):
        ua += lean
        fa += lean
        e = add(s0, ua, 1.45 * u)
        w = add(e, fa, 1.35 * u)
        seg(img, s0, e, 0.44 * u, pal["shirt"])
        seg(img, e, w, 0.36 * u, pal["skin"])
        seg(img, add(e, ua + 180, 0.3 * u), e, 0.44 * u, pal["shirt"])
        circle(img, add(w, fa, 0.08 * u), 0.22 * u, fill=pal["skin"])
        return e, w

    el, wl = arm(add(shl, lean + 180, 0.1 * u), *la)
    er, wr = arm(add(shr, lean + 180, 0.1 * u), *ra)
    return dict(head=hc, head_r=hr, shl=shl, shr=shr, neck=neck0, el=el, wl=wl, er=er, wr=wr,
                pelvis=pel, u=u)


# ---------------------------------------------------------------- furniture (side view)
def side_chair(img, hip, u, floor, f=1, col=STEEL, arm=False, lumbar=None, back_h=3.0, recline=0):
    sy = hip[1] + 0.48 * u
    x0 = hip[0] - 0.75 * u * f
    x1 = hip[0] + 1.75 * u * f
    rrect(img, (x0, sy, x1, sy + 0.3 * u), 0.14 * u, fill=col)
    bx = hip[0] - 0.9 * u * f
    top = add((bx, sy), -recline, back_h * u, f)
    seg(img, (bx, sy + 0.1 * u), top, 0.16 * u, shade(col, 0.8))
    pad_bot = (bx + 0.05 * u * f, sy - 0.35 * u)
    pad_top = add(pad_bot, -recline, (back_h - 0.5) * u, f)
    seg(img, pad_bot, pad_top, 0.42 * u, col)
    if lumbar:
        lp = add(pad_bot, -recline, 0.95 * u, f)
        lp = (lp[0] + 0.3 * u * f, lp[1])
        d = ImageDraw.Draw(img)
        d.ellipse([lp[0] - 0.3 * u, lp[1] - 0.55 * u, lp[0] + 0.3 * u, lp[1] + 0.55 * u], fill=lumbar)
    if arm:
        ay = hip[1] - 1.25 * u
        seg(img, (hip[0] + 0.2 * u * f, ay), (hip[0] + 1.3 * u * f, ay), 0.2 * u, shade(col, 0.75))
        seg(img, (hip[0] + 0.5 * u * f, ay), (hip[0] + 0.5 * u * f, sy), 0.12 * u, shade(col, 0.75))
    cxs = hip[0] + 0.5 * u * f
    seg(img, (cxs, sy + 0.3 * u), (cxs, floor - 0.45 * u), 0.2 * u, shade(col, 0.7))
    seg(img, (cxs - 1.0 * u, floor - 0.35 * u), (cxs + 1.0 * u, floor - 0.35 * u), 0.16 * u, shade(col, 0.7))
    for x in (cxs - 1.0 * u, cxs + 1.0 * u):
        circle(img, (x, floor - 0.17 * u), 0.17 * u, fill=NAVY)
    return sy


def side_desk(img, x0, x1, top, floor, u, col=WOOD):
    rrect(img, (x0, top, x1, top + 0.26 * u), 0.08 * u, fill=col)
    rrect(img, (x0, top + 0.18 * u, x1, top + 0.3 * u), 0.04 * u, fill=shade(col, 0.82))
    lx = x1 - 0.35 * u if x1 > x0 else x1 + 0.35 * u
    seg(img, (lx, top + 0.3 * u), (lx, floor), 0.18 * u, shade(col, 0.72))


def side_monitor(img, x, desk_top, u, screen_top, f=-1, col=(40, 44, 54)):
    """Monitor seen from the side.  f=-1 means the screen faces left."""
    seg(img, (x - 0.5 * u, desk_top - 0.06 * u), (x + 0.5 * u, desk_top - 0.06 * u), 0.12 * u, col)
    bottom = screen_top + 1.75 * u
    seg(img, (x, desk_top), (x, bottom - 0.4 * u), 0.14 * u, col)
    face = x + 0.18 * u * f
    polygon(img, [(x, screen_top), (face, screen_top + 0.05 * u), (face, bottom - 0.05 * u), (x, bottom)], SCREEN)
    rrect(img, (x - 0.1 * u, screen_top, x + 0.1 * u, bottom), 0.05 * u, fill=col)
    return (face, screen_top), (face, bottom)


def side_laptop(img, x, base_y, u, f=-1, open_angle=108, col=(150, 158, 172)):
    """Laptop base centred at x resting on base_y. f=-1: screen faces left
    (user sits on the left).  Returns (hinge, screen_top)."""
    b0 = (x - 0.75 * u, base_y)
    b1 = (x + 0.75 * u, base_y)
    seg(img, b0, b1, 0.1 * u, col)
    hinge = b1 if f == -1 else b0
    back = math.radians(open_angle - 90)
    top = (hinge[0] - f * math.sin(back) * 1.35 * u, hinge[1] - math.cos(back) * 1.35 * u)
    seg(img, hinge, top, 0.1 * u, col)
    return hinge, top


def floor_line(img, x0, x1, y, col):
    rrect(img, (x0, y, x1, y + 12), 6, fill=col)
