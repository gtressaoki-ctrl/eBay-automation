"""Plumb Line — vector drawing kit for the posture plates.

Figures are solid silhouettes built from tapered capsules and smooth
Catmull-Rom outlines; furniture is fine architectural linework.
Coordinates are in CSS px on a 1000x1500 plate.

Angle convention for joints: degrees clockwise from straight up
(0 = up, 90 = forward/right when facing right, 180 = down).
"""

import math

# ------------------------------------------------------------------ palette
PAPER = "#F2EDE4"
PAPER_DEEP = "#E8E1D5"
INK = "#1D2330"
INK_FAR = "#5B6070"
INK_SOFT = "#8B8578"
LINE = "#2A303C"
TERRA = "#C4553B"
TERRA_SOFT = "#E7B7A6"
SAGE = "#6F8F78"
SAGE_SOFT = "#C9D7CB"
GHOST = "#D9C9BC"

SANS = "Instrument Sans"
SERIF = "Instrument Serif"
MONO = "DM Mono"


def fmt(v):
    return f"{v:.1f}".rstrip("0").rstrip(".")


def D(a):
    r = math.radians(a)
    return math.sin(r), -math.cos(r)


def add(p, a, L, f=1):
    v = D(a)
    return (p[0] + f * v[0] * L, p[1] + v[1] * L)


def lerp(a, b, t):
    return (a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t)


def rot(p, c, a):
    r = math.radians(a)
    x, y = p[0] - c[0], p[1] - c[1]
    return (c[0] + x * math.cos(r) - y * math.sin(r), c[1] + x * math.sin(r) + y * math.cos(r))


# ------------------------------------------------------------------ path builders
def smooth_closed(pts, tension=1.0):
    """Closed Catmull-Rom spline through pts -> SVG path d."""
    n = len(pts)
    d = f"M{fmt(pts[0][0])},{fmt(pts[0][1])}"
    for i in range(n):
        p0, p1, p2, p3 = pts[i - 1], pts[i], pts[(i + 1) % n], pts[(i + 2) % n]
        c1 = (p1[0] + (p2[0] - p0[0]) / 6 * tension, p1[1] + (p2[1] - p0[1]) / 6 * tension)
        c2 = (p2[0] - (p3[0] - p1[0]) / 6 * tension, p2[1] - (p3[1] - p1[1]) / 6 * tension)
        d += f" C{fmt(c1[0])},{fmt(c1[1])} {fmt(c2[0])},{fmt(c2[1])} {fmt(p2[0])},{fmt(p2[1])}"
    return d + "Z"


def smooth_open(pts, tension=1.0):
    n = len(pts)
    d = f"M{fmt(pts[0][0])},{fmt(pts[0][1])}"
    for i in range(n - 1):
        p0 = pts[i - 1] if i > 0 else pts[i]
        p1, p2 = pts[i], pts[i + 1]
        p3 = pts[i + 2] if i + 2 < n else pts[i + 1]
        c1 = (p1[0] + (p2[0] - p0[0]) / 6 * tension, p1[1] + (p2[1] - p0[1]) / 6 * tension)
        c2 = (p2[0] - (p3[0] - p1[0]) / 6 * tension, p2[1] - (p3[1] - p1[1]) / 6 * tension)
        d += f" C{fmt(c1[0])},{fmt(c1[1])} {fmt(c2[0])},{fmt(c2[1])} {fmt(p2[0])},{fmt(p2[1])}"
    return d


def capsule(c1, r1, c2, r2):
    """Tapered capsule (two circles + outer tangents) as a path d."""
    dx, dy = c2[0] - c1[0], c2[1] - c1[1]
    d = math.hypot(dx, dy) or 1e-6
    th = math.atan2(dy, dx)
    k = max(-1.0, min(1.0, (r1 - r2) / d))
    ph = math.acos(k)
    pts = []
    steps = 14
    # far end (c2) arc from th-ph to th+ph
    for i in range(steps + 1):
        a = th - ph + 2 * ph * i / steps
        pts.append((c2[0] + r2 * math.cos(a), c2[1] + r2 * math.sin(a)))
    # near end (c1) arc from th+ph to th+2pi-ph
    for i in range(steps + 1):
        a = th + ph + (2 * math.pi - 2 * ph) * i / steps
        pts.append((c1[0] + r1 * math.cos(a), c1[1] + r1 * math.sin(a)))
    return "M" + " L".join(f"{fmt(x)},{fmt(y)}" for x, y in pts) + "Z"


