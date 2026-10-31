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
from svgkit import TERRA
from products import AMAZON_TAG, AMAZON_TAG_A, AMAZON_TAG_B, PRODUCTS, product_url
from scenes import SCENES
from scenes2 import SCENES2

SCENES.update(SCENES2)
from scenes3 import SCENES3  # noqa: E402
SCENES.update(SCENES3)
from scenes4 import SCENES4  # noqa: E402
SCENES.update(SCENES4)
from scenes5 import SCENES5  # noqa: E402
SCENES.update(SCENES5)

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
         products=["vivo_arm", "brace_comfy", "udemy_neck"]),
    dict(n=4, slug="tech-neck-exercises", keyword="tech neck exercises",
         title="Tech Neck Exercises You Can Do at Your Desk", text="Tech Neck Exercises",
         head="*Tech Neck*|Exercises",
         desc="Hours of looking down at screens can lead to tech neck. Try these quick stretches at your desk to relieve tension and improve alignment.",
         kicker="At-your-desk stretches", sub="Four moves, no equipment, right in your chair.", scene="exercise_grid",
         exercises=[("chin_tuck_seated", "Chin tucks", "10 reps"), ("side_neck", "Side neck stretch", "20 sec / side"),
                    ("upper_back_ext", "Upper-back extension", "8 reps"), ("shoulder_rolls", "Shoulder rolls", "10 backward")],
         products=["chirp_neck", "udemy_neck"]),
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
         products=["theraband", "udemy_reverse"]),
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
         products=["upright_go2", "udemy_15min"]),
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
         products=["brace_comfy", "udemy_textneck"]),
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
         products=["theraband", "udemy_15min"]),
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
         products=["upright_go2", "udemy_reverse"]),
]

