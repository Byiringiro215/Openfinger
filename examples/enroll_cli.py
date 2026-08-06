"""
Enroll a person from N fingerprint scans and pickle the resulting template.

Two modes:

  1. Live capture — reads N scans from the reader:
       python examples/enroll_cli.py alice --live --count 5

  2. From files — supply pre-captured PNG/JPEG files:
       python examples/enroll_cli.py alice img1.png img2.png img3.png

Output: gallery/<name>.pkl  (pickled tuple: (person_id, composite, [raw, ...]))
"""
import argparse
import logging
import pickle
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pipeline import enroll  # noqa: E402


def capture_live(count: int) -> list[bytes]:
    from scanner import ScannerBridge

    print(f"Live capture: press finger {count} times.\n")
    scans: list[bytes] = []
    with ScannerBridge() as bridge:
        for evt in bridge.events():
            if evt["type"] == "scan":
                scans.append(evt["data"])
                print(f"  [{len(scans)}/{count}] captured ({len(evt['data'])} bytes)")
                if len(scans) >= count:
                    break
            elif evt["type"] == "error":
                print(f"  bridge error [{evt['code']}]: {evt['message']}")
    return scans


def main() -> int:
    ap = argparse.ArgumentParser(description="Enroll a fingerprint")
    ap.add_argument("person_id", help="Identifier for this person (used as filename)")
    ap.add_argument("images", nargs="*", help="Pre-captured image files (if not --live)")
    ap.add_argument("--live", action="store_true", help="Capture from the reader now")
    ap.add_argument("--count", type=int, default=5, help="Number of live scans (--live mode)")
    ap.add_argument("--gallery", default="gallery", help="Output directory")
    args = ap.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

    if args.live:
        images = capture_live(args.count)
    elif args.images:
        images = [Path(p).read_bytes() for p in args.images]
    else:
        ap.error("Provide image files, or --live to capture from the reader.")
        return 2

    if len(images) < 2:
        print("Need at least 2 scans to enroll.")
        return 1

    print(f"\nEnrolling {args.person_id} from {len(images)} scans...")
    result = enroll(images)

    if result.get("error"):
        print(f"Enrollment failed: {result['error']}")
        for i, q in enumerate(result.get("quality_scores", [])):
            print(f"  scan {i}: {q}")
        return 1

    gallery_dir = Path(args.gallery)
    gallery_dir.mkdir(parents=True, exist_ok=True)
    out_path = gallery_dir / f"{args.person_id}.pkl"
    with open(out_path, "wb") as f:
        pickle.dump(
            (args.person_id, result["template_bytes"], result["raw_templates"]),
            f,
        )

    print(f"OK — enrolled {args.person_id}")
    print(f"  raw templates: {len(result['raw_templates'])}")
    print(f"  steps applied: {result['steps_applied']}")
    print(f"  saved: {out_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
