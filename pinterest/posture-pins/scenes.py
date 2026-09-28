"""Scene illustrations for each posture pin.  Every scene draws inside a
bounding box (x0, y0, x1, y1) on the 2x canvas."""

from pinlib import *  # noqa: F401,F403

LBL = lambda s=46: font("SemiBold", s)  # noqa: E731

GOOD = dict(lumbar=2, thoracic=-2, neck=6)
SLOUCH = dict(lumbar=-14, thoracic=30, neck=52)
TYPE_GOOD = dict(uarm=176, farm=96)
STAND = dict(thigh=180, shin=180, fthigh=180, fshin=180, uarm=182, farm=178)
STAND_BAD = dict(lumbar=-8, thoracic=26, neck=42, thigh=176, shin=184, fthigh=176, fshin=184,
                 uarm=196, farm=190)


def fit_u(box, w_units, h_units):
    x0, y0, x1, y1 = box
    return min((x1 - x0) / w_units, (y1 - y0) / h_units)


def panel(img, box, col, r=44):
    rrect(img, box, r, fill=col)


def panel_bg(bg):
    return shade(bg, 0.955)


# ------------------------------------------------------------ desk scene
def desk_scene(img, box, pal, u=None, posture=GOOD, arms=TYPE_GOOD, monitor="good",
               lumbar=None, footrest=False, chair_arm=False, cx=None, legs=(1, 1), laptop=None,
               desk_top_off=0.0, book=False, lamp=False, floor_col=None, show_floor=True, extra_kw=None):
    """Seated person facing right at a desk.  Returns joints + geometry."""
    x0, y0, x1, y1 = box
    if u is None:
        u = fit_u(box, 7.2, 8.2)
    floor = y1 - 0.25 * u
    leg_len = 2.05 * u * legs[1]
    hip = ((cx if cx is not None else x0 + 1.7 * u), floor - leg_len - 0.35 * u)
    if footrest:
        hip = (hip[0], hip[1])
    kw = dict(posture)
    kw.update(arms)
    if extra_kw:
        kw.update(extra_kw)
    if show_floor:
        floor_line(img, x0 + 0.1 * u, x1 - 0.1 * u, floor, floor_col or shade(STEEL_LIGHT, 1.2))
    side_chair(img, hip, u, floor, arm=chair_arm, lumbar=lumbar)
    # desk height from a neutral typing elbow
    sh_y = hip[1] - 2.8 * u
    desk_top = sh_y + 1.45 * u + 0.12 * u + desk_top_off * u
    desk_x0 = hip[0] + 1.25 * u
    desk_x1 = min(x1 - 0.05 * u, hip[0] + 5.2 * u)
    side_desk(img, desk_x0, desk_x1, desk_top, floor, u)
    eye_y = sh_y - 0.32 * u - 0.66 * u
    mx = hip[0] + 3.75 * u
    mon = None
    if monitor == "good":
        mon = side_monitor(img, mx, desk_top, u, eye_y - 0.05 * u)
    elif monitor == "low":
        mon = side_monitor(img, mx, desk_top, u, desk_top - 1.95 * u)
    lap = None
    if laptop == "desk":
        lap = side_laptop(img, hip[0] + 2.35 * u, desk_top - 0.05 * u, u)
    elif laptop == "stand":
        sx = hip[0] + 3.3 * u
        polygon(img, [(sx - 0.6 * u, desk_top), (sx + 0.7 * u, desk_top), (sx + 0.7 * u, desk_top - 1.05 * u)], STEEL_LIGHT)
        seg(img, (sx - 0.6 * u, desk_top - 0.05 * u), (sx + 0.75 * u, desk_top - 1.1 * u), 0.1 * u, STEEL)
        lap = side_laptop(img, sx + 0.05 * u, desk_top - 0.62 * u, u, open_angle=100)
    if monitor in ("good", "low") or laptop == "stand":
        # keyboard
        rrect(img, (hip[0] + 1.35 * u, desk_top - 0.14 * u, hip[0] + 2.25 * u, desk_top + 0.02 * u), 0.05 * u, fill=STEEL)
    if book:
        bx = hip[0] + 2.1 * u
        polygon(img, [(bx, desk_top), (bx + 0.25 * u, desk_top), (bx + 0.95 * u, desk_top - 1.2 * u), (bx + 0.72 * u, desk_top - 1.25 * u)], STEEL_LIGHT)
        polygon(img, [(bx + 0.05 * u, desk_top - 0.25 * u), (bx + 0.72 * u, desk_top - 1.22 * u), (bx + 0.2 * u, desk_top - 1.55 * u), (bx - 0.45 * u, desk_top - 0.6 * u)], CORAL)
    if lamp:
        lx = desk_x1 - 0.6 * u
        seg(img, (lx - 0.35 * u, desk_top - 0.05 * u), (lx + 0.35 * u, desk_top - 0.05 * u), 0.14 * u, NAVY)
        seg(img, (lx, desk_top), (lx - 0.3 * u, desk_top - 1.6 * u), 0.1 * u, NAVY)
        seg(img, (lx - 0.3 * u, desk_top - 1.6 * u), (lx - 0.9 * u, desk_top - 1.9 * u), 0.1 * u, NAVY)
        polygon(img, [(lx - 0.8 * u, desk_top - 2.1 * u), (lx - 1.35 * u, desk_top - 1.55 * u), (lx - 0.7 * u, desk_top - 1.6 * u)], MUSTARD)
    if footrest:
        fx = hip[0] + 2.05 * u
        polygon(img, [(fx - 0.55 * u, floor), (fx + 0.75 * u, floor), (fx + 0.75 * u, floor - 0.45 * u), (fx - 0.55 * u, floor - 0.2 * u)], SAND)
    j = side_figure(img, hip, u, pal, legs=legs, **kw)
    j.update(desk_top=desk_top, floor=floor, monitor=mon, laptop=lap, desk_x0=desk_x0, desk_x1=desk_x1)
    return j


def standing_scene(img, cx, floor, u, pal, pose, f=1, show_floor=True, floor_w=2.6, floor_col=None):
    hip = (cx, floor - 4.15 * u - 0.28 * u)
    if show_floor:
        floor_line(img, cx - floor_w * u, cx + floor_w * u, floor, floor_col or shade(STEEL_LIGHT, 1.2))
    return side_figure(img, hip, u, pal, f=f, **pose)


def plumb(img, j, col, top_pad=0.9):
    u = j["u"]
    x = j["ankle"][0] - 0.05 * u
    dashed(img, (x, j["head"][1] - j["head_r"] - top_pad * u * 0.3), (x, j["ankle"][1] + 0.3 * u), col, w=0.06 * u)


def two_up(box, gap=40):
    x0, y0, x1, y1 = box
    mid = (x0 + x1) / 2
    return (x0, y0, mid - gap / 2, y1), (mid + gap / 2, y0, x1, y1)


def chips_grid(img, box, items, cols=2, fnt=None, bg=WHITE, fg=NAVY, num_col=TEAL, row_h=None, numbered=True):
    x0, y0, x1, y1 = box
    fnt = fnt or LBL(44)
    rows = (len(items) + cols - 1) // cols
    gap = 26
    cw = (x1 - x0 - gap * (cols - 1)) / cols
    rh = row_h or min(130, (y1 - y0 - gap * (rows - 1)) / rows)
    for i, t in enumerate(items):
        r, c = divmod(i, cols)
        bx = x0 + c * (cw + gap)
        by = y0 + r * (rh + gap)
        rrect(img, (bx, by, bx + cw, by + rh), rh / 2 if rh < 110 else 36, fill=bg)
        if numbered:
            num_badge(img, (bx + rh / 2, by + rh / 2), rh * 0.32, i + 1, col=num_col)
            tx = bx + rh * 0.92
        else:
            check_badge(img, (bx + rh / 2, by + rh / 2), rh * 0.3, col=num_col)
            tx = bx + rh * 0.92
        lines = wrap(t, fnt, cw - (tx - bx) - 30)
        asc, desc = fnt.getmetrics()
        lh = (asc + desc) * 1.02
        ty = by + rh / 2 - lh * len(lines) / 2
        d = ImageDraw.Draw(img)
        for k, ln in enumerate(lines):
            d.text((tx, ty + k * lh), ln, font=fnt, fill=fg, anchor="la")
    return y0 + rows * rh + (rows - 1) * gap


def verdict(img, c, good, text, fnt=None):
    fnt = fnt or LBL(46)
    col = TEAL if good else CORAL
    b = pill(img, c, text, fnt, bg=col, pad=(34, 14))
    if good:
        check_badge(img, (b[0] - 10, (b[1] + b[3]) / 2), (b[3] - b[1]) * 0.55, col=NAVY)
    else:
        cross_badge(img, (b[0] - 10, (b[1] + b[3]) / 2), (b[3] - b[1]) * 0.55, col=NAVY)
    return b