def path(d, fill="none", stroke="none", sw=0, extra=""):
    return f'<path d="{d}" fill="{fill}" stroke="{stroke}" stroke-width="{fmt(sw)}" stroke-linecap="round" stroke-linejoin="round" {extra}/>'


def circle(c, r, fill="none", stroke="none", sw=0, extra=""):
    return f'<circle cx="{fmt(c[0])}" cy="{fmt(c[1])}" r="{fmt(r)}" fill="{fill}" stroke="{stroke}" stroke-width="{fmt(sw)}" {extra}/>'


def line(p1, p2, stroke=LINE, sw=1.6, dash=None, extra=""):
    da = f' stroke-dasharray="{dash}"' if dash else ""
    return (f'<line x1="{fmt(p1[0])}" y1="{fmt(p1[1])}" x2="{fmt(p2[0])}" y2="{fmt(p2[1])}" '
            f'stroke="{stroke}" stroke-width="{fmt(sw)}" stroke-linecap="round"{da} {extra}/>')


def polyline(pts, stroke=LINE, sw=1.6, fill="none", dash=None):
    da = f' stroke-dasharray="{dash}"' if dash else ""
    s = " ".join(f"{fmt(x)},{fmt(y)}" for x, y in pts)
    return f'<polyline points="{s}" fill="{fill}" stroke="{stroke}" stroke-width="{fmt(sw)}" stroke-linecap="round" stroke-linejoin="round"{da}/>'


def rect(x, y, w, h, rx=0, fill="none", stroke="none", sw=0, extra=""):
    return (f'<rect x="{fmt(x)}" y="{fmt(y)}" width="{fmt(w)}" height="{fmt(h)}" rx="{fmt(rx)}" '
            f'fill="{fill}" stroke="{stroke}" stroke-width="{fmt(sw)}" {extra}/>')


def text(x, y, s, size=20, family=SANS, fill=INK, anchor="start", weight=400, ls=0, italic=False, extra=""):
    st = ' font-style="italic"' if italic else ""
    s = s.replace("&", "&amp;").replace("<", "&lt;")
    return (f'<text x="{fmt(x)}" y="{fmt(y)}" font-family="{family}" font-size="{fmt(size)}" fill="{fill}" '
            f'text-anchor="{anchor}" font-weight="{weight}" letter-spacing="{fmt(ls)}"{st} {extra}>{s}</text>')


def g(children, extra=""):
    return f"<g {extra}>" + "".join(children) + "</g>"


# ------------------------------------------------------------------ annotations
def marker(p, col=TERRA, r=5.5, sw=1.8):
    return circle(p, r, fill=PAPER, stroke=col, sw=sw)


def label_width(s, size=21, num=None):
    return len(s) * size * 0.47 + (34 if num is not None else 0)


def label(x, y, s, anchor="start", col=INK, size=21, num=None, num_col=TERRA, knockout=True):
    """Short label; optional mono index number in front.  A paper knockout
    sits behind the text so leader lines never cut through it."""
    out = []
    w = label_width(s, size, num)
    x0 = x if anchor == "start" else x - w if anchor == "end" else x - w / 2
    if knockout:
        out.append(rect(x0 - 8, y - size * 0.95, w + 16, size * 1.35, rx=3, fill=PAPER))
    if num is not None:
        out.append(text(x0, y, f"{num:02d}", size=15, family=MONO, fill=num_col, ls=1))
        out.append(text(x0 + 34, y, s, size=size, fill=col))
    else:
        out.append(text(x, y, s, size=size, fill=col, anchor=anchor))
    return "".join(out)