# ---- batch 2: chairs and desk setup (best-performing topic in the first month)
PINS += [
    dict(n=31, slug="how-to-set-office-chair-height", keyword="office chair height",
         title="How to Set Your Office Chair to the Right Height", text="Set Your Chair Height",
         head="Set Your Chair to|the *Right* Height",
         desc="Most chairs are set too high or too low. Use your knee height as the guide: feet flat, thighs level, knees near 90 degrees. Takes one minute.",
         kicker="Chair setup", sub="Use your own knee height as the guide.", scene="chair_annot",
         dims=["seat_height", "knee"], arm=False,
         callouts=[("hip", "Thighs level with the floor", "L", 40), ("toe", "Feet flat, not dangling", "R", 760),
                   ("gas", "Lever sets the height", "R", 640)],
         products=["sihoo_m57", "footrest_ec"]),
    dict(n=32, slug="best-office-chair-features-for-back-pain", keyword="office chair for back pain",
         title="What to Look For in an Office Chair for Back Pain", text="Office Chair for Back Pain",
         head="Office Chair for|*Back Pain*",
         desc="If your back aches after sitting, these chair features matter most: adjustable lumbar support, seat depth, recline and armrests. A quick checklist before you buy.",
         kicker="Buyer's checklist", sub="Four features that matter most for your back.", scene="chair_annot",
         dims=["lumbar_ring"], lumbar_col=TERRA,
         callouts=[("lumbar", "Adjustable lumbar support", "L", 40), ("backrest", "Reclines and locks", "L", 110),
                   ("armrest", "Armrests that adjust", "R", 40), ("seat_front", "Seat depth slides", "R", 520)],
         products=["steelcase_s1", "sihoo_m57", "lumbar_ec"]),
    dict(n=33, slug="ergonomic-chair-vs-gaming-chair", keyword="ergonomic chair vs gaming chair",
         title="Ergonomic Chair vs Gaming Chair: Which Is Better for Posture", text="Ergonomic vs Gaming Chair",
         head="Ergonomic vs|*Gaming* Chair",
         desc="Gaming chairs look supportive, but posture comes from adjustability. Here's how an ergonomic chair compares for long workdays at a desk.",
         kicker="Side by side", sub="Which one actually supports long workdays?", scene="chair_compare",
         compare=[("Lumbar adjusts to your spine", "Fixed lumbar pillow"), ("Breathable mesh back", "Padded back runs warm"),
                  ("Seat depth adjusts", "Bucket seat limits movement")],
         verdict="For long workdays, adjustability beats looks.",
         products=["sihoo_m57", "steelcase_s1"]),
    dict(n=34, slug="do-you-need-a-monitor-arm", keyword="monitor arm for posture",
         title="Do You Need a Monitor Arm? Before and After", text="Do You Need a Monitor Arm?",
         head="Do You Need a|*Monitor Arm?*",
         desc="Most monitor stands leave the screen too low, so your head tips forward. A monitor arm lifts it to eye level and clears space on your desk.",
         kicker="Screen setup", sub="Same desk, same person, different screen height.", scene="monitor_arm",
         products=["vivo_arm", "huanuo_dual"]),
    dict(n=35, slug="dual-monitor-setup-for-posture", keyword="dual monitor setup ergonomics",
         title="How to Set Up Dual Monitors Without Neck Strain", text="Dual Monitor Setup",
         head="*Dual Monitor*|Setup Guide",
         desc="Two screens can mean hours with your head turned. Put your main screen straight ahead, angle the second toward you, and keep both at the same height.",
         kicker="Desk setup · plan view", sub="Keep your head straight for most of the day.", scene="dual_monitor",
         tips=["Use one screen more? Centre it", "Use both equally? Centre the seam", "Same height for both", "Arm's length away"],
         products=["huanuo_dual", "vivo_arm"]),
    dict(n=36, slug="standing-desk-height-guide", keyword="standing desk height",
         title="Standing Desk Height Guide for Better Posture", text="Standing Desk Height Guide",
         head="Standing Desk|*Height* Guide",
         desc="Set your standing desk to elbow height and your screen to eye level. A cushioned mat and soft knees make standing time more comfortable.",
         kicker="Standing desks", sub="Elbows, screen and feet, in one picture.", scene="standing_height",
         products=["flexispot_e7", "flexispot_conv"]),
    dict(n=37, slug="standing-desk-converter-vs-standing-desk", keyword="standing desk converter vs standing desk",
         title="Standing Desk Converter vs Standing Desk: Which to Choose", text="Converter vs Standing Desk",
         head="*Converter* vs|Standing Desk",
         desc="A desk converter sits on top of your current desk; a standing desk raises the whole surface. Here's how to choose for your space and budget.",
         kicker="Side by side", sub="Two ways to stand while you work.", scene="converter_vs_desk",
         compare=[("Keeps your current desk", "Replaces your desk"), ("Lower cost, no assembly", "More surface space"),
                  ("Good for renters", "Smoother height changes")],
         products=["flexispot_conv", "flexispot_e7"]),
    dict(n=38, slug="office-chair-setup-in-5-steps", keyword="how to adjust office chair",
         title="How to Adjust Your Office Chair in 5 Steps", text="Adjust Your Chair in 5 Steps",
         head="Adjust Your Chair|in *5 Steps*",
         desc="Height, depth, lumbar, armrests, recline. Adjust them in this order and your chair will support you instead of fighting you.",
         kicker="Chair setup", sub="Do them in this order.", scene="chair_annot",
         callouts=[("gas", "Height: feet flat", "R", 700), ("seat_front", "Depth: 2–3 finger gap", "R", 560),
                   ("lumbar", "Lumbar: into the curve", "L", 40), ("armrest", "Arms: at elbow height", "R", 40),
                   ("backrest", "Recline: 100–110°", "L", 110)],
         products=["lumbar_ec", "seat_ec", "footrest_ec"]),
    dict(n=39, slug="ergonomic-home-office-essentials", keyword="ergonomic home office essentials",
         title="6 Ergonomic Home Office Essentials Worth Buying", text="Ergonomic Office Essentials",
         head="Ergonomic Office|*Essentials*",
         desc="Six small upgrades that make a home office easier on your neck, back and wrists: monitor arm, laptop stand, lumbar pillow, seat cushion, footrest and wrist rest.",
         kicker="Small upgrades", sub="Six things that make a desk easier on your body.", scene="essentials",
         items=[("monitor_arm", "Monitor arm"), ("laptop_stand", "Laptop stand"), ("lumbar", "Lumbar pillow"),
                ("seat_cushion", "Seat cushion"), ("footrest", "Footrest"), ("wrist_rest", "Wrist rest")],
         products=["vivo_arm", "nulaxy", "lumbar_ec", "seat_ec", "footrest_ec", "gimars"]),
    dict(n=40, slug="office-chair-seat-depth", keyword="office chair seat depth",
         title="Seat Depth: The Chair Setting Most People Miss", text="The Chair Setting You Miss",
         head="The Chair Setting|Most People *Miss*",
         desc="If your chair seat presses into the back of your knees, it's too deep. Leave a 2-3 finger gap, or add a lumbar pillow to bring you forward.",
         kicker="Seat depth", sub="Leave a small gap behind your knees.", scene="chair_annot", zoom=True, arm=False,
         dims=["seat_depth"],
         callouts=[("seat_front", "Gap behind the knees", "R", 160), ("lumbar", "Pillow if the seat is too deep", "L", 160)],
         products=["lumbar_ec", "sihoo_m57"]),
]

