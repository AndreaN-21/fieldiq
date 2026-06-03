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

Your response must be valid JSON matching this schema exactly:
{
  "defect_type": "string — e.g., 'Structural crack', 'Moisture infiltration', 'Spalling'",
  "affected_component": "string — e.g., 'Reinforced concrete slab', 'External facade masonry'",
  "likely_cause": "string — 1-2 sentences, technical, concise",
  "severity": "one of: Critical, High, Medium, Low",
  "severity_justification": "string — 1-2 sentences explaining the severity rating",
  "norm_references": [
    {
      "title": "string — full name of the standard",
      "article": "string — specific article or section number",
      "excerpt": "string — verbatim excerpt from the provided context, max 200 chars",
      "source_url": "string — from the document metadata"
    }
  ],
  "report_template": "string — markdown-formatted pre-filled section for an inspection report",
  "disclaimer": "AI-assisted analysis based on public technical standards. Must be reviewed by a certified inspector before inclusion in official reports."
}

CRITICAL RULES:
- norm_references must ONLY cite documents present in the provided context. Never invent norm numbers.
- If the provided context does not contain a relevant norm, set norm_references to an empty array.
- severity must reflect structural risk, not just cosmetic concern. A large crack near a load-bearing element is Critical even if it looks minor.
- report_template must use the following markdown structure:
  ## Defect Observation
  [pre-filled based on description]
  ## Classification
  [type + component]
  ## Applicable Standards
  [list of references]
  ## Recommended Action
  [derived from severity]
- Do not add any text outside the JSON object.
"""


def _format_chunks(chunks: list[RetrievedChunk]) -> str:
    """Format retrieved chunks as labelled excerpts for the LLM prompt."""
    if not chunks:
        return "No relevant norm excerpts found in the knowledge base."

    parts: list[str] = []
    for chunk in chunks:
        header = f"[Source: {chunk.title}, Page {chunk.page}]"
        parts.append(f"{header}\n{chunk.text}")

    return "\n\n".join(parts)


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
        base_url=settings.openai_base_url,
    )

    logger.debug(f"Calling {settings.openai_model} with {len(context_chunks)} context chunks")

    message = client.chat.completions.create(
        model=settings.openai_model,
        max_tokens=2048,
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

    return result