def callout(p, lp, s, anchor="start", col=INK, lead=LINE, mcol=TERRA, num=None, size=21, elbow=True):
    """Marker at p, hairline leader to the nearer end of the label at lp."""
    out = [marker(p, mcol)]
    w = label_width(s, size, num)
    x0 = lp[0] if anchor == "start" else lp[0] - w if anchor == "end" else lp[0] - w / 2
    x1 = x0 + w
    ly = lp[1] - 7
    if x0 - 4 <= p[0] <= x1 + 4 and abs(p[1] - ly) > 40:
        # target sits under/over the label: drop a straight leader from its edge
        ex = min(max(p[0], x0 + 12), x1 - 12)
        end = (ex, ly + size * 0.55) if p[1] > ly else (ex, ly - size * 1.05)
        out.append(line(_toward(p, end, 6.5), end, stroke=lead, sw=1.1))
        out.append(label(lp[0], lp[1], s, anchor=anchor, col=col, num=num, size=size))
        return "".join(out)
    if p[0] > x1:  # target to the right: leave from the label's right end
        end = (x1 + 10, ly)
        corner = (x1 + 26, ly)
    else:
        end = (x0 - 10, ly)
        corner = (x0 - 26, ly)
    if elbow:
        out.append(polyline([_toward(p, corner, 6.5), corner, end], stroke=lead, sw=1.1))
    else:
        out.append(line(_toward(p, end, 6.5), end, stroke=lead, sw=1.1))
    out.append(label(lp[0], lp[1], s, anchor=anchor, col=col, num=num, size=size))
    return "".join(out)


def _toward(p, q, dist):
    dx, dy = q[0] - p[0], q[1] - p[1]
    L = math.hypot(dx, dy) or 1
    return (p[0] + dx / L * dist, p[1] + dy / L * dist)


def plumb(top, bottom, col=TERRA, sw=1.6, ticks=()):
    out = [line(top, bottom, stroke=col, sw=sw)]
    out.append(circle(top, 3.2, fill=col))
    # small bob
    b = bottom
    out.append(path(f"M{fmt(b[0]-6)},{fmt(b[1])} L{fmt(b[0]+6)},{fmt(b[1])} L{fmt(b[0])},{fmt(b[1]+13)}Z", fill=col))
    for t in ticks:
        out.append(line((t[0] - 7, t[1]), (t[0] + 7, t[1]), stroke=col, sw=sw))
    return "".join(out)


def angle_arc(c, r, a0, a1, col=TERRA, sw=1.4, value=None, value_off=16, size=15):
    """Arc between figure-convention angles a0..a1 with optional mono value."""
    s, e = sorted([a0, a1])
    p0 = add(c, s, r)
    p1 = add(c, e, r)
    large = 1 if e - s > 180 else 0
    d = f"M{fmt(p0[0])},{fmt(p0[1])} A{fmt(r)},{fmt(r)} 0 {large} 1 {fmt(p1[0])},{fmt(p1[1])}"
    out = [path(d, stroke=col, sw=sw)]
    if value:
        m = add(c, (s + e) / 2, r + value_off)
        out.append(text(m[0], m[1] + 5, value, size=size, family=MONO, fill=col, anchor="middle"))
    return "".join(out)


def dimension(p1, p2, s=None, col=LINE, sw=1.1, off=0, size=15, text_side=-1):
    """Dimension line with ticked ends and centred mono label."""
    dx, dy = p2[0] - p1[0], p2[1] - p1[1]
    L = math.hypot(dx, dy) or 1
    nx, ny = -dy / L, dx / L
    a = (p1[0] + nx * off, p1[1] + ny * off)
    b = (p2[0] + nx * off, p2[1] + ny * off)
    out = [line(a, b, stroke=col, sw=sw)]
    for q in (a, b):
        out.append(line((q[0] + nx * 8 + dx / L * 5, q[1] + ny * 8 + dy / L * 5),
                        (q[0] - nx * 8 - dx / L * 5, q[1] - ny * 8 - dy / L * 5), stroke=col, sw=sw))
    if s:
        m = ((a[0] + b[0]) / 2 + nx * 18 * text_side, (a[1] + b[1]) / 2 + ny * 18 * text_side)
        ang = math.degrees(math.atan2(dy, dx))
        if ang > 90 or ang < -90:
            ang += 180
        out.append(f'<g transform="rotate({fmt(ang)} {fmt(m[0])} {fmt(m[1])})">'
                   + text(m[0], m[1] + 5, s, size=size, family=MONO, fill=col, anchor="middle", ls=1) + "</g>")
    return "".join(out)


