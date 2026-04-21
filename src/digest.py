import json
import logging
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

from fetcher import fetch_home_timeline
from filter import tier1_filter, tier2_filter
from renderer import render_digest, render_index

logger = logging.getLogger(__name__)

ROOT = Path(__file__).parent.parent
STATE_FILE = ROOT / "state" / "last_run.json"
OUTPUT_DIR = ROOT / "output"


def load_state():
    if STATE_FILE.exists():
        return json.loads(STATE_FILE.read_text())
    return {}


def save_state(since_id):
    STATE_FILE.write_text(json.dumps({"since_id": since_id}, indent=2))


def regenerate_index():
    files = sorted(
        [f for f in OUTPUT_DIR.glob("????-??-??.html")],
        reverse=True,
    )
    digests = [{"date": f.stem, "filename": f.name} for f in files]
    render_index(digests, OUTPUT_DIR / "index.html")


def main():
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    state = load_state()
    since_id = state.get("since_id")

    fetch_kwargs = {}
    if since_id:
        fetch_kwargs["since_id"] = since_id
    else:
        start = (datetime.now(timezone.utc) - timedelta(days=7)).strftime("%Y-%m-%dT%H:%M:%SZ")
        fetch_kwargs["start_time"] = start

    logger.info("Fetching home timeline...")
    tweets, users, media, ref_tweets = fetch_home_timeline(**fetch_kwargs)
    logger.info("Fetched %d tweets", len(tweets))

    newest_id = str(max((int(t["id"]) for t in tweets), default=0)) if tweets else None

    filtered = tier1_filter(tweets) if tweets else []
    filtered = tier2_filter(filtered, users) if filtered else []

    date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    render_digest(filtered, users, media, ref_tweets, date_str, OUTPUT_DIR / f"{date_str}.html")
    logger.info("%d posts in today's digest", len(filtered))

    regenerate_index()

    if newest_id and newest_id != "0":
        save_state(newest_id)
        logger.info("State advanced to since_id=%s", newest_id)


if __name__ == "__main__":
    main()
