"""Pydantic v2 request and response models for the FieldIQ API."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class AnalyzeRequest(BaseModel):
    description: str = Field(
        ...,
        min_length=20,
        max_length=2000,
        description="Inspector's field description of the observed defect",
    )


class NormReference(BaseModel):
    title: str
    article: str
    excerpt: str
    source_url: str


class AnalysisResult(BaseModel):
    defect_type: str
    affected_component: str
    likely_cause: str
    severity: Literal["Critical", "High", "Medium", "Low"]
    severity_justification: str
    norm_references: list[NormReference]
    report_template: str
    disclaimer: str