def arrow(p1, p2, col=TERRA, sw=1.8, head=11):
    ang = math.atan2(p2[1] - p1[1], p2[0] - p1[0])
    h1 = (p2[0] - head * math.cos(ang - 0.45), p2[1] - head * math.sin(ang - 0.45))
    h2 = (p2[0] - head * math.cos(ang + 0.45), p2[1] - head * math.sin(ang + 0.45))
    return line(p1, p2, stroke=col, sw=sw) + polyline([h1, p2, h2], stroke=col, sw=sw)


def arc_arrow(c, r, a0, a1, col=TERRA, sw=1.8, head=10):
    """Arc arrow between figure-convention angles, arrow head at a1."""
    p0 = add(c, a0, r)
    p1 = add(c, a1, r)
    sweep = 1 if a1 > a0 else 0
    large = 1 if abs(a1 - a0) > 180 else 0
    d = f"M{fmt(p0[0])},{fmt(p0[1])} A{fmt(r)},{fmt(r)} 0 {large} {sweep} {fmt(p1[0])},{fmt(p1[1])}"
    tang = a1 + (90 if a1 > a0 else -90)
    back = add(p1, tang + 180, head)
    h1 = rot(back, p1, 25)
    h2 = rot(back, p1, -25)
    return path(d, stroke=col, sw=sw) + polyline([h1, p1, h2], stroke=col, sw=sw)


def strain(c, r, col=TERRA):
    """Concentric thin rings marking a point of strain."""
    out = [circle(c, r * 0.18, fill=col)]
    for k, op in ((0.5, 0.75), (0.8, 0.45), (1.1, 0.22)):
        out.append(circle(c, r * k, stroke=col, sw=1.3, extra=f'opacity="{op}"'))
    return "".join(out)


def check(c, r=13, col=SAGE):
    return circle(c, r, fill=col) + polyline([(c[0] - r * 0.42, c[1] + r * 0.02), (c[0] - r * 0.1, c[1] + r * 0.34), (c[0] + r * 0.45, c[1] - r * 0.32)], stroke=PAPER, sw=2.2)


def cross(c, r=13, col=TERRA):
    k = r * 0.36
    return (circle(c, r, fill=col) + line((c[0] - k, c[1] - k), (c[0] + k, c[1] + k), stroke=PAPER, sw=2.2)
            + line((c[0] - k, c[1] + k), (c[0] + k, c[1] - k), stroke=PAPER, sw=2.2))


# ------------------------------------------------------------------ figures
SIDE = dict(lumbar=0, thoracic=0, neck=4, head=0, thigh=90, shin=180, foot=90,
            uarm=176, farm=96, hand=0, fthigh=None, fshin=None, ffoot=None, fuarm=None, ffarm=None, fhand=None,
            far_arm=True, far_leg=True)


