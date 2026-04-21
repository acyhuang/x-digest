# X Feed Digest

## Goal

Daily digest of Allison's X / Twitter home timeline. Fetches recent posts, filters for relevance to Allison's interests, and renders as a static HTML digest page published to GitHub Pages.

## End-to-end flow

1. **Fetch** home timeline posts since last run (capped at 7 days / 200 posts)
2. **Tier 1 filter** — drop by rules (language, retweets, replies-to-others, account tier)
3. **Tier 2 filter** — batch LLM judgment against Allison's interests
4. **Render** surviving posts as a dated static HTML page
5. **Publish** to GitHub Pages; update root `index.html` listing all past digests

## Tech stack & project layout

### Language & dependencies
- Python 3.13 (package manager: `uv`)
- `requests`, `requests-oauthlib`, `anthropic`, `jinja2`, `pyyaml`

### Project structure
```
src/          # all Python source
config/       # interests.md, examples.yaml
state/        # last_run.json
output/       # generated HTML (gitignored on main; committed to gh-pages)
```

### Entry points
- `src/digest.py` — daily run

## Data fetching

### X API auth
- X API v2 with **OAuth 1.0a** (user context — required for home timeline)
- Credentials: `consumer_key`, `consumer_secret`, `access_token`, `access_token_secret` stored as GitHub Secrets
- OAuth 1.0a tokens do not expire — no refresh logic needed
- API reads generate no engagement signals (no side effects on feed algorithm)
- **Allison's user ID:** hardcode in config (look it up once via `GET /1.1/account/verify_credentials` or from the X developer portal); it never changes

### Home timeline (daily digest source)
- Endpoint: `GET /2/users/:id/timelines/reverse_chronological`
- Params:
  - `tweet.fields=text,lang,author_id,created_at,attachments,referenced_tweets,in_reply_to_user_id`
  - `expansions=author_id,attachments.media_keys,referenced_tweets.id,referenced_tweets.id.author_id`
  - `user.fields=name,username`
  - `media.fields=url,preview_image_url,type`
  - `max_results=100` (max per page)
- Pagination: follow `next_token` in response metadata until `since_id` is reached or 200-post cap hit
- Rate limit: 180 req / 15 min — well above what a single daily run needs

### Bookmarks
- Excluded intentionally — requires OAuth 2.0 PKCE; not supported with OAuth 1.0a

## Filtering

### Tier 1 — Rule-based (free, instant)
- Drop non-English posts — use `tweet.lang == "en"` (X's built-in field; no library needed)
- Drop pure retweets — signal: any entry in `referenced_tweets[].type == "retweeted"` (sufficient alone; quote tweets use `"quoted"`)
- Drop replies from others — signal: `in_reply_to_user_id != null && in_reply_to_user_id != author_id`; keep self-replies (`in_reply_to_user_id == author_id`)

### Tier 2 — LLM batch judgment
- Model: `claude-haiku-4-5-20251001` (pinned version; cheap, fast, structured output)
- All Tier 1 survivors sent in a single prompt (up to 200 posts ≈ 10K tokens — no chunking needed)
- Prompt format per post: `@handle: tweet text`
- Response: JSON array of `{"id": "...", "reason": "..."}` objects inside a ```json block
- Prompt structure: prose interest description from `config/interests.md`, followed by few-shot positive examples from `config/examples.yaml`, followed by the batch of candidate posts
- `config/interests.md` — Allison-authored prose ("interested in X, Y; not interested in A, B"). Prepended verbatim to the prompt; this is the primary signal for what counts as relevant
- `config/examples.yaml` — positive examples only, flat list of strings in `@handle: tweet text` format. Include all (cap at 30 in the prompt, sample randomly beyond that)
- `config/examples.yaml` is manually curated
- On malformed output: retry once with stricter prompt ("Return ONLY valid JSON"); if still malformed, pass all Tier 1 survivors through and log a warning
- ~$0.01–0.02/day estimated cost

## Rendering & publishing

### HTML output
- Static HTML page, one per run, stored with dated filename (e.g. `2026-04-19.html`)
- Fields per post: author name, `@handle`, timestamp (UTC), post text, inline image (linked to X CDN, if present), link to X
- Quote tweets: render the quoted tweet inline below the quoter's text (quoted `@handle` + quoted text), via the `referenced_tweets.id` expansion
- LLM one-line reason shown in small muted text below each post
- Sort order: chronological
- Page design: light CSS (font, spacing, card-per-post layout — no frameworks)
- Zero posts: publish with "No posts matched today" message (don't skip — preserves archive continuity)
- Video excluded (X CDN is auth-gated)

### Index page
- Each run also regenerates `index.html` at the root listing all past digests as links, newest first

### Deployment
- Deployed to GitHub Pages via `gh-pages` branch (keeps generated output separate from source on `main`)

## State & configuration

- `state/last_run.json` — persists `since_id` of the most recently fetched tweet, committed to the repo. Advanced only after a successful publish, so render failures don't silently drop posts from the next run
- On first run (no state file): use `start_time = now - 7 days` via the X API `start_time` param (ISO 8601)
- `config/interests.md` — Allison-authored prose description of what counts as relevant
- `config/examples.yaml` — few-shot positive examples for the LLM filter; manually curated

## Scheduling & CI

### Cron
- Daily digest: `0 9 * * *` (9am UTC)
- Lookback: since last successful run, capped at 7 days maximum
- Post volume cap: 200 posts per run

### GitHub Actions
- Required secrets: `X_CONSUMER_KEY`, `X_CONSUMER_SECRET`, `X_ACCESS_TOKEN`, `X_ACCESS_TOKEN_SECRET`, `ANTHROPIC_API_KEY`
- On failure: fail loudly (red workflow run); GitHub emails on failure by default — no extra notification infra needed
