"""Batch 3 scenes: quick setup fixes and accessories."""

from plate import ART_BOTTOM, W
from scenes import (BODY, L, R, SIT, STAND, STAND_BAD, caption, desk_side, floor, hair, keyboard_side, pose, seated)
from scenes2 import _arm_monitor
from svgkit import (INK, LINE, MONO, PAPER, SAGE, SAGE_SOFT, SERIF, TERRA, TERRA_SOFT, angle_arc, callout,
                    capsule, chair_side, check, circle, cross, dimension, fmt, line, monitor_side, path, rect,
                    side_figure, strain, text)


def _rig(u, hipx, floor_y, lift=0.0, legs=1.0, desk_top=None, p=SIT, footrest=False, desk_x1=None, screen_low=False):
    """Seated at a desk where chair height, leg length and desk height vary independently."""
    out = [floor(L, R, floor_y)]
    hip = (hipx, floor_y - 1.9 * u - 0.2 * u - lift * u)
    out.append(chair_side(hip, u, floor_y))
    dtop = desk_top if desk_top is not None else hip[1] - 0.82 * u
    dx1 = desk_x1 or R - 40
    out.append(desk_side(hip[0] + 1.25 * u, dx1, dtop, floor_y, u))
    fig, j = seated(hip, u, p, legs=legs)
    m, st, sb = monitor_side(hip[0] + 4.0 * u, dtop, u, dtop - 1.75 * u if screen_low else j["eye"][1] - 0.05 * u)
    out.append(m)
    out.append(keyboard_side(hip[0] + 1.5 * u, hip[0] + 2.35 * u, dtop, u))
    foot_y = hip[1] + 1.9 * u * legs + 0.2 * u
    if footrest and foot_y < floor_y - 4:
        fx = hip[0] + 1.6 * u
        out.append(path(f"M{fmt(fx - 0.2*u)},{fmt(floor_y)} L{fmt(fx + 1.25*u)},{fmt(floor_y)} "
                        f"L{fmt(fx + 1.25*u)},{fmt(foot_y - 0.06*u)} L{fmt(fx - 0.2*u)},{fmt(foot_y + 0.08*u)}Z",
                        fill=SAGE_SOFT, stroke=LINE, sw=2))
    out.append(fig)
    return "".join(out), j, dict(hip=hip, desk_top=dtop, screen_top=st, foot_y=foot_y)


def sc_rig_compare(pin, top):
    """Two stacked panels (problem above, fix below) built from _rig."""
    out = []
    mid_y = (top + ART_BOTTOM) / 2
    u = 70
    floors = (mid_y - 30, ART_BOTTOM - 20)
    for k, (cfg, fy) in enumerate(zip(pin["panels"], floors)):
        dtop = fy - 2.1 * u - 0.82 * u - cfg.get("desk_raise", 0.0) * u
        p = pose(SIT, **cfg.get("pose", {}))
        s, j, g = _rig(u, L + 1.1 * u, fy, lift=cfg.get("lift", 0.0), legs=cfg.get("legs", 1.0), desk_top=dtop,
                       p=p, footrest=cfg.get("footrest", False), screen_low=cfg.get("screen_low", False))
        out.append(s)
        for name in cfg.get("strain", []):
            out.append(strain(j[name], 24))
        if cfg.get("sightline"):
            out.append(line(j["eye"], g["screen_top"], stroke=SAGE if k else TERRA, sw=1.2, dash="1 6"))
        if cfg.get("gap"):
            x = j["toe"][0] + 0.25 * u
            out.append(dimension((x, g["foot_y"]), (x, fy), None, col=TERRA))
        good = k == 1
        cx = R if not good else R
        cy = top + 30 if not good else mid_y + 60
        out.append(caption(cx, cy, cfg["tag"], cfg["caption"], anchor="end", tag_col=SAGE if good else TERRA))
        if k == 0:
            out.append(hair(mid_y + 10))
    return "".join(out)


