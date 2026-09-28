"""Plumb Line scenes — one function per illustration type.

Each scene receives (pin, top) where top is the y where the illustration
field starts (below the headline block) and returns an SVG fragment.
The field ends at ART_BOTTOM.
"""

from plate import ART_BOTTOM, MARGIN, W
from svgkit import (GHOST, INK, INK_FAR, INK_SOFT, LINE, MONO, PAPER, PAPER_DEEP, SAGE, SAGE_SOFT, SERIF,
                    TERRA, TERRA_SOFT, add, angle_arc, arc_arrow, arrow, callout, capsule, chair_side, check,
                    circle, cross, desk_side, dimension, floor, fmt, front_figure, keyboard_side, laptop_side,
                    lerp, line, marker, monitor_side, path, plumb, polyline, rect, side_figure, smooth_closed,
                    strain, text, top_figure)

L, R = MARGIN, W - MARGIN
BODY = "#4E5260"

# ---------------------------------------------------------------- poses
SIT = dict(lumbar=2, thoracic=-2, neck=4, uarm=178, farm=97, hand=-8, fuarm=176, ffarm=97, fhand=-8)
SLUMP = dict(lumbar=-16, thoracic=30, neck=48, head=6, uarm=150, farm=100, hand=-4, fuarm=152, ffarm=100, fhand=-4)
STAND = dict(thigh=180, shin=180, fthigh=180, fshin=180, lumbar=0, thoracic=-1, neck=3,
             uarm=182, farm=178, hand=2, fuarm=178, ffarm=176, fhand=2)
STAND_BAD = dict(thigh=176, shin=184, fthigh=176, fshin=184, lumbar=-10, thoracic=24, neck=40, head=8,
                 uarm=192, farm=186, hand=4, fuarm=190, ffarm=184, fhand=4)


def pose(base, **kw):
    p = dict(base)
    p.update(kw)
    return p


def hair(y, x0=L, x1=R, op=0.45):
    return line((x0, y), (x1, y), sw=0.9, extra=f'opacity="{op}"')


# ---------------------------------------------------------------- composites
def seated(hip, u, p, col=INK, far=INK_FAR, legs=1.0):
    return side_figure(hip, u, col=col, far=far, legs=legs, **p)


def standing(cx, floor_y, u, p, col=INK, far=INK_FAR, f=1):
    hip = (cx, floor_y - 3.85 * u - 0.2 * u)
    return side_figure(hip, u, f=f, col=col, far=far, **p)


def seated_desk(u, hipx, floor_y, fig_pose=SIT, monitor="eye", laptop=None, lumbar=None, footrest=False,
                legs=1.0, chair_arm=False, desk_x1=None, desk_raise=0.0, show_floor=True, keyboard=True,
                book=False, lamp=False):
    """Person seated facing right at a desk.  Returns (svg, joints, geom)."""
    out = []
    hip = (hipx, floor_y - 1.9 * u * legs - 0.2 * u)
    if show_floor:
        out.append(floor(L, R, floor_y))
    out.append(chair_side(hip, u, floor_y, lumbar=lumbar, arm=chair_arm))
    desk_top = hip[1] - 0.82 * u - desk_raise * u
    dx0 = hip[0] + 1.25 * u
    dx1 = desk_x1 if desk_x1 is not None else min(R, hip[0] + 5.1 * u)
    out.append(desk_side(dx0, dx1, desk_top, floor_y, u))
    fig, j = seated(hip, u, fig_pose, legs=legs)
    geom = dict(desk_top=desk_top, dx0=dx0, dx1=dx1, floor=floor_y, hip=hip)
    if monitor in ("eye", "low"):
        top_y = j["eye"][1] - 0.05 * u if monitor == "eye" else desk_top - 1.75 * u
        m, st, sb = monitor_side(hip[0] + 4.0 * u, desk_top, u, top_y)
        out.append(m)
        geom.update(screen_top=st, screen_bot=sb)
    if laptop == "desk":
        s, hinge, top = laptop_side(hip[0] + 2.9 * u, desk_top - 1, u)
        out.append(s)
        geom.update(laptop_hinge=hinge, laptop_top=top)
    elif laptop == "stand":
        sx = hip[0] + 3.1 * u
        out.append(path(f"M{fmt(sx - 0.9*u)},{fmt(desk_top)} L{fmt(sx + 0.35*u)},{fmt(desk_top)} "
                        f"L{fmt(sx + 0.35*u)},{fmt(desk_top - 1.05*u)}Z", fill=PAPER, stroke=LINE, sw=2))
        s, hinge, top = laptop_side(sx + 0.4 * u, desk_top - 1.1 * u, u, open_deg=100, base_len=1.25)
        out.append(s)
        geom.update(laptop_hinge=hinge, laptop_top=top)
    if keyboard and (monitor in ("eye", "low") or laptop == "stand"):
        out.append(keyboard_side(hip[0] + 1.5 * u, hip[0] + 2.35 * u, desk_top, u))
    if book:
        bx = hip[0] + 2.2 * u
        out.append(path(f"M{fmt(bx)},{fmt(desk_top)} L{fmt(bx + 0.9*u)},{fmt(desk_top - 1.2*u)} "
                        f"L{fmt(bx + 1.05*u)},{fmt(desk_top - 1.1*u)} L{fmt(bx + 0.3*u)},{fmt(desk_top)}Z",
                        fill=PAPER, stroke=LINE, sw=2))
        out.append(path(f"M{fmt(bx + 0.05*u)},{fmt(desk_top - 0.35*u)} L{fmt(bx + 0.75*u)},{fmt(desk_top - 1.3*u)} "
                        f"L{fmt(bx + 0.25*u)},{fmt(desk_top - 1.62*u)} L{fmt(bx - 0.45*u)},{fmt(desk_top - 0.66*u)}Z",
                        fill=TERRA_SOFT, stroke=LINE, sw=2))
    if lamp:
        lx = dx1 - 0.55 * u
        out.append(line((lx - 0.3 * u, desk_top - 1), (lx + 0.3 * u, desk_top - 1), sw=3.2))
        out.append(polyline([(lx, desk_top), (lx - 0.25 * u, desk_top - 1.5 * u), (lx - 0.85 * u, desk_top - 1.85 * u)], sw=2))
        out.append(path(f"M{fmt(lx - 0.7*u)},{fmt(desk_top - 2.1*u)} L{fmt(lx - 1.3*u)},{fmt(desk_top - 1.55*u)} "
                        f"Q{fmt(lx - 0.9*u)},{fmt(desk_top - 1.5*u)} {fmt(lx - 0.62*u)},{fmt(desk_top - 1.7*u)}Z",
                        fill=PAPER, stroke=LINE, sw=2))
    if footrest:
        fx = hip[0] + 1.75 * u
        out.append(path(f"M{fmt(fx - 0.2*u)},{fmt(floor_y)} L{fmt(fx + 1.2*u)},{fmt(floor_y)} "
                        f"L{fmt(fx + 1.2*u)},{fmt(floor_y - 0.42*u)} L{fmt(fx - 0.2*u)},{fmt(floor_y - 0.2*u)}Z",
                        fill=PAPER, stroke=LINE, sw=2))
    out.append(fig)
    return "".join(out), j, geom


