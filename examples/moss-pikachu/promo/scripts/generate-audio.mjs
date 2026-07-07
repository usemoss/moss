/**
 * Generate SFX + ambient music for Moss Pikachu Video 2 via ElevenLabs.
 * Reads ELEVENLABS_API_KEY from repo root .env
 *
 * Usage: npm run generate-audio
 */
import { readFileSync, writeFileSync, mkdirSync, existsSync, copyFileSync } from "fs";
import { join, dirname } from "path";
import { fileURLToPath } from "url";

const __dirname = dirname(fileURLToPath(import.meta.url));
const ROOT = join(__dirname, "..", "..");
const OUT_DIR = join(__dirname, "..", "public", "audio");

function loadEnv() {
  const envPath = join(ROOT, ".env");
  const vars = {};
  if (!existsSync(envPath)) return vars;
  const content = readFileSync(envPath, "utf-8");
  for (const line of content.split("\n")) {
    const trimmed = line.trim();
    if (!trimmed || trimmed.startsWith("#")) continue;
    const eq = trimmed.indexOf("=");
    if (eq === -1) continue;
    const key = trimmed.slice(0, eq).trim();
    let val = trimmed.slice(eq + 1).trim();
    if (
      (val.startsWith('"') && val.endsWith('"')) ||
      (val.startsWith("'") && val.endsWith("'"))
    ) {
      val = val.slice(1, -1);
    }
    vars[key] = val;
  }
  return vars;
}

const SFX = [
  {
    file: "ui-tick.mp3",
    text: "Single soft macOS UI keystroke tick, very short, dry, subtle, no reverb",
    duration: 0.5,
    influence: 0.8,
  },
  {
    file: "music.mp3",
    text: "30 second tech product launch music, act structure with downbeats at 0s 5s 12s 20s 28s, driving kick drum four-on-the-floor, punchy synth bass, bright arpeggios, 120 BPM, builds to reveal at 12s, settles 20-28s, seamless loop ending",
    duration: 30,
    influence: 0.55,
  },
  {
    file: "drop-slam.mp3",
    text: "Short sub-heavy UI impact thud, deep 80Hz transient, punchy, dry, no long tail, no melody",
    duration: 1,
    influence: 0.75,
  },
  {
    file: "drop-soft.mp3",
    text: "Subtle soft UI swoosh with light body, short, modern, no harsh highs",
    duration: 1,
    influence: 0.65,
  },
  {
    file: "transition-whoosh.mp3",
    text: "Very short high-passed air whoosh transition, cinematic scene change, dry, fades quickly",
    duration: 0.5,
    influence: 0.7,
  },
  {
    file: "mouse-click.mp3",
    text: "Single macOS trackpad click, crisp, dry, short, no reverb, one tap",
    duration: 0.5,
    influence: 0.85,
  },
];

async function generate(apiKey, item) {
  console.log(`Generating ${item.file} ...`);
  const response = await fetch(
    "https://api.elevenlabs.io/v1/sound-generation",
    {
      method: "POST",
      headers: {
        "xi-api-key": apiKey,
        "Content-Type": "application/json",
        Accept: "audio/mpeg",
      },
      body: JSON.stringify({
        text: item.text,
        duration_seconds: item.duration,
        prompt_influence: item.influence,
      }),
    },
  );
  if (!response.ok) {
    const err = await response.text();
    console.error(`ElevenLabs error ${response.status} for ${item.file}:`, err);
    process.exit(1);
  }
  const buffer = Buffer.from(await response.arrayBuffer());
  const outPath = join(OUT_DIR, item.file);
  writeFileSync(outPath, buffer);
  console.log(`  wrote ${outPath} (${(buffer.length / 1024).toFixed(1)} KB)`);
}

async function main() {
  const env = { ...process.env, ...loadEnv() };
  const apiKey = env.ELEVENLABS_API_KEY;
  if (!apiKey) {
    console.error("ELEVENLABS_API_KEY not found in .env or environment");
    process.exit(1);
  }
  mkdirSync(OUT_DIR, { recursive: true });
  const only = process.argv.slice(2);
  const items =
    only.length > 0 ? SFX.filter((s) => only.includes(s.file)) : SFX;
  if (items.length === 0) {
    console.error("No matching SFX files. Available:", SFX.map((s) => s.file).join(", "));
    process.exit(1);
  }
  for (const item of items) {
    await generate(apiKey, item);
  }
  const clickMp3 = join(OUT_DIR, "mouse-click.mp3");
  const clickWav = join(OUT_DIR, "mouse-click.wav");
  if (existsSync(clickMp3) && !only.length) {
    copyFileSync(clickMp3, clickWav);
    console.log(`  copied ${clickWav}`);
  }
  console.log("Done.");
}

main().catch((e) => {
  console.error(e);
  process.exit(1);
});
