"""Batch 2 scenes: chairs and desk setup (the best-performing topic)."""

import math

from plate import ART_BOTTOM, W
from scenes import (L, R, SIT, STAND, caption, desk_side, floor, hair, inline_list, keyboard_side, kb_plan, pose,
                    rows, seated, seated_desk, standing)
from svgkit import (INK, INK_SOFT, LINE, MONO, PAPER, PAPER_DEEP, SAGE, SAGE_SOFT, SERIF, TERRA, TERRA_SOFT, add,
                    angle_arc, callout, chair_side, check, circle, cross, dimension, fmt, line, marker, monitor_side,
                    path, polyline, rect, smooth_open, strain, text, top_figure)


def _chair_anchors(hip, u, floor_y, j):
    return dict(
        lumbar=(hip[0] - 0.62 * u, hip[1] - 0.85 * u),
        backrest=(hip[0] - 1.2 * u, hip[1] - 2.4 * u),
        armrest=(hip[0] + 0.8 * u, hip[1] - 0.95 * u),
        seat=(hip[0] + 0.9 * u, hip[1] + 0.5 * u),
        seat_front=(hip[0] + 1.55 * u, hip[1] + 0.55 * u),
        gas=(hip[0] + 0.45 * u, floor_y - 0.9 * u),
        knee=j["knee"], toe=j["toe"], elbow=j["elbow"], ear=j["ear"], shoulder=j["shoulder"],
        hip=(hip[0] + 0.1 * u, hip[1]), back=j["back"],
    )


def sc_chair_annot(pin, top):
    """Seated figure on an office chair with configurable callouts and dimensions."""
    out = []
    zoom = pin.get("zoom")
    u = 170 if zoom else 118
    floor_y = ART_BOTTOM - 30
    hip = (pin.get("hip_x", 390 if not zoom else 330), floor_y - 1.9 * u - 0.2 * u)
    if zoom:
        out.append(f'<defs><clipPath id="artclip"><rect x="{L}" y="{top + 150}" width="{R - L}" height="{ART_BOTTOM - top - 150}"/></clipPath></defs><g clip-path="url(#artclip)">')
    out.append(floor(L, R, floor_y))
    if pin.get("chair") == "dining":
        out.append(_dining_chair(hip, u, floor_y))
        sy = hip[1] + 0.42 * u
        out.append(rect(hip[0] - 0.7 * u, sy - 0.22 * u, 1.9 * u, 0.24 * u, rx=0.1 * u, fill=SAGE_SOFT, stroke=SAGE, sw=1.6))
        out.append(f'<ellipse cx="{fmt(hip[0] - 0.6 * u)}" cy="{fmt(hip[1] - 0.8 * u)}" rx="{fmt(0.2 * u)}" ry="{fmt(0.42 * u)}" fill="{TERRA}"/>')
    else:
        out.append(chair_side(hip, u, floor_y, lumbar=pin.get("lumbar_col", TERRA_SOFT), arm=pin.get("arm", True),
                              recline=pin.get("recline", 8), back_h=3.2))
    s, j = seated(hip, u, pose(SIT, **dict(dict(thoracic=-4, neck=3, uarm=180, farm=92), **pin.get("pose", {}))))
    out.append(s)
    a = _chair_anchors(hip, u, floor_y, j)
    if "recline" in pin:  # follow the reclined backrest instead of the default offsets
        from svgkit import add, lerp
        rc = pin["recline"]
        b0 = (hip[0] - 0.78 * u, hip[1] + 0.24 * u)
        b1 = add(b0, -rc, 3.2 * u)
        a["backrest"] = lerp(b0, b1, 0.8)
        a["lumbar"] = add(lerp(b0, b1, 0.22), 90, 0.22 * u)
        a["arc"] = add((hip[0] - 0.7 * u, hip[1] + 0.3 * u), (90 - rc) / 2, 1.15 * u)
    for d in pin.get("dims", []):
        if d == "seat_height":
            x = hip[0] + 3.0 * u
            sy = hip[1] + 0.42 * u
            out.append(line((hip[0] + 1.6 * u, sy), (x + 10, sy), stroke=TERRA, sw=1.1, dash="3 5"))
            out.append(dimension((x, floor_y), (x, sy), "KNEE HEIGHT", col=TERRA, text_side=1))
        elif d == "knee":
            out.append(angle_arc(j["knee"], 0.45 * u, 180, 270))
        elif d == "seat_depth":
            y = hip[1] + 0.95 * u
            out.append(dimension((hip[0] + 1.55 * u, y), (j["knee"][0] - 0.05 * u, y), "2–3 FINGERS", col=TERRA))
        elif d == "recline":
            rc = pin.get("recline", 8)
            c = (hip[0] - 0.7 * u, hip[1] + 0.3 * u)
            out.append(line(c, (c[0] + 1.9 * u, c[1]), stroke=TERRA, sw=1.1, dash="3 5"))
            out.append(angle_arc(c, 1.15 * u, -rc, 90, value=pin.get("recline_label")))
        elif d == "elbow_line":
            out.append(line((j["elbow"][0] - 0.6 * u, j["elbow"][1]), (hip[0] + 1.6 * u, j["elbow"][1]),
                            stroke=TERRA, sw=1.2, dash="3 5"))
        elif d == "belt_line":
            y = a["lumbar"][1]
            out.append(line((L, y), (hip[0] + 1.2 * u, y), stroke=TERRA, sw=1.2, dash="3 5"))
            out.append(text(L, y - 12, "BELT LINE", size=14, family=MONO, fill=TERRA, ls=3))
        elif d == "lumbar_ring":
            c = a["lumbar"]
            out.append(circle((c[0] + 0.15 * u, c[1]), 0.9 * u, stroke=TERRA, sw=1.3))
    if zoom:
        out.append("</g>")
    for i, (anchor, txt, side, dy) in enumerate(pin["callouts"]):
        p = a[anchor]
        lp = (L, top + dy) if side == "L" else (R - 300, top + dy)
        out.append(callout(p, lp, txt, num=i + 1 if pin.get("numbered", True) else None))
    return "".join(out)


