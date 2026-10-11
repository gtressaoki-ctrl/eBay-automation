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
    """Pinterest bulk-create CSV: two posts a day (13:00 and 01:00 UTC) from `start` (a datetime)."""
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
