"""LLM-based defect analysis using OpenAI — builds prompt, calls API, parses response."""

from __future__ import annotations

import json

import openai
from loguru import logger

from config import settings
from core.rag import RetrievedChunk

SYSTEM_PROMPT = """
You are a technical assistant for certified building inspectors.
Your role is to analyze defect observations and provide structured, normatively grounded assessments.

You will receive:
1. A defect description written by a field inspector
2. A set of excerpts from technical standards and building norms (your ONLY allowed sources)

Your response must be a single valid JSON object. No text before or after it.

JSON schema (follow exactly):
{
  "defect_type": "short label, e.g. 'Moisture infiltration' — plain text, no markdown",
  "affected_component": "short label, e.g. 'Basement wall masonry' — plain text, no markdown",
  "likely_cause": "1-2 sentences, technical, concise — plain text, no markdown headers",
  "severity": "exactly one of: Critical, High, Medium, Low",
  "severity_justification": "1-2 sentences — plain text, no markdown headers, separate from severity",
  "norm_references": [
    {
      "title": "full name of the standard or guide",
      "article": "article/section number if present, otherwise 'p.<page number>' e.g. 'p.69'",
      "excerpt": "verbatim excerpt from the provided context only, max 200 chars",
      "source_url": "URL from the document metadata provided in context"
    }
  ],
  "report_template": "markdown string — see format below",
  "disclaimer": "AI-assisted analysis based on public technical standards. Must be reviewed by a certified inspector before inclusion in official reports."
}

CRITICAL RULES:
- defect_type, affected_component, likely_cause, severity_justification must be plain text strings. Never use markdown headers (##, ###) inside these fields.
- severity must be exactly one word: Critical, High, Medium, or Low. Nothing else in that field.
- severity_justification is a separate field from severity — never concatenate them.
- norm_references must ONLY cite documents present in the provided context. Never invent norm numbers or URLs.
- You MUST include a norm_reference for every document in the context that contains content relevant to the defect, even partially. Do not leave norm_references empty if the context contains any relevant text.
- If a document has no visible article number, use the page number as the article field: e.g. 'p.69'.
- If the context contains no relevant content at all, only then set norm_references to [].
- severity must reflect structural risk. A large crack near a load-bearing element is Critical even if it looks minor.
- report_template must use exactly this markdown structure:
  ## Defect Observation
  [pre-filled based on description]
  ## Classification
  [type + component]
  ## Applicable Standards
  For each relevant norm, one bullet with: standard name + article, why it applies, key requirement/limit value.
  Example: - **NIST TN 2220, Section 3.2** — Applies because moisture infiltration in basements requires assessment of wall permeability. Requirement: "...verbatim key sentence..."
  ## Recommended Action
  [concrete action derived from severity: Critical=immediate intervention, High=urgent repair within weeks, Medium=planned maintenance, Low=monitor]
- Do not add any text outside the JSON object.
"""


def _format_chunks(chunks: list[RetrievedChunk]) -> str:
    """Format retrieved chunks as labelled excerpts for the LLM prompt."""
    if not chunks:
        return "No relevant norm excerpts found in the knowledge base."

    parts: list[str] = []
    for chunk in chunks:
        location = f"§{chunk.section}" if chunk.section else f"p.{chunk.page}" 
        header = f"[Source: {chunk.title}, Location: {location}, URL: {chunk.source_url}]"
        parts.append(f"{header}\n{chunk.text}")

    return "\n\n".join(parts)


import re

def _sanitize(raw: dict) -> dict:
    """Strip markdown headers and fix common GPT formatting mistakes in plain-text fields."""

    def clean(text: str) -> str:
        if not isinstance(text, str):
            return text
        # Remove lines that are only markdown headers (## Title, ### Title)
        lines = text.splitlines()
        cleaned = [re.sub(r"^#{1,4}\s+", "", line) for line in lines]
        return "\n".join(cleaned).strip()

    # Fields that must be plain text (no markdown headers)
    for field in ("defect_type", "affected_component", "likely_cause", "severity_justification"):
        if field in raw:
            raw[field] = clean(raw[field])

    # severity must be exactly one word — strip anything after the first word
    if "severity" in raw and isinstance(raw["severity"], str):
        # Fix "HighWhile there are no..." → split into severity + justification
        valid = {"Critical", "High", "Medium", "Low"}
        for level in valid:
            if raw["severity"].startswith(level) and raw["severity"] != level:
                # The model concatenated severity + justification
                overflow = raw["severity"][len(level):].strip()
                raw["severity"] = level
                # Prepend the overflow to severity_justification if it's missing context
                existing = raw.get("severity_justification", "")
                if overflow and overflow not in existing:
                    raw["severity_justification"] = overflow + (" " + existing if existing else "")
                break

    return raw


def analyze(description: str, context_chunks: list[RetrievedChunk]) -> dict:
    """Call OpenAI to classify the defect and build a structured analysis result.

    Returns the raw parsed dict — callers are responsible for constructing the
    AnalysisResult Pydantic model so validation happens at the API boundary.

    Raises error on API failures — callers must catch and convert to 503.
    """
    user_message = (
        f"DEFECT DESCRIPTION:\n{description}\n\n"
        f"RELEVANT NORM EXCERPTS:\n{_format_chunks(context_chunks)}"
    )

    client = openai.OpenAI(
        api_key=settings.openai_api_key,
        base_url=settings.openai_base_url
    )

    logger.debug(f"Calling {settings.openai_model} with {len(context_chunks)} context chunks")

    message = client.chat.completions.create(
        model=settings.openai_model,
        max_tokens=2048,
        temperature=0.1,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_message},
        ],
    )

    raw_text = message.choices[0].message.content.strip()

    # Strip markdown code fences if the model wraps the JSON in ```json ... ```
    if raw_text.startswith("```"):
        lines = raw_text.splitlines()
        raw_text = "\n".join(
            line for line in lines if not line.strip().startswith("```")
        ).strip()

    try:
        result = json.loads(raw_text)
    except json.JSONDecodeError as exc:
        logger.error(f"LLM returned non-JSON: {raw_text[:200]}")
        raise ValueError(f"LLM response is not valid JSON: {exc}") from exc

    return _sanitize(result)