def caption(x, y, tag, s, tag_col=TERRA, anchor="start", size=24):
    """Mono tag above a short sans caption."""
    return (text(x, y, tag.upper(), size=14, family=MONO, fill=tag_col, ls=3, anchor=anchor)
            + text(x, y + 34, s, size=size, fill=INK, anchor=anchor))


def _rows(x, y, w, items, num_col, size, gap, start):
    out = [hair(y, x, x + w, 0.5)]
    for i, s in enumerate(items):
        yy = y + gap * (i + 1)
        out.append(text(x, yy - gap / 2 + 6, f"{start + i + 1:02d}", size=15, family=MONO, fill=num_col, ls=1))
        out.append(text(x + 44, yy - gap / 2 + 8, s, size=size, fill=INK))
        out.append(hair(yy, x, x + w, 0.5))
    return "".join(out)


def rows(x, y, w, items, num_col=TERRA, size=24, gap=58, two_col=False, start=0):
    """Editorial numbered list with hairline separators."""
    if two_col:
        half = (len(items) + 1) // 2
        colw = (w - 48) / 2
        return (_rows(x, y, colw, items[:half], num_col, size, gap, start)
                + _rows(x + colw + 48, y, colw, items[half:], num_col, size, gap, start + half))
    return _rows(x, y, w, items, num_col, size, gap, start)


def inline_list(x, y, title, items):
    out = [text(x, y, title, size=14, family=MONO, fill=TERRA, ls=3)]
    xx = x
    for i, fx in enumerate(items):
        out.append(text(xx, y + 40, f"{i + 1:02d}", size=15, family=MONO, fill=TERRA))
        out.append(text(xx + 34, y + 42, fx, size=24, fill=INK))
        xx += 34 + len(fx) * 11.5 + 52
    return "".join(out)


def verdict_mark(x, y, good, s, anchor="start"):
    c = (x + 13, y - 8)
    mark = check(c) if good else cross(c)
    return mark + text(x + 36, y, s, size=23, fill=INK, anchor=anchor)


# ================================================================ scenes
def sc_desk_guide(pin, top):
    u = 124
    floor_y = ART_BOTTOM - 30
    s, j, g = seated_desk(u, 280, floor_y)
    out = [s]
    ex = j["ear"][0]
    out.append(plumb((ex, j["top"] - 36), (ex, j["hip"][1] + 34), ticks=[(ex, j["shoulder"][1])]))
    st = g["screen_top"]
    out.append(line((j["eye"][0] + 8, j["eye"][1]), (st[0] - 4, j["eye"][1]), stroke=TERRA, sw=1.2, dash="1 7"))
    out.append(callout(j["ear"], (L, top + 40), "Ears stacked over shoulders", num=1))
    out.append(callout(st, (R - 290, top + 40), "Screen top at eye level", num=2))
    out.append(callout(j["back"], (L, top + 100), "Lower back supported", num=3))
    out.append(callout(j["elbow"], (R - 270, j["elbow"][1] + 90), "Elbows open to ~90°", num=4))
    out.append(callout(j["knee"], (R - 270, j["knee"][1] + 75), "Knees level with hips", num=5))
    out.append(callout(j["toe"], (R - 270, floor_y - 40), "Feet flat on the floor", num=6))
    return "".join(out)


def sc_signs(pin, top):
    out = []
    u = 70
    floor_y = top + 480
    hip = (300, floor_y - 1.9 * u - 0.2 * u)
    out.append(floor(L, R, floor_y))
    out.append(chair_side(hip, u, floor_y))
    desk_top = hip[1] - 0.82 * u
    out.append(desk_side(hip[0] + 1.25 * u, R - 40, desk_top, floor_y, u))
    m, st, sb = monitor_side(hip[0] + 4.6 * u, desk_top, u, desk_top - 2.5 * u)
    out.append(m)
    ghost, jg = seated(hip, u, SIT, col=GHOST, far=GHOST)
    out.append(ghost)
    fig, jb = seated(hip, u, SLUMP)
    out.append(fig)
    out.append(strain(jb["neck"], 30))
    out.append(strain(jb["upper_back"], 26))
    out.append(callout(jb["ear"], (R - 300, top + 40), "Head drifts forward", num=1))
    out.append(callout(jb["upper_back"], (L, top + 40), "Upper back rounds", num=2))
    items = ["Head juts forward of the shoulders", "Shoulders roll in and round",
             "Upper back hunches over the desk", "Neck and traps tight by noon",
             "Tension headaches after screen time", "Low back aches when you sit",
             "You tire after short sits"]
    out.append(rows(L, floor_y + 56, R - L, items, gap=54, size=25))
    return "".join(out)


def sc_forward_head(pin, top):
    out = []
    u = 88
    floor_y = ART_BOTTOM - 130
    cx1, cx2 = 300, 700
    out.append(floor(L, R, floor_y))
    gb, jb = standing(cx1, floor_y, u, pose(STAND, lumbar=-4, thoracic=12, neck=44, head=4))
    gg, jg = standing(cx2, floor_y, u, STAND)
    out += [gb, gg]
    for j, good in ((jb, False), (jg, True)):
        x = j["ankle"][0] + 4
        out.append(line((x, j["top"] - 50), (x, floor_y - 4), stroke=SAGE if good else INK_SOFT, sw=1.3,
                        dash=None if good else "4 6"))
        out.append(marker(j["ear"], SAGE if good else TERRA))
    out.append(dimension((jb["ankle"][0] + 4, jb["top"] - 24), (jb["ear"][0], jb["top"] - 24), None, col=TERRA))
    out.append(verdict_mark(cx1 - 120, top + 40, False, "Head forward"))
    out.append(verdict_mark(cx2 - 120, top + 40, True, "Ear over shoulder"))
    out.append(inline_list(L, floor_y + 64, "DAILY FIXES", ["Chin tucks", "Raise the screen", "Strengthen upper back"]))
    return "".join(out)


# ---- exercise library (small figures in cells)
SEATED_FRONT = ("side_neck", "shoulder_rolls", "overhead_reach", "side_bend", "neck_turn")


