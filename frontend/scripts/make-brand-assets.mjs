// Derives the web logo, favicon and touch icon from the source logo.
// Usage: npm i --no-save sharp && node scripts/make-brand-assets.mjs /path/to/logo.png
import sharp from "sharp";

const src = process.argv[2];
if (!src) {
  console.error("usage: node scripts/make-brand-assets.mjs <logo.png>");
  process.exit(1);
}
const meta = await sharp(src).metadata();
console.log("source", meta.width, meta.height);
const px = await sharp(src).extract({ left: 4, top: 4, width: 1, height: 1 }).raw().toBuffer();
console.log("corner rgb", [...px]);

// Web logo: keep the square, 720px is enough for 2x of the largest display size (360px).
await sharp(src).resize(720, 720).png({ compressionLevel: 9 }).toFile("public/logo.png");
// Icon: crop to the column mark (upper area) so it stays legible at 32px.
// Mark occupies roughly x 28-74%, y 17-60% of the canvas; crop a square around it.
const side = Math.round(meta.width * 0.51);
const crop = { left: Math.round(meta.width * 0.253), top: Math.round(meta.width * 0.126), width: side, height: side };
await sharp(src).extract(crop).resize(512, 512).png().toFile("src/app/icon.png");
await sharp(src).extract(crop).resize(180, 180).png().toFile("src/app/apple-icon.png");
console.log("done");