# ------------------------------------------------------------ scenes
def sc_desk_guide(img, box, pin):
    """Pin 1: correct desk sitting posture, annotated head to toe."""
    x0, y0, x1, y1 = box
    pal = person(shirt=TEAL, pants=NAVY, skin=0, hair=0)
    u = fit_u(box, 8.2, 8.0)
    j = desk_scene(img, box, pal, u=u, cx=x0 + 2.3 * u)
    f = LBL(42)
    # ear-shoulder-hip line
    dashed(img, (j["ear"][0], j["ear"][1] - 0.5 * u), (j["hip"][0], j["hip"][1] + 0.2 * u), CORAL, w=8)
    top_mon = j["monitor"][0]
    dashed(img, j["eye"], (top_mon[0], j["eye"][1]), TEAL, w=7)
    callout(img, (top_mon[0] + 0.1 * u, top_mon[1] + 0.1 * u), (x1 - 3.0 * u, y0 + 0.35 * u), "Screen top at eye level", f, col=TEAL)
    callout(img, j["ear"], (x0 + 1.6 * u, y0 + 0.35 * u), "Ears over shoulders", f)
    callout(img, j["elbow"], (j["elbow"][0] + 1.2 * u, j["elbow"][1] + 0.75 * u), "Elbows ~90°", f)
    back = (j["mid"][0] - 0.5 * u, j["mid"][1] - 0.2 * u)
    callout(img, back, (x0 + 1.2 * u, j["mid"][1] - 1.3 * u), "Back supported", f)
    callout(img, j["knee"], (j["knee"][0] + 1.5 * u, j["knee"][1] + 0.95 * u), "Knees at hip level", f)
    callout(img, j["toe"], (j["toe"][0] + 1.6 * u, j["floor"] - 0.55 * u), "Feet flat", f, col=TEAL)


def sc_signs_compare(img, box, pin):
    """Pin 2: slouched vs aligned at a desk + seven signs."""
    x0, y0, x1, y1 = box
    top = (x0, y0, x1, y0 + (y1 - y0) * 0.62)
    bl, br = two_up(top)
    panel(img, bl, CORAL_LIGHT)
    panel(img, br, TEAL_LIGHT)
    for b, good in ((bl, False), (br, True)):
        inner = (b[0] + 20, b[1] + 150, b[2] - 10, b[3] - 20)
        u = fit_u(inner, 5.6, 7.6)
        pal = person(shirt=CORAL if not good else TEAL, pants=NAVY, skin=1 if good else 1, hair=1)
        j = desk_scene(img, inner, pal, u=u, posture=GOOD if good else SLOUCH,
                       arms=TYPE_GOOD if good else dict(uarm=150, farm=100), cx=inner[0] + 1.3 * u,
                       show_floor=False, extra_kw=None)
        if not good:
            glow(img, j["neck"], 0.8 * u)
        verdict(img, ((b[0] + b[2]) / 2 + 20, b[1] + 80), good, "Aligned" if good else "Slouched")
    items = ["Head juts forward", "Rounded shoulders", "Hunched upper back", "Tight neck & traps",
             "Tension headaches", "Low back ache when sitting", "Tired after short sits"]
    chips_grid(img, (x0 + 10, top[3] + 50, x1 - 10, y1), items, cols=2, fnt=LBL(42), num_col=CORAL, row_h=132)


def sc_forward_head(img, box, pin):
    """Pin 3: forward head vs neutral with plumb line + fixes."""
    x0, y0, x1, y1 = box
    top = (x0, y0, x1, y1 - 260)
    bl, br = two_up(top)
    panel(img, bl, CORAL_LIGHT)
    panel(img, br, TEAL_LIGHT)
    for b, good in ((bl, False), (br, True)):
        inner = (b[0], b[1] + 160, b[2], b[3] - 40)
        u = fit_u(inner, 4.6, 9.0)
        cx = (b[0] + b[2]) / 2 - 0.2 * u
        pal = person(shirt=SAND if not good else TEAL, pants=NAVY, skin=2, hair=1)
        pose = dict(STAND_BAD) if not good else dict(STAND, neck=4)
        if not good:
            pose.update(lumbar=-4, thoracic=12, neck=44, uarm=188, farm=182)
        j = standing_scene(img, cx, inner[3], u, pal, pose, floor_w=1.8)
        x = j["ankle"][0]
        dashed(img, (x, j["head"][1] - 1.0 * u), (x, j["ankle"][1] + 0.3 * u), TEAL if good else STEEL_LIGHT, w=8)
        circle(img, j["ear"], 0.2 * u, outline=NAVY if good else CORAL, width=10)
        if not good:
            arrow(img, (x, j["ear"][1]), (j["ear"][0] - 0.22 * u, j["ear"][1]), CORAL, w=12, head=36)
        verdict(img, ((b[0] + b[2]) / 2 + 20, b[1] + 80), good, "Ear over shoulder" if good else "Head forward", fnt=LBL(40))
    chips = ["Chin tucks", "Raise your screen", "Strengthen upper back"]
    cw = (x1 - x0 - 40) / 3
    for i, t in enumerate(chips):
        cx = x0 + cw / 2 + i * (cw + 20)
        pill(img, (cx, y1 - 110), t, LBL(40), fg=NAVY, bg=WHITE, pad=(28, 22))
    ImageDraw.Draw(img).text(((x0 + x1) / 2, y1 - 215), "DAILY FIXES", font=font("Bold", 40), fill=TEAL, anchor="mm")


# ---- exercise grids
def grid4(box, gap=36):
    x0, y0, x1, y1 = box
    w = (x1 - x0 - gap) / 2
    h = (y1 - y0 - gap) / 2
    return [(x0 + c * (w + gap), y0 + r * (h + gap), x0 + c * (w + gap) + w, y0 + r * (h + gap) + h)
            for r in range(2) for c in range(2)]


def ex_panel(img, b, n, title, tag=None, col=WHITE, num_col=TEAL):
    panel(img, b, col, r=40)
    num_badge(img, (b[0] + 62, b[1] + 62), 38, n, col=num_col)
    ImageDraw.Draw(img).text((b[0] + 118, b[1] + 62), title, font=LBL(44), fill=NAVY, anchor="lm")
    if tag:
        pill(img, ((b[0] + b[2]) / 2, b[3] - 52), tag, font("Medium", 36), fg=NAVY, bg=shade(col, 0.93), pad=(22, 8))
    return (b[0] + 20, b[1] + 120, b[2] - 20, b[3] - (100 if tag else 30))


def seated_side(img, inner, pal, pose, arrows=None):
    u = fit_u(inner, 4.2, 7.2)
    cx = (inner[0] + inner[2]) / 2 - 0.4 * u
    floor = inner[3] - 0.05 * u
    hip = (cx, floor - 2.05 * u - 0.35 * u)
    side_chair(img, hip, u, floor, col=STEEL_LIGHT)
    return side_figure(img, hip, u, pal, **pose)


def seated_front(img, inner, pal, **kw):
    u = fit_u(inner, 4.6, 8.3)
    cx = (inner[0] + inner[2]) / 2
    hipy = inner[3] - 2.45 * u
    return front_figure(img, cx, hipy, u, pal, seated=True, chair=STEEL_LIGHT, **kw)


def standing_front(img, inner, pal, **kw):
    u = fit_u(inner, 4.6, 10.2)
    cx = (inner[0] + inner[2]) / 2
    hipy = inner[3] - 4.35 * u
    return front_figure(img, cx, hipy, u, pal, seated=False, **kw)


def standing_side(img, inner, pal, pose):
    u = fit_u(inner, 4.6, 9.2)
    cx = (inner[0] + inner[2]) / 2 - 0.2 * u
    return standing_scene(img, cx, inner[3], u, pal, pose, show_floor=False)


