import json
import logging
from datetime import datetime, timezone, timedelta
from zoneinfo import ZoneInfo

_ET = ZoneInfo("America/New_York")
from pathlib import Path

from fetcher import fetch_home_timeline
from filter import tier1_filter, tier2_filter, collapse_threads
from renderer import render_digest, render_editor, render_index

logger = logging.getLogger(__name__)

ROOT = Path(__file__).parent.parent
STATE_FILE = ROOT / "state" / "last_run.json"
OUTPUT_DIR = ROOT / "output"


def load_state():
    if STATE_FILE.exists():
        return json.loads(STATE_FILE.read_text())
    return {}


MIN_WINDOW = timedelta(hours=24)
MAX_WINDOW = timedelta(days=7)


def save_state():
    STATE_FILE.write_text(json.dumps({
        "last_run_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }, indent=2))


def regenerate_index():
    files = sorted(
        [f for f in OUTPUT_DIR.glob("????-??-??.html")],
        reverse=True,
    )
    digests = [{"date": f.stem, "filename": f.name} for f in files]
    render_index(digests, OUTPUT_DIR / "index.html")


def main():
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    now = datetime.now(timezone.utc)
    state = load_state()
    last_run_at_str = state.get("last_run_at")

    if last_run_at_str:
        last_run_at = datetime.fromisoformat(last_run_at_str.replace("Z", "+00:00"))
        window = min(max(now - last_run_at, MIN_WINDOW), MAX_WINDOW)
    else:
        window = MAX_WINDOW

    start_time = (now - window).strftime("%Y-%m-%dT%H:%M:%SZ")
    logger.info("Fetching home timeline (window: %s)...", window)
    tweets, users, media, ref_tweets = fetch_home_timeline(start_time=start_time)
    logger.info("Fetched %d tweets", len(tweets))

    filtered = tier1_filter(tweets) if tweets else []
    filtered = collapse_threads(filtered) if filtered else []
    filtered = tier2_filter(filtered, users) if filtered else []

    date_str = now.astimezone(_ET).strftime("%Y-%m-%d")
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    render_digest(filtered, users, media, ref_tweets, date_str, OUTPUT_DIR / f"{date_str}.html", total_fetched=len(tweets))
    logger.info("%d posts in today's digest", len(filtered))

    regenerate_index()
    render_editor(OUTPUT_DIR / "edit.html")

    save_state()
    logger.info("State updated (last_run_at=%s)", now.strftime("%Y-%m-%dT%H:%M:%SZ"))


if __name__ == "__main__":
    main()
