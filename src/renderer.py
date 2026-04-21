import re
from datetime import datetime
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape
from markupsafe import Markup, escape

TEMPLATES_DIR = Path(__file__).parent.parent / "templates"

_URL_RE = re.compile(r"(https?://\S+)")


def _linkify(text):
    escaped = escape(text)
    linked = _URL_RE.sub(
        r'<a href="\1" target="_blank" rel="noopener">\1</a>', str(escaped)
    )
    return Markup(linked)


def _env():
    env = Environment(
        loader=FileSystemLoader(str(TEMPLATES_DIR)),
        autoescape=select_autoescape(["html", "j2"]),
    )
    env.filters["linkify"] = _linkify
    return env


def _build_post(tweet, users, media, ref_tweets):
    author = users.get(tweet["author_id"], {})
    handle = author.get("username", "unknown")
    name = author.get("name", handle)

    created_at = tweet.get("created_at", "")
    if created_at:
        dt = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
        timestamp = dt.strftime("%Y-%m-%d %H:%M UTC")
    else:
        timestamp = ""

    image_url = None
    for mk in tweet.get("attachments", {}).get("media_keys", []):
        m = media.get(mk, {})
        if m.get("type") == "photo":
            image_url = m.get("url") or m.get("preview_image_url")
            break

    quote = None
    for ref in tweet.get("referenced_tweets", []):
        if ref.get("type") == "quoted":
            qt = ref_tweets.get(ref["id"])
            if qt:
                qt_author = users.get(qt.get("author_id", ""), {})
                quote = {
                    "handle": qt_author.get("username", "unknown"),
                    "text": qt.get("text", ""),
                }
            break

    return {
        "author_name": name,
        "handle": handle,
        "timestamp": timestamp,
        "created_at": created_at,
        "text": tweet["text"],
        "image_url": image_url,
        "quote": quote,
        "tweet_url": f"https://x.com/{handle}/status/{tweet['id']}",
        "reason": tweet.get("_reason", ""),
    }


def render_digest(tweets, users, media, ref_tweets, date_str, output_path, total_fetched=0):
    posts = [_build_post(t, users, media, ref_tweets) for t in tweets]
    posts.sort(key=lambda p: p["created_at"])
    html = _env().get_template("digest.html.j2").render(
        date=date_str, posts=posts, total_fetched=total_fetched
    )
    Path(output_path).write_text(html, encoding="utf-8")


def render_index(digests, output_path):
    html = _env().get_template("index.html.j2").render(digests=digests)
    Path(output_path).write_text(html, encoding="utf-8")


def render_editor(output_path):
    html = _env().get_template("edit.html.j2").render()
    Path(output_path).write_text(html, encoding="utf-8")
