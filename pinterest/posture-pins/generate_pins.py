"""Generate the 30 desk-posture Pinterest pins (1000x1500, 2:3) in the
"Plumb Line" style (see DESIGN_PHILOSOPHY.md).

    python pinterest/posture-pins/generate_pins.py            # all pins
    python pinterest/posture-pins/generate_pins.py 1 9 15     # selected pins

Each plate is composed as HTML + inline SVG and rendered with Chromium
(Playwright), then downsampled for crisp edges.  Also writes a contact
sheet, pins.csv and AFFILIATES.md.
"""

import csv
import os
import re
import sys
import tempfile

from PIL import Image

from plate import H, W, plate_html, render_all
from products import AMAZON_TAG, AMAZON_TAG_A, AMAZON_TAG_B, PRODUCTS, product_url
from scenes import SCENES

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "images")
BOARD = "Desk Posture & Ergonomics"

# head: "|" = line break, *word* = italic terracotta accent
PINS = [
    dict(n=1, slug="how-to-sit-properly-at-a-desk", keyword="how to sit properly at a desk",
         title="How to Sit Properly at Your Desk (Simple Guide)", text="Correct Desk Sitting Posture",
         head="Correct Desk|*Sitting* Posture",
         desc="A quick visual guide to proper desk sitting posture, from foot placement to screen height. Save this before your next long work session.",
         kicker="Desk posture guide", sub="Six checkpoints, from your feet to your screen.", scene="desk_guide",
         products=["lumbar_ec", "seat_ec", "udemy_correct"]),
    dict(n=2, slug="signs-of-bad-posture", keyword="signs of bad posture",
         title="7 Signs Your Posture Needs Fixing", text="Signs of Bad Posture",
         head="Signs of|*Bad* Posture",
         desc="Rounded shoulders, forward head, and constant neck tension are common signs your posture is off. Here's what to look for before it gets worse.",
         kicker="Seven signs to check", sub="The slump, traced over the posture it replaced.", scene="signs",
         products=["upright_go2", "brace_schiara"]),
    dict(n=3, slug="forward-head-posture-fix", keyword="forward head posture fix",
         title="How to Fix Forward Head Posture", text="Fix Forward Head Posture",
         head="Fix *Forward*|Head Posture",
         desc="Forward head posture from screen time can strain your neck and shoulders. These simple daily habits help bring your head back into alignment.",
         kicker="Neck alignment", sub="Bring your ears back over your shoulders.", scene="forward_head",
         products=["udemy_neck", "brace_comfy", "vivo_arm"]),
    dict(n=4, slug="tech-neck-exercises", keyword="tech neck exercises",
         title="Tech Neck Exercises You Can Do at Your Desk", text="Tech Neck Exercises",
         head="*Tech Neck*|Exercises",
         desc="Hours of looking down at screens can lead to tech neck. Try these quick stretches at your desk to relieve tension and improve alignment.",
         kicker="At-your-desk stretches", sub="Four moves, no equipment, right in your chair.", scene="exercise_grid",
         exercises=[("chin_tuck_seated", "Chin tucks", "10 reps"), ("side_neck", "Side neck stretch", "20 sec / side"),
                    ("upper_back_ext", "Upper-back extension", "8 reps"), ("shoulder_rolls", "Shoulder rolls", "10 backward")],
         products=["udemy_neck", "chirp_neck"]),
    dict(n=5, slug="upper-back-pain-from-sitting", keyword="upper back pain from sitting",
         title="Why Your Upper Back Hurts From Sitting All Day", text="Upper Back Pain From Sitting",
         head="Upper Back Pain|From *Sitting*",
         desc="Upper back pain often comes from prolonged sitting and poor desk posture. Understanding the cause is the first step to relief.",
         kicker="Why it happens", sub="The hunch that builds up, hour by hour.", scene="pain", area="upper_back",
         causes=["Hunching toward the screen", "No support behind the back", "Hours without moving"],
         products=["lumbar_ec", "chirp", "udemy_reverse"]),
    dict(n=6, slug="posture-correction-exercises-for-beginners", keyword="posture correction exercises for beginners",
         title="Posture Correction Exercises for Beginners", text="Posture Exercises for Beginners",
         head="Posture Exercises|for *Beginners*",
         desc="New to fixing your posture? These beginner-friendly exercises target the muscles that support better alignment, no equipment needed.",
         kicker="Start here", sub="Four easy moves that build better alignment.", scene="exercise_grid",
         exercises=[("wall_angels", "Wall angels", "8 slow reps"), ("chin_tuck_standing", "Chin tucks", "10 reps"),
                    ("chest_opener_stand", "Chest opener", "20 sec"), ("scap_squeeze", "Blade squeeze", "10 reps")],
         products=["udemy_reverse", "theraband"]),
    dict(n=7, slug="desk-stretches-every-hour", keyword="desk stretches every hour",
         title="Desk Stretches to Do Every Hour", text="Hourly Desk Stretch Routine",
         head="The *Hourly* Desk|Stretch Routine",
         desc="Sitting too long without moving can worsen posture problems. These quick stretches take under a minute and fit right at your desk.",
         kicker="Under one minute", sub="Set a timer. Run through these every hour.", scene="exercise_grid",
         badge="Every 60 minutes",
         exercises=[("overhead_reach", "Overhead reach", "10 sec"), ("side_bend", "Side bend", "10 sec / side"),
                    ("side_neck", "Neck tilt", "10 sec / side"), ("shoulder_rolls", "Shoulder rolls", "5 backward")],
         products=["timetimer", "udemy_15min"]),
    dict(n=8, slug="ergonomic-desk-setup-ideas", keyword="ergonomic desk setup ideas",
         title="Ergonomic Desk Setup Ideas for Better Posture", text="Ergonomic Desk Setup Ideas",
         head="*Ergonomic* Desk|Setup Ideas",
         desc="A few adjustments to your desk setup can make a big difference for your posture. See how monitor height, chair position, and keyboard placement work together.",
         kicker="Desk setup · plan view", sub="How monitor, keyboard and chair work together.", scene="topdown_setup",
         products=["vivo_arm", "sihoo_m57", "huanuo_dual"]),
    dict(n=9, slug="correct-monitor-height-for-posture", keyword="correct monitor height for posture",
         title="The Right Monitor Height for Better Posture", text="Correct Monitor Height",
         head="Correct|*Monitor* Height",
         desc="A monitor set too low or too high can strain your neck without you noticing. Here's how to find the right eye-level height.",
         kicker="Screen setup", sub="Find your eye-level height in thirty seconds.", scene="monitor_height",
         products=["vivo_arm", "huanuo_dual", "nulaxy"]),
    dict(n=10, slug="how-to-choose-an-ergonomic-chair", keyword="how to choose an ergonomic chair",
         title="How to Choose an Ergonomic Chair That Actually Helps", text="Choosing an Ergonomic Chair",
         head="Choosing an|Ergonomic *Chair*",
         desc="Not every \"ergonomic\" chair supports your posture the same way. Here's what to check before you decide on one.",
         kicker="Buyer's checklist", sub="Five things to check before you buy.", scene="chair_check",
         products=["sihoo_m57", "steelcase_s1"]),
    dict(n=11, slug="standing-desk-vs-sitting-desk-posture", keyword="standing desk vs sitting desk posture",
         title="Standing Desk or Sitting Desk: Which Helps Posture More", text="Standing Desk vs Sitting Desk",
         head="*Standing* Desk vs|Sitting Desk",
         desc="Both setups can support better posture when used correctly. Here's how they compare for people who sit most of the day.",
         kicker="Side by side", sub="What good posture looks like in each.", scene="stand_vs_sit",
         products=["flexispot_e7", "flexispot_conv"]),
    dict(n=12, slug="lumbar-support-pillow-for-office-chair", keyword="lumbar support pillow for office chair",
         title="Do You Need a Lumbar Support Pillow at Your Desk", text="Lumbar Support at Your Desk",
         head="*Lumbar* Support|at Your Desk",
         desc="Lower back pain from sitting often comes down to missing support at the curve of your spine. Here's how a lumbar pillow can help.",
         kicker="Lower back support", sub="Where it goes, and what it does.", scene="lumbar",
         products=["lumbar_ec"]),
    dict(n=13, slug="posture-corrector-before-and-after", keyword="posture corrector before and after",
         title="What Changes With a Posture Corrector (Before and After)", text="Posture Correction: Before & After",
         head="Posture Correction:|Before &amp; *After*",
         desc="Consistent posture correction habits can visibly change shoulder and neck alignment over time. Here's a realistic look at what changes and what takes time.",
         kicker="Realistic results", sub="Typical alignment change, overlaid on one plumb line.", scene="before_after",
         labels=[("Before", "Head forward, shoulders round"), ("After", "Ears, shoulders, hips stacked")],
         fixes=["Daily habits", "Upper-back strength", "Screen at eye level"],
         products=["brace_schiara", "upright_go2", "udemy_reverse"]),
    dict(n=14, slug="how-long-does-it-take-to-fix-posture", keyword="how long does it take to fix posture",
         title="How Long Does It Actually Take to Fix Your Posture", text="How Long to Fix Posture",
         head="How *Long* to|Fix Posture",
         desc="Posture doesn't change overnight, but small consistent habits add up. Here's a realistic timeline for noticeable improvement.",
         kicker="A realistic timeline", sub="Small daily habits, stacked over weeks.", scene="timeline",
         stages=[("Week 1–2", "You notice when you slouch"), ("Week 3–4", "Less neck and shoulder tension"),
                 ("Week 6–8", "Upright feels easier to hold"), ("Month 3+", "Better posture is the default")],
         products=["udemy_15min", "upright_go2"]),
    dict(n=15, slug="laptop-stand-for-posture", keyword="laptop stand for posture",
         title="Why a Laptop Stand Can Help Your Posture", text="Laptop Stand for Better Posture",
         head="A *Laptop Stand*|for Better Posture",
         desc="Working directly on a laptop often means looking down and hunching forward. Raising the screen with a stand can change that.",
         kicker="Laptop users", sub="Raise the screen. Add a keyboard.", scene="laptop",
         products=["nulaxy", "k860"]),
    dict(n=16, slug="rounded-shoulders-fix", keyword="rounded shoulders fix",
         title="How to Fix Rounded Shoulders From Desk Work", text="Fix Rounded Shoulders",
         head="Fix *Rounded*|Shoulders",
         desc="Rounded shoulders are common after years of desk work and can affect posture beyond your upper body. These exercises help reverse the pattern.",
         kicker="Open the chest", sub="The doorway stretch, and three moves to pair with it.", scene="doorway",
         tips=["Doorway stretch · 30 sec", "Band pull-aparts · 12", "Wall angels · 8", "Chin tucks · 10"],
         products=["theraband", "udemy_reverse"]),
    dict(n=17, slug="neck-pain-from-working-on-computer", keyword="neck pain from working on computer",
         title="Why Your Neck Hurts After a Full Day at the Computer", text="Neck Pain From Computer Work",
         head="Neck Pain From|*Computer* Work",
         desc="Neck pain after long computer sessions usually points to posture and screen position. Small setup changes can reduce the strain.",
         kicker="Screen + posture", sub="Your screen height may be the real culprit.", scene="pain", area="neck",
         causes=["Screen below eye level", "Head drifting forward", "No breaks for hours"],
         products=["vivo_arm", "nulaxy", "restcloud"]),
    dict(n=18, slug="how-to-check-your-posture-at-home", keyword="how to check your posture at home",
         title="A Simple Way to Check Your Posture at Home", text="Check Your Posture at Home",
         head="Check Your Posture|at *Home*",
         desc="You don't need special equipment to see how your posture looks. This simple wall test takes less than a minute.",
         kicker="The sixty-second wall test", sub="No equipment. Just a wall.", scene="wall_test",
         steps=[("Stand tall", "Heels a few inches from a wall."), ("Touch four points", "Head, shoulders, hips, heels."),
                ("Check the gap", "Slide a hand behind the low back."), ("Read it", "About a palm's width is good.")],
         products=["upright_go2", "udemy_correct"]),
    dict(n=19, slug="office-chair-posture-tips", keyword="office chair posture tips",
         title="Office Chair Posture Tips That Actually Work", text="Office Chair Posture Tips",
         head="Office Chair|Posture *Tips*",
         desc="How you sit in your chair matters as much as the chair itself. These small adjustments can improve your posture right away.",
         kicker="Use the chair you have", sub="Small adjustments, big difference.", scene="chair_tips",
         tips=["Sit all the way back", "Add lumbar support", "Thighs parallel to floor", "Armrests at elbow height", "Feet flat on the floor"],
         products=["lumbar_ec", "seat_ec"]),
    dict(n=20, slug="keyboard-and-mouse-placement-for-posture", keyword="keyboard and mouse placement for posture",
         title="Keyboard and Mouse Placement for Better Posture", text="Keyboard and Mouse Placement",
         head="Keyboard &amp; Mouse|*Placement*",
         desc="Reaching too far or too high for your keyboard and mouse can throw off your whole upper body posture. Here's where they should sit.",
         kicker="Plan view", sub="Keep everything close, and centred on you.", scene="topdown_keyboard",
         products=["k860", "gimars"]),
    dict(n=21, slug="posture-correction-for-remote-workers", keyword="posture correction for remote workers",
         title="Posture Correction Tips for People Who Work From Home", text="Posture Tips for Remote Work",
         head="Posture Tips for|*Remote* Work",
         desc="Working from home often means less structured breaks and makeshift desk setups. These tips help protect your posture through the workday.",
         kicker="Work from home", sub="Turn a makeshift desk into a good one.", scene="home",
         tips=["Raise the laptop screen", "Use a separate keyboard", "Support the lower back", "Move every hour"],
         products=["nulaxy", "lumbar_ec", "footrest_ec"]),
    dict(n=22, slug="5-minute-posture-reset", keyword="posture exercises for beginners at desk",
         title="5-Minute Posture Reset You Can Do at Your Desk", text="5-Minute Posture Reset",
         head="The *5-Minute*|Posture Reset",
         desc="A short posture reset between meetings can undo some of the slouching from sitting. Here's a quick routine to try today.",
         kicker="Between meetings", sub="Four moves, five minutes, stay in your chair.", scene="exercise_grid",
         badge="Five minutes total",
         exercises=[("shoulder_rolls", "Shoulder rolls", "1 min"), ("chin_tuck_seated", "Chin tucks", "1 min"),
                    ("chest_opener_seated", "Chest opener", "1 min"), ("overhead_reach", "Reach + breathe", "2 min")],
         products=["timetimer", "theraband"]),
    dict(n=23, slug="text-neck-posture-correction", keyword="text neck posture correction",
         title="What Is Text Neck and How to Correct It", text="What Is Text Neck",
         head="What Is|*Text Neck?*",
         desc="Text neck develops from constantly looking down at phones and screens. Here's what it looks like and how to start correcting it.",
         kicker="Phone posture", sub="Bring the phone up, not your head down.", scene="phone",
         labels=[("Text neck", "Head bent down to the phone"), ("Better", "Phone raised toward the eyes")],
         fixes=["Raise the phone", "Chin tucks", "Screen breaks"],
         products=["udemy_textneck", "brace_comfy"]),
    dict(n=24, slug="posture-correction-for-tall-people", keyword="posture correction for tall people",
         title="Posture Correction Tips for Tall People at a Desk", text="Posture Tips for Tall People",
         head="Posture Tips for|*Tall* People",
         desc="A standard desk setup doesn't always work for taller bodies, which can lead to extra strain. Here's how to adjust it properly.",
         kicker="For taller bodies", sub="Adjust the desk to you, not the other way.", scene="tall",
         products=["flexispot_e7", "huanuo_dual"]),
    dict(n=25, slug="wrist-pain-from-typing-posture", keyword="wrist pain from typing posture",
         title="How Your Posture Affects Wrist Pain From Typing", text="Wrist Pain From Typing",
         head="Wrist Pain|From *Typing*",
         desc="Wrist pain while typing is often connected to arm and shoulder posture, not just hand position. Here's how they're related.",
         kicker="Typing posture", sub="Keep forearm and hand in one line.", scene="wrist",
         products=["gimars", "k860"]),
    dict(n=26, slug="posture-correction-routine-morning", keyword="posture correction routine morning",
         title="A Morning Routine to Support Better Posture All Day", text="Morning Posture Routine",
         head="A *Morning*|Posture Routine",
         desc="A few minutes of movement before you sit down can set your posture up for the whole day. Here's a simple routine to start with.",
         kicker="Before you sit down", sub="A five-minute wake-up for your spine.", scene="exercise_grid",
         badge="Every morning",
         exercises=[("overhead_reach_stand", "Full-body reach", "5 breaths"), ("side_bend_stand", "Side bend", "5 breaths / side"),
                    ("chest_opener_stand", "Chest opener", "20 sec"), ("wall_angels", "Wall angels", "8 reps")],
         products=["udemy_15min", "theraband"]),
    dict(n=27, slug="tension-headache-from-posture", keyword="tension headache from posture",
         title="Can Bad Posture Cause Tension Headaches", text="Posture and Tension Headaches",
         head="Posture &amp; Tension|*Headaches*",
         desc="Tension headaches are sometimes linked to tight neck and shoulder muscles from poor desk posture. Here's what the connection looks like.",
         kicker="The neck connection", sub="How tight neck and shoulders can add up.", scene="headache",
         products=["chirp_neck", "udemy_neck", "restcloud"]),
    dict(n=28, slug="posture-correction-for-students-studying", keyword="posture correction for students studying",
         title="Posture Tips for Students Studying at a Desk", text="Posture Tips for Studying",
         head="Posture Tips for|*Studying*",
         desc="Long study sessions can lead to the same posture issues as desk jobs. These tips help students stay comfortable through longer sessions.",
         kicker="Study smarter", sub="Stay comfortable through long sessions.", scene="student",
         tips=["Prop books or laptop up", "Keep feet supported", "Back against the chair", "Break every 45 min"],
         products=["nulaxy", "footrest_ec", "seat_ec"]),
    dict(n=29, slug="things-that-help-posture-at-a-desk", keyword="things that help posture at a desk",
         title="Simple Things That Actually Help Posture at a Desk", text="What Helps Desk Posture",
         head="What *Helps*|Desk Posture",
         desc="You don't need a full desk overhaul to support better posture. These small, practical changes make a noticeable difference.",
         kicker="Small upgrades", sub="Six simple things worth trying.", scene="flatlay",
         items=[("lumbar", "Lumbar pillow"), ("laptop_stand", "Laptop stand"), ("footrest", "Footrest"),
                ("wrist_rest", "Wrist rest"), ("timer", "Break timer"), ("band", "Resistance band")],
         products=["lumbar_ec", "nulaxy", "footrest_ec", "gimars", "timetimer", "theraband"]),
    dict(n=30, slug="posture-correction-timeline-what-to-expect", keyword="posture correction timeline what to expect",
         title="What to Expect When You Start Correcting Your Posture", text="What to Expect Fixing Posture",
         head="What to *Expect*|Fixing Posture",
         desc="The first few weeks of posture correction can feel more noticeable than comfortable. Here's what's normal and what to watch for.",
         kicker="Week by week", sub="What's normal as your body adjusts.", scene="timeline",
         stages=[("Week 1", "Upright feels awkward"), ("Week 2–3", "Mild muscle fatigue is common"),
                 ("Week 4–6", "Habits start to stick"), ("Week 8+", "Good posture feels natural")],
         products=["udemy_reverse", "upright_go2"]),
]