# ---- batch 3: quick setup fixes and accessories
PINS += [
    dict(n=41, slug="desk-too-high-fix", keyword="desk too high",
         title="Desk Too High? Raise Your Chair, Then Add a Footrest", text="Desk Too High? Easy Fix",
         head="Is Your Desk|Too *High?*",
         desc="Most desks are built for tall people. If your shoulders creep up while you type, raise your chair until your elbows clear the desk, then add a footrest so your feet stay supported.",
         kicker="Quick fix", sub="Raise the chair, then bring the floor up to your feet.", scene="rig_compare",
         panels=[dict(tag="Desk too high", caption="Shoulders creep up", desk_raise=0.5,
                      pose=dict(uarm=164, farm=84, fuarm=162, ffarm=84), strain=["shoulder"]),
                 dict(tag="Chair up + footrest", caption="Elbows level with the desk", lift=0.5, desk_raise=0.5,
                      footrest=True)],
         products=["footrest_ec", "seat_ec"]),
    dict(n=42, slug="do-you-need-a-footrest", keyword="under desk footrest",
         title="Do You Need a Footrest? The 5-Second Test", text="Do You Need a Footrest?",
         head="Do You Need a|*Footrest?*",
         desc="Sit back in your chair. If your feet don't rest flat on the floor, the seat edge presses into your thighs. A footrest closes the gap in seconds.",
         kicker="5-second test", sub="If your feet don't reach the floor, yes.", scene="rig_compare",
         panels=[dict(tag="Feet dangling", caption="Seat edge presses the thighs", legs=0.82, gap=True,
                      strain=["knee"]),
                 dict(tag="With a footrest", caption="Feet supported, thighs level", legs=0.82, footrest=True)],
         products=["footrest_ec", "seat_ec"]),
    dict(n=43, slug="best-office-chair-recline-angle", keyword="office chair recline angle",
         title="Don't Sit at 90 Degrees: The Better Backrest Angle", text="Don't Sit at 90 Degrees",
         head="Don't Sit at|*90 Degrees*",
         desc="Sitting bolt upright isn't the goal. A slight recline of 100-110 degrees lets the backrest take some of your weight. Lock it there and keep the lumbar support in place.",
         kicker="Backrest angle", sub="A slight recline lets the chair carry some of your weight.", scene="chair_annot",
         recline=14, dims=["recline"], arm=False,
         pose=dict(lumbar=-8, thoracic=-12, neck=18, uarm=172, farm=128, fuarm=170, ffarm=128),
         callouts=[("backrest", "Lock the backrest here", "L", 40), ("arc", "Recline 100–110°", "R", 520),
                   ("ear", "Head stays level", "R", 40), ("lumbar", "Lumbar stays in contact", "L", 110)],
         products=["steelcase_s1", "lumbar_ec"]),
    dict(n=44, slug="office-chair-armrest-height", keyword="office chair armrest height",
         title="How High Should Office Chair Armrests Be?", text="Set Your Armrests Right",
         head="Set Your|*Armrests* Right",
         desc="Armrests set too high push your shoulders up; too low and you lean to one side. Set them level with your desk so your elbows rest at about 90 degrees.",
         kicker="Chair setup", sub="Level with your desk, shoulders relaxed.", scene="chair_annot",
         dims=["elbow_line"],
         callouts=[("shoulder", "Shoulders down, not shrugged", "R", 40), ("elbow", "Elbows about 90°", "R", 110),
                   ("armrest", "Armrest at elbow height", "R", 520), ("lumbar", "Back against the chair", "L", 40)],
         products=["sihoo_m57", "gimars"]),
    dict(n=45, slug="where-to-put-lumbar-pillow", keyword="lumbar pillow placement",
         title="Where to Put a Lumbar Pillow (Lower Than You Think)", text="Where to Put a Lumbar Pillow",
         head="Where to Put a|*Lumbar Pillow*",
         desc="A lumbar pillow belongs in the small of your back, around belt-line height, not between your shoulder blades. Sit all the way back so it fills the curve.",
         kicker="Lumbar support", sub="Around belt-line height, not up between the shoulders.", scene="chair_annot",
         arm=False, lumbar_col=TERRA, dims=["belt_line", "lumbar_ring"],
         callouts=[("lumbar", "In the small of the back", "L", 40), ("shoulder", "Not up between the shoulders", "R", 40),
                   ("hip", "Hips all the way back", "R", 520)],
         products=["lumbar_ec", "seat_ec"]),
    dict(n=46, slug="is-an-ergonomic-chair-worth-it", keyword="is an ergonomic chair worth it",
         title="Is an Ergonomic Chair Worth It? A Side-by-Side Look", text="Is an Ergonomic Chair Worth It?",
         head="Is an Ergonomic|Chair *Worth It?*",
         desc="A basic office chair is fine for short sessions. If you sit for most of the day, adjustable lumbar, seat depth and armrests make the difference. Here's how they compare.",
         kicker="Side by side", sub="What you get for the extra money.", scene="chair_compare", right="basic",
         sides=(("Ergonomic chair", "Adjusts to your body"), ("Basic chair", "One shape for everyone")),
         compare=[("Lumbar adjusts to your back", "No lumbar support"), ("Seat depth + arms adjust", "Fixed seat and arms"),
                  ("Made for full workdays", "Fine for short sessions")],
         verdict="Sit most of the day? Adjustability matters.",
         products=["sihoo_m57", "steelcase_s1"]),
    dict(n=47, slug="standing-desk-mistakes", keyword="standing desk mistakes",
         title="5 Standing Desk Mistakes (And How to Fix Them)", text="5 Standing Desk Mistakes",
         head="5 Standing Desk|*Mistakes*",
         desc="Bought a standing desk and still sore? Avoid these five mistakes: locked knees, standing all day, the wrong desk height, a low screen and a hard floor.",
         kicker="Standing desks", sub="Small fixes that make standing comfortable.", scene="standing_tips",
         tips=["Locking your knees", "Standing all day long", "Desk above elbow height", "Screen below eye level",
               "Hard floor, no mat"],
         products=["topo_mat", "flexispot_e7"]),
    dict(n=48, slug="standing-desk-accessories", keyword="standing desk accessories",
         title="6 Standing Desk Accessories That Actually Help", text="Standing Desk Accessories",
         head="Standing Desk|*Accessories*",
         desc="A standing desk works better with the right extras: an anti-fatigue mat, a monitor arm, a visual timer to switch positions, a vertical mouse, a laptop stand and a wrist rest.",
         kicker="Small upgrades", sub="Six extras that make a standing desk easier to use.", scene="essentials",
         items=[("mat", "Anti-fatigue mat"), ("monitor_arm", "Monitor arm"), ("timer", "Sit-stand timer"),
                ("vmouse", "Vertical mouse"), ("laptop_stand", "Laptop stand"), ("wrist_rest", "Wrist rest")],
         products=["topo_mat", "vivo_arm", "timetimer", "mx_vertical", "nulaxy", "gimars"]),
    dict(n=49, slug="vertical-mouse-vs-regular-mouse", keyword="vertical mouse",
         title="Vertical Mouse vs Regular Mouse: What's the Difference?", text="Vertical vs Regular Mouse",
         head="*Vertical* vs|Regular Mouse",
         desc="A regular mouse turns your palm flat, which twists the forearm. A vertical mouse keeps your hand in a handshake position. It takes about a week to get used to.",
         kicker="Side by side", sub="It's about how far your forearm twists.", scene="mouse_compare",
         compare=[("Forearm stays neutral", "Forearm twists flat"), ("Wrist off the desk", "Wrist rests on the desk")],
         verdict="Wrists tired by Friday? Try a handshake grip.",
         products=["mx_vertical", "gimars"]),
    dict(n=50, slug="how-to-set-up-a-monitor-arm", keyword="monitor arm setup",
         title="How to Set Up a Monitor Arm in 4 Steps", text="Monitor Arm Setup",
         head="Set Up Your|*Monitor Arm*",
         desc="A monitor arm only helps if it's set right: top edge at eye level, about an arm's length away, tilted back slightly, clamped at the back edge of the desk.",
         kicker="Screen setup", sub="Four adjustments, five minutes.", scene="monitor_setup",
         products=["vivo_arm", "huanuo_dual"]),
]