def draw_exercise(img, inner, pal, kind):
    """Library of small exercise illustrations."""
    if kind == "chin_tuck_seated":
        j = seated_side(img, inner, pal, dict(GOOD, neck=-4, uarm=170, farm=120))
        u = j["u"]
        arrow(img, (j["head"][0] + 1.45 * u, j["head"][1]), (j["head"][0] + 0.85 * u, j["head"][1]), CORAL, w=0.14 * u, head=0.4 * u)
    elif kind == "chin_tuck_standing":
        j = standing_side(img, inner, pal, dict(STAND, neck=-4))
        u = j["u"]
        arrow(img, (j["head"][0] + 1.5 * u, j["head"][1]), (j["head"][0] + 0.9 * u, j["head"][1]), CORAL, w=0.14 * u, head=0.4 * u)
    elif kind == "side_neck":
        j = seated_front(img, inner, pal, tilt=24, la=(188, 182), ra=(20, 300))
    elif kind == "side_neck_stand":
        j = standing_front(img, inner, pal, tilt=24, la=(188, 182), ra=(20, 300))
    elif kind == "upper_back_ext":
        j = seated_side(img, inner, pal, dict(lumbar=-4, thoracic=-16, neck=-14, uarm=150, farm=345, fuarm=150, ffarm=345))
    elif kind == "shoulder_rolls":
        j = seated_front(img, inner, pal)
        u = j["u"]
        for s, c in ((-1, j["shl"]), (1, j["shr"])):
            cc = (c[0] + s * 0.25 * u, c[1] - 0.55 * u)
            curved_arrow(img, cc, 0.5 * u, 200 if s < 0 else -20, 470 if s < 0 else 250, CORAL, w=0.12 * u, head=0.35 * u)
    elif kind == "overhead_reach":
        j = seated_front(img, inner, pal, la=(12, 20), ra=(348, 340))
    elif kind == "overhead_reach_stand":
        j = standing_front(img, inner, pal, la=(12, 20), ra=(348, 340))
    elif kind == "side_bend":
        j = seated_front(img, inner, pal, lean=-16, la=(200, 185), ra=(338, 300))
    elif kind == "side_bend_stand":
        j = standing_front(img, inner, pal, lean=-14, la=(200, 185), ra=(338, 300))
    elif kind == "wall_angels":
        x0, y0, x1, y1 = inner
        rrect(img, (x0 + 30, y0, x1 - 30, y1), 20, fill=shade(WHITE, 0.94))
        j = standing_front(img, inner, pal, back=True, la=(270, 330), ra=(90, 30))
        u = j["u"]
        for s, e in ((-1, j["el"]), (1, j["er"])):
            arrow(img, (e[0], e[1] - 0.3 * u), (e[0], e[1] - 1.2 * u), CORAL, w=0.12 * u, head=0.35 * u)
    elif kind == "scap_squeeze":
        j = standing_front(img, inner, pal, back=True, la=(250, 350), ra=(110, 10))
        u = j["u"]
        c = ((j["shl"][0] + j["shr"][0]) / 2, j["shl"][1] + 0.9 * u)
        arrow(img, (c[0] - 1.1 * u, c[1]), (c[0] - 0.2 * u, c[1]), CORAL, w=0.12 * u, head=0.32 * u)
        arrow(img, (c[0] + 1.1 * u, c[1]), (c[0] + 0.2 * u, c[1]), CORAL, w=0.12 * u, head=0.32 * u)
    elif kind == "chest_opener_stand":
        j = standing_side(img, inner, pal, dict(STAND, thoracic=-8, neck=-2, uarm=208, farm=196, fuarm=208, ffarm=196))
    elif kind == "chest_opener_seated":
        j = seated_side(img, inner, pal, dict(GOOD, thoracic=-8, neck=0, uarm=208, farm=196, fuarm=208, ffarm=196))
    elif kind == "neck_turn":
        j = seated_front(img, inner, pal)
        u = j["u"]
        curved_arrow(img, j["head"], j["head_r"] * 1.55, 200, 340, CORAL, w=0.12 * u, head=0.35 * u)
    elif kind == "stand_up":
        j = standing_side(img, inner, pal, dict(STAND, uarm=182, farm=178))
    else:
        raise ValueError(kind)
    return j


def sc_exercise_grid(img, box, pin):
    x0, y0, x1, y1 = box
    ex = pin["exercises"]
    top_pad = pin.get("grid_top", 0)
    if top_pad:
        pill(img, ((x0 + x1) / 2, y0 + top_pad / 2 - 10), pin["grid_badge"], LBL(42), fg=WHITE, bg=pin.get("badge_col", NAVY), pad=(34, 16))
    cells = grid4((x0, y0 + top_pad, x1, y1))
    pals = [person(shirt=TEAL, skin=0, hair=0), person(shirt=CORAL, skin=1, hair=1),
            person(shirt=MUSTARD, pants=STEEL, skin=2, hair=1), person(shirt=NAVY, pants=STEEL, skin=3, hair=2)]
    who = pin.get("who", 0)
    for i, (b, (kind, title, tag)) in enumerate(zip(cells, ex)):
        inner = ex_panel(img, b, i + 1, title, tag, num_col=pin.get("num_col", TEAL))
        draw_exercise(img, inner, pals[(who) % 4], kind)


def sc_pain(img, box, pin):
    """Pins 5 & 17: seated person with an aching back / neck."""
    x0, y0, x1, y1 = box
    area = pin["area"]
    illo = (x0, y0, x1, y1 - 270)
    pal = person(shirt=pin.get("shirt", SAND), pants=NAVY, skin=pin.get("skin", 0), hair=pin.get("hair", 0))
    u = fit_u(illo, 7.4, 8.2)
    if area == "upper_back":
        j = desk_scene(img, illo, pal, u=u, posture=dict(lumbar=-6, thoracic=26, neck=40),
                       arms=dict(uarm=150, farm=98, fuarm=210, ffarm=320), monitor="good", cx=x0 + 2.6 * u)
        spot = add(j["mid"], 26 + 180, -0.55 * u)
        spot = ((j["mid"][0] + j["shoulder"][0]) / 2 - 0.45 * u, (j["mid"][1] + j["shoulder"][1]) / 2)
        glow(img, spot, 1.0 * u)
        callout(img, spot, (x0 + 1.4 * u, y0 + 0.4 * u), "Between the shoulder blades", LBL(40), col=CORAL)
    else:
        j = desk_scene(img, illo, pal, u=u, posture=dict(lumbar=-4, thoracic=22, neck=50),
                       arms=dict(uarm=150, farm=100, fuarm=150, ffarm=345), monitor="low", cx=x0 + 2.6 * u)
        glow(img, j["neck"], 0.9 * u)
        callout(img, j["neck"], (x0 + 1.4 * u, y0 + 0.4 * u), "Neck strain", LBL(40), col=CORAL)
        top = j["monitor"][0]
        dashed(img, j["eye"], (top[0], top[1] + 0.8 * u), CORAL, w=7)
        callout(img, (top[0] + 0.1 * u, top[1] + 0.2 * u), (x1 - 2.2 * u, top[1] - 1.6 * u), "Screen too low", LBL(40), col=NAVY)
    items = pin["causes"]
    ImageDraw.Draw(img).text(((x0 + x1) / 2, y1 - 235), pin.get("causes_title", "COMMON CAUSES"), font=font("Bold", 40), fill=CORAL, anchor="mm")
    cw = (x1 - x0 - 40) / 3
    for i, t in enumerate(items):
        cx = x0 + cw / 2 + i * (cw + 20)
        b = (cx - cw / 2, y1 - 185, cx + cw / 2, y1 - 25)
        rrect(img, b, 36, fill=WHITE)
        text_block(img, cx, b[1] + 30 if len(wrap(t, LBL(40), cw - 50)) > 1 else b[1] + 55, t, LBL(40), NAVY, cw - 50)


def sc_headache(img, box, pin):
    """Pin 27: front view, hands to temples at desk."""
    x0, y0, x1, y1 = box
    illo = (x0, y0, x1, y1 - 60)
    pal = person(shirt=NAVY, pants=STEEL, skin=1, hair=0)
    u = fit_u(illo, 7.0, 8.4)
    cx = (x0 + x1) / 2
    hipy = y1 - 2.2 * u
    j = front_figure(img, cx, hipy, u, pal, seated=True, chair=STEEL_LIGHT, legs_visible=False,
                     la=(215, 20), ra=(145, 340), tilt=4)
    glow(img, j["head"], 1.35 * u, alpha=120)
    glow(img, j["neck"], 0.8 * u, alpha=150)
    # desk in front
    dy = hipy - 0.9 * u
    rrect(img, (x0 + 0.2 * u, dy, x1 - 0.2 * u, dy + 0.35 * u), 0.1 * u, fill=WOOD)
    rrect(img, (x0 + 0.2 * u, dy + 0.3 * u, x1 - 0.2 * u, y1), 0.1 * u, fill=shade(WOOD, 0.85))
    rrect(img, (x0 + 0.6 * u, dy - 1.3 * u, x0 + 2.2 * u, dy - 0.02 * u), 0.1 * u, fill=(60, 64, 76))
    rrect(img, (x0 + 0.7 * u, dy - 1.2 * u, x0 + 2.1 * u, dy - 0.15 * u), 0.06 * u, fill=SCREEN)
    circle(img, (x1 - 1.2 * u, dy - 0.35 * u), 0.33 * u, fill=CORAL)
    rrect(img, (x1 - 1.55 * u, dy - 0.68 * u, x1 - 0.85 * u, dy - 0.02 * u), 0.1 * u, fill=CORAL)
    f = LBL(40)
    callout(img, (j["head"][0], j["head"][1] - j["head_r"] * 0.9), (cx, y0 + 0.25 * u), "Pressure around the head", f, col=CORAL)
    callout(img, j["shl"], (x0 + 1.2 * u, j["shl"][1] - 0.2 * u), "Tight neck", f)
    callout(img, j["shr"], (x1 - 1.3 * u, j["shr"][1] - 0.2 * u), "Raised shoulders", f)