HEAD_TOP = 118
HEAD_LH = 102


def headline_html(head):
    return "<br>".join(re.sub(r"\*(.+?)\*", r"<em>\1</em>", part) for part in head.split("|"))


def build(pin, tmp, variant="a"):
    lines = pin["head"].count("|") + 1
    lh = HEAD_LH if variant == "a" else 121
    sub_top = HEAD_TOP + lines * lh + 14
    art_top = sub_top + (70 if variant == "a" else 130)
    art = SCENES[pin["scene"]](pin, art_top)
    page = dict(pin, headline_html=headline_html(pin["head"]))
    html = plate_html(page, art, sub_top, variant)
    hp = os.path.join(tmp, f"{pin['n']:02d}{variant}.html")
    with open(hp, "w", encoding="utf-8") as fh:
        fh.write(html)
    return hp, os.path.join(tmp, f"{pin['n']:02d}{variant}.png")


def finish(pin, raw, variant="a"):
    im = Image.open(raw).convert("RGB")
    if im.size != (W, H):
        im = im.resize((W, H), Image.LANCZOS)
    if variant == "a":
        path = os.path.join(OUT, f"{pin['n']:02d}-{pin['slug']}.png")
    else:
        os.makedirs(os.path.join(OUT, "ab-test"), exist_ok=True)
        path = os.path.join(OUT, "ab-test", f"{pin['n']:02d}-{pin['slug']}-B.png")
    im.save(path, optimize=True)
    return path


