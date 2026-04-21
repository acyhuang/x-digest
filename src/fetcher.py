import os
import requests
from requests_oauthlib import OAuth1

USER_ID = "1330044133000491008" 
BASE_URL = "https://api.twitter.com/2"

TWEET_FIELDS = "text,lang,author_id,created_at,attachments,referenced_tweets,in_reply_to_user_id"
EXPANSIONS = "author_id,attachments.media_keys,referenced_tweets.id,referenced_tweets.id.author_id"
USER_FIELDS = "name,username"
MEDIA_FIELDS = "url,preview_image_url,type"


def _auth():
    return OAuth1(
        os.environ["X_CONSUMER_KEY"],
        os.environ["X_CONSUMER_SECRET"],
        os.environ["X_ACCESS_TOKEN"],
        os.environ["X_ACCESS_TOKEN_SECRET"],
    )


def fetch_home_timeline(since_id=None, start_time=None, max_posts=200):
    url = f"{BASE_URL}/users/{USER_ID}/timelines/reverse_chronological"
    params = {
        "tweet.fields": TWEET_FIELDS,
        "expansions": EXPANSIONS,
        "user.fields": USER_FIELDS,
        "media.fields": MEDIA_FIELDS,
        "max_results": 100,
    }
    if since_id:
        params["since_id"] = since_id
    elif start_time:
        params["start_time"] = start_time

    tweets, users, media, ref_tweets = [], {}, {}, {}
    next_token = None

    while len(tweets) < max_posts:
        if next_token:
            params["pagination_token"] = next_token

        resp = requests.get(url, params=params, auth=_auth())
        resp.raise_for_status()
        data = resp.json()

        batch = data.get("data", [])
        tweets.extend(batch)

        includes = data.get("includes", {})
        for u in includes.get("users", []):
            users[u["id"]] = u
        for m in includes.get("media", []):
            media[m["media_key"]] = m
        for t in includes.get("tweets", []):
            ref_tweets[t["id"]] = t

        next_token = data.get("meta", {}).get("next_token")
        if not next_token or not batch:
            break

    return tweets[:max_posts], users, media, ref_tweets
