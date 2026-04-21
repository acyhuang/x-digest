import json
import logging
import random
import re
from pathlib import Path

import anthropic
import yaml

logger = logging.getLogger(__name__)

CONFIG_DIR = Path(__file__).parent.parent / "config"
MODEL = "claude-haiku-4-5-20251001"


def tier1_filter(tweets):
    kept = []
    for t in tweets:
        if t.get("lang") != "en":
            continue
        refs = t.get("referenced_tweets", [])
        if any(r.get("type") == "retweeted" for r in refs):
            continue
        reply_to = t.get("in_reply_to_user_id")
        if reply_to and reply_to != t.get("author_id"):
            continue
        kept.append(t)
    logger.info("Tier 1: %d → %d", len(tweets), len(kept))
    return kept


def tier2_filter(tweets, users):
    if not tweets:
        return []

    interests = (CONFIG_DIR / "interests.md").read_text()

    examples_path = CONFIG_DIR / "examples.yaml"
    examples = yaml.safe_load(examples_path.read_text()) if examples_path.exists() else []
    examples = examples or []
    sampled = random.sample(examples, min(30, len(examples)))

    bad_examples_path = CONFIG_DIR / "bad-examples.yaml"
    bad_examples = yaml.safe_load(bad_examples_path.read_text()) if bad_examples_path.exists() else []
    bad_examples = bad_examples or []
    sampled_bad = random.sample(bad_examples, min(15, len(bad_examples)))

    lines = []
    for t in tweets:
        handle = users.get(t["author_id"], {}).get("username", "unknown")
        text = t["text"].replace("\n", " ")
        lines.append(f'[id:{t["id"]}] @{handle}: {text}')

    prompt = (
        "You are filtering a Twitter/X timeline for relevance to a specific person's interests.\n\n"
        "## Interests\n"
        f"{interests}\n\n"
        "## Positive examples (posts this person wants to see):\n"
        + "\n".join(f"- {e}" for e in sampled)
        + "\n\n## Negative examples (posts this person does NOT want to see):\n"
        + "\n".join(f"- {e}" for e in sampled_bad)
        + "\n\n## Posts to evaluate:\n"
        + "\n".join(lines)
        + "\n\nReturn a JSON array of relevant posts in a ```json block:\n"
        "```json\n"
        '[{"id": "tweet_id", "reason": "one-line reason"}]\n'
        "```\n"
        "Include only posts that match the interests. Omit irrelevant posts entirely."
    )

    result = _call_llm(prompt, strict=False)
    if result is None:
        logger.warning("LLM filter failed — passing all Tier 1 survivors through")
        return [dict(t, _reason="unfiltered (LLM error)") for t in tweets]

    id_to_reason = {item["id"]: item["reason"] for item in result}
    kept = []
    for t in tweets:
        if t["id"] in id_to_reason:
            kept.append(dict(t, _reason=id_to_reason[t["id"]]))

    logger.info("Tier 2: %d → %d", len(tweets), len(kept))
    return kept


def _call_llm(prompt, strict):
    client = anthropic.Anthropic()
    suffix = "\n\nReturn ONLY valid JSON. No other text." if strict else ""
    msg = client.messages.create(
        model=MODEL,
        max_tokens=4096,
        messages=[{"role": "user", "content": prompt + suffix}],
    )
    text = msg.content[0].text
    result = _parse_json(text)
    if result is None and not strict:
        logger.warning("Malformed LLM output, retrying with stricter prompt")
        return _call_llm(prompt, strict=True)
    return result


def _parse_json(text):
    m = re.search(r"```json\s*([\s\S]*?)\s*```", text)
    if m:
        try:
            return json.loads(m.group(1))
        except json.JSONDecodeError:
            pass
    try:
        return json.loads(text.strip())
    except json.JSONDecodeError:
        return None