def contact_sheet(paths, name="contact-sheet.png", cols=6):
    tw, th = 250, 375
    rows = (len(paths) + cols - 1) // cols
    sheet = Image.new("RGB", (cols * (tw + 16) + 16, rows * (th + 16) + 16), (226, 221, 212))
    for i, p in enumerate(paths):
        im = Image.open(p).resize((tw, th), Image.LANCZOS)
        r, c = divmod(i, cols)
        sheet.paste(im, (16 + c * (tw + 16), 16 + r * (th + 16)))
    path = os.path.join(HERE, name)
    sheet.save(path, optimize=True)
    return path


def alt_text(pin):
    return f"Illustration: {pin['text']} - {pin['sub'].rstrip('.?')}. {pin['title']}."


def write_csv(pins):
    path = os.path.join(HERE, "pins.csv")
    with open(path, "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["#", "Image file", "Title", "Description", "Alt text", "Keywords", "Pinterest board",
                    "Link (primary affiliate)", "Primary product", "Other products"])
        for pin in pins:
            prim = PRODUCTS[pin["products"][0]]
            others = "; ".join(f"{PRODUCTS[k]['name']} <{product_url(k)}>" for k in pin["products"][1:])
            w.writerow([pin["n"], f"images/{pin['n']:02d}-{pin['slug']}.png", pin["title"], pin["desc"],
                        alt_text(pin), pin["keyword"], BOARD, product_url(pin["products"][0]), prim["name"], others])
    return path