def side_figure(hip, u, f=1, col=INK, far=INK_FAR, legs=1.0, **kw):
    """Side-view silhouette. hip = hip joint (px); u = head height (px)."""
    p = dict(SIDE)
    p.update(kw)
    for k in ("thigh", "shin", "foot", "uarm", "farm", "hand"):
        if p["f" + k] is None:
            p["f" + k] = p[k]

    lum, tho, nk = p["lumbar"], p["thoracic"], p["neck"]
    mid = add(hip, lum, 1.18 * u, f)
    sh = add(mid, tho, 1.22 * u, f)
    nb = add(sh, nk, 0.2 * u, f)
    ear = add(nb, nk, 0.55 * u, f)
    head_tilt = nk + p["head"]

    def fwd(a):  # forward normal of a spine direction
        return a + 90

    # ---- torso outline
    st = [  # (point, spine angle, back half, front half)
        (add(hip, lum + 180, 0.18 * u, f), lum, 0.44, 0.36),
        (hip, lum, 0.50, 0.40),
        (lerp(hip, mid, 0.5), lum, 0.42, 0.38),
        (mid, (lum + tho) / 2, 0.36, 0.40),
        (lerp(mid, sh, 0.45), tho, 0.40, 0.50),
        (lerp(mid, sh, 0.8), tho, 0.40, 0.44),
        (sh, (tho + nk) / 2, 0.40, 0.33),
        (lerp(sh, nb, 0.5), nk, 0.27, 0.21),
        (lerp(sh, nb, 1.0), nk, 0.19, 0.16),
    ]
    front = [add(pt, fwd(a), fr * u, f) for pt, a, bk, fr in st]
    back = [add(pt, fwd(a) + 180, bk * u, f) for pt, a, bk, fr in st]
    torso_pts = front + back[::-1]

    # ---- head (profile), local coords facing right: x forward, y down; origin = ear
    prof = [(-0.47, -0.02), (-0.43, -0.32), (-0.24, -0.52), (0.06, -0.57), (0.3, -0.47), (0.41, -0.27),
            (0.44, -0.12), (0.53, 0.03), (0.45, 0.11), (0.46, 0.2), (0.4, 0.33), (0.22, 0.4), (0.02, 0.34),
            (-0.18, 0.28), (-0.38, 0.18)]
    head_pts = []
    for x, y in prof:
        q = (ear[0] + f * x * u, ear[1] + y * u)
        head_pts.append(rot(q, ear, head_tilt * f))

    arm0 = add(sh, tho + 180, 0.14 * u, f)

    def arm(ua, fa, ha, c):
        e = add(arm0, ua, 1.32 * u, f)
        w = add(e, fa, 1.22 * u, f)
        hd = add(w, fa + ha, 0.5 * u, f)
        return [path(capsule(arm0, 0.19 * u, e, 0.135 * u), fill=c),
                path(capsule(e, 0.135 * u, w, 0.095 * u), fill=c),
                path(capsule(w, 0.1 * u, hd, 0.075 * u), fill=c)], e, w, hd

    def leg(th, sn, ft, c):
        k = add(hip, th, 1.95 * u * legs, f)
        a = add(k, sn, 1.9 * u * legs, f)
        calf = add(lerp(k, a, 0.32), sn + 90, -0.07 * u, f)
        heel = add(add(a, ft + 180, 0.14 * u, f), ft + 90, 0.1 * u, f)
        toe = add(add(a, ft, 0.78 * u, f), ft + 90, 0.12 * u, f)
        return [path(capsule(hip, 0.4 * u, k, 0.22 * u), fill=c),
                path(capsule(k, 0.21 * u, calf, 0.2 * u), fill=c),
                path(capsule(calf, 0.2 * u, a, 0.11 * u), fill=c),
                path(capsule(heel, 0.11 * u, toe, 0.075 * u), fill=c),
                circle(a, 0.12 * u, fill=c)], k, a, toe

    out = []
    if p["far_leg"]:
        out += leg(p["fthigh"], p["fshin"], p["ffoot"], far)[0]
    fa_parts = None
    if p["far_arm"]:
        fa_parts = arm(p["fuarm"], p["ffarm"], p["fhand"], far)
        out += fa_parts[0]
    out.append(path(smooth_closed(torso_pts), fill=col))
    glute = add(add(hip, lum + 180, 0.12 * u, f), lum - 90, 0.22 * u, f)
    out.append(circle(glute, 0.38 * u, fill=col))
    neck_top = rot((ear[0] - f * 0.06 * u, ear[1] + 0.3 * u), ear, head_tilt * f)
    out.append(path(capsule(lerp(sh, nb, 0.4), 0.2 * u, neck_top, 0.17 * u), fill=col))
    out.append(path(smooth_closed(head_pts), fill=col))
    lg, knee, ankle, toe = leg(p["thigh"], p["shin"], p["foot"], col)
    ar, elbow, wrist, hand = arm(p["uarm"], p["farm"], p["hand"], col)
    # a thin paper outline separates the near limbs from the body behind them
    halo = 'stroke="%s" stroke-width="%s" stroke-linejoin="round"' % (PAPER, fmt(max(2.0, 0.035 * u)))
    for part in lg[:3] + ar:
        out.append(part.replace('stroke="none" stroke-width="0"', halo))
    out += lg + ar
    head_c = rot((ear[0] + f * 0.02 * u, ear[1] - 0.12 * u), ear, head_tilt * f)
    return "".join(out), dict(hip=hip, mid=mid, shoulder=sh, neck=nb, ear=ear, head=head_c,
                              eye=rot((ear[0] + f * 0.36 * u, ear[1] - 0.14 * u), ear, head_tilt * f),
                              knee=knee, ankle=ankle, toe=toe, elbow=elbow, wrist=wrist, hand=hand,
                              top=min(pt[1] for pt in head_pts), u=u,
                              back=add(mid, (lum + tho) / 2 - 90, 0.36 * u, f),
                              upper_back=add(lerp(mid, sh, 0.55), tho - 90, 0.42 * u, f),
                              chest=add(lerp(mid, sh, 0.5), tho + 90, 0.5 * u, f))