def sc_timeline(img, box, pin):
    """Pins 14 & 30: posture changes over time."""
    x0, y0, x1, y1 = box
    stages = pin["stages"]
    n = len(stages)
    pal = person(shirt=TEAL, pants=NAVY, skin=pin.get("skin", 0), hair=pin.get("hair", 0))
    illo_h = (y1 - y0) * 0.56
    cw = (x1 - x0) / n
    u = min(cw / 3.1, illo_h / 9.4)
    floor = y0 + illo_h
    floor_line(img, x0 + 20, x1 - 20, floor, shade(STEEL_LIGHT, 1.2))
    for i, st in enumerate(stages):
        t = i / (n - 1)
        pose = dict(STAND)
        pose.update(lumbar=-8 * (1 - t), thoracic=26 * (1 - t) - 1 * t, neck=42 * (1 - t) + 4 * t,
                    uarm=196 * (1 - t) + 182 * t, farm=190 * (1 - t) + 178 * t)
        cx = x0 + cw * (i + 0.5) - 0.2 * u
        standing_scene(img, cx, floor, u, pal, pose, show_floor=False)
    # timeline bar
    ty = floor + 110
    seg(img, (x0 + cw / 2, ty), (x1 - cw / 2, ty), 16, shade(TEAL, 1.0))
    col_text_top = ty + 80
    for i, (when, what) in enumerate(stages):
        cx = x0 + cw * (i + 0.5)
        circle(img, (cx, ty), 34, fill=WHITE, outline=TEAL, width=12)
        pill(img, (cx, col_text_top + 10), when, LBL(38), fg=WHITE, bg=NAVY, pad=(20, 10))
        text_block(img, cx, col_text_top + 85, what, font("Medium", 38), INK, cw - 24)


def sc_before_after(img, box, pin):
    """Pin 13 (standing) & 23 (phone)."""
    x0, y0, x1, y1 = box
    bl, br = two_up((x0, y0, x1, y1 - pin.get("foot_space", 0)))
    panel(img, bl, CORAL_LIGHT)
    panel(img, br, TEAL_LIGHT)
    labels = pin["labels"]
    phone = pin.get("phone", False)
    for b, good in ((bl, False), (br, True)):
        inner = (b[0], b[1] + 170, b[2], b[3] - 40)
        u = fit_u(inner, 4.6, 9.4)
        cx = (b[0] + b[2]) / 2 - 0.2 * u
        pal = person(shirt=pin.get("shirt", MUSTARD), pants=NAVY, skin=pin.get("skin", 3), hair=pin.get("hair", 2))
        if phone:
            pose = dict(STAND_BAD, uarm=176, farm=70, fuarm=176, ffarm=70, neck=58) if not good else dict(STAND, neck=6, uarm=160, farm=30, fuarm=160, ffarm=30)
        else:
            pose = dict(STAND_BAD) if not good else dict(STAND)
        j = standing_scene(img, cx, inner[3], u, pal, pose, floor_w=1.8)
        if phone:
            w = j["wrist"]
            ang = 70 if not good else 30
            p = add(w, ang - 90, 0.15 * u)
            rrect(img, (p[0] - 0.12 * u, p[1] - 0.42 * u, p[0] + 0.12 * u, p[1] + 0.42 * u), 0.06 * u, fill=NAVY)
            dashed(img, j["eye"], (p[0], p[1] - 0.2 * u), CORAL if not good else TEAL, w=6)
        if not good:
            glow(img, j["neck"], 0.7 * u, alpha=140)
        x = j["ankle"][0]
        dashed(img, (x, j["head"][1] - 0.9 * u), (x, j["ankle"][1] + 0.3 * u), TEAL if good else STEEL_LIGHT, w=7)
        ImageDraw.Draw(img).text(((b[0] + b[2]) / 2, b[1] + 64), labels[1 if good else 0][0], font=font("ExtraBold", 58),
                                 fill=TEAL if good else CORAL, anchor="mm")
        text_block(img, (b[0] + b[2]) / 2, b[1] + 104, labels[1 if good else 0][1], font("Medium", 36), INK, b[2] - b[0] - 40)
    if pin.get("footer_chips"):
        cw = (x1 - x0 - 40) / 3
        for i, t in enumerate(pin["footer_chips"]):
            cx = x0 + cw / 2 + i * (cw + 20)
            pill(img, (cx, y1 - 70), t, LBL(38), fg=NAVY, bg=WHITE, pad=(24, 20))


def sc_monitor_height(img, box, pin):
    """Pin 9: eye line vs monitor top."""
    x0, y0, x1, y1 = box
    pal = person(shirt=NAVY, pants=STEEL, skin=2, hair=1)
    u = fit_u(box, 7.2, 8.0)
    j = desk_scene(img, box, pal, u=u, cx=x0 + 1.9 * u)
    top, bot = j["monitor"]
    eye = j["eye"]
    dashed(img, eye, (top[0], eye[1]), TEAL, w=8)
    centre = (top[0], (top[1] + bot[1]) / 2)
    dashed(img, eye, centre, CORAL, w=7)
    angle_arc(img, eye, 1.4 * u, 90, 90 + 18, CORAL, w=8)
    f = LBL(40)
    ImageDraw.Draw(img).text((eye[0] + 1.0 * u, eye[1] + 0.75 * u), "15–20° down", font=font("Bold", 40), fill=CORAL, anchor="lm")
    callout(img, (top[0] + 0.12 * u, top[1]), (top[0] + 0.35 * u, eye[1] - 0.45 * u), "Top at or just below eye level", f, col=TEAL, anchor="rm")
    ydist = eye[1] - 1.0 * u
    arrow(img, (eye[0] + 0.3 * u, ydist), (top[0] - 0.25 * u, ydist), NAVY, w=8, head=28)
    arrow(img, (top[0] - 0.25 * u, ydist), (eye[0] + 0.3 * u, ydist), NAVY, w=8, head=28)
    pill(img, ((eye[0] + top[0]) / 2, ydist - 60), "About an arm's length", f, fg=NAVY, bg=WHITE)


def sc_chair_check(img, box, pin):
    """Pin 10: ergonomic chair checkpoints."""
    x0, y0, x1, y1 = box
    pal = person(shirt=CORAL, pants=NAVY, skin=0, hair=2)
    u = fit_u(box, 7.2, 8.4)
    floor = y1 - 0.2 * u
    hip = (x0 + 3.0 * u, floor - 2.4 * u)
    floor_line(img, x0 + 0.3 * u, x1 - 0.3 * u, floor, shade(STEEL_LIGHT, 1.2))
    side_chair(img, hip, u, floor, col=STEEL, arm=True, lumbar=TEAL, back_h=3.9, recline=8)
    j = side_figure(img, hip, u, pal, lumbar=0, thoracic=-6, neck=2, uarm=178, farm=95)
    f = LBL(38)
    pts = [
        ((hip[0] - 0.95 * u, hip[1] - 1.0 * u), (x0 + 0.1 * u, hip[1] - 1.0 * u), "Lumbar support", "lm"),
        ((hip[0] - 1.25 * u, hip[1] - 3.4 * u), (x0 + 0.1 * u, hip[1] - 3.9 * u), "Reclines 100–110°", "lm"),
        ((hip[0] + 0.8 * u, hip[1] - 1.25 * u), (x1 - 0.1 * u, hip[1] - 2.2 * u), "Armrests at elbow height", "rm"),
        ((hip[0] + 1.75 * u, hip[1] + 0.55 * u), (x1 - 0.1 * u, hip[1] - 0.6 * u), "2–3 finger gap at knees", "rm"),
        ((hip[0] + 0.5 * u, floor - 1.2 * u), (x1 - 0.1 * u, floor - 1.0 * u), "Height: feet flat", "rm"),
    ]
    for i, (p, lab, t, anc) in enumerate(pts):
        b = callout(img, p, lab, t, f, col=NAVY if i % 2 else TEAL, anchor=anc)