# ---- batch 4: laptops, keyboards, sit-stand rhythm and gifts
PINS += [
    dict(n=51, slug="laptop-with-external-monitor-setup", keyword="laptop and monitor setup",
         title="How to Set Up a Laptop With an External Monitor", text="Laptop + Monitor Setup",
         head="Laptop + Monitor|*Setup*",
         desc="Using your laptop next to a monitor? Put the monitor straight ahead, raise the laptop on a stand to the side, and type on a separate keyboard and mouse.",
         kicker="Desk setup · plan view", sub="Main screen ahead, laptop raised beside it.", scene="laptop_monitor",
         tips=["Monitor = main screen", "Laptop on a stand", "Screens at the same height", "Keyboard centred on you"],
         products=["nulaxy", "vivo_arm"]),
    dict(n=52, slug="laptop-ergonomics-essentials", keyword="laptop ergonomics",
         title="Working on a Laptop All Day? 6 Things That Help", text="Laptop Setup Essentials",
         head="Laptop Setup|*Essentials*",
         desc="A laptop forces you to choose between a good screen height and a good typing height. These six add-ons fix both: a stand, an external keyboard and mouse, a wrist rest, a monitor arm and a timer.",
         kicker="Small upgrades", sub="Six add-ons that fix the laptop hunch.", scene="essentials",
         items=[("laptop_stand", "Laptop stand"), ("wrist_rest", "External keyboard"), ("vmouse", "Vertical mouse"),
                ("monitor_arm", "Monitor arm"), ("lumbar", "Lumbar pillow"), ("timer", "Break timer")],
         products=["nulaxy", "k860", "mx_vertical", "gimars", "vivo_arm", "timetimer"]),
    dict(n=53, slug="split-keyboard-vs-regular-keyboard", keyword="split keyboard",
         title="Split Keyboard vs Regular Keyboard: What Changes for Your Wrists", text="Split vs Regular Keyboard",
         head="*Split* vs|Regular Keyboard",
         desc="A regular keyboard pulls your hands together, so your wrists bend outward. A split keyboard lets your hands sit at shoulder width with straight wrists.",
         kicker="Side by side", sub="Look at where the wrists bend.", scene="keyboard_compare",
         compare=[("Wrists stay straight", "Wrists bend outward"), ("Shoulders open", "Shoulders pulled in")],
         verdict="Typing all day? Give your wrists more room.",
         products=["k860", "gimars"]),
    dict(n=54, slug="20-8-2-rule-standing-desk", keyword="how long to stand at a standing desk",
         title="The 20-8-2 Rule: How Long to Sit and Stand at Your Desk", text="The 20-8-2 Rule",
         head="The *20-8-2*|Rule",
         desc="Not sure how long to stand at your standing desk? Try 20 minutes sitting, 8 minutes standing and 2 minutes moving, then repeat every half hour.",
         kicker="Sit-stand rhythm", sub="Sit, stand, move, repeat every half hour.", scene="rhythm",
         segments=[(20, "Sit", "sit"), (8, "Stand", "stand"), (2, "Move", "move")],
         verdict="Changing position matters more than standing.",
         products=["timetimer", "flexispot_e7", "topo_mat"]),
    dict(n=55, slug="office-chair-too-low-fix", keyword="office chair too low",
         title="Chair Too Low for Your Desk? Try a Seat Cushion", text="Chair Too Low? Easy Fix",
         head="Is Your Chair|Too *Low?*",
         desc="If your chair won't go high enough, your shoulders lift to reach the keyboard. A firm seat cushion raises you a couple of inches so your elbows clear the desk.",
         kicker="Quick fix", sub="A firm cushion lifts you to the right height.", scene="rig_compare",
         panels=[dict(tag="Chair too low", caption="Reaching up to type", lift=-0.45,
                      pose=dict(uarm=164, farm=84, fuarm=162, ffarm=84), strain=["shoulder"]),
                 dict(tag="With a seat cushion", caption="Elbows level with the desk")],
         products=["seat_ec", "sihoo_m57"]),
    dict(n=56, slug="home-office-setup-checklist", keyword="home office setup checklist",
         title="Home Office Setup Checklist: 5 Things to Check Today", text="Home Office Checklist",
         head="Home Office|*Checklist*",
         desc="Five quick checks for a home office that's easy on your body: screen at eye level, elbows at desk height, back supported, feet flat and light from the side.",
         kicker="5-minute check", sub="Run through these once, then every few months.", scene="chair_tips",
         tips=["Screen at eye level", "Elbows at desk height", "Lower back supported", "Feet flat or on a rest",
               "Light from the side"],
         products=["vivo_arm", "lumbar_ec", "footrest_ec"]),
    dict(n=57, slug="signs-you-need-a-new-office-chair", keyword="signs you need a new office chair",
         title="5 Signs You Need a New Office Chair", text="Signs You Need a New Chair",
         head="Time for a|*New Chair?*",
         desc="Back aching by lunchtime? Perching on the edge of the seat? These five signs mean your chair isn't supporting you anymore, and what to look for in the next one.",
         kicker="Buyer's guide", sub="If two or more sound familiar, it's time.", scene="chair_tips",
         pose=dict(lumbar=-14, thoracic=26, neck=40, head=6, uarm=160, farm=100), lumbar_col=None,
         tips=["Your back aches by noon", "You perch on the edge", "The seat has sunk flat", "Armrests won't adjust",
               "It wobbles or leans"],
         products=["sihoo_m57", "steelcase_s1"]),
    dict(n=58, slug="gaming-posture-setup", keyword="gaming posture",
         title="Gaming Posture: 4 Fixes for Long Sessions", text="Gaming Posture Fixes",
         head="Better *Gaming*|Posture",
         desc="Long gaming sessions add up. Raise the screen to eye level, keep elbows close, fill the gap behind your lower back and rest your feet flat.",
         kicker="Long sessions", sub="Four fixes that work in any chair.", scene="chair_annot",
         callouts=[("ear", "Screen at eye level", "R", 40), ("elbow", "Elbows close, wrists straight", "R", 110),
                   ("lumbar", "Pillow behind the lower back", "L", 40), ("toe", "Feet flat or on a rest", "R", 760)],
         products=["lumbar_ec", "footrest_ec", "mx_vertical"]),
    dict(n=59, slug="ergonomic-gifts-for-work-from-home", keyword="gifts for people who work from home",
         title="6 Ergonomic Gifts for People Who Work From Home", text="Gifts for Work From Home",
         head="Gifts for *Work*|*From Home*",
         desc="Practical gift ideas for anyone who works from home: a lumbar pillow, seat cushion, vertical mouse, visual timer, footrest and standing mat.",
         kicker="Gift guide", sub="Useful presents for the home office.", scene="essentials",
         items=[("lumbar", "Lumbar pillow"), ("seat_cushion", "Seat cushion"), ("vmouse", "Vertical mouse"),
                ("timer", "Visual timer"), ("footrest", "Footrest"), ("mat", "Standing mat")],
         products=["lumbar_ec", "seat_ec", "mx_vertical", "timetimer", "footrest_ec", "topo_mat"]),
    dict(n=60, slug="is-your-monitor-too-low", keyword="monitor too low",
         title="Is Your Monitor Too Low? Here's the Fix", text="Is Your Monitor Too Low?",
         head="Is Your Monitor|Too *Low?*",
         desc="If you look down at your screen, your head tips forward all day. Raise the monitor so the top edge sits at eye level, with an arm or a stand.",
         kicker="Screen height", sub="Top edge of the screen at eye level.", scene="rig_compare",
         panels=[dict(tag="Screen too low", caption="Head tips forward", screen_low=True, sightline=True,
                      pose=dict(lumbar=-6, thoracic=16, neck=44, head=6), strain=["neck"]),
                 dict(tag="Raised to eye level", caption="Head stays level", sightline=True)],
         products=["vivo_arm", "huanuo_dual"]),
]

