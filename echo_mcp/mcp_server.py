"""ECHO — Explore Calls, Hearings & Observations.

MCP server for searching Zoom meeting transcripts.
Part of the Alpine Toolkit.
"""

from __future__ import annotations

import re
from datetime import date, timedelta

from mcp.server.fastmcp import FastMCP

from .auth import load_tokens, tokens_valid
from .connector import ZoomConnector

mcp = FastMCP(
    "ECHO",
    instructions="Explore Calls, Hearings & Observations — search Zoom meeting transcripts",
)
zoom = ZoomConnector()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _parse_vtt(vtt_text: str) -> list[dict]:
    """Parse a WebVTT transcript into a list of {timestamp, speaker, text} dicts."""
    blocks = re.split(r"\n\n+", vtt_text.strip())
    entries = []
    for block in blocks:
        lines = block.strip().splitlines()
        if not lines or lines[0].startswith("WEBVTT"):
            continue
        ts_line = None
        text_lines = []
        for line in lines:
            if "-->" in line:
                ts_line = line.strip()
            elif ts_line is not None:
                text_lines.append(line.strip())
        if ts_line and text_lines:
            full_text = " ".join(text_lines)
            speaker = ""
            text = full_text
            if ": " in full_text:
                speaker, text = full_text.split(": ", 1)
            entries.append({"timestamp": ts_line, "speaker": speaker, "text": text})
    return entries


async def _get_transcript_for_meeting(meeting_id: str) -> list[dict] | None:
    """Fetch and parse the transcript for a meeting, or None if unavailable."""
    try:
        rec_data = await zoom.get_meeting_recordings(meeting_id)
    except Exception:
        return None

    download_url = None
    for f in rec_data.get("recording_files", []):
        if (
            f.get("recording_type") == "audio_transcript"
            or f.get("file_extension", "").upper() == "VTT"
        ):
            download_url = f.get("download_url")
            break

    if not download_url:
        return None

    vtt_text = await zoom.get_transcript_content(download_url)
    return _parse_vtt(vtt_text)


# ---------------------------------------------------------------------------
# Tools
# ---------------------------------------------------------------------------

@mcp.tool()
async def auth_status() -> str:
    """Check if ECHO is authenticated with Zoom.

    Returns the current auth status and instructions if not logged in.
    """
    tokens = load_tokens()
    if tokens is None:
        return (
            "**Not authenticated.**\n\n"
            "Run this in your terminal to log in:\n"
            "```\necho-login\n```\n"
            "This will open Zoom in your browser to authorize ECHO."
        )

    if tokens_valid(tokens):
        return "**Authenticated** — ECHO is connected to your Zoom account."
    else:
        return (
            "**Token expired** — ECHO will auto-refresh on the next request.\n"
            "If that fails, run `echo-login` to re-authenticate."
        )


@mcp.tool()
async def list_meetings(days: int = 30) -> str:
    """List recent Zoom meetings that have cloud recordings (and potentially transcripts).

    Args:
        days: How many days back to look (default 30, max 30).
    """
    days = min(days, 30)
    to_date = date.today()
    from_date = to_date - timedelta(days=days)

    data = await zoom.list_recordings(
        from_date=from_date.isoformat(), to_date=to_date.isoformat()
    )

    meetings = data.get("meetings", [])
    if not meetings:
        return "No recordings found in the last {} days.".format(days)

    results = []
    for m in meetings:
        has_transcript = any(
            f.get("recording_type") == "audio_transcript"
            or f.get("file_extension", "").upper() == "VTT"
            for f in m.get("recording_files", [])
        )
        results.append(
            "- **{}** (ID: {}) — {} | Transcript: {}".format(
                m.get("topic", "Untitled"),
                m.get("id") or m.get("uuid"),
                m.get("start_time", "unknown date"),
                "Yes" if has_transcript else "No",
            )
        )

    return "## Meetings with recordings (last {} days)\n\n{}".format(
        days, "\n".join(results)
    )


