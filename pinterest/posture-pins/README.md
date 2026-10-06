# Desk posture Pinterest pins (30)

Pinterest-ready pin images (1000×1500 px, 2:3) for the 30 desk-posture pin plans, plus matched affiliate products.

The visual system is **Plumb Line**, described in [`DESIGN_PHILOSOPHY.md`](DESIGN_PHILOSOPHY.md):

- figures are solid ink silhouettes;
- furniture is drawn as fine architectural linework;
- a single terracotta accent marks the line of alignment or a point of strain;
- each plate uses serif headlines with mono reference marks.

| File | Contents |
|---|---|
| `images/NN-slug.png` | The 30 pin images, ready to upload |
| `contact-sheet.png` | All 30 at a glance |
| `pins.csv` | Per pin: title, description, alt text, keyword, board, link (primary affiliate) and other products |
| `AFFILIATES.md` | Product table per pin (auto-generated) |
| `generate_pins.py` | Pin data (copy, scene, products) and the build pipeline |
| `scenes.py` / `svgkit.py` | Vector illustration code: scenes, silhouettes, furniture, annotations |
| `plate.py` / `render.mjs` | HTML plate template, rendered to PNG with Playwright (Chromium) |
| `products.py` | Affiliate product master list (ASINs / URLs) |
| `fonts/` | Instrument Serif, Instrument Sans and DM Mono (SIL Open Font License) |

## Regenerate

```bash
pip install pillow            # plus Node + Playwright with Chromium available
AMAZON_TAG=yourid-20 python pinterest/posture-pins/generate_pins.py   # all pins + CSV + AFFILIATES.md
python pinterest/posture-pins/generate_pins.py 1 9 15                  # only some pins
```

## Before posting

- **Affiliate IDs**: until `AMAZON_TAG` is set, Amazon links carry the placeholder `deskpostureat-20` (default). Replace the Udemy (via Impact), FlexiSpot (Awin/CJ) and UPRIGHT links with the tracking links from each program's dashboard.
- **Disclosure**: add `#affiliate` or `#ad` to the pin description. This is an FTC requirement and Amazon Associates policy.
- **Availability**: the ASINs were checked against amazon.com listings in Sept 2026. Stock and prices change, so open each link once before posting.
- **Health wording**: the images avoid claims of cure or medical effect. Keep product copy, especially for posture correctors, to "supports" or "helps".

## A/B test (pins 1, 2, 4, 14, 22)

`python generate_pins.py --ab` renders a bolder **B** variant of five pins into `images/ab-test/`. B keeps the same illustration as A but adds:

- a dark headline band;
- a larger headline;
- a terracotta number badge (6 checkpoints, 7 signs, 4 moves, 3 months, 5 minutes).

`pins-ab-test.csv` lists both variants. Each variant links through its own Amazon tracking ID (`AMAZON_TAG_A` / `AMAZON_TAG_B`, created under Associates → Manage Tracking IDs), so Amazon reports clicks and orders per variant.

Post A and B on different days, into the same board, with the same title and description. After 2–4 weeks, compare in Pinterest Analytics:

- outbound clicks per impression;
- saves per impression.

Then roll the winning style out to all 30 pins.