def sc_stand_vs_sit(img, box, pin):
    """Pin 11."""
    x0, y0, x1, y1 = box
    bl, br = two_up((x0, y0, x1, y1 - 190))
    panel(img, bl, panel_bg(BG["sky"]))
    panel(img, br, panel_bg(BG["sky"]))
    # sitting
    inner = (bl[0] + 10, bl[1] + 170, bl[2] - 10, bl[3] - 20)
    u = fit_u(inner, 5.5, 8.6)
    pal = person(shirt=TEAL, pants=NAVY, skin=1, hair=0)
    desk_scene(img, inner, pal, u=u, cx=inner[0] + 1.25 * u, show_floor=True)
    ImageDraw.Draw(img).text(((bl[0] + bl[2]) / 2, bl[1] + 70), "SITTING", font=font("ExtraBold", 58), fill=NAVY, anchor="mm")
    text_block(img, (bl[0] + bl[2]) / 2, bl[1] + 110, "Support your lower back", font("Medium", 36), INK, 800)
    # standing
    inner = (br[0] + 10, br[1] + 170, br[2] - 10, br[3] - 20)
    u2 = fit_u(inner, 5.5, 9.6)
    pal2 = person(shirt=CORAL, pants=NAVY, skin=3, hair=2)
    floor = inner[3] - 0.2 * u2
    cx = inner[0] + 1.5 * u2
    floor_line(img, inner[0] + 0.1 * u2, inner[2] - 0.1 * u2, floor, shade(STEEL_LIGHT, 1.2))
    hip = (cx, floor - 4.15 * u2 - 0.28 * u2)
    sh_y = hip[1] - 2.8 * u2
    dtop = sh_y + 1.45 * u2 + 0.12 * u2
    side_desk(img, cx + 1.25 * u2, inner[2] - 0.1 * u2, dtop, floor, u2)
    seg(img, (inner[2] - 0.45 * u2, dtop), (inner[2] - 0.45 * u2, floor), 0.3 * u2, STEEL)
    side_monitor(img, cx + 3.3 * u2, dtop, u2, sh_y - 1.03 * u2)
    rrect(img, (cx + 1.35 * u2, dtop - 0.14 * u2, cx + 2.25 * u2, dtop + 0.02 * u2), 0.05 * u2, fill=STEEL)
    side_figure(img, hip, u2, pal2, **dict(STAND, uarm=176, farm=96, fuarm=176, ffarm=96))
    ImageDraw.Draw(img).text(((br[0] + br[2]) / 2, br[1] + 70), "STANDING", font=font("ExtraBold", 58), fill=NAVY, anchor="mm")
    text_block(img, (br[0] + br[2]) / 2, br[1] + 110, "Stack joints, soft knees", font("Medium", 36), INK, 800)
    b = pill(img, ((x0 + x1) / 2, y1 - 80), "Best: switch every 30–60 minutes", LBL(46), fg=WHITE, bg=TEAL, pad=(40, 24))


def sc_lumbar(img, box, pin):
    """Pin 12."""
    x0, y0, x1, y1 = box
    pal = person(shirt=MUSTARD, pants=NAVY, skin=1, hair=1)
    u = fit_u(box, 7.2, 8.1)
    floor = y1 - 0.25 * u
    hip = (x0 + 2.6 * u, floor - 2.4 * u)
    floor_line(img, x0 + 0.2 * u, x1 - 0.2 * u, floor, shade(STEEL_LIGHT, 1.2))
    side_chair(img, hip, u, floor, col=STEEL, lumbar=TEAL, back_h=3.3)
    j = side_figure(img, hip, u, pal, lumbar=4, thoracic=-4, neck=4, uarm=178, farm=100)
    lp = (hip[0] - 0.5 * u, hip[1] - 0.95 * u)
    circle(img, lp, 1.05 * u, outline=TEAL, width=12)
    f = LBL(40)
    callout(img, (lp[0] - 1.0 * u, lp[1] - 0.3 * u), (x0 + 1.35 * u, y0 + 0.5 * u), "Fills the curve of your lower back", f, col=TEAL, anchor="lm")
    callout(img, j["shoulder"], (x1 - 0.2 * u, j["shoulder"][1] - 0.8 * u), "Shoulders stay back", f, anchor="rm")
    callout(img, (hip[0] + 0.3 * u, hip[1]), (x1 - 0.2 * u, hip[1] - 0.3 * u), "Hips all the way back", f, anchor="rm")
    callout(img, j["toe"], (x1 - 0.2 * u, floor - 0.65 * u), "Feet flat", f, col=TEAL, anchor="rm")


def sc_laptop(img, box, pin):
    """Pin 15: laptop flat vs on a stand."""
    x0, y0, x1, y1 = box
    mid = (y0 + y1) / 2
    top = (x0, y0, x1, mid - 20)
    bot = (x0, mid + 20, x1, y1)
    panel(img, top, CORAL_LIGHT)
    panel(img, bot, TEAL_LIGHT)
    pal = person(shirt=SAND, pants=NAVY, skin=0, hair=1)
    for b, good in ((top, False), (bot, True)):
        inner = (b[0] + 40, b[1] + 30, b[2] - 20, b[3] - 10)
        u = fit_u(inner, 7.4, 7.9)
        if good:
            j = desk_scene(img, inner, person(shirt=TEAL, pants=NAVY, skin=0, hair=1), u=u, laptop="stand", monitor=None,
                           cx=inner[0] + 2.0 * u, show_floor=False)
            hinge, st = j["laptop"]
            dashed(img, j["eye"], (st[0] - 0.1 * u, j["eye"][1] + 0.1 * u), TEAL, w=7)
        else:
            j = desk_scene(img, inner, pal, u=u, laptop="desk", monitor=None, posture=dict(lumbar=-10, thoracic=30, neck=58),
                           arms=dict(uarm=150, farm=100), cx=inner[0] + 2.0 * u, show_floor=False)
            hinge, st = j["laptop"]
            dashed(img, j["eye"], ((hinge[0] + st[0]) / 2, (hinge[1] + st[1]) / 2), CORAL, w=7)
            glow(img, j["neck"], 0.7 * u, alpha=140)
        verdict(img, (b[2] - 360, b[1] + 80), good, "Screen raised + keyboard" if good else "Looking down all day", fnt=LBL(40))


def sc_wall_test(img, box, pin):
    """Pin 18."""
    x0, y0, x1, y1 = box
    u = fit_u((x0, y0, x0 + (x1 - x0) * 0.5, y1), 3.6, 9.2)
    floor = y1 - 0.2 * u
    wall_x = x0 + 0.9 * u
    rrect(img, (x0, y0, wall_x, floor), 20, fill=shade(BG["sage"], 0.88))
    floor_line(img, x0, x0 + 4.6 * u, floor, shade(STEEL_LIGHT, 1.2))
    pal = person(shirt=TEAL, pants=NAVY, skin=2, hair=0)
    hip = (wall_x + 0.52 * u, floor - 4.15 * u - 0.28 * u)
    j = side_figure(img, hip, u, pal, **dict(STAND, lumbar=0, thoracic=-4, neck=6))
    pts = [(wall_x, j["head"][1]), (wall_x, j["shoulder"][1] + 0.3 * u), (wall_x, hip[1]), (wall_x, j["ankle"][1] + 0.05 * u)]
    for p in pts:
        circle(img, p, 0.16 * u, fill=CORAL)
    # hand gap
    gap = (wall_x + 0.12 * u, hip[1] - 1.0 * u)
    rrect(img, (gap[0] - 0.08 * u, gap[1] - 0.3 * u, gap[0] + 0.2 * u, gap[1] + 0.3 * u), 0.1 * u, fill=MUSTARD)
    steps = pin["steps"]
    sx = x0 + (x1 - x0) * 0.47
    sy = y0 + 30
    step_h = (y1 - y0 - 60) / len(steps)
    for i, (h, t) in enumerate(steps):
        b = (sx, sy + i * step_h, x1, sy + i * step_h + step_h - 34)
        rrect(img, b, 36, fill=WHITE)
        num_badge(img, (b[0] + 70, b[1] + 72), 42, i + 1, col=CORAL if i < len(steps) - 1 else TEAL)
        ImageDraw.Draw(img).text((b[0] + 130, b[1] + 72), h, font=font("Bold", 52), fill=NAVY, anchor="lm")
        text_block(img, b[0] + 44, b[1] + 140, t, font("Medium", 44), INK, b[2] - b[0] - 80, align="left")


def sc_chair_tips(img, box, pin):
    """Pin 19: office chair posture tips (no desk)."""
    x0, y0, x1, y1 = box
    illo = (x0, y0, x0 + (x1 - x0) * 0.54, y1)
    pal = person(shirt=NAVY, pants=STEEL, skin=3, hair=2)
    u = fit_u(illo, 4.3, 8.0)
    floor = y1 - 0.2 * u
    hip = (x0 + 1.3 * u, floor - 2.4 * u)
    floor_line(img, x0 + 0.1 * u, illo[2], floor, shade(STEEL_LIGHT, 1.2))
    side_chair(img, hip, u, floor, col=STEEL, arm=True, lumbar=MUSTARD, back_h=3.4)
    j = side_figure(img, hip, u, pal, lumbar=2, thoracic=-3, neck=5, uarm=178, farm=92)
    items = pin["tips"]
    tx = x0 + (x1 - x0) * 0.57
    ty0 = floor - 7.4 * u
    th = (y1 - ty0 - 30) / len(items)
    for i, t in enumerate(items):
        b = (tx, ty0 + i * th, x1, ty0 + i * th + th - 30)
        rrect(img, b, 34, fill=WHITE)
        check_badge(img, (b[0] + 60, (b[1] + b[3]) / 2), 34, col=TEAL)
        lines = wrap(t, LBL(38), b[2] - b[0] - 140)
        text_block(img, b[0] + 112, (b[1] + b[3]) / 2 - len(lines) * 27, t, LBL(38), NAVY, b[2] - b[0] - 140, align="left")


