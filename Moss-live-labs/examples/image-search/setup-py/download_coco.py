"""Downloads COCO Captions annotations and produces tiered JSON files.

Source: http://images.cocodataset.org/annotations/annotations_trainval2017.zip

Output files (gitignored):
    coco-data-1k.json, coco-data-10k.json, coco-data-50k.json,
    coco-data-100k.json
"""

from __future__ import annotations

import json
import random
import urllib.request
import zipfile
from pathlib import Path
from typing import Any

ANNOTATIONS_URL = (
    "http://images.cocodataset.org/annotations/annotations_trainval2017.zip"
)
ROOT_DIR = Path(__file__).resolve().parent.parent
ANNOTATIONS_DIR = ROOT_DIR / "annotations"
OUTPUT_DIR = ROOT_DIR
SEED = 42

TIERS: list[tuple[str, int | None]] = [
    ("1k", 1_000),
    ("10k", 10_000),
    ("50k", 50_000),
    ("100k", 100_000),
]


def download_file(url: str, dest: Path) -> None:
    """Download a file with progress reporting."""
    print(f"Downloading {url}...")

    def _report(block_num: int, block_size: int, total_size: int) -> None:
        if total_size > 0:
            pct = min(100.0, block_num * block_size / total_size * 100)
            print(f"\rDownloading... {pct:.1f}%", end="", flush=True)

    urllib.request.urlretrieve(url, str(dest), reporthook=_report)
    print("\nDownload complete.")


def parse_captions_file(file_path: Path) -> dict[str, Any]:
    """Parse a COCO captions JSON file."""
    with file_path.open("r", encoding="utf-8") as f:
        return json.load(f)


def build_documents(caption_files: list[Path]) -> list[dict[str, Any]]:
    """Build Moss-compatible documents from COCO caption files."""
    image_map: dict[int, dict[str, Any]] = {}

    for file_path in caption_files:
        print(f"Parsing {file_path.name}...")
        data = parse_captions_file(file_path)

        for img in data["images"]:
            if img["id"] not in image_map:
                image_map[img["id"]] = {
                    "url": img["coco_url"],
                    "captions": [],
                }

        for ann in data["annotations"]:
            entry = image_map.get(ann["image_id"])
            if entry is not None:
                entry["captions"].append(ann["caption"].strip())

    documents: list[dict[str, Any]] = []
    for image_id, entry in image_map.items():
        if not entry["captions"]:
            continue
        documents.append(
            {
                "id": f"coco-{image_id}",
                "text": " | ".join(entry["captions"]),
                "metadata": {
                    "url": entry["url"],
                    "image_id": str(image_id),
                },
            }
        )

    return documents


def main() -> None:
    """Download COCO annotations and produce tiered JSON files."""
    zip_path = ANNOTATIONS_DIR / "annotations_trainval2017.zip"

    # Download if not already present
    if not zip_path.exists():
        ANNOTATIONS_DIR.mkdir(parents=True, exist_ok=True)
        download_file(ANNOTATIONS_URL, zip_path)
    else:
        print("Annotations zip already downloaded, skipping.")

    # Extract if needed
    train_file = ANNOTATIONS_DIR / "annotations" / "captions_train2017.json"
    val_file = ANNOTATIONS_DIR / "annotations" / "captions_val2017.json"

    if not train_file.exists() or not val_file.exists():
        print("Extracting annotations...")
        with zipfile.ZipFile(zip_path, "r") as zf:
            zf.extractall(ANNOTATIONS_DIR)
    else:
        print("Annotations already extracted, skipping.")

    # Build combined document list
    print("Building document list from captions...")
    all_documents = build_documents([train_file, val_file])
    print(f"Total unique images with captions: {len(all_documents)}")

    # Shuffle deterministically
    rng = random.Random(SEED)
    rng.shuffle(all_documents)

    # Write tiered files
    for tier_name, tier_size in TIERS:
        count = len(all_documents) if tier_size is None else min(tier_size, len(all_documents))
        tier_slice = all_documents[:count]
        output_path = OUTPUT_DIR / f"coco-data-{tier_name}.json"

        with output_path.open("w", encoding="utf-8") as f:
            json.dump(tier_slice, f, indent=2)

        print(f"Wrote {len(tier_slice)} documents to {output_path.name}")

    print("\nDone! Tiered COCO data files are ready.")


if __name__ == "__main__":
    main()
