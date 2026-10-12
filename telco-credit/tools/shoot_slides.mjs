// Render every .slide of an HTML deck to a PNG at 16:9, 2x.
//   node tools/shoot_slides.mjs <deck.html> <out-dir> <prefix>
// Each .slide is exactly one viewport, so an element screenshot is the slide.
import { createRequire } from 'node:module';
import { pathToFileURL } from 'node:url';
import path from 'node:path';
const require = createRequire(import.meta.url);
let pw;
for (const p of ['/opt/node22/lib/node_modules/playwright/index.js', 'playwright']) {
  try { pw = require(p); break; } catch (e) { /* try the next */ }
}
if (!pw) { console.error('playwright not found'); process.exit(1); }

const [src, outDir, prefix] = process.argv.slice(2);
const b = await pw.chromium.launch();
const ctx = await b.newContext({ viewport: { width: 1920, height: 1080 },
                                 colorScheme: 'light', deviceScaleFactor: 2 });
const pg = await ctx.newPage();
await pg.goto(pathToFileURL(path.resolve(src)).href);
await pg.waitForTimeout(2500);          // webfonts, if the network allows them
const n = await pg.locator('.slide').count();
for (let i = 0; i < n; i++) {
  const loc = pg.locator('.slide').nth(i);
  await loc.scrollIntoViewIfNeeded();
  await pg.waitForTimeout(300);
  const out = path.join(outDir, `${prefix}${i + 1}.png`);
  await loc.screenshot({ path: out });
  console.log(out);
}
await b.close();