# ---- batch 5: fresh designs for the best-performing topics (chairs, sitting, monitor height, desk setup)
SLUMP_SIT = dict(lumbar=-16, thoracic=30, neck=48, head=6, uarm=150, farm=100, fuarm=152, ffarm=100)
PINS += [
    dict(n=61, slug="how-to-choose-an-office-chair-checklist", keyword="how to choose an office chair",
         title="How to Choose an Office Chair: 5-Point Checklist", text="Office Chair Checklist",
         head="Choosing an|*Office Chair*",
         desc="Shopping for an office chair? Check these five things before you buy: lumbar support, seat depth, armrests, recline and seat height range.",
         kicker="Buyer's checklist", sub="Check these five before you buy.", scene="chair_annot",
         dims=["lumbar_ring"],
         callouts=[("lumbar", "Lumbar adjusts up and down", "L", 40), ("backrest", "Recline that locks", "L", 110),
                   ("armrest", "Armrests move", "R", 40), ("seat_front", "Seat depth slides", "R", 520),
                   ("gas", "Height fits your desk", "R", 640)],
         products=["sihoo_m57", "steelcase_s1"]),
    dict(n=62, slug="ergonomic-chair-must-haves", keyword="ergonomic chair features",
         title="5 Ergonomic Chair Must-Haves for Long Workdays", text="Ergonomic Chair Must-Haves",
         head="Ergonomic Chair|*Must-Haves*",
         desc="Not every 'ergonomic' chair is. Look for these five features if you sit for most of the day: adjustable lumbar, sliding seat, movable armrests, locking recline and a breathable back.",
         kicker="Buyer's guide", sub="If it's missing one of these, keep looking.", scene="chair_tips",
         tips=["Adjustable lumbar support", "A seat that slides", "Armrests that move", "Recline that locks",
               "A breathable mesh back"],
         products=["sihoo_m57", "steelcase_s1"]),
    dict(n=63, slug="sitting-posture-wrong-vs-right", keyword="correct sitting posture at desk",
         title="Sitting Posture at Your Desk: Wrong vs Right", text="Sitting Posture: Wrong vs Right",
         head="Sitting Posture|Wrong vs *Right*",
         desc="Same chair, same desk, two postures. Sit all the way back, let the chair support your lower back, and keep your head over your shoulders.",
         kicker="Side by side", sub="Same desk, same chair, different habits.", scene="rig_compare",
         panels=[dict(tag="Wrong", caption="Slumped, head forward", pose=SLUMP_SIT, strain=["neck", "back"]),
                 dict(tag="Right", caption="Back supported, head level")],
         products=["lumbar_ec", "seat_ec"]),
    dict(n=64, slug="ergonomic-desk-setup-measurements", keyword="ergonomic desk height",
         title="Ergonomic Desk Setup Measurements (Cheat Sheet)", text="Desk Setup Measurements",
         head="Desk Setup|*Measurements*",
         desc="Typical ranges for a seated desk setup: seat height 16-21 in, desk height 25-30 in, screen 20-30 in from your eyes with the top edge at eye level. Adjust to fit your body.",
         kicker="Cheat sheet", sub="Typical ranges for seat, desk and screen.", scene="measurements",
         dims=["SEAT 16–21 IN", "DESK 25–30 IN", "SCREEN 20–30 IN AWAY"],
         products=["sihoo_m57", "vivo_arm", "footrest_ec"]),
    dict(n=65, slug="monitor-height-too-high-too-low", keyword="monitor height",
         title="Monitor Height: Too High, Too Low or Just Right?", text="Monitor Height Check",
         head="Is Your Monitor|*Just Right?*",
         desc="Too high and your chin tips up. Too low and your head drops forward. Set the top edge of the screen at or just below eye level, about an arm's length away.",
         kicker="Screen height", sub="Three heights, one that works.", scene="monitor_zones",
         tips=["Top edge at or just below eye level", "Centre about 15–20° below your eyes", "Roughly an arm's length away"],
         products=["vivo_arm", "nulaxy"]),
    dict(n=66, slug="upper-back-stretches-at-desk", keyword="upper back stretches at desk",
         title="4 Upper Back Stretches You Can Do at Your Desk", text="Upper Back Desk Stretches",
         head="Upper Back|*Desk Stretches*",
         desc="Two minutes, no equipment, no getting changed. Four seated moves for a stiff upper back after hours at the computer.",
         kicker="Two minutes", sub="Seated moves, no equipment needed.", scene="exercise_grid", badge="Two minutes",
         exercises=[("upper_back_ext", "Upper-back extension", "8 reps"), ("scap_squeeze", "Blade squeeze", "10 reps"),
                    ("chest_opener_seated", "Chest opener", "20 sec"), ("shoulder_rolls", "Shoulder rolls", "10 backward")],
         products=["chirp", "theraband"]),
    dict(n=67, slug="neck-stretches-at-desk", keyword="neck stretches at desk",
         title="3-Minute Neck Stretches for Desk Workers", text="Neck Stretches at Your Desk",
         head="Neck Stretches|at Your *Desk*",
         desc="Stiff neck by the afternoon? Four gentle seated stretches you can do between meetings. Move slowly and stop if anything hurts.",
         kicker="Three minutes", sub="Gentle moves between meetings.", scene="exercise_grid", badge="Three minutes",
         exercises=[("chin_tuck_seated", "Chin tucks", "10 reps"), ("side_neck", "Side neck stretch", "20 sec / side"),
                    ("neck_turn", "Slow neck turns", "5 / side"), ("shoulder_rolls", "Shoulder rolls", "10 backward")],
         products=["chirp_neck", "restcloud"]),
    dict(n=68, slug="upper-back-pain-from-sitting-checklist", keyword="upper back pain from sitting",
         title="Upper Back Pain From Sitting? Check These 3 Things", text="Upper Back Pain From Sitting",
         head="Upper Back Sore|From *Sitting?*",
         desc="Upper back tension after a long day usually comes down to three things: screen height, back support and how long you sit without moving.",
         kicker="Quick check", sub="Three things to check before anything else.", scene="pain", area="upper_back",
         causes_title="CHECK THESE FIRST", causes=["Is your screen at eye level?", "Is your back supported?",
                                                     "Do you move every 30–60 minutes?"],
         products=["lumbar_ec", "chirp"]),
    dict(n=69, slug="proper-sitting-posture-cheat-sheet", keyword="proper sitting posture",
         title="Proper Sitting Posture: 6-Point Cheat Sheet", text="Sitting Posture Cheat Sheet",
         head="Sitting Posture|*Cheat Sheet*",
         desc="Run through these six points from head to toe: ears over shoulders, shoulders relaxed, elbows near 90 degrees, lower back supported, knees level with hips, feet flat.",
         kicker="Head to toe", sub="Six checkpoints from head to toe.", scene="chair_annot", arm=False,
         callouts=[("ear", "Ears over shoulders", "R", 40), ("shoulder", "Shoulders relaxed", "R", 110),
                   ("elbow", "Elbows near 90°", "R", 180), ("lumbar", "Lower back supported", "L", 40),
                   ("knee", "Knees level with hips", "R", 560), ("toe", "Feet flat on the floor", "R", 760)],
         products=["lumbar_ec", "footrest_ec"]),
    dict(n=70, slug="mesh-vs-padded-office-chair", keyword="mesh vs padded office chair",
         title="Mesh vs Padded Office Chair: Which Is Better for Long Days?", text="Mesh vs Padded Chair",
         head="*Mesh* vs|Padded Chair",
         desc="Padded chairs feel soft in the showroom; mesh chairs tend to stay cooler and keep their shape. Here's how they compare for a full workday.",
         kicker="Side by side", sub="Which holds up over a full workday?", scene="chair_compare", right="basic",
         sides=(("Mesh chair", "Breathes and flexes"), ("Padded chair", "Soft at first")),
         compare=[("Stays cool all day", "Can run warm"), ("Keeps its shape", "Foam can flatten"),
                  ("Even, firm support", "Plush, softer feel")],
         verdict="Long days? Mesh tends to age better.",
         products=["sihoo_m57", "steelcase_s1"]),
]