# ---- top-down scenes
def td_person(img, c, u, pal, arms_to=None):
    """Top-down person at c (head centre) facing up."""
    seg(img, (c[0] - 1.05 * u, c[1] + 0.35 * u), (c[0] + 1.05 * u, c[1] + 0.35 * u), 0.9 * u, pal["shirt"])
    if arms_to:
        for s, tgt in zip((-1, 1), arms_to):
            sh = (c[0] + s * 1.1 * u, c[1] + 0.35 * u)
            el = (c[0] + s * 1.2 * u, c[1] - 0.55 * u)
            seg(img, sh, el, 0.42 * u, pal["shirt"])
            seg(img, el, tgt, 0.34 * u, pal["skin"])
            circle(img, tgt, 0.2 * u, fill=pal["skin"])
    circle(img, c, 0.55 * u, fill=pal["hair"])


def td_keyboard(img, c, u, w=3.0):
    b = (c[0] - w / 2 * u, c[1] - 0.45 * u, c[0] + w / 2 * u, c[1] + 0.45 * u)
    rrect(img, b, 0.12 * u, fill=STEEL)
    for r in range(4):
        for k in range(int(w * 4)):
            kx = b[0] + 0.12 * u + k * (w * u - 0.24 * u) / int(w * 4)
            ky = b[1] + 0.12 * u + r * 0.17 * u
            rrect(img, (kx, ky, kx + (w * u - 0.24 * u) / int(w * 4) - 6, ky + 0.13 * u), 4, fill=STEEL_LIGHT)
    return b


def td_mouse(img, c, u):
    ImageDraw.Draw(img).ellipse([c[0] - 0.24 * u, c[1] - 0.38 * u, c[0] + 0.24 * u, c[1] + 0.38 * u], fill=STEEL)
    seg(img, (c[0], c[1] - 0.36 * u), (c[0], c[1] - 0.1 * u), 4, STEEL_LIGHT)


def td_plant(img, c, u):
    circle(img, c, 0.42 * u, fill=CORAL)
    for a in range(0, 360, 60):
        p = add(c, a, 0.42 * u)
        ImageDraw.Draw(img).ellipse([p[0] - 0.22 * u, p[1] - 0.22 * u, p[0] + 0.22 * u, p[1] + 0.22 * u], fill=PLANT)
    circle(img, c, 0.2 * u, fill=shade(PLANT, 0.8))


def td_mug(img, c, u):
    circle(img, c, 0.3 * u, fill=WHITE)
    circle(img, c, 0.22 * u, fill=(120, 80, 60))
    rrect(img, (c[0] + 0.25 * u, c[1] - 0.08 * u, c[0] + 0.45 * u, c[1] + 0.08 * u), 0.06 * u, fill=WHITE)


def sc_topdown_setup(img, box, pin):
    """Pin 8: ergonomic desk setup from above."""
    x0, y0, x1, y1 = box
    u = fit_u(box, 8.4, 9.6)
    cx = (x0 + x1) / 2
    dtop = y0 + 1.6 * u
    dbot = dtop + 4.2 * u
    rrect(img, (cx - 4.0 * u, dtop, cx + 4.0 * u, dbot), 0.3 * u, fill=WOOD)
    # monitor
    rrect(img, (cx - 1.9 * u, dtop + 0.45 * u, cx + 1.9 * u, dtop + 0.75 * u), 0.1 * u, fill=(40, 44, 54))
    rrect(img, (cx - 0.5 * u, dtop + 0.7 * u, cx + 0.5 * u, dtop + 1.2 * u), 0.1 * u, fill=STEEL_LIGHT)
    kb = td_keyboard(img, (cx - 0.25 * u, dtop + 2.85 * u), u, w=2.8)
    td_mouse(img, (cx + 1.65 * u, dtop + 2.85 * u), u)
    td_plant(img, (cx - 3.3 * u, dtop + 0.8 * u), u)
    td_mug(img, (cx + 3.1 * u, dtop + 2.3 * u), u)
    # lamp
    circle(img, (cx + 3.2 * u, dtop + 0.8 * u), 0.4 * u, fill=MUSTARD)
    circle(img, (cx + 3.2 * u, dtop + 0.8 * u), 0.18 * u, fill=NAVY)
    # chair
    rrect(img, (cx - 1.3 * u, dbot + 0.35 * u, cx + 1.3 * u, dbot + 2.4 * u), 0.5 * u, fill=STEEL)
    rrect(img, (cx - 1.5 * u, dbot + 2.2 * u, cx + 1.5 * u, dbot + 2.7 * u), 0.25 * u, fill=shade(STEEL, 0.75))
    pal = person(shirt=TEAL, skin=1, hair=0)
    td_person(img, (cx, dbot + 1.0 * u), u, pal, arms_to=[(cx - 0.95 * u, dtop + 3.05 * u), (cx + 0.6 * u, dtop + 3.05 * u)])
    # distance marker
    arrow(img, (cx + 4.35 * u, dbot + 0.9 * u), (cx + 4.35 * u, dtop + 0.65 * u), NAVY, w=10, head=34)
    arrow(img, (cx + 4.35 * u, dtop + 0.65 * u), (cx + 4.35 * u, dbot + 0.9 * u), NAVY, w=10, head=34)
    f = LBL(38)
    callout(img, (cx - 1.9 * u, dtop + 0.6 * u), (x0 + 1.6 * u, y0 + 0.35 * u), "Monitor centred, at eye level", f, col=TEAL)
    callout(img, (cx + 3.2 * u, dtop + 0.8 * u), (x1 - 1.6 * u, y0 + 0.35 * u), "Light from the side", f)
    pill(img, (cx + 4.2 * u, (dtop + dbot) / 2 + 0.5 * u), "Arm's length", font("Bold", 34), fg=WHITE, bg=NAVY, pad=(16, 10), anchor="rm")
    callout(img, (kb[0], kb[3]), (x0 + 1.4 * u, dbot + 1.35 * u), "Keyboard in line with you", f, col=TEAL)
    callout(img, (cx + 1.65 * u, dtop + 3.2 * u), (x1 - 1.6 * u, dbot + 1.35 * u), "Mouse close by", f)
    callout(img, (cx, dbot + 2.45 * u), ((x0 + x1) / 2, y1 - 0.25 * u), "Chair tucked in, elbows at your sides", f, col=NAVY)


def sc_topdown_keyboard(img, box, pin):
    """Pin 20: keyboard & mouse placement."""
    x0, y0, x1, y1 = box
    u = fit_u(box, 7.6, 9.0)
    cx = (x0 + x1) / 2
    dtop = y0 + 0.9 * u
    dbot = dtop + 3.6 * u
    rrect(img, (x0 + 0.2 * u, dtop, x1 - 0.2 * u, dbot), 0.3 * u, fill=WOOD)
    kb = td_keyboard(img, (cx - 0.3 * u, dtop + 2.35 * u), u, w=2.6)
    mouse = (cx + 1.55 * u, dtop + 2.4 * u)
    td_mouse(img, mouse, u)
    rrect(img, (kb[0], kb[3] + 0.12 * u, kb[2], kb[3] + 0.45 * u), 0.15 * u, fill=MUSTARD)
    pal = person(shirt=CORAL, skin=0, hair=1)
    hc = (cx, dbot + 1.55 * u)
    td_person(img, hc, u, pal, arms_to=[(cx - 0.75 * u, dtop + 2.55 * u), (mouse[0], mouse[1] + 0.35 * u)])
    dashed(img, (cx, dtop + 0.3 * u), (cx, hc[1] - 0.6 * u), TEAL, w=7)
    f = LBL(38)
    callout(img, (cx, dtop + 0.6 * u), (x0 + 1.9 * u, y0 + 0.2 * u), "Centre on your body", f, col=TEAL)
    callout(img, (mouse[0], mouse[1] - 0.4 * u), (x1 - 1.7 * u, y0 + 0.2 * u), "Mouse right beside it", f)
    callout(img, (kb[0] + 0.3 * u, kb[3] + 0.3 * u), (x0 + 1.7 * u, dbot + 0.75 * u), "Wrists straight", f, col=TEAL)
    callout(img, (cx - 1.2 * u, hc[1] - 0.5 * u), (x0 + 1.7 * u, y1 - 0.9 * u), "Elbows by your sides", f)
    callout(img, (cx + 1.2 * u, hc[1] - 0.5 * u), (x1 - 1.7 * u, y1 - 0.9 * u), "Shoulders relaxed", f, col=TEAL)
    # side inset: height
    pill(img, ((x0 + x1) / 2, y1 - 0.2 * u), "Keys at elbow height, not higher", LBL(40), fg=WHITE, bg=NAVY, pad=(34, 18))


