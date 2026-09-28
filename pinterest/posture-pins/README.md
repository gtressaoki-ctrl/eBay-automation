# Desk posture Pinterest pins (30)

Pinterest-ready pin images (1000×1500 px, 2:3) for the 30 desk-posture pin plans, plus matched affiliate products.

| File | Contents |
|---|---|
| `images/NN-slug.png` | The 30 pin images, ready to upload |
| `contact-sheet.png` | All 30 at a glance |
| `pins.csv` | Per pin: title, description, alt text, keyword, board, link (primary affiliate) and other products |
| `AFFILIATES.md` | Product table per pin (auto-generated) |
| `generate_pins.py` / `scenes.py` / `pinlib.py` | Image generator (Pillow only, no external image assets) |
| `products.py` | Affiliate product master list (ASINs / URLs) |
| `fonts/` | Poppins (SIL Open Font License, see `fonts/OFL.txt`) |

## Regenerate

```bash
pip install pillow
AMAZON_TAG=yourid-20 python pinterest/posture-pins/generate_pins.py   # all pins + CSV + AFFILIATES.md
python pinterest/posture-pins/generate_pins.py 1 9 15                  # only some pins
```

Titles, text, product mapping etc. live in the `PINS` list in `generate_pins.py`.

## Before posting

- **Affiliate IDs**: Amazon links carry `YOURTAG-20` until `AMAZON_TAG` is set. Udemy (via Impact), FlexiSpot (Awin/CJ) and UPRIGHT links must be swapped for the tracking links from each program's dashboard.
- **Disclosure**: add `#affiliate` or `#ad` to the pin description (FTC requirement and Amazon Associates policy).
- **Availability**: ASINs were checked against amazon.com listings in Sept 2026; stock and prices change, so open each link once before posting.
- **Health wording**: the images avoid claims of cure or medical effect. Keep product copy (especially for posture correctors) to "supports / helps".