def ex_figure(kind, box):
    x0, y0, x1, y1 = box
    cx = (x0 + x1) / 2
    fy = y1 - 8
    out = []
    h = y1 - y0
    if kind in ("chin_tuck_seated", "upper_back_ext", "chest_opener_seated"):
        u = min(62, h / 6.4)
        hip = (cx - 70, fy - 1.9 * u - 0.2 * u)
        out.append(chair_side(hip, u, fy, sw=1.6))
        p = {"chin_tuck_seated": pose(SIT, neck=-2, head=-4, uarm=176, farm=150, fuarm=176, ffarm=150),
             "upper_back_ext": pose(SIT, lumbar=-4, thoracic=-16, neck=-12, uarm=150, farm=345, fuarm=150, ffarm=345),
             "chest_opener_seated": pose(SIT, thoracic=-8, neck=0, uarm=206, farm=196, fuarm=206, ffarm=196)}[kind]
        s, j = seated(hip, u, p)
        out.append(s)
        if kind == "chin_tuck_seated":
            out.append(arrow((j["ear"][0] + 100, j["ear"][1]), (j["ear"][0] + 52, j["ear"][1])))
        elif kind == "upper_back_ext":
            out.append(arc_arrow(j["mid"], 2.9 * u, 10, -14))
        else:
            out.append(arrow((j["chest"][0] + 26, j["chest"][1]), (j["chest"][0] + 72, j["chest"][1] - 12)))
    elif kind in ("chin_tuck_standing", "chest_opener_stand"):
        u = min(52, h / 8.5)
        p = {"chin_tuck_standing": pose(STAND, neck=-2, head=-4),
             "chest_opener_stand": pose(STAND, thoracic=-8, neck=-2, uarm=206, farm=196, fuarm=206, ffarm=196)}[kind]
        s, j = standing(cx - 10, fy, u, p)
        out.append(s)
        if kind == "chin_tuck_standing":
            out.append(arrow((j["ear"][0] + 92, j["ear"][1]), (j["ear"][0] + 46, j["ear"][1])))
        else:
            out.append(arrow((j["chest"][0] + 26, j["chest"][1]), (j["chest"][0] + 72, j["chest"][1] - 12)))
    else:
        seat = kind in SEATED_FRONT
        up = kind in ("overhead_reach", "overhead_reach_stand", "side_neck", "side_bend", "side_bend_stand", "wall_angels")
        u = h / ((8.8 if up else 6.8) if seat else (10.4 if up else 8.8))
        hipy = fy - 2.3 * u if seat else fy - 4.0 * u
        kw = {
            "side_neck": dict(tilt=26, la=(186, 180), ra=(28, 292)),
            "shoulder_rolls": dict(),
            "overhead_reach": dict(la=(12, 18), ra=(348, 342)),
            "side_bend": dict(lean=-15, la=(196, 182), ra=(340, 305)),
            "neck_turn": dict(),
            "overhead_reach_stand": dict(la=(12, 18), ra=(348, 342)),
            "side_bend_stand": dict(lean=-13, la=(196, 182), ra=(340, 305)),
            "wall_angels": dict(la=(272, 340), ra=(88, 20)),
            "scap_squeeze": dict(la=(245, 350), ra=(115, 10)),
        }[kind]
        if seat:
            out.append(rect(cx - 1.25 * u, hipy - 2.3 * u, 2.5 * u, 2.4 * u, rx=0.35 * u, fill=PAPER, stroke=LINE, sw=1.6))
            out.append(rect(cx - 1.35 * u, hipy + 0.1 * u, 2.7 * u, 0.26 * u, rx=0.12 * u, fill=PAPER, stroke=LINE, sw=1.6))
            out.append(line((cx, hipy + 0.36 * u), (cx, fy - 0.35 * u), sw=1.6))
            out.append(path(f"M{fmt(cx - 1.1*u)},{fmt(fy - 0.12*u)} Q{fmt(cx)},{fmt(fy - 0.5*u)} {fmt(cx + 1.1*u)},{fmt(fy - 0.12*u)}",
                            stroke=LINE, sw=1.6))
        if kind == "wall_angels":
            out.append(rect(cx - 2.2 * u, y0 + 4, 4.4 * u, fy - y0 - 4, fill=PAPER_DEEP))
        s, j = front_figure(cx, hipy, u, seated=seat, **kw)
        out.append(s)
        if kind == "shoulder_rolls":
            for sgn, c in ((-1, j["shl"]), (1, j["shr"])):
                cc = (c[0] + sgn * 0.35 * u, c[1] - 0.5 * u)
                out.append(arc_arrow(cc, 0.42 * u, 180 + sgn * 60, 180 + sgn * 330, sw=1.6, head=8))
        elif kind == "neck_turn":
            out.append(arc_arrow(j["head"], 0.95 * u, -60, 60, sw=1.6, head=8))
        elif kind == "wall_angels":
            for e in (j["el"], j["er"]):
                out.append(arrow((e[0], e[1] - 0.3 * u), (e[0], e[1] - 1.1 * u), sw=1.6, head=8))
        elif kind == "scap_squeeze":
            c = ((j["shl"][0] + j["shr"][0]) / 2, j["shl"][1] + 0.55 * u)
            out.append(arrow((c[0] - 1.7 * u, c[1]), (c[0] - 0.95 * u, c[1]), sw=1.6, head=8))
            out.append(arrow((c[0] + 1.7 * u, c[1]), (c[0] + 0.95 * u, c[1]), sw=1.6, head=8))
    return "".join(out)


def sc_exercise_grid(pin, top):
    out = []
    y0 = top + 10
    if pin.get("badge"):
        b = pin["badge"].upper()
        out.append(text(L, y0 + 16, b, size=15, family=MONO, fill=TERRA, ls=4))
        out.append(line((L + len(b) * 13.2 + 18, y0 + 11), (R, y0 + 11), stroke=TERRA, sw=1))
        y0 += 44
    mid_x = (L + R) / 2
    mid_y = (y0 + ART_BOTTOM) / 2
    out.append(line((mid_x, y0), (mid_x, ART_BOTTOM), sw=0.9, extra='opacity="0.45"'))
    out.append(hair(mid_y))
    cells = [(L, y0, mid_x, mid_y), (mid_x, y0, R, mid_y), (L, mid_y, mid_x, ART_BOTTOM), (mid_x, mid_y, R, ART_BOTTOM)]
    for i, ((kind, title, dose), c) in enumerate(zip(pin["exercises"], cells)):
        x0, cy0, x1, cy1 = c
        px = x0 + (0 if i % 2 == 0 else 32)
        out.append(text(px, cy0 + 42, f"{i + 1:02d}", size=15, family=MONO, fill=TERRA, ls=2))
        out.append(text(px + 40, cy0 + 46, title, size=33, family=SERIF, fill=INK))
        out.append(text(px + 40, cy0 + 74, dose.upper(), size=13, family=MONO, fill=INK_SOFT, ls=3))
        out.append(ex_figure(kind, (x0 + 20, cy0 + 100, x1 - 20, cy1 - 22)))
    return "".join(out)


def sc_pain(pin, top):
    out = []
    u = 96
    floor_y = ART_BOTTOM - 236
    if pin["area"] == "upper_back":
        p = pose(SIT, lumbar=-6, thoracic=26, neck=40, head=4, uarm=150, farm=98, fuarm=152, ffarm=98)
        s, j, g = seated_desk(u, 330, floor_y, p)
        out.append(s)
        spot = lerp(j["upper_back"], j["shoulder"], 0.25)
        out.append(strain(spot, 46))
        out.append(callout(spot, (L, top + 40), "Between the shoulder blades", num=1))
        out.append(callout(j["ear"], (R - 290, top + 40), "Head pulled forward", num=2))
    else:
        p = pose(SIT, lumbar=-4, thoracic=20, neck=50, head=6, uarm=150, farm=100, fuarm=150, ffarm=340, fhand=-10)
        s, j, g = seated_desk(u, 330, floor_y, p, monitor="low")
        out.append(s)
        out.append(strain(j["neck"], 44))
        st = g["screen_top"]
        centre = lerp(g["screen_top"], g["screen_bot"], 0.5)
        out.append(line(j["eye"], centre, stroke=TERRA, sw=1.2, dash="1 7"))
        out.append(callout(j["neck"], (L, top + 40), "Neck strain", num=1))
        out.append(callout(st, (R - 270, top + 40), "Screen too low", num=2))
    out.append(text(L, floor_y + 62, pin.get("causes_title", "COMMON CAUSES"), size=14, family=MONO, fill=TERRA, ls=3))
    out.append(rows(L, floor_y + 80, R - L, pin["causes"], gap=48, size=24))
    return "".join(out)


