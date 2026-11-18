"""Build the exercise library from Free Exercise DB (public domain, Unlicense).

Source: https://github.com/yuhonas/free-exercise-db

The curated subset, Polish names and Polish instructions live in
scripts/exercises_curated.json. The script downloads the dataset JSON and the
start/end photos of every curated exercise, converts the photos to WebP
(max 640 px wide) and writes:

    app/data/exercises.json            library metadata (PL + EN)
    app/static/exercises/<slug>/0.webp start position
    app/static/exercises/<slug>/1.webp end position

Usage (requires Pillow from requirements-dev.txt):

    python scripts/import_exercises.py [--cache DIR] [--quality 75] [--width 640]
"""

import argparse
import io
import json
import re
import shutil
import sys
import urllib.request
from pathlib import Path

from PIL import Image

BASE_URL = "https://raw.githubusercontent.com/yuhonas/free-exercise-db/main"
DATASET_URL = f"{BASE_URL}/dist/exercises.json"
IMAGE_URL = f"{BASE_URL}/exercises/{{path}}"

ROOT = Path(__file__).resolve().parent.parent
CURATED = ROOT / "scripts" / "exercises_curated.json"
DATA_OUT = ROOT / "app" / "data" / "exercises.json"
IMAGES_OUT = ROOT / "app" / "static" / "exercises"

MUSCLES = {
    "abdominals", "abductors", "adductors", "biceps", "calves", "chest", "forearms", "glutes", "hamstrings",
    "lats", "lower back", "middle back", "neck", "quadriceps", "shoulders", "traps", "triceps",
}
# Dataset entries without equipment are body-weight drills and stretches.
EQUIPMENT_FALLBACK = {"Inverted_Row": "other"}


def slugify(value):
    return re.sub(r"-{2,}", "-", re.sub(r"[^a-z0-9]+", "-", value.lower())).strip("-")


def fetch(url, cache_dir):
    if not url.startswith("https://"):
        raise ValueError(f"refusing non-https URL: {url}")
    target = cache_dir / url.removeprefix(BASE_URL + "/")
    if target.exists():
        return target.read_bytes()
    with urllib.request.urlopen(url, timeout=60) as response:  # noqa: S310 - fixed https host
        data = response.read()
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(data)
    return data


def to_webp(data, width, quality):
    with Image.open(io.BytesIO(data)) as img:
        img = img.convert("RGB")
        if img.width > width:
            img = img.resize((width, round(img.height * width / img.width)), Image.LANCZOS)
        out = io.BytesIO()
        img.save(out, "WEBP", quality=quality, method=6)
        return out.getvalue(), img.size


def build_entry(src, cur):
    equipment = src["equipment"] or EQUIPMENT_FALLBACK.get(src["id"], "body only")
    primary = list(src["primaryMuscles"])
    secondary = [m for m in src["secondaryMuscles"] if m not in primary]
    assert set(primary) | set(secondary) <= MUSCLES, src["id"]
    entry = {
        "slug": slugify(src["id"]),
        "source_id": src["id"],
        "name_en": cur.get("name_en") or src["name"],
        "name_pl": cur["name_pl"],
        "category": "cardio" if src["category"] == "cardio" else "strength",
        "kind": src["category"],
        "level": src["level"],
        "equipment": equipment,
        "force": src["force"],
        "mechanic": src["mechanic"],
        "primary": primary,
        "secondary": secondary,
        "instructions_en": cur.get("instructions_en") or src["instructions"],
        "instructions_pl": cur["instructions_pl"],
    }
    if cur.get("legacy_name"):
        entry["legacy_name"] = cur["legacy_name"]
    return entry


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--cache", type=Path, default=ROOT / ".cache" / "free-exercise-db")
    parser.add_argument("--quality", type=int, default=75)
    parser.add_argument("--width", type=int, default=640)
    args = parser.parse_args(argv)

    curated = json.loads(CURATED.read_text(encoding="utf-8"))
    dataset = {x["id"]: x for x in json.loads(fetch(DATASET_URL, args.cache))}

    if IMAGES_OUT.exists():
        shutil.rmtree(IMAGES_OUT)
    entries, total_bytes = [], 0
    for cur in curated["exercises"]:
        src = dataset[cur["source"]]
        entry = build_entry(src, cur)
        if not entry["instructions_en"] or len(entry["instructions_pl"]) == 0:
            raise SystemExit(f"missing instructions for {src['id']}")
        images = []
        for idx, path in enumerate(src["images"][:2]):
            webp, size = to_webp(fetch(IMAGE_URL.format(path=path), args.cache), args.width, args.quality)
            rel = f"exercises/{entry['slug']}/{idx}.webp"
            out = IMAGES_OUT / entry["slug"] / f"{idx}.webp"
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_bytes(webp)
            total_bytes += len(webp)
            images.append(rel)
            entry["image_size"] = list(size)
        entry["images"] = images
        entries.append(entry)

    for extra in curated.get("extra", []):
        entries.append({"source_id": None, "kind": extra["category"], "images": [], **extra})

    slugs = [e["slug"] for e in entries]
    if len(slugs) != len(set(slugs)):
        raise SystemExit("duplicate slugs")
    entries.sort(key=lambda e: e["slug"])
    DATA_OUT.parent.mkdir(parents=True, exist_ok=True)
    DATA_OUT.write_text(json.dumps(entries, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"{len(entries)} exercises, {total_bytes / 1024 / 1024:.1f} MiB of images -> {DATA_OUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
