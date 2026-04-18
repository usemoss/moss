/**
 * Downloads COCO Captions annotations and produces tiered JSON files
 * compatible with the Moss document schema.
 *
 * Source: http://images.cocodataset.org/annotations/annotations_trainval2017.zip
 *
 * Output files (gitignored):
 *   coco-data-1k.json, coco-data-10k.json, coco-data-50k.json,
 *   coco-data-100k.json
 */

import * as fs from "fs";
import * as path from "path";
import * as https from "https";
import * as http from "http";
import { execSync } from "child_process";

const ANNOTATIONS_URL =
  "http://images.cocodataset.org/annotations/annotations_trainval2017.zip";
const ANNOTATIONS_DIR = path.resolve(__dirname, "../annotations");
const OUTPUT_DIR = path.resolve(__dirname, "..");
const SEED = 42;

const TIERS: ReadonlyArray<{ readonly name: string; readonly size: number }> = [
  { name: "1k", size: 1_000 },
  { name: "10k", size: 10_000 },
  { name: "50k", size: 50_000 },
  { name: "100k", size: 100_000 },
];

interface CocoCaption {
  readonly image_id: number;
  readonly id: number;
  readonly caption: string;
}

interface CocoImage {
  readonly id: number;
  readonly coco_url: string;
  readonly file_name: string;
}

interface CocoCaptionsFile {
  readonly images: readonly CocoImage[];
  readonly annotations: readonly CocoCaption[];
}

interface MossDocument {
  readonly id: string;
  readonly text: string;
  readonly metadata: {
    readonly url: string;
    readonly image_id: string;
  };
}

/** Deterministic shuffle using a seeded PRNG (mulberry32). */
function seededShuffle<T>(array: T[], seed: number): T[] {
  let s = seed | 0;
  const next = (): number => {
    s = (s + 0x6d2b79f5) | 0;
    let t = Math.imul(s ^ (s >>> 15), 1 | s);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4_294_967_296;
  };

  const result = [...array];
  for (let i = result.length - 1; i > 0; i--) {
    const j = Math.floor(next() * (i + 1));
    [result[i], result[j]] = [result[j], result[i]];
  }
  return result;
}

function downloadFile(url: string, dest: string): Promise<void> {
  return new Promise((resolve, reject) => {
    const file = fs.createWriteStream(dest);
    const protocol = url.startsWith("https") ? https : http;

    protocol
      .get(url, (response) => {
        if (
          response.statusCode &&
          response.statusCode >= 300 &&
          response.statusCode < 400 &&
          response.headers.location
        ) {
          const redirectUrl = response.headers.location;
          // Prevent HTTPS-to-HTTP downgrade on redirect
          if (url.startsWith("https://") && redirectUrl.startsWith("http://")) {
            file.close();
            if (fs.existsSync(dest)) fs.unlinkSync(dest);
            reject(
              new Error(
                `Refusing to follow insecure redirect from HTTPS to HTTP: ${redirectUrl}`
              )
            );
            return;
          }

          file.close();
          if (fs.existsSync(dest)) fs.unlinkSync(dest);
          downloadFile(redirectUrl, dest)
            .then(resolve)
            .catch(reject);
          return;
        }

        if (response.statusCode !== 200) {
          file.close();
          fs.unlinkSync(dest);
          reject(new Error(`Download failed with status ${response.statusCode}`));
          return;
        }

        const totalBytes = parseInt(response.headers["content-length"] ?? "0", 10);
        let downloadedBytes = 0;

        response.on("data", (chunk: Buffer) => {
          downloadedBytes += chunk.length;
          if (totalBytes > 0) {
            const pct = ((downloadedBytes / totalBytes) * 100).toFixed(1);
            process.stdout.write(`\rDownloading... ${pct}%`);
          }
        });

        response.pipe(file);
        file.on("finish", () => {
          file.close();
          console.log("\nDownload complete.");
          resolve();
        });
      })
      .on("error", (err) => {
        file.close();
        if (fs.existsSync(dest)) fs.unlinkSync(dest);
        reject(err);
      });
  });
}

function parseCaptionsFile(filePath: string): CocoCaptionsFile {
  const raw = fs.readFileSync(filePath, "utf-8");
  return JSON.parse(raw) as CocoCaptionsFile;
}

function buildDocuments(
  captionFiles: readonly string[]
): MossDocument[] {
  const imageMap = new Map<number, { url: string; captions: string[] }>();

  for (const file of captionFiles) {
    console.log(`Parsing ${path.basename(file)}...`);
    const data = parseCaptionsFile(file);

    for (const img of data.images) {
      if (!imageMap.has(img.id)) {
        imageMap.set(img.id, { url: img.coco_url, captions: [] });
      }
    }

    for (const ann of data.annotations) {
      const entry = imageMap.get(ann.image_id);
      if (entry) {
        entry.captions.push(ann.caption.trim());
      }
    }
  }

  const documents: MossDocument[] = [];
  for (const [imageId, entry] of imageMap) {
    if (entry.captions.length === 0) continue;
    documents.push({
      id: `coco-${imageId}`,
      text: entry.captions.join(" | "),
      metadata: {
        url: entry.url,
        image_id: String(imageId),
      },
    });
  }

  return documents;
}

async function main(): Promise<void> {
  const zipPath = path.join(ANNOTATIONS_DIR, "annotations_trainval2017.zip");

  // Download if not already present
  if (!fs.existsSync(zipPath)) {
    console.log("Downloading COCO annotations...");
    fs.mkdirSync(ANNOTATIONS_DIR, { recursive: true });
    await downloadFile(ANNOTATIONS_URL, zipPath);
  } else {
    console.log("Annotations zip already downloaded, skipping.");
  }

  // Extract if needed
  const trainFile = path.join(ANNOTATIONS_DIR, "annotations", "captions_train2017.json");
  const valFile = path.join(ANNOTATIONS_DIR, "annotations", "captions_val2017.json");

  if (!fs.existsSync(trainFile) || !fs.existsSync(valFile)) {
    console.log("Extracting annotations...");
    execSync(`unzip -o "${zipPath}" -d "${ANNOTATIONS_DIR}"`, { stdio: "inherit" });
  } else {
    console.log("Annotations already extracted, skipping.");
  }

  // Build combined document list
  console.log("Building document list from captions...");
  const allDocuments = buildDocuments([trainFile, valFile]);
  console.log(`Total unique images with captions: ${allDocuments.length}`);

  // Shuffle deterministically
  const shuffled = seededShuffle(allDocuments, SEED);

  // Write tiered files
  for (const tier of TIERS) {
    const count = Math.min(tier.size, shuffled.length);
    const slice = shuffled.slice(0, count);
    const outputPath = path.join(OUTPUT_DIR, `coco-data-${tier.name}.json`);

    fs.writeFileSync(outputPath, JSON.stringify(slice, null, 2), "utf-8");
    console.log(`Wrote ${slice.length} documents to ${path.basename(outputPath)}`);
  }

  console.log("\nDone! Tiered COCO data files are ready.");
}

main().catch((err) => {
  console.error("Fatal error:", err);
  process.exit(1);
});