def write_affiliates_md(pins):
    """Per-pin product table (kept in sync with PINS / PRODUCTS)."""
    path = os.path.join(HERE, "AFFILIATES.md")
    lines = ["# Pin ごとのアフィリエイト商品", "",
             "`generate_pins.py` が自動生成します（手で編集しないでください）。",
             f"Amazon リンクのタグは現在 `{AMAZON_TAG}`。`AMAZON_TAG=yourid-20 python generate_pins.py` で差し替えできます。", "",
             "| # | ピン | 商品（1つ目がピンのリンク先） | プログラム |", "|---|---|---|---|"]
    for pin in pins:
        prods = "<br>".join(f"[{PRODUCTS[k]['name']}]({product_url(k)})" for k in pin["products"])
        progs = "<br>".join(PRODUCTS[k]["program"] for k in pin["products"])
        lines.append(f"| {pin['n']} | {pin['text']} | {prods} | {progs} |")
    lines += ["", "## 直販アフィリエイト（Amazon より料率が高い候補）", ""]
    for p in PRODUCTS.values():
        if p.get("alt_url"):
            lines.append(f"- {p['name']}: {p['alt_url']}")
    with open(path, "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines) + "\n")
    return path


AB_TEST = {1: ("6", "checkpoints"), 2: ("7", "signs"), 4: ("4", "moves"), 14: ("3", "months"), 22: ("5", "minutes")}


def write_ab_csv():
    """Both variants of the A/B test pins, each with its own Amazon tracking ID."""
    path = os.path.join(HERE, "pins-ab-test.csv")
    with open(path, "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["#", "Variant", "Image file", "Title", "Description", "Alt text", "Keywords", "Pinterest board",
                    "Link (primary affiliate)"])
        for pin in PINS:
            if pin["n"] not in AB_TEST:
                continue
            for v, img, tag in (("A", f"images/{pin['n']:02d}-{pin['slug']}.png", AMAZON_TAG_A),
                                ("B", f"images/ab-test/{pin['n']:02d}-{pin['slug']}-B.png", AMAZON_TAG_B)):
                w.writerow([pin["n"], v, img, pin["title"], pin["desc"], alt_text(pin), pin["keyword"], BOARD,
                            product_url(pin["products"][0], tag)])
    return path


