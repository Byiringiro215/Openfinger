"""
openfinger — fingerprint enrollment and identification pipeline.

Public API:

    from pipeline import enroll, identify, check_quality, PIPELINE_CONFIG

    # Enroll: pass a list of PNG/JPEG bytes (multiple scans of one finger)
    result = enroll([img1_bytes, img2_bytes, ...])
    template_bytes = result["template_bytes"]
    raw_templates  = result["raw_templates"]

    # Identify: pass one probe scan + the enrolled gallery
    gallery = [(person_id, composite_bytes, raw_templates_list), ...]
    result = identify(probe_bytes, gallery)
    if result["matched"]:
        print("Match:", result["person_id"], result["confidence_score"])

Matcher backend is selected in `PIPELINE_CONFIG`:
  * USE_NBIS_MATCHER      — NIST bozorth3 (biometric-grade). Requires
                            mindtct.exe + bozorth3.exe in bridge/nbis/.
  * USE_EMBEDDING_MATCHER — DINOv2 cosine (transformers optional dep).
  * (fallback)            — homebrew edge-based BFS matcher in minutiae.py.
"""
from .enroll import enroll
from .match import identify
from .quality import check_quality
from .preprocess import preprocess, preprocess_for_template
from .pipeline_config import PIPELINE_CONFIG

__all__ = [
    "enroll",
    "identify",
    "check_quality",
    "preprocess",
    "preprocess_for_template",
    "PIPELINE_CONFIG",
]