def sc_headache(pin, top):
    out = []
    u = 118
    cx = W / 2
    desk_y = ART_BOTTOM - 150
    hipy = desk_y + 0.55 * u
    out.append(rect(cx - 1.35 * u, hipy - 2.75 * u, 2.7 * u, 2.9 * u, rx=0.4 * u, fill=PAPER, stroke=LINE, sw=2))
    s, j = front_figure(cx, hipy, u, seated=True, legs=False, la=(212, 22), ra=(148, 338), tilt=3)
    out.append(s)
    out.append(rect(L - 10, desk_y, R - L + 20, 0.2 * u, rx=2, fill=PAPER, stroke=LINE, sw=2))
    out.append(rect(L + 10, desk_y + 0.2 * u, R - L - 20, ART_BOTTOM - desk_y - 0.2 * u, fill=PAPER, stroke=LINE, sw=2))
    out.append(path(f"M{fmt(L + 50)},{fmt(desk_y)} L{fmt(L + 80)},{fmt(desk_y - 1.2*u)} L{fmt(L + 270)},{fmt(desk_y - 1.2*u)} "
                    f"L{fmt(L + 300)},{fmt(desk_y)}Z", fill=PAPER, stroke=LINE, sw=2))
    out.append(rect(R - 150, desk_y - 0.62 * u, 0.62 * u, 0.62 * u, rx=0.08 * u, fill=PAPER, stroke=LINE, sw=2))
    out.append(path(f"M{fmt(R - 150 + 0.62*u)},{fmt(desk_y - 0.5*u)} q{fmt(0.25*u)},0 {fmt(0.25*u)},{fmt(0.2*u)} "
                    f"q0,{fmt(0.2*u)} {fmt(-0.25*u)},{fmt(0.2*u)}", stroke=LINE, sw=2))
    hc = j["head"]
    for k, op in ((0.95, 0.55), (1.25, 0.32), (1.55, 0.16)):
        out.append(circle(hc, k * u, stroke=TERRA, sw=1.4, extra=f'opacity="{op}"'))
    out.append(strain(j["neck"], 30))
    out.append(callout(j["neck"], (L, top + 40), "Tight neck muscles", num=1))
    out.append(callout(j["shr"], (R - 280, top + 40), "Shoulders creep up", num=2))
    return "".join(out)


def sc_timeline(pin, top):
    out = []
    stages = pin["stages"]
    n = len(stages)
    u = 60
    floor_y = top + 560
    cw = (R - L) / n
    out.append(floor(L, R, floor_y))
    tones = [GHOST, TERRA_SOFT, INK_FAR, INK]
    for i in range(n):
        t = i / (n - 1)
        p = pose(STAND, lumbar=-9 * (1 - t), thoracic=26 * (1 - t) - t, neck=42 * (1 - t) + 3 * t, head=8 * (1 - t),
                 uarm=194 * (1 - t) + 182 * t, farm=188 * (1 - t) + 178 * t)
        cx = L + cw * (i + 0.5) - 0.3 * u
        col = tones[i] if n == 4 else INK
        s, j = standing(cx, floor_y, u, p, col=col, far=col)
        out.append(s)
        x = j["ankle"][0] + 3
        out.append(line((x, j["top"] - 30), (x, floor_y - 3), stroke=TERRA, sw=1.1, dash="3 5"))
    ty = floor_y + 70
    out.append(line((L + cw / 2, ty), (R - cw / 2, ty), stroke=INK, sw=1.4))
    for i, (when, what) in enumerate(stages):
        cx = L + cw * (i + 0.5)
        out.append(circle((cx, ty), 9, fill=PAPER if i < n - 1 else TERRA, stroke=TERRA, sw=2))
        out.append(text(cx, ty + 60, when.upper(), size=15, family=MONO, fill=TERRA, anchor="middle", ls=2))
        lines, cur = [], ""
        for w_ in what.split():
            if len(cur + " " + w_) > 14 and cur:
                lines.append(cur)
                cur = w_
            else:
                cur = (cur + " " + w_).strip()
        lines.append(cur)
        for k, ln in enumerate(lines):
            out.append(text(cx, ty + 102 + k * 32, ln, size=24, fill=INK, anchor="middle"))
    return "".join(out)


def sc_phone(pin, top):
    """Pin 23: text neck vs raised phone, side by side."""
    out = []
    u = 86
    floor_y = ART_BOTTOM - 120
    out.append(floor(L, R, floor_y))
    pb = pose(STAND_BAD, neck=58, head=12, uarm=172, farm=58, hand=12, fuarm=172, ffarm=58, fhand=12)
    pg = pose(STAND, neck=4, uarm=164, farm=26, hand=-8, fuarm=164, ffarm=26, fhand=-8)
    for cx, p, good in ((280, pb, False), (690, pg, True)):
        s, j = standing(cx, floor_y, u, p)
        out.append(s)
        h = j["hand"]
        out.append(rect(h[0] - 8, h[1] - 32, 16, 42, rx=4, fill=INK, stroke=PAPER, sw=2))
        out.append(line(j["eye"], (h[0] - 2, h[1] - 18), stroke=SAGE if good else TERRA, sw=1.2, dash="1 6"))
        x = j["ankle"][0] + 4
        out.append(line((x, j["top"] - 50), (x, floor_y - 4), stroke=SAGE if good else INK_SOFT, sw=1.3,
                        dash=None if good else "4 6"))
        out.append(marker(j["ear"], SAGE if good else TERRA))
        if not good:
            out.append(strain(j["neck"], 34))
    la, lb = pin["labels"]
    out.append(caption(L, top + 36, la[0], la[1], tag_col=TERRA))
    out.append(caption(R, top + 36, lb[0], lb[1], tag_col=SAGE, anchor="end"))
    out.append(inline_list(L, floor_y + 62, "WHAT HELPS", pin["fixes"]))
    return "".join(out)


