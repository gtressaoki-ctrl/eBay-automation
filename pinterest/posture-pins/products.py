"""Affiliate products matched to the posture pins.

Set your Amazon Associates tracking ID with the AMAZON_TAG environment
variable (e.g. AMAZON_TAG=yourname-20) before running generate_pins.py and
every Amazon link in pins.csv gets it appended.  Non-Amazon links need the
tracking link generated inside that program's dashboard (Udemy via Impact,
FlexiSpot via Awin/CJ, Upright via its partner program).
"""

import os

AMAZON_TAG = os.environ.get("AMAZON_TAG", "YOURTAG-20")

PRODUCTS = {
    # ---- chair add-ons
    "lumbar_ec": dict(name="Everlasting Comfort Original Lumbar Support Pillow", asin="B01IJNJAZ0", program="Amazon"),
    "seat_ec": dict(name="Everlasting Comfort Memory Foam Seat Cushion", asin="B01EBDV9BU", program="Amazon"),
    "footrest_ec": dict(name="Everlasting Comfort Under-Desk Foot Rest", asin="B07PGLBCFG", program="Amazon"),
    # ---- posture correctors / trainers
    "brace_schiara": dict(name="Schiara Posture Corrector", asin="B07VST9VYH", program="Amazon"),
    "brace_comfy": dict(name="ComfyBrace Posture Corrector", asin="B07ZQPKTVV", program="Amazon"),
    "upright_go2": dict(name="UPRIGHT GO 2 Posture Trainer (app-connected)", asin="B07SRW2D38", program="Amazon",
                        alt_url="https://store.uprightpose.com/products/upright-go2"),
    # ---- screens
    "vivo_arm": dict(name="VIVO Single Monitor Arm STAND-V001", asin="B00B21TLQU", program="Amazon"),
    "huanuo_dual": dict(name="HUANUO Dual Monitor Stand (gas spring)", asin="B08G8M72ZG", program="Amazon"),
    "nulaxy": dict(name="Nulaxy Adjustable Laptop Stand", asin="B077B9W343", program="Amazon"),
    # ---- input devices
    "k860": dict(name="Logitech ERGO K860 Split Ergonomic Keyboard", asin="B07ZWK2TQT", program="Amazon"),
    "gimars": dict(name="Gimars Gel Memory Foam Keyboard + Mouse Wrist Rest Set", asin="B01M11FLUJ", program="Amazon"),
    # ---- chairs & desks (high ticket)
    "sihoo_m57": dict(name="SIHOO M57 Ergonomic Office Chair", asin="B07BDFW1Y7", program="Amazon"),
    "steelcase_s1": dict(name="Steelcase Series 1 Office Chair", asin="B078HFDMKD", program="Amazon"),
    "flexispot_e7": dict(name="FlexiSpot E7 Pro Electric Standing Desk", asin="B094N16PQM", program="Amazon",
                         alt_url="https://www.flexispot.com/flexispot-best-standing-desk-e7pro"),
    "flexispot_conv": dict(name="FlexiSpot 35in Standing Desk Converter", asin="B0C8TMNWP8", program="Amazon"),
    # ---- stretching / recovery
    "theraband": dict(name="THERABAND Resistance Band Set", asin="B000LX4KRA", program="Amazon"),
    "chirp": dict(name="Chirp Wheel+ Foam Roller (10in/12in)", asin="B0B88FZ1LC", program="Amazon"),
    "chirp_neck": dict(name="Chirp Wheel+ 4in Neck Roller", asin="B09M678BZB", program="Amazon"),
    "restcloud": dict(name="RESTCLOUD Neck and Shoulder Relaxer", asin="B07QSFJ8S2", program="Amazon"),
    "timetimer": dict(name="Time Timer PLUS 60-Minute Desk Visual Timer", asin="B0DCCHV881", program="Amazon"),
    # ---- online courses (Udemy affiliate via Impact)
    "udemy_reverse": dict(name="Udemy: Reverse Bad Posture Exercises", program="Udemy",
                          url="https://www.udemy.com/course/reverse-bad-posture-exercises/"),
    "udemy_neck": dict(name="Udemy: Neck, Shoulder & Upper Back Stretching to Improve Posture", program="Udemy",
                       url="https://www.udemy.com/course/neck-shoulder-upper-back-stretching-to-improve-posture/"),
    "udemy_textneck": dict(name="Udemy: Text Neck - Pain Relief Stretches and Exercises", program="Udemy",
                           url="https://www.udemy.com/course/text-neck/"),
    "udemy_15min": dict(name="Udemy: Fix Your Posture - 15-Minute Back, Shoulders, Neck Exercises", program="Udemy",
                        url="https://www.udemy.com/course/fix-your-posture-15-minute-back-shoulders-neck-exercises/"),
    "udemy_correct": dict(name="Udemy: Correct Body Posture and Relieve Pain", program="Udemy",
                          url="https://www.udemy.com/course/correct-body-posture-and-relieve-pain/"),
}


def product_url(key):
    p = PRODUCTS[key]
    if "asin" in p:
        return f"https://www.amazon.com/dp/{p['asin']}?tag={AMAZON_TAG}"
    return p["url"]