def _gaming_chair(hip, u, floor_y):
    """Racing-style gaming chair in elevation (back on the left)."""
    out = []
    sy = hip[1] + 0.42 * u
    out.append(rect(hip[0] - 0.7 * u, sy, 2.3 * u, 0.32 * u, rx=0.14 * u, fill=PAPER, stroke=LINE, sw=2))
    # bucket bolster
    out.append(path(f"M{fmt(hip[0] - 0.6*u)},{fmt(sy)} Q{fmt(hip[0] + 0.5*u)},{fmt(sy - 0.45*u)} {fmt(hip[0] + 1.5*u)},{fmt(sy)}",
                    stroke=LINE, sw=2))
    bx = hip[0] - 0.85 * u
    pts = [(bx + 0.1 * u, sy), (bx - 0.25 * u, sy - 1.6 * u), (bx - 0.35 * u, sy - 3.3 * u), (bx - 0.15 * u, sy - 4.0 * u)]
    out.append(path(smooth_open(pts), stroke=LINE, sw=0.5 * u))
    out.append(path(smooth_open(pts), stroke=PAPER, sw=0.5 * u - 4))
    # side wing line
    out.append(path(smooth_open([(bx + 0.25 * u, sy - 0.2 * u), (bx + 0.05 * u, sy - 1.6 * u), (bx + 0.05 * u, sy - 2.9 * u)]), stroke=LINE, sw=1.4))
    # pillows
    out.append(f'<ellipse cx="{fmt(bx + 0.05*u)}" cy="{fmt(sy - 3.45*u)}" rx="{fmt(0.22*u)}" ry="{fmt(0.32*u)}" fill="{TERRA_SOFT}" stroke="{LINE}" stroke-width="1.6"/>')
    out.append(f'<ellipse cx="{fmt(bx + 0.18*u)}" cy="{fmt(sy - 0.95*u)}" rx="{fmt(0.24*u)}" ry="{fmt(0.38*u)}" fill="{TERRA_SOFT}" stroke="{LINE}" stroke-width="1.6"/>')
    # armrest
    ay = hip[1] - 0.95 * u
    out.append(line((hip[0] + 0.05 * u, ay), (hip[0] + 1.1 * u, ay), sw=0.14 * u))
    out.append(line((hip[0] + 0.3 * u, ay), (hip[0] + 0.3 * u, sy), sw=2))
    cx = hip[0] + 0.45 * u
    out.append(line((cx, sy + 0.32 * u), (cx, floor_y - 0.5 * u), sw=0.1 * u))
    out.append(path(f"M{fmt(cx - 0.95*u)},{fmt(floor_y - 0.2*u)} Q{fmt(cx)},{fmt(floor_y - 0.62*u)} {fmt(cx + 0.95*u)},{fmt(floor_y - 0.2*u)}", stroke=LINE, sw=2))
    for x in (cx - 0.95 * u, cx + 0.95 * u):
        out.append(circle((x, floor_y - 0.1 * u), 0.1 * u, fill=PAPER, stroke=LINE, sw=2))
    return "".join(out)


