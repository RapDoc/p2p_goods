from typing import List

from pydantic import BaseModel, Field, validator


class QualityChecks(BaseModel):
    page_blurriness: str = Field(..., alias="Page Blurriness")
    page_rotation: str = Field(..., alias="Page Rotation")
    ocr_confidence_score: str = Field(..., alias="OCR Confidence Score")
    resolution_validation: str = Field(..., alias="Resolution/DPI Validation")
    crop_cutoff: str = Field(..., alias="Crop Cutoff / margins")
    clarity_rating: str = Field(..., alias="Clarity Rating")
    blank_page: str = Field(..., alias="Blank page")
    content_coverage: str = Field(..., alias="Content Coverage")

    class Config:
        validate_by_name = True


class PageQualityResponse(BaseModel):
    page_number: int
    quality_score: float
    is_compliant: bool
    reasons: List[str]
    flowback_status: str | None = None
    schema_version: str | None = None
    quality_checks: QualityChecks
    analysis_method: str = "rule_based"
    llm_quality_review: str | None = None
    page_bytes_base64: str | None = None

    @validator("quality_score")
    def validate_quality_score(cls, value):
        if not 0.0 <= value <= 1.0:
            raise ValueError("quality_score must be between 0 and 1")
        return round(value, 3)


class DocumentQualityResponse(BaseModel):
    pages: List[PageQualityResponse]