# ---- batch 6: A-style design; descriptions lead with the product to lift outbound clicks
PINS += [
    dict(n=71, slug="desk-chair-for-lower-back-pain", keyword="office chair for lower back pain",
         title="Lower Back Sore at Your Desk? Check Your Chair First", text="Check Your Chair First",
         head="Lower Back Sore?|Check Your *Chair*",
         desc="Our pick: Everlasting Comfort lumbar pillow, linked below. Most lower-back tension at a desk starts with the chair: no lumbar support, a seat that's too deep, or feet that don't reach the floor. Tap the link to see the pillow on Amazon.",
         kicker="Quick check", sub="Four things to check before anything else.", scene="chair_annot",
         dims=["lumbar_ring"], arm=False,
         callouts=[("lumbar", "Gap behind the lower back?", "L", 40), ("backrest", "Backrest upright or locked?", "L", 110),
                   ("seat_front", "Seat too deep?", "R", 520), ("toe", "Feet reaching the floor?", "R", 760)],
         products=["lumbar_ec", "sihoo_m57"]),
    dict(n=72, slug="how-to-sit-comfortably-all-day", keyword="how to sit comfortably at a desk all day",
         title="How to Sit Comfortably at a Desk All Day: 5 Habits", text="Sit Comfortably All Day",
         head="Sit Comfortably|*All Day*",
         desc="Our pick: Everlasting Comfort lumbar pillow, linked below. Five habits for long desk days: sit all the way back, feet flat, screen at eye level, back supported and a break every 30 minutes. Tap the link to see it on Amazon.",
         kicker="Five habits", sub="Small habits that add up over a workday.", scene="chair_tips",
         tips=["Sit all the way back", "Feet flat on the floor", "Screen at eye level", "Lower back supported",
               "Stand up every 30 min"],
         products=["lumbar_ec", "timetimer"]),
    dict(n=73, slug="how-to-use-a-standing-desk", keyword="how to use a standing desk",
         title="How to Use a Standing Desk the Right Way", text="Use a Standing Desk Right",
         head="Use a Standing|Desk *Right*",
         desc="Our pick: Ergodriven Topo standing mat, linked below. Set the desk at elbow height, the screen at eye level, keep your knees soft and stand on a cushioned mat. Switch between sitting and standing through the day. Tap the link to see it on Amazon.",
         kicker="Standing desks", sub="Five settings that make standing easier.", scene="standing_tips", mode="tips",
         tips=["Desk at elbow height", "Screen top at eye level", "Soft knees, shift weight", "Stand on a cushioned mat",
               "Switch every 30–60 min"],
         products=["topo_mat", "flexispot_e7"]),
    dict(n=74, slug="gift-ideas-for-remote-workers", keyword="gifts for remote workers",
         title="Gift Ideas for Remote Workers: 6 Desk Upgrades", text="Gifts for Remote Workers",
         head="Gifts for|*Remote Workers*",
         desc="Our pick: VIVO monitor arm, linked below. Six desk upgrades remote workers actually use: a monitor arm, laptop stand, ergonomic keyboard, vertical mouse, visual timer and seat cushion. Tap the link to see it on Amazon.",
         kicker="Gift guide", sub="Desk upgrades they'll use every day.", scene="essentials",
         items=[("monitor_arm", "Monitor arm"), ("laptop_stand", "Laptop stand"), ("wrist_rest", "Ergonomic keyboard"),
                ("vmouse", "Vertical mouse"), ("timer", "Visual timer"), ("seat_cushion", "Seat cushion")],
         products=["vivo_arm", "nulaxy", "k860", "mx_vertical", "timetimer", "seat_ec"]),
    dict(n=75, slug="25-5-posture-break-routine", keyword="posture breaks at work",
         title="The 25-5 Posture Break: Focus, Then Move", text="The 25-5 Posture Break",
         head="The *25-5*|Posture Break",
         desc="Our pick: Time Timer visual desk timer, linked below. Work for 25 minutes, then stand up and move for 5. A visual timer makes the habit stick without checking your phone. Tap the link to see it on Amazon.",
         kicker="Break routine", sub="Focus for 25 minutes, move for 5.", scene="rhythm",
         segments=[(25, "Focus", "sit"), (5, "Move", "move")],
         verdict="Short, regular breaks beat one long one.",
         products=["timetimer", "theraband"]),
    dict(n=76, slug="shoulder-stretches-at-desk", keyword="shoulder stretches at desk",
         title="4 Shoulder Stretches to Do at Your Desk", text="Shoulder Stretches at Your Desk",
         head="Shoulder Stretches|at Your *Desk*",
         desc="Our pick: THERABAND resistance band set, linked below. Four seated moves for tight shoulders after a long day at the computer. Two minutes, no getting up. Tap the link to see the bands on Amazon.",
         kicker="Two minutes", sub="Seated moves for tight shoulders.", scene="exercise_grid", badge="Two minutes",
         exercises=[("shoulder_rolls", "Shoulder rolls", "10 backward"), ("scap_squeeze", "Blade squeeze", "10 reps"),
                    ("chest_opener_seated", "Chest opener", "20 sec"), ("overhead_reach", "Overhead reach", "5 breaths")],
         products=["theraband", "chirp"]),
    dict(n=77, slug="standing-desk-stretches", keyword="standing desk stretches",
         title="4 Quick Stretches for Standing Desk Breaks", text="Standing Desk Stretches",
         head="Standing Desk|*Stretches*",
         desc="Our pick: THERABAND resistance band set, linked below. Already standing? Use the moment: four quick stretches for your neck, sides and chest between tasks. Tap the link to see the bands on Amazon.",
         kicker="Between tasks", sub="Four moves while you're already up.", scene="exercise_grid", badge="Three minutes",
         exercises=[("chin_tuck_standing", "Chin tucks", "10 reps"), ("side_bend_stand", "Side bend", "5 breaths / side"),
                    ("chest_opener_stand", "Chest opener", "20 sec"), ("overhead_reach_stand", "Full-body reach", "5 breaths")],
         products=["theraband", "topo_mat"]),
    dict(n=78, slug="neck-hurts-after-work-checklist", keyword="neck pain from computer",
         title="Neck Sore After Work? Check These 3 Things", text="Neck Sore After Work?",
         head="Neck Sore|After *Work?*",
         desc="Our pick: VIVO monitor arm, linked below. A stiff neck after a desk day usually comes back to three things: screen height, how far your head drifts forward and how long you go without a break. Tap the link to see it on Amazon.",
         kicker="Quick check", sub="Three things to check before anything else.", scene="pain", area="neck",
         causes_title="CHECK THESE FIRST", causes=["Is the screen top at eye level?", "Is your head over your shoulders?",
                                                     "Do you look away every 20 minutes?"],
         products=["vivo_arm", "chirp_neck"]),
    dict(n=79, slug="dining-chair-for-working-from-home", keyword="dining chair for working from home",
         title="Working From a Dining Chair? 3 Easy Fixes", text="Dining Chair? 3 Easy Fixes",
         head="Working From a|*Dining Chair?*",
         desc="Our pick: Everlasting Comfort seat cushion, linked below. A kitchen chair can work for a while with three cheap fixes: a cushion to raise you, a pillow behind your lower back and a footrest if your feet dangle. Tap the link to see it on Amazon.",
         kicker="Budget fixes", sub="Three add-ons before you buy a new chair.", scene="chair_annot", arm=False,
         chair="dining", hip_x=420,
         callouts=[("seat", "Cushion raises you up", "R", 520), ("lumbar", "Pillow behind lower back", "L", 40),
                   ("toe", "Footrest if feet dangle", "L", 720)],
         products=["seat_ec", "lumbar_ec", "footrest_ec"]),
    dict(n=80, slug="office-chair-vs-dining-chair", keyword="office chair vs dining chair",
         title="Office Chair vs Dining Chair for Working From Home", text="Office vs Dining Chair",
         head="Office Chair vs|*Dining Chair*",
         desc="Our pick: SIHOO M57 ergonomic chair, linked below. A dining chair is fine for an hour; an office chair adjusts to your body for a full day. Here's what changes. Tap the link to see it on Amazon.",
         kicker="Side by side", sub="Fine for dinner, but for a workday?", scene="chair_compare", right="dining",
         sides=(("Office chair", "Adjusts to your body"), ("Dining chair", "Fixed height and angle")),
         compare=[("Height matches your desk", "Fixed seat height"), ("Supports the lower back", "Flat, upright back"),
                  ("Rolls and swivels", "Stays put")],
         verdict="Working from home for good? Upgrade the chair.",
         products=["sihoo_m57", "seat_ec"]),
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


RAW_BASE = ("https://raw.githubusercontent.com/gtressaoki-ctrl/eBay-automation/"
            "claude/pinterest-posture-pins-affiliates-el8251/pinterest/posture-pins/images/")


def write_bulk_csv(name, order, start, board="Desk Posture & Ergonomics"):
    """Pinterest bulk-create CSV: one post every 12 hours from `start` (a datetime).

    Pinterest reads "Publish date" in the account's own time zone (JST here), not UTC,
    so batch 5 onwards starts at 22:00 to land at 9am US Eastern and 9pm the next slot.
    """
    from datetime import timedelta
    by_n = {p["n"]: p for p in PINS}
    path = os.path.join(HERE, name)
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["Title", "Media URL", "Pinterest board", "Thumbnail", "Description", "Link", "Publish date", "Keywords"])
        for i, n in enumerate(order):
            p = by_n[n]
            when = start + timedelta(hours=12 * i)
            w.writerow([p["title"], f"{RAW_BASE}{p['n']:02d}-{p['slug']}.png", board, "", p["desc"] + " #affiliate",
                        product_url(p["products"][0]), when.strftime("%Y-%m-%dT%H:%M:%S"), p["keyword"]])
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
