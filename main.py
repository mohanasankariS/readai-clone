"""
Read AI Clone - Backend
Handles: sending a bot into a meeting (Zoom/Meet/Teams via Recall.ai),
receiving the transcript webhook, summarizing with Claude, storing results.
"""
import os
import requests
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from summarizer import summarize_transcript
from db import save_meeting, get_meeting, list_meetings

app = FastAPI(title="Read AI Clone")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

RECALL_API_KEY = os.environ.get("RECALL_API_KEY")
RECALL_BASE_URL = "https://ap-northeast-1.recall.ai/api/v1"  # Asia (Japan) region

# Where Recall.ai should send the webhook when the meeting is done.
# In production this is your public backend URL, e.g. https://yourapp.onrender.com/webhook/recall
WEBHOOK_URL = os.environ.get("WEBHOOK_URL", "http://localhost:8000/webhook/recall")


class JoinMeetingRequest(BaseModel):
    meeting_url: str          # any Zoom/Meet/Teams link
    bot_name: str = "Meeting Notetaker"


@app.post("/meetings/join")
def join_meeting(req: JoinMeetingRequest):
    """
    Sends a bot into the given meeting URL. Works for Zoom, Google Meet,
    and Microsoft Teams links automatically - Recall.ai detects the platform.
    """
    if not RECALL_API_KEY:
        raise HTTPException(500, "RECALL_API_KEY not configured")

    payload = {
        "meeting_url": req.meeting_url,
        "bot_name": req.bot_name,
        "transcription_options": {"provider": "meeting_captions"},
        "recording_config": {
            "transcript": {"provider": {"meeting_captions": {}}}
        },
        "webhook_url": WEBHOOK_URL,
    }

    resp = requests.post(
        f"{RECALL_BASE_URL}/bot",
        json=payload,
        headers={"Authorization": f"Token {RECALL_API_KEY}"},
    )

    if resp.status_code >= 300:
        raise HTTPException(resp.status_code, resp.text)

    bot_data = resp.json()
    save_meeting(bot_id=bot_data["id"], meeting_url=req.meeting_url, status="joining")
    return {"bot_id": bot_data["id"], "status": "bot is joining the meeting"}


@app.post("/webhook/recall")
async def recall_webhook(request: Request):
    """
    Recall.ai calls this URL when events happen (bot joined, recording done,
    transcript ready, etc). We care mostly about 'transcript.done'.
    """
    payload = await request.json()
    event = payload.get("event")
    bot_id = payload.get("data", {}).get("bot", {}).get("id")

    if event == "transcript.done" and bot_id:
        transcript_text = fetch_transcript_text(bot_id)
        summary = summarize_transcript(transcript_text)
        save_meeting(
            bot_id=bot_id,
            status="completed",
            transcript=transcript_text,
            summary=summary["summary"],
            action_items=summary["action_items"],
            highlights=summary["highlights"],
        )

    return {"received": True}


def fetch_transcript_text(bot_id: str) -> str:
    """Pulls the finished transcript from Recall.ai for a given bot."""
    resp = requests.get(
        f"{RECALL_BASE_URL}/bot/{bot_id}/transcript",
        headers={"Authorization": f"Token {RECALL_API_KEY}"},
    )
    resp.raise_for_status()
    data = resp.json()
    # Each entry has speaker + words; join into plain text with speaker labels
    lines = []
    for segment in data:
        speaker = segment.get("speaker", "Unknown")
        words = " ".join(w["text"] for w in segment.get("words", []))
        lines.append(f"{speaker}: {words}")
    return "\n".join(lines)


@app.get("/meetings")
def get_meetings():
    return list_meetings()


@app.get("/meetings/{bot_id}")
def get_single_meeting(bot_id: str):
    meeting = get_meeting(bot_id)
    if not meeting:
        raise HTTPException(404, "Meeting not found")
    return meeting