@mcp.tool()
async def get_transcript(meeting_id: str) -> str:
    """Get the full transcript for a specific Zoom meeting.

    Args:
        meeting_id: The Zoom meeting ID (numeric or UUID).
    """
    entries = await _get_transcript_for_meeting(meeting_id)
    if entries is None:
        return "No transcript found for meeting {}.".format(meeting_id)

    lines = []
    for e in entries:
        speaker = "**{}**".format(e["speaker"]) if e["speaker"] else ""
        lines.append("{} {}: {}".format(e["timestamp"], speaker, e["text"]))

    return "## Transcript for meeting {}\n\n{}".format(meeting_id, "\n".join(lines))


@mcp.tool()
async def search_transcripts(query: str, days: int = 30) -> str:
    """Search across Zoom meeting transcripts for a keyword or phrase.

    Fetches all recent meetings with transcripts and searches through them.

    Args:
        query: The search term or phrase to find in transcripts.
        days: How many days back to search (default 30, max 30).
    """
    days = min(days, 30)
    to_date = date.today()
    from_date = to_date - timedelta(days=days)

    data = await zoom.list_recordings(
        from_date=from_date.isoformat(), to_date=to_date.isoformat()
    )

    meetings = data.get("meetings", [])
    if not meetings:
        return "No recordings found in the last {} days.".format(days)

    query_lower = query.lower()
    results = []

    for m in meetings:
        meeting_id = str(m.get("id") or m.get("uuid"))
        topic = m.get("topic", "Untitled")

        entries = await _get_transcript_for_meeting(meeting_id)
        if not entries:
            continue

        matches = [e for e in entries if query_lower in e["text"].lower()]
        if matches:
            hit_lines = []
            for e in matches[:10]:
                speaker = e["speaker"] or "Unknown"
                hit_lines.append(
                    "  - [{}] {}: ...{}...".format(
                        e["timestamp"].split(" --> ")[0],
                        speaker,
                        e["text"][:200],
                    )
                )
            results.append(
                "### {} (ID: {})\n{} match(es)\n{}".format(
                    topic, meeting_id, len(matches), "\n".join(hit_lines)
                )
            )

    if not results:
        return 'No matches for "{}" in the last {} days of transcripts.'.format(
            query, days
        )

    return '## Search results for "{}"\n\n{}'.format(query, "\n\n".join(results))


@mcp.tool()
async def meeting_summary(meeting_id: str) -> str:
    """Get a structured summary of a Zoom meeting transcript.

    Extracts participants and a condensed view of the conversation flow.

    Args:
        meeting_id: The Zoom meeting ID (numeric or UUID).
    """
    entries = await _get_transcript_for_meeting(meeting_id)
    if entries is None:
        return "No transcript found for meeting {}.".format(meeting_id)

    speakers = sorted({e["speaker"] for e in entries if e["speaker"]})

    segments = []
    current_speaker = None
    current_texts = []
    for e in entries:
        if e["speaker"] != current_speaker:
            if current_speaker and current_texts:
                combined = " ".join(current_texts)
                if len(combined) > 300:
                    combined = combined[:300] + "..."
                segments.append("**{}**: {}".format(current_speaker, combined))
            current_speaker = e["speaker"]
            current_texts = [e["text"]]
        else:
            current_texts.append(e["text"])

    if current_speaker and current_texts:
        combined = " ".join(current_texts)
        if len(combined) > 300:
            combined = combined[:300] + "..."
        segments.append("**{}**: {}".format(current_speaker, combined))

    duration_note = ""
    if entries:
        first_ts = entries[0]["timestamp"].split(" --> ")[0]
        last_ts = entries[-1]["timestamp"].split(" --> ")[0]
        duration_note = "Time span: {} to {}".format(first_ts, last_ts)

    return (
        "## Meeting summary ({})\n\n"
        "**Participants:** {}\n{}\n\n"
        "### Conversation flow\n\n{}"
    ).format(
        meeting_id,
        ", ".join(speakers) if speakers else "Unknown",
        duration_note,
        "\n\n".join(segments),
    )


def main():
    mcp.run()


if __name__ == "__main__":
    main()