def sc_before_after(pin, top):
    out = []
    u = 88
    floor_y = ART_BOTTOM - (120 if pin.get("fixes") else 30)
    cx = W / 2 - 30
    phone = pin.get("phone")
    if phone:
        pb = pose(STAND_BAD, neck=56, head=10, uarm=174, farm=62, hand=10, fuarm=174, ffarm=62, fhand=10)
        pg = pose(STAND, neck=4, uarm=162, farm=28, hand=-6, fuarm=162, ffarm=28, fhand=-6)
    else:
        pb, pg = STAND_BAD, STAND
    out.append(floor(L, R, floor_y))
    sb, jb = standing(cx, floor_y, u, pb, col=TERRA_SOFT, far=TERRA_SOFT)
    sg, jg = standing(cx, floor_y, u, pg)
    out += [sb, sg]
    x = jg["ankle"][0] + 4
    out.append(plumb((x, jg["top"] - 50), (x, floor_y - 16)))
    out.append(marker(jb["ear"], TERRA))
    out.append(marker(jg["ear"], SAGE))
    out.append(dimension((x, jb["top"] - 22), (jb["ear"][0], jb["top"] - 22), None, col=TERRA))
    if not phone:
        out.append(callout(jb["shoulder"], (R - 250, jb["shoulder"][1] + 40), "Shoulders roll forward", num=1))
        out.append(callout(jb["mid"], (R - 250, jb["mid"][1] + 90), "Pelvis tucks under", num=2))
    else:
        out.append(callout(jb["neck"], (R - 250, jb["neck"][1] + 60), "Neck bends to the screen", num=1))
    if phone:
        for j, col in ((jb, TERRA_SOFT), (jg, INK)):
            h = j["hand"]
            out.append(rect(h[0] - 9, h[1] - 34, 18, 44, rx=4, fill=col))
        out.append(line(jb["eye"], (jb["hand"][0], jb["hand"][1] - 20), stroke=TERRA, sw=1.2, dash="1 6"))
    la, lb = pin["labels"]
    out.append(caption(L, top + 36, la[0], la[1], tag_col=TERRA))
    out.append(caption(R, top + 36, lb[0], lb[1], tag_col=SAGE, anchor="end"))
    if pin.get("fixes"):
        out.append(inline_list(L, floor_y + 62, "WHAT HELPS", pin["fixes"]))
    return "".join(out)


def sc_monitor_height(pin, top):
    out = []
    u = 112
    floor_y = ART_BOTTOM - 30
    s, j, g = seated_desk(u, 260, floor_y)
    out.append(s)
    st, sb = g["screen_top"], g["screen_bot"]
    eye = j["eye"]
    out.append(line(eye, (st[0], eye[1]), stroke=TERRA, sw=1.3, dash="1 7"))
    centre = lerp(st, sb, 0.45)
    out.append(line(eye, centre, stroke=INK_SOFT, sw=1.2, dash="1 7"))
    out.append(angle_arc(eye, 150, 90, 107, value="15–20°", value_off=46))
    out.append(dimension((eye[0] + 20, eye[1] - 150), (st[0], eye[1] - 150), "ARM'S LENGTH", col=INK))
    out.append(callout(st, (R - 300, top + 36), "Top at or below eye level", num=1))
    out.append(callout(centre, (R - 300, centre[1] + 150), "Centre 15–20° below", num=2))
    return "".join(out)


def sc_chair_check(pin, top):
    out = []
    u = 118
    floor_y = ART_BOTTOM - 30
    hip = (390, floor_y - 1.9 * u - 0.2 * u)
    out.append(floor(L, R, floor_y))
    out.append(chair_side(hip, u, floor_y, lumbar=TERRA_SOFT, arm=True, recline=10, back_h=3.3))
    s, j = seated(hip, u, pose(SIT, thoracic=-6, neck=2, uarm=180, farm=92))
    out.append(s)
    out.append(callout((hip[0] - 0.62 * u, hip[1] - 0.85 * u), (L, top + 40), "Lumbar support that adjusts", num=1))
    out.append(callout((hip[0] - 1.25 * u, hip[1] - 2.6 * u), (L, top + 100), "Backrest reclines 100–110°", num=2))
    out.append(callout((hip[0] + 0.8 * u, hip[1] - 0.95 * u), (R - 300, top + 40), "Armrests at elbow height", num=3))
    out.append(callout((hip[0] + 1.55 * u, hip[1] + 0.55 * u), (R - 300, hip[1] - 20), "2–3 fingers behind knees", num=4))
    out.append(callout((hip[0] + 0.45 * u, floor_y - 0.9 * u), (R - 300, floor_y - 120), "Height lets feet rest flat", num=5))
    return "".join(out)


def sc_stand_vs_sit(pin, top):
    out = []
    floor_y = ART_BOTTOM - 150
    u = 74
    mid = W / 2
    out.append(line((mid, top + 20), (mid, floor_y + 20), sw=0.9, extra='opacity="0.45"'))
    out.append(floor(L, mid - 30, floor_y))
    out.append(floor(mid + 30, R, floor_y))
    s, j, g = seated_desk(u, L + 1.0 * u, floor_y, desk_x1=mid - 40, show_floor=False)
    out.append(s)
    hip = (mid + 1.0 * u + 30, floor_y - 3.85 * u - 0.2 * u)
    dtop = hip[1] - 0.82 * u
    out.append(desk_side(hip[0] + 1.25 * u, R, dtop, floor_y, u))
    fig, j2 = side_figure(hip, u, **pose(STAND, uarm=178, farm=97, hand=-8, fuarm=176, ffarm=97, fhand=-8))
    m, st, sb = monitor_side(hip[0] + 4.0 * u, dtop, u, j2["eye"][1] - 0.05 * u)
    out.append(m)
    out.append(keyboard_side(hip[0] + 1.5 * u, hip[0] + 2.35 * u, dtop, u))
    out.append(fig)
    out.append(caption(L, top + 36, "Sitting", "Support the lower back"))
    out.append(caption(mid + 30, top + 36, "Standing", "Stack joints, soft knees"))
    out.append(text(W / 2, floor_y + 88, "The best posture is your next posture.", size=38, family=SERIF, fill=INK,
                    anchor="middle", italic=True))
    out.append(text(W / 2, floor_y + 126, "SWITCH EVERY 30–60 MINUTES", size=14, family=MONO, fill=TERRA, anchor="middle", ls=3))
    return "".join(out)


def sc_lumbar(pin, top):
    out = []
    u = 118
    floor_y = ART_BOTTOM - 30
    hip = (390, floor_y - 1.9 * u - 0.2 * u)
    out.append(floor(L, R, floor_y))
    out.append(chair_side(hip, u, floor_y, lumbar=TERRA, back_h=3.0))
    s, j = seated(hip, u, pose(SIT, lumbar=4, thoracic=-4, uarm=180, farm=100))
    out.append(s)
    lp = (hip[0] - 0.6 * u, hip[1] - 0.75 * u)
    out.append(circle(lp, 1.1 * u, stroke=TERRA, sw=1.3))
    out.append(circle(lp, 1.1 * u + 9, stroke=TERRA, sw=0.8, extra='opacity=".5"'))
    out.append(callout((lp[0] - 1.1 * u, lp[1]), (L, top + 40), "Fills the curve of the lower back", num=1))
    out.append(callout(j["shoulder"], (R - 280, top + 40), "Shoulders settle back", num=2))
    out.append(callout((hip[0] + 0.2 * u, hip[1]), (R - 280, hip[1] - 60), "Hips all the way back", num=3))
    out.append(callout(j["toe"], (R - 280, floor_y - 60), "Feet flat", num=4))
    return "".join(out)