def sc_standing_tips(pin, top):
    """Standing figure on a mat, list of mistakes on the right."""
    out = []
    u = 106
    floor_y = ART_BOTTOM - 30
    cx = L + 1.35 * u
    out.append(floor(L, 470, floor_y))
    out.append(rect(cx - 1.0 * u, floor_y - 0.13 * u, 2.2 * u, 0.13 * u, rx=5, fill=SAGE_SOFT))
    hip = (cx, floor_y - 3.85 * u - 0.2 * u - 0.13 * u)
    s, j = side_figure(hip, u, **pose(STAND, uarm=178, farm=97, hand=-8, fuarm=176, ffarm=97, fhand=-8))
    out.append(s)
    x0 = 540
    for i, t in enumerate(pin["tips"]):
        yy = top + 60 + i * 166
        out.append(cross((x0 + 10, yy - 6), r=10))
        out.append(text(x0 + 32, yy, f"MISTAKE {i + 1:02d}", size=14, family=MONO, fill=TERRA, ls=2))
        words = t.split()
        out.append(text(x0, yy + 48, " ".join(words[:3]), size=36, family=SERIF, fill=INK))
        if len(words) > 3:
            out.append(text(x0, yy + 88, " ".join(words[3:]), size=36, family=SERIF, fill=INK))
        out.append(hair(yy + 118, x0, R))
    return "".join(out)


def _bones(c, r, crossed, col):
    out = [circle(c, r, fill=PAPER, stroke=LINE, sw=2)]
    if crossed:
        out.append(path(capsule((c[0] - 0.5 * r, c[1] - 0.45 * r), 9, (c[0] + 0.5 * r, c[1] + 0.45 * r), 9), fill=col))
        out.append(path(capsule((c[0] + 0.5 * r, c[1] - 0.45 * r), 8, (c[0] - 0.5 * r, c[1] + 0.45 * r), 8), fill=col))
    else:
        out.append(path(capsule((c[0] - 0.3 * r, c[1] - 0.55 * r), 9, (c[0] - 0.3 * r, c[1] + 0.55 * r), 9), fill=col))
        out.append(path(capsule((c[0] + 0.3 * r, c[1] - 0.55 * r), 8, (c[0] + 0.3 * r, c[1] + 0.55 * r), 8), fill=col))
    return "".join(out)