def main_ab():
    todo = [dict(p, badge_b=AB_TEST[p["n"]]) for p in PINS if p["n"] in AB_TEST]
    with tempfile.TemporaryDirectory() as tmp:
        jobs = [build(p, tmp, "b") for p in todo]
        render_all(jobs, tmp, scale=2)
        paths = [finish(p, png, "b") for p, (_, png) in zip(todo, jobs)]
    for p in paths:
        print("wrote", os.path.relpath(p, HERE))
    print("wrote", os.path.relpath(contact_sheet(paths, "ab-test-sheet.png", cols=5), HERE))
    print("wrote", os.path.relpath(write_ab_csv(), HERE))


def main(argv):
    if argv[:1] == ["--ab"]:
        return main_ab()
    want = {int(a) for a in argv} if argv else None
    todo = [p for p in PINS if not want or p["n"] in want]
    os.makedirs(OUT, exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        jobs = [build(p, tmp) for p in todo]
        render_all(jobs, tmp, scale=2)
        paths = [finish(p, png) for p, (_, png) in zip(todo, jobs)]
    for p in paths:
        print("wrote", os.path.relpath(p, HERE))
    if not want:
        print("wrote", os.path.relpath(contact_sheet(paths), HERE))
        print("wrote", os.path.relpath(write_csv(PINS), HERE))
        print("wrote", os.path.relpath(write_affiliates_md(PINS), HERE))
    print("Amazon tag in links:", AMAZON_TAG)


if __name__ == "__main__":
    main(sys.argv[1:])