def sc_laptop(pin, top):
    out = []
    mid_y = (top + ART_BOTTOM) / 2
    u = 70
    f1 = mid_y - 30
    s, j, g = seated_desk(u, L + 1.1 * u, f1, pose(SLUMP, neck=58, uarm=150, farm=102), monitor=None,
                          laptop="desk", desk_x1=R - 40)
    out.append(s)
    out.append(line(j["eye"], lerp(g["laptop_hinge"], g["laptop_top"], 0.5), stroke=TERRA, sw=1.2, dash="1 6"))
    out.append(strain(j["neck"], 26))
    out.append(caption(R, top + 30, "Flat on the desk", "Eyes and head drop", anchor="end"))
    out.append(hair(mid_y + 10))
    f2 = ART_BOTTOM - 20
    s, j2, g2 = seated_desk(u, L + 1.1 * u, f2, monitor=None, laptop="stand", desk_x1=R - 40)
    out.append(s)
    out.append(line(j2["eye"], g2["laptop_top"], stroke=SAGE, sw=1.2, dash="1 6"))
    out.append(caption(R, mid_y + 60, "Raised + keyboard", "Screen near eye level", anchor="end", tag_col=SAGE))
    return "".join(out)


def sc_wall_test(pin, top):
    out = []
    u = 92
    floor_y = ART_BOTTOM - 20
    wall_x = L + 70
    out.append(rect(L, top + 10, wall_x - L, floor_y - top - 10, fill=PAPER_DEEP))
    out.append(line((wall_x, top + 10), (wall_x, floor_y), sw=1.6))
    out.append(floor(L, L + 380, floor_y))
    hip = (wall_x + 0.5 * u, floor_y - 3.85 * u - 0.2 * u)
    s, j = side_figure(hip, u, **pose(STAND, thoracic=-3, neck=5))
    out.append(s)
    for p in [(wall_x, j["head"][1] - 0.15 * u), (wall_x, j["shoulder"][1] + 0.2 * u), (wall_x, hip[1] + 0.1 * u),
              (wall_x, j["ankle"][1] + 0.1 * u)]:
        out.append(circle(p, 6, fill=TERRA))
    gy = hip[1] - 0.95 * u
    out.append(dimension((wall_x, gy), (wall_x + 0.34 * u, gy), None, col=TERRA, sw=1.3))
    x0 = 470
    for i, (h, t) in enumerate(pin["steps"]):
        yy = top + 30 + i * 205
        out.append(text(x0, yy + 20, f"STEP {i + 1:02d}", size=14, family=MONO, fill=TERRA, ls=3))
        out.append(text(x0, yy + 68, h, size=42, family=SERIF, fill=INK))
        out.append(text(x0, yy + 108, t, size=23, fill=BODY))
        out.append(hair(yy + 150, x0, R))
    return "".join(out)


def sc_chair_tips(pin, top):
    out = []
    u = 104
    floor_y = ART_BOTTOM - 30
    hip = (L + 1.05 * u, floor_y - 1.9 * u - 0.2 * u)
    out.append(floor(L, 470, floor_y))
    out.append(chair_side(hip, u, floor_y, lumbar=TERRA_SOFT, arm=True, back_h=2.9))
    s, j = seated(hip, u, pose(SIT, uarm=178, farm=92))
    out.append(s)
    x0 = 540
    for i, t in enumerate(pin["tips"]):
        yy = top + 60 + i * 166
        out.append(text(x0, yy, f"{i + 1:02d}", size=15, family=MONO, fill=TERRA, ls=2))
        words = t.split()
        out.append(text(x0, yy + 48, " ".join(words[:3]), size=36, family=SERIF, fill=INK))
        if len(words) > 3:
            out.append(text(x0, yy + 88, " ".join(words[3:]), size=36, family=SERIF, fill=INK))
        out.append(hair(yy + 118, x0, R))
    return "".join(out)


# ---- plan views
def kb_plan(x, y, w, h):
    out = [rect(x, y, w, h, rx=6, fill=PAPER, stroke=LINE, sw=1.8)]
    cols, rws = 14, 4
    kw = (w - 16) / cols
    kh = (h - 16) / rws
    for r in range(rws):
        for c in range(cols):
            out.append(rect(x + 8 + c * kw + 1.5, y + 8 + r * kh + 1.5, kw - 3, kh - 3, rx=2, stroke=LINE, sw=0.8,
                            extra='opacity=".7"'))
    return "".join(out)


def sc_topdown_setup(pin, top):
    out = []
    u = 60
    cx = W / 2
    dtop = top + 110
    dbot = dtop + 420
    out.append(rect(L + 20, dtop, R - L - 40, dbot - dtop, rx=8, fill=PAPER, stroke=LINE, sw=2))
    out.append(rect(cx - 190, dtop + 45, 380, 22, rx=4, fill=INK))
    out.append(rect(cx - 55, dtop + 67, 110, 44, rx=8, stroke=LINE, sw=1.6))
    out.append(kb_plan(cx - 160, dtop + 250, 300, 96))
    out.append(f'<ellipse cx="{fmt(cx + 200)}" cy="{fmt(dtop + 298)}" rx="24" ry="36" fill="{PAPER}" stroke="{LINE}" stroke-width="1.8"/>')
    out.append(circle((R - 110, dtop + 90), 34, stroke=LINE, sw=1.8))
    out.append(circle((R - 110, dtop + 90), 10, fill=TERRA))
    for a in range(0, 360, 45):
        p = add((L + 110, dtop + 95), a, 26)
        out.append(circle(p, 16, fill=SAGE_SOFT, stroke=SAGE, sw=1.4))
    out.append(circle((R - 120, dtop + 300), 22, stroke=LINE, sw=1.8))
    out.append(rect(cx - 90, dbot + 70, 180, 150, rx=40, fill=PAPER, stroke=LINE, sw=2))
    out.append(path(f"M{fmt(cx - 105)},{fmt(dbot + 225)} Q{fmt(cx)},{fmt(dbot + 265)} {fmt(cx + 105)},{fmt(dbot + 225)}", stroke=LINE, sw=10))
    out.append(top_figure((cx, dbot + 95), u, arms_to=[(cx - 70, dtop + 330), (cx + 200, dtop + 330)]))
    out.append(dimension((R - 30, dtop + 56), (R - 30, dbot + 70), "ARM'S LENGTH", text_side=1))
    out.append(callout((cx - 190, dtop + 56), (L, top + 40), "Monitor centred", num=1))
    out.append(callout((R - 110, dtop + 90), (R - 320, top + 40), "Light from the side", num=2))
    out.append(callout((cx - 160, dtop + 330), (L, dbot + 120), "Keyboard in line", num=3))
    out.append(callout((cx + 200, dtop + 334), (R - 290, dbot + 120), "Mouse close by", num=4))
    out.append(callout((cx, dbot + 225), (L, ART_BOTTOM - 20), "Chair tucked in", num=5))
    return "".join(out)