def sc_mouse_compare(pin, top):
    """Vertical vs regular mouse, front view, with forearm end-view icons."""
    out = []
    mid = W / 2
    desk_y = top + 580
    out.append(line((mid, top + 10), (mid, desk_y + 30), sw=0.9, extra='opacity="0.45"'))
    out.append(caption(L, top + 36, "Vertical mouse", "Handshake grip", tag_col=SAGE))
    out.append(caption(mid + 30, top + 36, "Regular mouse", "Palm turned flat", tag_col=TERRA))
    for k, x0 in enumerate((L, mid + 30)):
        cxp = x0 + (mid - 30 - L) / 2
        out.append(line((x0, desk_y), (x0 + mid - 30 - L, desk_y), sw=2))
        out.append(line((x0, desk_y + 14), (x0 + mid - 30 - L, desk_y + 14), sw=1, extra='opacity=".5"'))
        # forearm end view
        out.append(_bones((cxp, top + 200), 62, crossed=k == 1, col=SAGE if k == 0 else TERRA))
        out.append(text(cxp, top + 296, "FOREARM, END VIEW", size=13, family=MONO, fill=BODY, anchor="middle", ls=2))
        if k == 0:
            mx = cxp + 20
            out.append(path(f"M{fmt(mx - 50)},{fmt(desk_y)} L{fmt(mx - 42)},{fmt(desk_y - 105)} "
                            f"Q{fmt(mx - 30)},{fmt(desk_y - 140)} {fmt(mx + 10)},{fmt(desk_y - 128)} "
                            f"Q{fmt(mx + 52)},{fmt(desk_y - 110)} {fmt(mx + 55)},{fmt(desk_y - 40)} "
                            f"L{fmt(mx + 55)},{fmt(desk_y)}Z", fill=PAPER, stroke=LINE, sw=2))
            out.append(path(capsule((mx - 84, desk_y - 22), 30, (mx - 76, desk_y - 112), 34), fill=INK))
            out.append(path(capsule((mx - 70, desk_y - 128), 13, (mx - 30, desk_y - 150), 12), fill=INK))
        else:
            out.append(path(f"M{fmt(cxp - 80)},{fmt(desk_y)} Q{fmt(cxp - 75)},{fmt(desk_y - 62)} {fmt(cxp)},{fmt(desk_y - 64)} "
                            f"Q{fmt(cxp + 75)},{fmt(desk_y - 62)} {fmt(cxp + 80)},{fmt(desk_y)}Z",
                            fill=PAPER, stroke=LINE, sw=2))
            out.append(path(capsule((cxp - 110, desk_y - 66), 30, (cxp + 70, desk_y - 84), 34), fill=TERRA_SOFT))
            out.append(path(capsule((cxp - 150, desk_y - 50), 26, (cxp - 100, desk_y - 64), 30), fill=TERRA_SOFT))
            out.append(strain((cxp - 150, desk_y - 36), 22))
    y0 = desk_y + 90
    for i, (good_txt, bad_txt) in enumerate(pin["compare"]):
        yy = y0 + i * 70
        out.append(check((L + 14, yy - 8), r=12))
        out.append(text(L + 40, yy, good_txt, size=23, fill=INK))
        out.append(cross((mid + 44, yy - 8), r=12))
        out.append(text(mid + 70, yy, bad_txt, size=23, fill=INK))
        out.append(hair(yy + 26, L, R, 0.35))
    out.append(text(W / 2, ART_BOTTOM - 40, pin["verdict"], size=34, family=SERIF, fill=INK, anchor="middle", italic=True))
    return "".join(out)


def sc_monitor_setup(pin, top):
    """Seated figure with a monitor on an arm, annotated set-up steps."""
    out = []
    u = 108
    floor_y = ART_BOTTOM - 30
    hip = (L + 1.6 * u, floor_y - 1.9 * u - 0.2 * u)
    out.append(floor(L, R, floor_y))
    out.append(chair_side(hip, u, floor_y, lumbar=TERRA_SOFT))
    dtop = hip[1] - 0.82 * u
    out.append(desk_side(hip[0] + 1.25 * u, R, dtop, floor_y, u))
    s, j = seated(hip, u, SIT)
    sx = hip[0] + 4.0 * u
    arm, st = _arm_monitor(R, dtop, u, j["eye"][1] - 0.05 * u, sx)
    out.append(arm)
    out.append(rect(sx + 0.05 * u, st[1] + 0.62 * u, 0.24 * u, 0.36 * u, rx=4, fill=LINE))
    out.append(keyboard_side(hip[0] + 1.5 * u, hip[0] + 2.35 * u, dtop, u))
    out.append(s)
    out.append(line(j["eye"], st, stroke=TERRA, sw=1.2, dash="1 7"))
    dy = j["eye"][1] - 0.9 * u
    out.append(dimension((j["eye"][0] + 10, dy), (sx, dy), "ARM'S LENGTH", col=INK))
    out.append(callout(st, (R - 300, top + 40), "Top edge at eye level", num=1))
    out.append(callout((sx, st[1] + 1.2 * u), (R - 290, st[1] + 1.9 * u), "Tilt back 10–20°", num=2))
    out.append(callout((R - 0.25 * u, dtop + 0.2 * u), (R - 300, dtop + 110), "Clamp at the back edge", num=3))
    out.append(callout((hip[0] + 3.2 * u, dtop), (R - 300, dtop + 180), "Desk space freed up", num=4))
    return "".join(out)


SCENES3 = {
    "rig_compare": sc_rig_compare, "standing_tips": sc_standing_tips, "mouse_compare": sc_mouse_compare,
    "monitor_setup": sc_monitor_setup,
}
