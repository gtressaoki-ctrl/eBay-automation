"""Batch 5 scenes: fresh takes on the best-performing topics."""

from plate import ART_BOTTOM, W
from scenes import L, R, SIT, desk_side, floor, keyboard_side, pose, rows, seated, seated_desk
from svgkit import (INK, INK_SOFT, MONO, SAGE, TERRA, chair_side, check, cross, dimension, line, monitor_side,
                    strain, text)


def sc_monitor_zones(pin, top):
    """Three small desk scenes: screen too high, just right, too low."""
    out = []
    cw = (R - L) / 3
    u = 54
    floor_y = top + 600
    cases = [("Too high", "Chin tips up", dict(neck=-12, head=-8), "high"),
             ("Just right", "Head stays level", {}, "eye"),
             ("Too low", "Head drops forward", dict(thoracic=12, neck=40, head=6), "low")]
    for i, (tag, cap, kw, mode) in enumerate(cases):
        x0 = L + cw * i
        good = mode == "eye"
        out.append(floor(x0 + 6, x0 + cw - 6, floor_y))
        hip = (x0 + 0.95 * u, floor_y - 2.1 * u)
        out.append(chair_side(hip, u, floor_y))
        dtop = hip[1] - 0.82 * u
        out.append(desk_side(hip[0] + 1.25 * u, x0 + cw - 10, dtop, floor_y, u))
        s, j = seated(hip, u, pose(SIT, **kw))
        st_y = {"high": j["eye"][1] - 1.0 * u, "eye": j["eye"][1] - 0.05 * u, "low": dtop - 1.75 * u}[mode]
        m, st, sb = monitor_side(hip[0] + 4.0 * u, dtop, u, st_y)
        out.append(m)
        out.append(keyboard_side(hip[0] + 1.5 * u, hip[0] + 2.35 * u, dtop, u))
        out.append(s)
        out.append(line(j["eye"], st, stroke=SAGE if good else TERRA, sw=1.2, dash="1 6"))
        if not good:
            out.append(strain(j["neck"], 16))
        cx = x0 + cw / 2
        mark = check((x0 + 18, top + 40), r=12) if good else cross((x0 + 18, top + 40), r=12)
        out.append(mark)
        out.append(text(x0 + 40, top + 47, tag.upper(), size=15, family=MONO, fill=SAGE if good else TERRA, ls=3))
        out.append(text(cx, floor_y + 56, cap, size=24, fill=INK, anchor="middle"))
        if i:
            out.append(line((x0, top + 10), (x0, floor_y + 80), sw=0.9, extra='opacity="0.45"'))
    out.append(rows(L, floor_y + 120, R - L, pin["tips"], gap=62, size=28))
    return "".join(out)


def sc_measurements(pin, top):
    """Seated desk set-up with typical dimension ranges."""
    out = []
    u = 116
    floor_y = ART_BOTTOM - 30
    s, j, g = seated_desk(u, L + 1.75 * u, floor_y)
    out.append(s)
    hip = g["hip"]
    seat_top = hip[1] + 0.42 * u
    x = L + 14
    out.append(line((x - 6, seat_top), (hip[0] - 0.5 * u, seat_top), stroke=TERRA, sw=1.1, dash="3 5"))
    out.append(dimension((x, floor_y), (x, seat_top), pin["dims"][0], col=TERRA, text_side=1, size=19))
    dx = g["dx1"] - 0.75 * u
    out.append(dimension((dx, floor_y), (dx, g["desk_top"]), pin["dims"][1], col=TERRA, text_side=-1, size=19))
    st = g["screen_top"]
    dy = j["top"] - 50
    out.append(dimension((j["eye"][0] + 10, dy), (st[0], dy), pin["dims"][2], col=INK, size=19))
    out.append(line(j["eye"], (st[0], j["eye"][1]), stroke=TERRA, sw=1.2, dash="1 7"))
    out.append(text(R, top + 40, "TYPICAL RANGES · ADJUST TO YOUR BODY", size=13, family=MONO, fill=INK_SOFT, anchor="end", ls=2))
    return "".join(out)


SCENES5 = {"monitor_zones": sc_monitor_zones, "measurements": sc_measurements}