def sc_topdown_keyboard(pin, top):
    out = []
    u = 78
    cx = W / 2
    dtop = top + 90
    dbot = dtop + 460
    out.append(rect(L + 20, dtop, R - L - 40, dbot - dtop, rx=8, fill=PAPER, stroke=LINE, sw=2))
    out.append(kb_plan(cx - 190, dtop + 250, 340, 110))
    mouse = (cx + 215, dtop + 305)
    out.append(f'<ellipse cx="{fmt(mouse[0])}" cy="{fmt(mouse[1])}" rx="26" ry="40" fill="{PAPER}" stroke="{LINE}" stroke-width="1.8"/>')
    out.append(rect(cx - 190, dtop + 372, 340, 36, rx=18, fill=TERRA_SOFT))
    hc = (cx, dbot + 150)
    out.append(top_figure(hc, u, arms_to=[(cx - 80, dtop + 340), (mouse[0], mouse[1] + 30)]))
    out.append(line((cx - 20, dtop + 30), (cx - 20, hc[1] - 60), stroke=TERRA, sw=1.3, dash="3 6"))
    out.append(callout((cx - 20, dtop + 60), (L, top + 40), "Centre it on your body", num=1))
    out.append(callout((mouse[0], mouse[1] - 40), (R - 290, top + 40), "Mouse right beside it", num=2))
    out.append(callout((cx - 190, dtop + 390), (L, dbot + 60), "Wrists straight", num=3))
    out.append(callout((cx - 1.0 * u, hc[1] - 0.5 * u), (L, ART_BOTTOM - 20), "Elbows by your sides", num=4))
    out.append(callout((cx + 1.0 * u, hc[1] + 0.3 * u), (R - 270, ART_BOTTOM - 20), "Shoulders relaxed", num=5))
    return "".join(out)


def sc_flatlay(pin, top):
    out = []
    items = pin["items"]
    cols, rws = 2, 3
    cw = (R - L) / cols
    rh = (ART_BOTTOM - top - 10) / rws
    out.append(line((L + cw, top + 10), (L + cw, ART_BOTTOM), sw=0.9, extra='opacity="0.45"'))
    for i in range(1, rws):
        out.append(hair(top + 10 + rh * i))
    for i, (kind, lab) in enumerate(items):
        r, c = divmod(i, cols)
        x0 = L + c * cw
        y0 = top + 10 + r * rh
        cc = (x0 + cw / 2, y0 + rh / 2 - 6)
        if kind == "lumbar":
            out.append(f'<ellipse cx="{fmt(cc[0])}" cy="{fmt(cc[1])}" rx="118" ry="62" fill="{TERRA}"/>')
            out.append(path(f"M{fmt(cc[0]-118)},{fmt(cc[1])} C{fmt(cc[0]-60)},{fmt(cc[1]-28)} {fmt(cc[0]+60)},{fmt(cc[1]-28)} {fmt(cc[0]+118)},{fmt(cc[1])}",
                            stroke=PAPER, sw=1.2, extra='opacity=".5"'))
            out.append(line((cc[0] - 175, cc[1]), (cc[0] - 118, cc[1]), sw=2.4))
            out.append(line((cc[0] + 118, cc[1]), (cc[0] + 175, cc[1]), sw=2.4))
        elif kind == "laptop_stand":
            out.append(rect(cc[0] - 130, cc[1] - 70, 260, 140, rx=10, stroke=LINE, sw=2))
            out.append(rect(cc[0] - 110, cc[1] - 52, 220, 104, rx=6, fill=INK))
        elif kind == "footrest":
            out.append(rect(cc[0] - 150, cc[1] - 55, 300, 110, rx=40, fill=PAPER, stroke=LINE, sw=2))
            for q in range(-4, 5):
                out.append(circle((cc[0] + q * 28, cc[1]), 4, fill=INK_SOFT))
        elif kind == "wrist_rest":
            out.append(kb_plan(cc[0] - 150, cc[1] - 70, 300, 80))
            out.append(rect(cc[0] - 150, cc[1] + 24, 300, 34, rx=17, fill=INK))
        elif kind == "timer":
            out.append(circle(cc, 70, fill=PAPER, stroke=LINE, sw=2))
            e = add(cc, 110, 58)
            out.append(path(f"M{fmt(cc[0])},{fmt(cc[1])} L{fmt(cc[0])},{fmt(cc[1]-58)} A58,58 0 0 1 {fmt(e[0])},{fmt(e[1])}Z", fill=TERRA))
            for a in range(0, 360, 30):
                out.append(line(add(cc, a, 62), add(cc, a, 68), sw=1.4))
        elif kind == "band":
            out.append(f'<ellipse cx="{fmt(cc[0])}" cy="{fmt(cc[1])}" rx="130" ry="58" fill="none" stroke="{TERRA}" stroke-width="16"/>')
            out.append(f'<ellipse cx="{fmt(cc[0] + 16)}" cy="{fmt(cc[1] + 8)}" rx="104" ry="44" fill="none" stroke="{SAGE}" stroke-width="12"/>')
        out.append(text(x0 + (0 if c == 0 else 24), y0 + 36, f"{i + 1:02d}", size=15, family=MONO, fill=TERRA, ls=2))
        out.append(text(cc[0], y0 + rh - 26, lab, size=32, family=SERIF, fill=INK, anchor="middle"))
    return "".join(out)


def sc_home(pin, top):
    out = []
    u = 92
    floor_y = ART_BOTTOM - 250
    wx, wy = R - 300, top + 20
    out.append(rect(wx, wy, 250, 220, rx=4, stroke=LINE, sw=2))
    out.append(line((wx + 125, wy), (wx + 125, wy + 220), sw=1.4))
    out.append(line((wx, wy + 110), (wx + 250, wy + 110), sw=1.4))
    out.append(path(f"M{fmt(wx + 20)},{fmt(wy + 200)} q30,-40 60,-10 q30,-50 70,-20", stroke=SAGE, sw=1.4))
    out.append(rect(L + 20, top + 50, 120, 150, rx=2, stroke=LINE, sw=1.6))
    out.append(circle((L + 80, top + 110), 32, fill=TERRA_SOFT))
    s, j, g = seated_desk(u, L + 1.25 * u, floor_y, monitor=None, laptop="stand")
    out.append(s)
    px = g["dx1"] - 0.6 * u
    base = (px, g["desk_top"] - 52)
    out.append(rect(px - 22, g["desk_top"] - 52, 44, 52, rx=6, stroke=LINE, sw=2))
    for a in (-35, -5, 25):
        tip = add(base, a, 70)
        mid = add(lerp(base, tip, 0.5), a + 90, 12)
        out.append(path(smooth_closed([base, mid, tip, add(lerp(base, tip, 0.5), a - 90, 12)]), fill=SAGE_SOFT, stroke=SAGE, sw=1.2))
    out.append(rows(L, floor_y + 60, R - L, pin["tips"], gap=50, size=23, two_col=True))
    return "".join(out)


