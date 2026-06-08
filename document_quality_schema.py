SCHEMA_VERSION = "1.0"

# Universal schema for all document types
UNIVERSAL_SCHEMA = {
    "min_quality_score": 0.65,
    "min_ocr_confidence": 0.60,
    "min_coverage": 0.14,
    "min_contrast": 28,
    "min_resolution": 180_000,
    "max_skew": 6,
}


def get_universal_schema():
    return UNIVERSAL_SCHEMA
