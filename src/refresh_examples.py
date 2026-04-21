import logging
from pathlib import Path

import yaml

from fetcher import fetch_liked_tweets

logger = logging.getLogger(__name__)

CONFIG_DIR = Path(__file__).parent.parent / "config"
EXAMPLES_FILE = CONFIG_DIR / "examples.yaml"
MAX_EXAMPLES = 50


def main():
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    logger.info("Fetching liked tweets...")
    tweets, users = fetch_liked_tweets(max_results=MAX_EXAMPLES)
    logger.info("Fetched %d liked tweets", len(tweets))

    examples = []
    for t in tweets:
        handle = users.get(t["author_id"], {}).get("username", "unknown")
        text = t["text"].replace("\n", " ").strip()
        examples.append(f"@{handle}: {text}")

    examples = examples[:MAX_EXAMPLES]
    EXAMPLES_FILE.write_text(
        yaml.dump(examples, default_flow_style=False, allow_unicode=True),
        encoding="utf-8",
    )
    logger.info("Wrote %d examples to %s", len(examples), EXAMPLES_FILE)


if __name__ == "__main__":
    main()