def front_figure(cx, hipy, u, col=INK, seated=False, lean=0, tilt=0, la=(186, 180), ra=(174, 180),
                 lh=0, rh=0, legs=True):
    """Front/back-view silhouette.  la/ra: (upper, fore) angles of image-left/right arm."""
    pel = (cx, hipy)

    def R(q):
        return rot(q, pel, lean)

    top = hipy - 2.45 * u
    pts = [(-0.66, 0.05), (-0.6, -0.55), (-0.52, -1.1), (-0.56, -1.6), (-0.7, -2.05), (-0.84, -2.3),
           (-0.72, -2.46), (-0.22, -2.6), (0.22, -2.6), (0.72, -2.46), (0.84, -2.3), (0.7, -2.05),
           (0.56, -1.6), (0.52, -1.1), (0.6, -0.55), (0.66, 0.05), (0.3, 0.22), (-0.3, 0.22)]
    torso = [R((cx + x * u, hipy + y * u)) for x, y in pts]
    neck0 = R((cx, top - 0.05 * u))
    neck1 = add(neck0, lean, 0.34 * u)
    hc = add(neck1, lean + tilt, 0.5 * u)
    out = []
    shl = R((cx - 0.72 * u, top + 0.12 * u))
    shr = R((cx + 0.72 * u, top + 0.12 * u))

    def arm(s, ua, fa, ha):
        ua += lean
        fa += lean
        e = add(s, ua, 1.3 * u)
        w = add(e, fa, 1.2 * u)
        hd = add(w, fa + ha, 0.46 * u)
        return [path(capsule(s, 0.2 * u, e, 0.14 * u), fill=col),
                path(capsule(e, 0.14 * u, w, 0.1 * u), fill=col),
                path(capsule(w, 0.1 * u, hd, 0.07 * u), fill=col)], e, w

    if legs:
        if seated:
            for s in (-1, 1):
                h = (cx + s * 0.34 * u, hipy + 0.05 * u)
                k = (cx + s * 0.44 * u, hipy + 0.42 * u)
                a = (cx + s * 0.46 * u, hipy + 2.15 * u)
                out.append(path(capsule(h, 0.36 * u, k, 0.27 * u), fill=col))
                out.append(path(capsule(k, 0.22 * u, a, 0.11 * u), fill=col))
                out.append(path(capsule((a[0] - s * 0.02 * u, a[1] + 0.08 * u), 0.1 * u, (a[0] + s * 0.12 * u, a[1] + 0.14 * u), 0.09 * u), fill=col))
        else:
            for s in (-1, 1):
                h = (cx + s * 0.34 * u, hipy + 0.05 * u)
                k = (cx + s * 0.4 * u, hipy + 1.95 * u)
                a = (cx + s * 0.4 * u, hipy + 3.85 * u)
                out.append(path(capsule(h, 0.36 * u, k, 0.21 * u), fill=col))
                out.append(path(capsule(k, 0.21 * u, a, 0.1 * u), fill=col))
                out.append(path(capsule(a, 0.1 * u, (a[0] + s * 0.2 * u, a[1] + 0.14 * u), 0.09 * u), fill=col))
    out.append(path(smooth_closed(torso), fill=col))
    out.append(path(capsule(neck0, 0.2 * u, neck1, 0.17 * u), fill=col))
    head = [(0, -0.56), (0.3, -0.48), (0.42, -0.2), (0.38, 0.12), (0.22, 0.38), (0, 0.46),
            (-0.22, 0.38), (-0.38, 0.12), (-0.42, -0.2), (-0.3, -0.48)]
    out.append(path(smooth_closed([rot((hc[0] + x * u, hc[1] + y * u), hc, lean + tilt) for x, y in head]), fill=col))
    a1, el, wl = arm(shl, *la, lh)
    a2, er, wr = arm(shr, *ra, rh)
    out += a1 + a2
    return "".join(out), dict(head=hc, shl=shl, shr=shr, el=el, er=er, wl=wl, wr=wr, neck=neck0, pelvis=pel,
                              top=hc[1] - 0.56 * u, u=u)


