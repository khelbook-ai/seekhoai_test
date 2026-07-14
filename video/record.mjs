// Records the SeekhAI explainer HTML to a .webm video by driving it in headless Chromium.
// Playwright records the page via the browser's own screencast (no system ffmpeg needed).
// Note: page audio (the Web-Audio score) is NOT captured — the recording is silent.
import { chromium } from "playwright";
import fs from "fs";
import path from "path";
import { fileURLToPath } from "url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const HTML = "file://" + path.join(__dirname, "seekhai-explainer.html");
const OUT_DIR = path.join(__dirname, "out");
const W = 1280, H = 720;
const DURATION_MS = 178000; // full tour (~2:53) + a little tail

fs.mkdirSync(OUT_DIR, { recursive: true });

const browser = await chromium.launch({ args: ["--autoplay-policy=no-user-gesture-required"] });
const context = await browser.newContext({
  viewport: { width: W, height: H },
  recordVideo: { dir: OUT_DIR, size: { width: W, height: H } },
  deviceScaleFactor: 1,
});
const page = await context.newPage();
await page.goto(HTML, { waitUntil: "load" });

// start the tour (click the play cover)
await page.click("#cover");
console.log("recording…", DURATION_MS / 1000, "s");
await page.waitForTimeout(DURATION_MS);

const video = page.video();
await context.close();          // finalizes the .webm
await browser.close();

const src = await video.path();
const dest = path.join(__dirname, "seekhai-tour.webm");
fs.copyFileSync(src, dest);
console.log("saved:", dest, (fs.statSync(dest).size / 1e6).toFixed(1), "MB");