def _dining_chair(hip, u, floor_y):
    """Plain four-legged dining chair in elevation (back on the left)."""
    out = []
    sy = hip[1] + 0.42 * u
    x0, x1 = hip[0] - 0.75 * u, hip[0] + 1.25 * u
    out.append(rect(x0, sy, x1 - x0, 0.16 * u, rx=3, fill=PAPER, stroke=LINE, sw=2))
    out.append(line((x0 + 0.08 * u, sy + 0.16 * u), (x0 + 0.08 * u, floor_y), sw=0.1 * u))
    out.append(line((x1 - 0.1 * u, sy + 0.16 * u), (x1 - 0.1 * u, floor_y), sw=0.1 * u))
    out.append(line((x0 + 0.08 * u, sy + 0.9 * u), (x1 - 0.1 * u, sy + 0.9 * u), sw=1.6))
    out.append(line((x0 + 0.04 * u, sy), (x0 - 0.06 * u, sy - 2.3 * u), sw=0.1 * u))
    for k in (0.7, 1.4, 2.1):
        out.append(line((x0 - 0.0 * u - k * 0.04 * u, sy - k * u), (x0 + 0.2 * u - k * 0.04 * u, sy - k * u), sw=0.08 * u))
    return "".join(out)


def sc_chair_compare(pin, top):
    out = []
    u = 78
    floor_y = top + 600
    mid = W / 2
    out.append(line((mid, top + 10), (mid, ART_BOTTOM - 100), sw=0.9, extra='opacity="0.45"'))
    (lt, ls), (rt, rs) = pin.get("sides", (("Ergonomic chair", "Built to adjust to you"), ("Gaming chair", "Built for the look")))
    out.append(caption(L, top + 36, lt, ls, tag_col=SAGE))
    out.append(caption(mid + 30, top + 36, rt, rs, tag_col=TERRA))
    out.append(floor(L, mid - 30, floor_y))
    out.append(floor(mid + 30, R, floor_y))
    hip1 = (L + 1.6 * u, floor_y - 2.1 * u)
    out.append(chair_side(hip1, u, floor_y, lumbar=SAGE_SOFT, arm=True, recline=6, back_h=3.0))
    # mesh hatch on the ergonomic backrest
    for k in range(5):
        y = hip1[1] - 0.6 * u - k * 0.45 * u
        out.append(line((hip1[0] - 1.0 * u, y), (hip1[0] - 0.65 * u, y - 0.12 * u), sw=0.9, extra='opacity=".5"'))
    hip2 = (mid + 30 + 1.8 * u, floor_y - 2.1 * u)
    if pin.get("right") == "dining":
        out.append(_dining_chair(hip2, u, floor_y))
    elif pin.get("right") == "basic":
        out.append(chair_side(hip2, u, floor_y, recline=1, back_h=2.1))
    else:
        out.append(_gaming_chair(hip2, u, floor_y))
    y0 = floor_y + 60
    for i, (good_txt, bad_txt) in enumerate(pin["compare"]):
        yy = y0 + i * 70
        out.append(check((L + 14, yy - 8), r=12))
        out.append(text(L + 40, yy, good_txt, size=23, fill=INK))
        out.append(cross((mid + 44, yy - 8), r=12))
        out.append(text(mid + 70, yy, bad_txt, size=23, fill=INK))
        out.append(hair(yy + 26, L, R, 0.35))
    out.append(text(W / 2, ART_BOTTOM - 40, pin["verdict"], size=34, family=SERIF, fill=INK, anchor="middle", italic=True))
    return "".join(out)


def _arm_monitor(desk_x1, desk_top, u, screen_top, x):
    """Monitor on a clamp-mounted arm. Returns svg and screen top point."""
    out = []
    cx = desk_x1 - 0.25 * u
    out.append(rect(cx - 0.18 * u, desk_top - 0.05 * u, 0.36 * u, 0.4 * u, rx=4, fill=PAPER, stroke=LINE, sw=2))
    pole_top = (cx, screen_top - 0.1 * u)
    out.append(line((cx, desk_top), pole_top, sw=0.12 * u))
    j1 = (cx - 0.9 * u, screen_top + 0.35 * u)
    out.append(polyline([pole_top, j1, (x + 0.25 * u, screen_top + 0.8 * u)], sw=0.1 * u))
    for p in (pole_top, j1):
        out.append(circle(p, 0.09 * u, fill=PAPER, stroke=LINE, sw=2))
    out.append(rect(x - 0.05 * u, screen_top, 0.1 * u, 1.6 * u, rx=0.03 * u, fill=PAPER, stroke=LINE, sw=2))
    return "".join(out), (x - 0.05 * u, screen_top)