def top_figure(c, u, col=INK, arms_to=None):
    """Plan view: head circle, shoulders, optional arms reaching to points."""
    out = [path(smooth_closed([(c[0] - 1.0 * u, c[1] + 0.35 * u), (c[0] - 0.9 * u, c[1] + 0.05 * u),
                              (c[0], c[1] - 0.1 * u), (c[0] + 0.9 * u, c[1] + 0.05 * u),
                              (c[0] + 1.0 * u, c[1] + 0.35 * u), (c[0] + 0.85 * u, c[1] + 0.62 * u),
                              (c[0], c[1] + 0.72 * u), (c[0] - 0.85 * u, c[1] + 0.62 * u)]), fill=col)]
    if arms_to:
        for s, t in zip((-1, 1), arms_to):
            sh = (c[0] + s * 0.86 * u, c[1] + 0.3 * u)
            el = (c[0] + s * 1.02 * u, c[1] - 0.55 * u)
            out.append(path(capsule(sh, 0.2 * u, el, 0.14 * u), fill=col))
            out.append(path(capsule(el, 0.14 * u, t, 0.09 * u), fill=col))
    out.append(path(smooth_closed([(c[0], c[1] - 0.62 * u), (c[0] + 0.36 * u, c[1] - 0.45 * u), (c[0] + 0.4 * u, c[1] - 0.05 * u),
                                   (c[0] + 0.24 * u, c[1] + 0.22 * u), (c[0] - 0.24 * u, c[1] + 0.22 * u), (c[0] - 0.4 * u, c[1] - 0.05 * u),
                                   (c[0] - 0.36 * u, c[1] - 0.45 * u)]), fill=col))
    return "".join(out)


# ------------------------------------------------------------------ furniture (linework)
def chair_side(hip, u, floor, f=1, sw=2.0, col=LINE, lumbar=None, arm=False, recline=6, back_h=2.6, fill=None):
    """Office chair in elevation. Returns svg."""
    out = []
    sy = hip[1] + 0.42 * u
    x0 = hip[0] - 0.62 * u * f
    x1 = hip[0] + 1.55 * u * f
    xa, xb = min(x0, x1), max(x0, x1)
    out.append(rect(xa, sy, xb - xa, 0.26 * u, rx=0.13 * u, fill=fill or PAPER, stroke=col, sw=sw))
    # backrest
    bx = hip[0] - 0.78 * u * f
    b0 = (bx, sy - 0.18 * u)
    b1 = add(b0, -recline, back_h * u, f)
    mid = lerp(b0, b1, 0.45)
    mid = (mid[0] - 0.12 * u * f, mid[1])
    out.append(path(smooth_open([add(b0, 90, 0.05 * u, f), mid, b1]), stroke=col, sw=0.26 * u))
    out.append(path(smooth_open([add(b0, 90, 0.05 * u, f), mid, b1]), stroke=fill or PAPER, sw=0.26 * u - 2 * sw))
    # spine connecting backrest to seat
    out.append(path(smooth_open([(bx - 0.06 * u * f, sy - 0.1 * u), (bx - 0.1 * u * f, sy + 0.2 * u), (hip[0] - 0.2 * u * f, sy + 0.34 * u)]),
                    stroke=col, sw=sw))
    if lumbar:
        lp = add(lerp(b0, b1, 0.22), 90, 0.22 * u, f)
        out.append(f'<ellipse cx="{fmt(lp[0])}" cy="{fmt(lp[1])}" rx="{fmt(0.2*u)}" ry="{fmt(0.42*u)}" fill="{lumbar}"/>')
    if arm:
        ay = hip[1] - 0.95 * u
        out.append(line((hip[0] + 0.05 * u * f, ay), (hip[0] + 1.1 * u * f, ay), stroke=col, sw=0.14 * u))
        out.append(line((hip[0] + 0.25 * u * f, ay), (hip[0] + 0.25 * u * f, sy), stroke=col, sw=sw))
    # gas lift + base
    cx = hip[0] + 0.45 * u * f
    out.append(line((cx, sy + 0.26 * u), (cx, floor - 0.5 * u), stroke=col, sw=0.1 * u))
    out.append(rect(cx - 0.07 * u, floor - 0.62 * u, 0.14 * u, 0.2 * u, rx=0.03 * u, fill=col))
    out.append(path(f"M{fmt(cx - 0.95*u)},{fmt(floor - 0.2*u)} Q{fmt(cx)},{fmt(floor - 0.62*u)} {fmt(cx + 0.95*u)},{fmt(floor - 0.2*u)}", stroke=col, sw=sw))
    for x in (cx - 0.95 * u, cx + 0.95 * u):
        out.append(circle((x, floor - 0.1 * u), 0.1 * u, fill=PAPER, stroke=col, sw=sw))
    return "".join(out)