def sc_flatlay(img, box, pin):
    """Pin 29: what helps posture at a desk — flat lay of items."""
    x0, y0, x1, y1 = box
    rrect(img, box, 44, fill=WOOD)
    items = pin["items"]
    cols, rows = 2, 3
    cw = (x1 - x0) / cols
    rh = (y1 - y0) / rows
    f = LBL(38)
    for i, (kind, label) in enumerate(items):
        r, c = divmod(i, cols)
        cc = (x0 + cw * (c + 0.5), y0 + rh * r + rh * 0.44)
        u = min(cw, rh) / 5.2
        if kind == "lumbar":
            ImageDraw.Draw(img).rounded_rectangle([cc[0] - 1.7 * u, cc[1] - 0.9 * u, cc[0] + 1.7 * u, cc[1] + 0.9 * u], radius=0.9 * u, fill=TEAL)
            seg(img, (cc[0] - 2.2 * u, cc[1]), (cc[0] - 1.6 * u, cc[1]), 0.16 * u, NAVY)
            seg(img, (cc[0] + 1.6 * u, cc[1]), (cc[0] + 2.2 * u, cc[1]), 0.16 * u, NAVY)
        elif kind == "laptop_stand":
            rrect(img, (cc[0] - 1.6 * u, cc[1] - 1.0 * u, cc[0] + 1.6 * u, cc[1] + 1.0 * u), 0.2 * u, fill=STEEL_LIGHT)
            rrect(img, (cc[0] - 1.3 * u, cc[1] - 0.75 * u, cc[0] + 1.3 * u, cc[1] + 0.75 * u), 0.15 * u, fill=shade(STEEL_LIGHT, 1.18))
        elif kind == "footrest":
            rrect(img, (cc[0] - 1.8 * u, cc[1] - 0.8 * u, cc[0] + 1.8 * u, cc[1] + 0.8 * u), 0.5 * u, fill=SAND)
            for k in range(-3, 4):
                circle(img, (cc[0] + k * 0.45 * u, cc[1]), 0.1 * u, fill=shade(SAND, 0.85))
        elif kind == "wrist_rest":
            td_keyboard(img, (cc[0], cc[1] - 0.45 * u), u * 0.9, w=3.4)
            rrect(img, (cc[0] - 1.55 * u, cc[1] + 0.25 * u, cc[0] + 1.55 * u, cc[1] + 0.7 * u), 0.2 * u, fill=NAVY)
        elif kind == "timer":
            circle(img, cc, 1.05 * u, fill=WHITE)
            ImageDraw.Draw(img).pieslice([cc[0] - 0.85 * u, cc[1] - 0.85 * u, cc[0] + 0.85 * u, cc[1] + 0.85 * u], 270, 360 + 30, fill=CORAL)
            circle(img, cc, 0.12 * u, fill=NAVY)
        elif kind == "band":
            ImageDraw.Draw(img).ellipse([cc[0] - 1.6 * u, cc[1] - 0.8 * u, cc[0] + 1.6 * u, cc[1] + 0.8 * u], outline=CORAL, width=int(0.28 * u))
            ImageDraw.Draw(img).ellipse([cc[0] - 1.2 * u, cc[1] - 0.55 * u, cc[0] + 1.35 * u, cc[1] + 0.7 * u], outline=MUSTARD, width=int(0.24 * u))
        elif kind == "monitor_riser":
            rrect(img, (cc[0] - 1.8 * u, cc[1] - 0.6 * u, cc[0] + 1.8 * u, cc[1] + 0.6 * u), 0.15 * u, fill=shade(WOOD, 0.75))
            rrect(img, (cc[0] - 1.8 * u, cc[1] - 0.6 * u, cc[0] + 1.8 * u, cc[1] - 0.35 * u), 0.1 * u, fill=shade(WOOD, 0.6))
        elif kind == "brace":
            d = ImageDraw.Draw(img)
            for s in (-1, 1):
                d.ellipse([cc[0] + s * 0.8 * u - 0.7 * u, cc[1] - 0.8 * u, cc[0] + s * 0.8 * u + 0.7 * u, cc[1] + 0.6 * u], outline=NAVY, width=int(0.22 * u))
            rrect(img, (cc[0] - 0.35 * u, cc[1] - 0.2 * u, cc[0] + 0.35 * u, cc[1] + 0.9 * u), 0.1 * u, fill=NAVY)
        pill(img, (cc[0], y0 + rh * r + rh * 0.86), label, f, fg=NAVY, bg=WHITE, pad=(22, 12))


def sc_scene_home(img, box, pin):
    """Pin 21: remote work set-up at home."""
    x0, y0, x1, y1 = box
    illo = (x0, y0, x1, y1 - 300)
    # window
    u = fit_u(illo, 7.6, 8.2)
    wx0, wy0 = x1 - 3.4 * u, y0 + 0.2 * u
    rrect(img, (wx0, wy0, wx0 + 2.8 * u, wy0 + 2.4 * u), 0.15 * u, fill=WHITE)
    rrect(img, (wx0 + 0.15 * u, wy0 + 0.15 * u, wx0 + 2.65 * u, wy0 + 2.25 * u), 0.1 * u, fill=(190, 222, 240))
    seg(img, (wx0 + 1.4 * u, wy0 + 0.15 * u), (wx0 + 1.4 * u, wy0 + 2.25 * u), 0.1 * u, WHITE)
    seg(img, (wx0 + 0.15 * u, wy0 + 1.2 * u), (wx0 + 2.65 * u, wy0 + 1.2 * u), 0.1 * u, WHITE)
    # wall art
    rrect(img, (x0 + 0.3 * u, y0 + 0.4 * u, x0 + 1.6 * u, y0 + 1.9 * u), 0.08 * u, fill=MUSTARD)
    circle(img, (x0 + 0.95 * u, y0 + 1.0 * u), 0.35 * u, fill=CORAL)
    pal = person(shirt=CORAL, pants=NAVY, skin=2, hair=1)
    j = desk_scene(img, illo, pal, u=u, laptop="stand", monitor=None, cx=x0 + 2.0 * u, footrest=False)
    # plant on desk
    px = j["desk_x1"] - 0.6 * u
    rrect(img, (px - 0.3 * u, j["desk_top"] - 0.6 * u, px + 0.3 * u, j["desk_top"]), 0.08 * u, fill=CORAL)
    for a in (-35, 0, 35):
        seg(img, (px, j["desk_top"] - 0.55 * u), add((px, j["desk_top"] - 0.55 * u), a, 0.8 * u), 0.22 * u, PLANT)
    tips = pin["tips"]
    chips_grid(img, (x0, y1 - 280, x1, y1), tips, cols=2, fnt=LBL(38), numbered=False, num_col=TEAL, row_h=120)


def sc_tall(img, box, pin):
    """Pin 24: tall person with raised desk & monitor."""
    x0, y0, x1, y1 = box
    pal = person(shirt=NAVY, pants=STEEL, skin=1, hair=0)
    u = fit_u(box, 7.8, 8.9)
    legs = (1.18, 1.16)
    j = desk_scene(img, box, pal, u=u, legs=legs, cx=x0 + 2.2 * u)
    f = LBL(38)
    top = j["monitor"][0]
    dashed(img, j["eye"], (top[0], j["eye"][1]), TEAL, w=7)
    callout(img, top, (x1 - 2.1 * u, y0 + 0.3 * u), "Raise monitor to eye level", f, col=TEAL)
    callout(img, (j["desk_x0"] + 0.4 * u, j["desk_top"]), (x1 - 1.9 * u, j["desk_top"] - 1.2 * u), "Higher desk surface", f)
    callout(img, (j["hip"][0] + 1.2 * u, j["hip"][1] + 0.5 * u), (x1 - 1.9 * u, j["floor"] - 1.9 * u), "Deeper seat for long thighs", f, col=TEAL)
    callout(img, j["knee"], (x1 - 1.9 * u, j["floor"] - 0.7 * u), "Knees ~90°, feet flat", f)
    # height ruler
    rx = x0 + 0.35 * u
    seg(img, (rx, j["head"][1] - 0.6 * u), (rx, j["floor"]), 10, NAVY)
    for k in range(0, 12):
        yy = j["floor"] - k * (j["floor"] - j["head"][1] + 0.6 * u) / 11
        seg(img, (rx, yy), (rx + (0.3 if k % 2 == 0 else 0.18) * u, yy), 6, NAVY)