def sc_monitor_arm(pin, top):
    out = []
    mid_y = (top + ART_BOTTOM) / 2
    u = 72
    f1 = mid_y - 30
    p_low = pose(SIT, lumbar=-6, thoracic=18, neck=46, head=6)
    s, j, g = seated_desk(u, L + 1.1 * u, f1, p_low, monitor="low", desk_x1=R - 40)
    out.append(s)
    out.append(strain(j["neck"], 26))
    out.append(line(j["eye"], g["screen_top"], stroke=TERRA, sw=1.2, dash="1 6"))
    out.append(caption(R, top + 30, "Monitor on its stand", "Screen sits too low", anchor="end"))
    out.append(hair(mid_y + 10))
    f2 = ART_BOTTOM - 20
    s, j2, g2 = seated_desk(u, L + 1.1 * u, f2, monitor=None, desk_x1=R - 40)
    out.append(s)
    arm, st = _arm_monitor(g2["dx1"], g2["desk_top"], u, j2["eye"][1] - 0.05 * u, g2["hip"][0] + 4.0 * u)
    out.append(arm)
    out.append(keyboard_side(g2["hip"][0] + 1.5 * u, g2["hip"][0] + 2.35 * u, g2["desk_top"], u))
    out.append(line(j2["eye"], st, stroke=SAGE, sw=1.2, dash="1 6"))
    out.append(caption(R - 90, g2["desk_top"] + 90, "On a monitor arm", "Raised to eye level", anchor="end", tag_col=SAGE))
    return "".join(out)


def _rot_rect(cx, cy, w, h, ang):
    a = math.radians(ang)
    pts = []
    for dx, dy in ((-w / 2, -h / 2), (w / 2, -h / 2), (w / 2, h / 2), (-w / 2, h / 2)):
        pts.append((cx + dx * math.cos(a) - dy * math.sin(a), cy + dx * math.sin(a) + dy * math.cos(a)))
    return "M" + " L".join(f"{fmt(x)},{fmt(y)}" for x, y in pts) + "Z"


def sc_dual_monitor(pin, top):
    out = []
    u = 66
    cx = W / 2
    dtop = top + 120
    dbot = dtop + 430
    out.append(rect(L + 10, dtop, R - L - 20, dbot - dtop, rx=8, fill=PAPER, stroke=LINE, sw=2))
    # primary straight ahead, secondary angled
    out.append(path(_rot_rect(cx - 30, dtop + 70, 330, 22, 0), fill=INK))
    out.append(path(_rot_rect(cx + 240, dtop + 105, 260, 22, 26), fill=INK))
    out.append(rect(cx - 85, dtop + 82, 110, 40, rx=8, stroke=LINE, sw=1.6))
    out.append(kb_plan(cx - 190, dtop + 270, 300, 96))
    out.append(f'<ellipse cx="{fmt(cx + 160)}" cy="{fmt(dtop + 318)}" rx="24" ry="36" fill="{PAPER}" stroke="{LINE}" stroke-width="1.8"/>')
    hc = (cx - 40, dbot + 110)
    out.append(top_figure(hc, u, arms_to=[(cx - 120, dtop + 350), (cx + 160, dtop + 350)]))
    out.append(line((cx - 40, dtop + 85), (cx - 40, hc[1] - 50), stroke=TERRA, sw=1.3, dash="3 6"))
    out.append(callout((cx - 195, dtop + 70), (L, top + 40), "Main screen straight ahead", num=1))
    out.append(callout((cx + 340, dtop + 155), (R - 290, top + 40), "Second screen angled in", num=2))
    out.append(callout((cx - 190, dtop + 340), (L, dbot + 70), "Keyboard centred on main", num=3))
    out.append(rows(L, ART_BOTTOM - 150, R - L, pin["tips"], gap=48, size=22, two_col=True))
    return "".join(out)


