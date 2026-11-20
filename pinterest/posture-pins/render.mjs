// Render plate HTML files to PNG with Playwright's Chromium.
// usage: node render.mjs jobs.json [deviceScaleFactor]
import { readFileSync } from "node:fs";
import { createRequire } from "node:module";

const require = createRequire(import.meta.url);
let pw;
try {
  pw = require("playwright");
} catch {
  pw = require((process.env.NODE_PATH || "/opt/node22/lib/node_modules") + "/playwright");
}

const jobs = JSON.parse(readFileSync(process.argv[2], "utf8"));
const scale = Number(process.argv[3] || 2);
const browser = await pw.chromium.launch();
const page = await browser.newPage({ viewport: { width: 1000, height: 1500 }, deviceScaleFactor: scale });
for (const { html, png } of jobs) {
  await page.goto("file://" + html);
  await page.evaluate(() => document.fonts.ready);
  await page.screenshot({ path: png, clip: { x: 0, y: 0, width: 1000, height: 1500 } });
}
await browser.close();
