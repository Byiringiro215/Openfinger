"""
1:N fingerprint identification against a gallery of enrolled templates.

Two modes:

  1. Live capture — reads one scan then matches:
       python examples/identify_cli.py --live

  2. From file — supply a pre-captured probe image:
       python examples/identify_cli.py probe.png

Gallery is loaded from `--gallery` (default: `gallery/`).
Each `<name>.pkl` in that directory should have been produced by enroll_cli.py.
"""
import argparse
import logging
import pickle
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pipeline import identify  # noqa: E402


def load_gallery(gallery_dir: Path) -> list[tuple[str, bytes, list[bytes]]]:
    entries: list[tuple[str, bytes, list[bytes]]] = []
    for pkl in sorted(gallery_dir.glob("*.pkl")):
        with open(pkl, "rb") as f:
            person_id, composite, raws = pickle.load(f)
        entries.append((person_id, composite, raws))
    return entries


def unpickle_templates(gallery: list[tuple[str, bytes, list[bytes]]]):
    """identify() expects unpickled template objects."""
    unpacked = []
    for person_id, comp, raws in gallery:
        comp_obj = pickle.loads(comp) if isinstance(comp, bytes) else comp
        raws_obj = [pickle.loads(r) if isinstance(r, bytes) else r for r in raws]
        unpacked.append((person_id, comp_obj, raws_obj))
    return unpacked


def capture_probe() -> bytes:
    from scanner import ScannerBridge

    print("Place your finger on the reader to identify...\n")
    with ScannerBridge() as bridge:
        for evt in bridge.events():
            if evt["type"] == "scan":
                return evt["data"]
            if evt["type"] == "error":
                print(f"  bridge error [{evt['code']}]: {evt['message']}")
    return b""


def main() -> int:
    ap = argparse.ArgumentParser(description="Identify a fingerprint against a gallery")
    ap.add_argument("probe", nargs="?", help="Probe image file (omit if --live)")
    ap.add_argument("--live", action="store_true", help="Capture probe from the reader")
    ap.add_argument("--gallery", default="gallery", help="Directory of enrolled *.pkl files")
    args = ap.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

    gallery_dir = Path(args.gallery)
    if not gallery_dir.exists():
        print(f"Gallery directory not found: {gallery_dir}")
        print("Enroll someone first: python examples/enroll_cli.py alice --live")
        return 1

    gallery = load_gallery(gallery_dir)
    if not gallery:
        print(f"No enrolled templates in {gallery_dir}/")
        return 1
    print(f"Loaded {len(gallery)} enrolled persons from {gallery_dir}/")

    if args.live:
        probe = capture_probe()
    elif args.probe:
        probe = Path(args.probe).read_bytes()
    else:
        ap.error("Provide a probe image file, or --live to capture now.")
        return 2

    if not probe:
        print("No probe image.")
        return 1

    unpacked_gallery = unpickle_templates(gallery)
    result = identify(probe, unpacked_gallery)

    print()
    print(f"Result:  matched={result['matched']}")
    print(f"         flag={result['flag']}")
    print(f"         person_id={result['person_id']}")
    print(f"         confidence_score={result['confidence_score']:.2f}")
    if "second_score" in result:
        print(f"         second_score={result['second_score']:.2f}")
    if "clarity" in result:
        print(f"         probe_clarity={result['clarity']:.3f}")
    return 0 if result["matched"] else 1


if __name__ == "__main__":
    sys.exit(main())