def sc_standing_height(pin, top):
    out = []
    u = 96
    floor_y = ART_BOTTOM - 40
    cx = L + 1.7 * u
    hip = (cx, floor_y - 3.85 * u - 0.2 * u)
    dtop = hip[1] - 0.82 * u
    out.append(floor(L, R, floor_y))
    out.append(rect(cx - 0.9 * u, floor_y - 0.12 * u, 2.2 * u, 0.12 * u, rx=4, fill=SAGE_SOFT))
    out.append(desk_side(cx + 1.25 * u, R - 20, dtop, floor_y, u))
    out.append(line((R - 0.6 * u, dtop + 0.16 * u), (R - 0.6 * u, floor_y), sw=0.22 * u))
    from svgkit import side_figure
    s, j = side_figure(hip, u, **pose(STAND, uarm=178, farm=97, hand=-8, fuarm=176, ffarm=97, fhand=-8))
    m, st, sb = monitor_side(cx + 4.0 * u, dtop, u, j["eye"][1] - 0.05 * u)
    out.append(m)
    out.append(keyboard_side(cx + 1.5 * u, cx + 2.35 * u, dtop, u))
    out.append(s)
    out.append(line(j["eye"], st, stroke=TERRA, sw=1.2, dash="1 7"))
    out.append(line(j["elbow"], (cx + 1.3 * u, j["elbow"][1]), stroke=TERRA, sw=1.2, dash="3 5"))
    out.append(dimension((cx + 3.2 * u, floor_y), (cx + 3.2 * u, dtop), "ELBOW HEIGHT", col=TERRA, text_side=1))
    out.append(callout(st, (R - 290, top + 40), "Screen top at eye level", num=1))
    out.append(callout(j["elbow"], (R - 290, top + 110), "Desk at elbow height", num=2))
    out.append(callout(j["knee"], (R - 290, j["knee"][1] - 40), "Soft knees, weight even", num=3))
    out.append(callout((cx + 0.5 * u, floor_y - 0.08 * u), (R - 290, floor_y - 90), "Cushioned mat underfoot", num=4))
    return "".join(out)


def sc_converter_vs_desk(pin, top):
    out = []
    floor_y = ART_BOTTOM - 150
    u = 64
    mid = W / 2
    out.append(line((mid, top + 20), (mid, floor_y + 20), sw=0.9, extra='opacity="0.45"'))
    from svgkit import side_figure
    for k, (x0, x1) in enumerate(((L, mid - 30), (mid + 30, R))):
        out.append(floor(x0, x1, floor_y))
        hip = (x0 + 1.1 * u, floor_y - 3.85 * u - 0.2 * u)
        work = hip[1] - 0.82 * u
        s, j = side_figure(hip, u, **pose(STAND, uarm=178, farm=97, hand=-8, fuarm=176, ffarm=97, fhand=-8))
        if k == 0:
            dtop = floor_y - 2.45 * u  # regular desk height
            out.append(desk_side(hip[0] + 1.3 * u, x1, dtop, floor_y, u))
            # converter platform: keyboard tray + upper deck on scissor legs
            out.append(rect(hip[0] + 1.25 * u, work, 2.6 * u, 0.12 * u, rx=3, fill=PAPER, stroke=LINE, sw=2))
            out.append(polyline([(hip[0] + 2.2 * u, dtop), (hip[0] + 3.4 * u, work), ], sw=2))
            out.append(polyline([(hip[0] + 3.4 * u, dtop), (hip[0] + 2.2 * u, work)], sw=2))
            m, st, sb = monitor_side(hip[0] + 3.3 * u, work, u, j["eye"][1] - 0.05 * u)
        else:
            out.append(desk_side(hip[0] + 1.25 * u, x1, work, floor_y, u))
            out.append(line((x1 - 0.5 * u, work + 0.16 * u), (x1 - 0.5 * u, floor_y), sw=0.22 * u))
            m, st, sb = monitor_side(hip[0] + 3.3 * u, work, u, j["eye"][1] - 0.05 * u)
        out.append(m)
        out.append(keyboard_side(hip[0] + 1.45 * u, hip[0] + 2.25 * u, work, u))
        out.append(s)
    out.append(caption(L, top + 36, "Desk converter", "Sits on the desk you have"))
    out.append(caption(mid + 30, top + 36, "Standing desk", "The whole surface moves", tag_col=SAGE))
    y0 = floor_y + 56
    for i, (a, b) in enumerate(pin["compare"]):
        yy = y0 + i * 40
        out.append(text(L, yy, "· " + a, size=21, fill=INK))
        out.append(text(mid + 30, yy, "· " + b, size=21, fill=INK))
    return "".join(out)


def sc_essentials(pin, top):
    """Flat lay of setup essentials, extends the batch-1 flat lay with new items."""
    from scenes import sc_flatlay
    return sc_flatlay(pin, top)


SCENES2 = {
    "chair_annot": sc_chair_annot, "chair_compare": sc_chair_compare, "monitor_arm": sc_monitor_arm,
    "dual_monitor": sc_dual_monitor, "standing_height": sc_standing_height,
    "converter_vs_desk": sc_converter_vs_desk, "essentials": sc_essentials,
}