def desk_side(x0, x1, top, floor, u, sw=2.0, col=LINE, legs=True):
    xa, xb = min(x0, x1), max(x0, x1)
    out = [rect(xa, top, xb - xa, 0.16 * u, rx=1.5, fill=PAPER, stroke=col, sw=sw)]
    if legs:
        lx = xb - 0.25 * u
        out.append(line((lx, top + 0.16 * u), (lx, floor), stroke=col, sw=sw))
        out.append(line((lx - 0.35 * u, floor), (lx + 0.15 * u, floor), stroke=col, sw=sw))
        out.append(line((lx - 0.14 * u, top + 0.16 * u), (lx - 0.14 * u, top + 0.5 * u), stroke=col, sw=sw))
    return "".join(out)


def monitor_side(x, desk_top, u, screen_top, face=-1, sw=2.0, col=LINE, h=1.6, screen=None):
    """Monitor in elevation; face=-1 screen faces left (viewer sits left)."""
    bot = screen_top + h * u
    out = [line((x - 0.42 * u, desk_top - 1), (x + 0.42 * u, desk_top - 1), stroke=col, sw=sw * 1.6),
           line((x, desk_top), (x, bot - 0.45 * u), stroke=col, sw=sw * 1.5),
           path(f"M{fmt(x)},{fmt(bot-0.45*u)} Q{fmt(x+0.05*u*-face)},{fmt(bot-0.2*u)} {fmt(x + 0.05*u*face)},{fmt(bot-0.25*u)}", stroke=col, sw=sw)]
    fx = x + 0.1 * u * face
    out.append(rect(min(fx, fx + 0.1 * u * face), screen_top, 0.1 * u, h * u, rx=0.03 * u, fill=screen or PAPER, stroke=col, sw=sw))
    return "".join(out), (fx + 0.05 * u * face, screen_top), (fx + 0.05 * u * face, bot)


def keyboard_side(x0, x1, desk_top, u, sw=2.0, col=LINE, tilt=0.0):
    return path(f"M{fmt(x0)},{fmt(desk_top)} L{fmt(x1)},{fmt(desk_top)} L{fmt(x1)},{fmt(desk_top - (0.1 + tilt) * u)} L{fmt(x0)},{fmt(desk_top - 0.06*u)}Z",
                fill=PAPER, stroke=col, sw=sw)


def laptop_side(hinge_x, base_y, u, face=-1, sw=2.0, col=LINE, open_deg=108, base_len=1.3):
    """Laptop in elevation.  face=-1: user on the left, hinge on the right."""
    b0 = (hinge_x + base_len * u * face, base_y)
    hinge = (hinge_x, base_y)
    back = math.radians(open_deg - 90)
    top = (hinge_x - face * math.sin(back) * 1.2 * u, base_y - math.cos(back) * 1.2 * u)
    return (line(b0, hinge, stroke=col, sw=sw * 1.8) + line(hinge, top, stroke=col, sw=sw * 1.8)), hinge, top


def floor(x0, x1, y, col=LINE, sw=1.4):
    out = [line((x0, y), (x1, y), stroke=col, sw=sw)]
    # hatching under floor line: architectural ground
    x = x0 + 6
    while x < x1 - 14:
        out.append(line((x + 12, y + 2), (x, y + 14), stroke=col, sw=0.8, extra='opacity="0.35"'))
        x += 16
    return "".join(out)