def sc_student(img, box, pin):
    """Pin 28."""
    x0, y0, x1, y1 = box
    illo = (x0, y0, x1, y1 - 290)
    pal = person(shirt=MUSTARD, pants=(70, 110, 170), skin=3, hair=2)
    u = fit_u(illo, 7.4, 8.1)
    j = desk_scene(img, illo, pal, u=u, monitor=None, book=True, lamp=True, footrest=True, cx=x0 + 2.2 * u,
                   arms=dict(uarm=172, farm=100))
    # backpack
    bx = x0 + 0.5 * u
    rrect(img, (bx - 0.45 * u, j["floor"] - 1.3 * u, bx + 0.45 * u, j["floor"]), 0.3 * u, fill=CORAL)
    rrect(img, (bx - 0.3 * u, j["floor"] - 0.7 * u, bx + 0.3 * u, j["floor"] - 0.2 * u), 0.12 * u, fill=shade(CORAL, 0.8))
    f = LBL(38)
    callout(img, (j["hip"][0] + 3.0 * u, j["desk_top"] - 1.3 * u), (x1 - 2.1 * u, y0 + 0.3 * u), "Prop books up", f, col=TEAL)
    callout(img, (j["hip"][0] + 2.1 * u, j["floor"] - 0.3 * u), (x1 - 1.9 * u, j["floor"] - 0.9 * u), "Footrest if feet dangle", f)
    tips = pin["tips"]
    chips_grid(img, (x0, y1 - 270, x1, y1), tips, cols=2, fnt=LBL(38), numbered=False, row_h=115)


def sc_wrist(img, box, pin):
    """Pin 25: wrist angle bent vs neutral (close-up side view)."""
    x0, y0, x1, y1 = box
    mid = (y0 + y1) / 2
    for b, good in (((x0, y0, x1, mid - 20), False), ((x0, mid + 20, x1, y1), True)):
        panel(img, b, TEAL_LIGHT if good else CORAL_LIGHT)
        u = (b[3] - b[1]) / 4.6
        pal = person(shirt=NAVY, skin=1)
        desk_y = b[3] - 1.2 * u
        rrect(img, (b[0] + 0.3 * u, desk_y, b[2] - 0.3 * u, desk_y + 0.3 * u), 0.1 * u, fill=WOOD)
        ex = b[0] + 1.6 * u
        if good:
            elbow = (ex, desk_y - 1.05 * u)
            wrist = (ex + 3.0 * u, desk_y - 0.62 * u)
            hand = (wrist[0] + 1.0 * u, wrist[1] + 0.12 * u)
            rrect(img, (wrist[0] - 0.1 * u, desk_y - 0.32 * u, wrist[0] + 1.6 * u, desk_y), 0.08 * u, fill=STEEL)
            rrect(img, (wrist[0] - 0.9 * u, desk_y - 0.2 * u, wrist[0] - 0.05 * u, desk_y), 0.1 * u, fill=MUSTARD)
        else:
            elbow = (ex, desk_y - 0.35 * u)
            wrist = (ex + 3.0 * u, desk_y - 0.3 * u)
            hand = (wrist[0] + 0.85 * u, wrist[1] - 0.6 * u)
            polygon(img, [(wrist[0] + 0.1 * u, desk_y), (wrist[0] + 1.9 * u, desk_y), (wrist[0] + 1.9 * u, desk_y - 0.6 * u), (wrist[0] + 0.1 * u, desk_y - 0.25 * u)], STEEL)
        if good:
            knuckle = (wrist[0] + 0.85 * u, wrist[1] + 0.05 * u)
            tip = (knuckle[0] + 0.32 * u, knuckle[1] + 0.26 * u)
        else:
            knuckle = (wrist[0] + 0.72 * u, wrist[1] - 0.5 * u)
            tip = (knuckle[0] + 0.36 * u, knuckle[1] + 0.36 * u)
        seg(img, (elbow[0] - 0.9 * u, elbow[1] - 0.25 * u), elbow, 0.62 * u, pal["shirt"])
        seg(img, elbow, wrist, 0.5 * u, pal["skin"])
        seg(img, wrist, knuckle, 0.46 * u, pal["skin"])
        seg(img, knuckle, tip, 0.24 * u, pal["skin"])
        seg(img, (elbow[0] - 0.9 * u, elbow[1] - 0.25 * u), (elbow[0] - 0.2 * u, elbow[1] - 0.05 * u), 0.62 * u, pal["shirt"])
        # angle guide
        dashed(img, elbow, (wrist[0] + (wrist[0] - elbow[0]) * 0.45, wrist[1] + (wrist[1] - elbow[1]) * 0.45), TEAL if good else STEEL_LIGHT, w=7)
        if not good:
            glow(img, wrist, 0.55 * u, alpha=160)
        verdict(img, (b[2] - 0.3 * u - 260, b[1] + 70), good, "Neutral, straight wrist" if good else "Wrist bent upward", fnt=LBL(40))
        ImageDraw.Draw(img).text((b[0] + 50, b[1] + 70), "Forearm + hand in one line" if good else "Keyboard tilted, wrist cocked",
                                 font=font("Medium", 36), fill=INK, anchor="lm")


def sc_generic_desk(img, box, pin):
    """Simple annotated desk scene for pins that list tips beneath."""
    x0, y0, x1, y1 = box
    illo = (x0, y0, x1, y1 - 290)
    pal = person(**pin.get("pal", {}))
    u = fit_u(illo, 7.4, 8.2)
    j = desk_scene(img, illo, pal, u=u, cx=x0 + 2.2 * u, lumbar=pin.get("lumbar"))
    chips_grid(img, (x0, y1 - 270, x1, y1), pin["tips"], cols=2, fnt=LBL(38), numbered=False, row_h=115)
    return j


def sc_doorway(img, box, pin):
    """Pin 16: rounded shoulders - doorway stretch hero + mini tips."""
    x0, y0, x1, y1 = box
    illo = (x0, y0, x1, y1 - 300)
    u = fit_u(illo, 6.4, 9.4)
    floor = illo[3] - 0.1 * u
    cx = (x0 + x1) / 2 - 0.3 * u
    floor_line(img, x0 + 0.2 * u, x1 - 0.2 * u, floor, shade(STEEL_LIGHT, 1.2))
    # door frame (behind)
    fx = cx - 1.35 * u
    rrect(img, (fx - 0.35 * u, illo[1], fx + 0.05 * u, floor), 0.08 * u, fill=WOOD)
    rrect(img, (fx - 2.6 * u, illo[1], fx - 0.35 * u, floor), 0.08 * u, fill=shade(BG["cream"], 0.93))
    pal = person(shirt=TEAL, pants=NAVY, skin=1, hair=1)
    hip = (cx, floor - 4.15 * u - 0.28 * u)
    j = side_figure(img, hip, u, pal, lumbar=8, thoracic=6, neck=4, thigh=198, shin=182, fthigh=160, fshin=182,
                    uarm=262, farm=2, fuarm=262, ffarm=2)
    c = (j["shoulder"][0] + 0.9 * u, j["shoulder"][1] + 0.35 * u)
    arrow(img, c, (c[0] + 1.0 * u, c[1]), CORAL, w=0.12 * u, head=0.36 * u)
    f = LBL(38)
    callout(img, j["wrist"], (x0 + 1.2 * u, illo[1] + 0.4 * u), "Forearms on the frame", f, col=NAVY, anchor="mm")
    pill(img, (c[0] - 0.1 * u, c[1] + 0.75 * u), "Lean chest through gently", f, fg=WHITE, bg=CORAL, anchor="lm")
    chips = pin["tips"]
    chips_grid(img, (x0, y1 - 270, x1, y1), chips, cols=2, fnt=LBL(38), numbered=True, row_h=115)


SCENES = {
    "desk_guide": sc_desk_guide,
    "signs": sc_signs_compare,
    "forward_head": sc_forward_head,
    "exercise_grid": sc_exercise_grid,
    "pain": sc_pain,
    "headache": sc_headache,
    "timeline": sc_timeline,
    "before_after": sc_before_after,
    "monitor_height": sc_monitor_height,
    "chair_check": sc_chair_check,
    "stand_vs_sit": sc_stand_vs_sit,
    "lumbar": sc_lumbar,
    "laptop": sc_laptop,
    "wall_test": sc_wall_test,
    "chair_tips": sc_chair_tips,
    "topdown_setup": sc_topdown_setup,
    "topdown_keyboard": sc_topdown_keyboard,
    "flatlay": sc_flatlay,
    "home": sc_scene_home,
    "tall": sc_tall,
    "student": sc_student,
    "wrist": sc_wrist,
    "generic_desk": sc_generic_desk,
    "doorway": sc_doorway,
}