def sc_tall(pin, top):
    out = []
    u = 96
    floor_y = ART_BOTTOM - 30
    s, j, g = seated_desk(u, 290, floor_y, legs=1.16, desk_raise=-0.25)
    out.append(s)
    st = g["screen_top"]
    out.append(line(j["eye"], (st[0], j["eye"][1]), stroke=TERRA, sw=1.2, dash="1 7"))
    rx = L + 6
    out.append(line((rx, j["top"]), (rx, floor_y), sw=1.2))
    for k in range(13):
        yy = floor_y - k * (floor_y - j["top"]) / 12
        out.append(line((rx, yy), (rx + (14 if k % 2 == 0 else 8), yy), sw=1.2))
    out.append(callout(st, (R - 280, top + 36), "Raise the monitor", num=1))
    out.append(callout((g["dx0"] + 40, g["desk_top"]), (R - 280, g["desk_top"] - 110), "Higher work surface", num=2))
    out.append(callout((j["hip"][0] + 1.0 * u, j["hip"][1] + 0.4 * u), (R - 300, g["desk_top"] + 190), "Deeper seat, long thighs", num=3))
    out.append(callout(j["knee"], (R - 280, floor_y - 50), "Knees ~90°, feet flat", num=4))
    return "".join(out)


def sc_student(pin, top):
    out = []
    u = 92
    floor_y = ART_BOTTOM - 250
    s, j, g = seated_desk(u, L + 1.25 * u, floor_y, pose(SIT, uarm=172, farm=100), monitor=None, book=True,
                          lamp=True, footrest=True)
    out.append(s)
    out.append(callout((g["hip"][0] + 2.9 * u, g["desk_top"] - 1.25 * u), (R - 260, top + 36), "Prop books up", num=1))
    out.append(callout((g["hip"][0] + 2.3 * u, floor_y - 0.3 * u), (R - 290, floor_y - 0.9 * u), "Footrest if feet dangle", num=2))
    out.append(rows(L, floor_y + 60, R - L, pin["tips"], gap=50, size=23, two_col=True))
    return "".join(out)


def sc_wrist(pin, top):
    out = []
    mid_y = (top + ART_BOTTOM) / 2
    for good, (y0, y1) in ((False, (top, mid_y - 10)), (True, (mid_y + 10, ART_BOTTOM))):
        u = 100
        desk_y = y1 - 90
        out.append(line((L, desk_y), (R, desk_y), sw=2))
        out.append(line((L, desk_y + 16), (R, desk_y + 16), sw=1, extra='opacity=".5"'))
        ex = L + 110
        if good:
            elbow = (ex, desk_y - 1.0 * u)
            wrist = (ex + 4.0 * u, desk_y - 0.55 * u)
            knuckle = (wrist[0] + 0.95 * u, wrist[1] + 0.05 * u)
            tip = (knuckle[0] + 0.42 * u, knuckle[1] + 0.3 * u)
            out.append(rect(wrist[0] - 0.05 * u, desk_y - 0.26 * u, 1.9 * u, 0.26 * u, rx=4, fill=PAPER, stroke=LINE, sw=2))
            out.append(rect(wrist[0] - 1.3 * u, desk_y - 0.18 * u, 1.2 * u, 0.18 * u, rx=0.09 * u, fill=TERRA_SOFT))
        else:
            elbow = (ex, desk_y - 0.3 * u)
            wrist = (ex + 4.0 * u, desk_y - 0.26 * u)
            knuckle = (wrist[0] + 0.8 * u, wrist[1] - 0.6 * u)
            tip = (knuckle[0] + 0.45 * u, knuckle[1] + 0.4 * u)
            out.append(path(f"M{fmt(wrist[0] + 0.15*u)},{fmt(desk_y)} L{fmt(wrist[0] + 2.1*u)},{fmt(desk_y)} "
                            f"L{fmt(wrist[0] + 2.1*u)},{fmt(desk_y - 0.65*u)} L{fmt(wrist[0] + 0.15*u)},{fmt(desk_y - 0.26*u)}Z",
                            fill=PAPER, stroke=LINE, sw=2))
        out.append(path(capsule((elbow[0] - 0.9 * u, elbow[1] - 0.35 * u), 0.3 * u, elbow, 0.26 * u), fill=INK))
        out.append(path(capsule(elbow, 0.25 * u, wrist, 0.15 * u), fill=INK))
        out.append(path(capsule(wrist, 0.16 * u, knuckle, 0.14 * u), fill=INK))
        out.append(path(capsule(knuckle, 0.12 * u, tip, 0.07 * u), fill=INK))
        dx, dy = wrist[0] - elbow[0], wrist[1] - elbow[1]
        out.append(line(elbow, (wrist[0] + dx * 0.4, wrist[1] + dy * 0.4), stroke=SAGE if good else TERRA, sw=1.3, dash="3 6"))
        if not good:
            out.append(strain(wrist, 34))
        out.append(caption(L, y0 + 44, "Neutral" if good else "Extended",
                           "Forearm and hand in one line" if good else "Keyboard tilted, wrist cocked up",
                           tag_col=SAGE if good else TERRA))
    out.append(hair(mid_y))
    return "".join(out)


def sc_doorway(pin, top):
    out = []
    u = 90
    floor_y = ART_BOTTOM - 250
    cx = W / 2 - 20
    fx = cx - 1.45 * u
    out.append(rect(L, top + 10, fx - L - 18, floor_y - top - 10, fill=PAPER_DEEP))
    out.append(rect(fx - 18, top + 10, 30, floor_y - top - 10, fill=PAPER, stroke=LINE, sw=2))
    out.append(floor(L, R, floor_y))
    s, j = standing(cx, floor_y, u, pose(STAND, lumbar=8, thoracic=6, neck=4, thigh=196, shin=184, fthigh=160, fshin=182,
                                         uarm=262, farm=2, hand=0, fuarm=262, ffarm=2, fhand=0))
    out.append(s)
    c = (j["chest"][0] + 40, j["chest"][1])
    out.append(arrow(c, (c[0] + 110, c[1])))
    out.append(callout(j["hand"], (R - 320, top + 40), "Forearms on the frame", num=1))
    out.append(callout(j["chest"], (R - 320, c[1] + 110), "Lean the chest through", num=2))
    out.append(text(L, floor_y + 70, "PAIR IT WITH", size=14, family=MONO, fill=TERRA, ls=3))
    out.append(rows(L, floor_y + 88, R - L, pin["tips"], gap=52, size=24, two_col=True))
    return "".join(out)


SCENES = {
    "desk_guide": sc_desk_guide, "signs": sc_signs, "forward_head": sc_forward_head,
    "exercise_grid": sc_exercise_grid, "pain": sc_pain, "headache": sc_headache, "timeline": sc_timeline,
    "before_after": sc_before_after, "phone": sc_phone, "monitor_height": sc_monitor_height, "chair_check": sc_chair_check,
    "stand_vs_sit": sc_stand_vs_sit, "lumbar": sc_lumbar, "laptop": sc_laptop, "wall_test": sc_wall_test,
    "chair_tips": sc_chair_tips, "topdown_setup": sc_topdown_setup, "topdown_keyboard": sc_topdown_keyboard,
    "flatlay": sc_flatlay, "home": sc_home, "tall": sc_tall, "student": sc_student, "wrist": sc_wrist,
    "doorway": sc_doorway,
}
