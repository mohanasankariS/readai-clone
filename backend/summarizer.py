"""
Turns a raw transcript into: summary, action items, highlights.
Uses Claude via the Anthropic API.
"""
import os
import json
import anthropic

client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))

PROMPT_TEMPLATE = """You are analyzing a meeting transcript. Return ONLY valid JSON
(no markdown, no preamble) in this exact shape:

{{
  "summary": "2-4 sentence summary of what the meeting was about and what was decided",
  "action_items": ["action item 1", "action item 2"],
  "highlights": ["notable quote or moment 1", "notable quote or moment 2"]
}}

Transcript:
{transcript}
"""


def summarize_transcript(transcript: str) -> dict:
    if not transcript.strip():
        return {"summary": "", "action_items": [], "highlights": []}

    message = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1024,
        messages=[
            {"role": "user", "content": PROMPT_TEMPLATE.format(transcript=transcript)}
        ],
    )

    raw_text = message.content[0].text.strip()
    raw_text = raw_text.replace("```json", "").replace("```", "").strip()

    try:
        return json.loads(raw_text)
    except json.JSONDecodeError:
        return {"summary": raw_text, "action_items": [], "highlights": []}