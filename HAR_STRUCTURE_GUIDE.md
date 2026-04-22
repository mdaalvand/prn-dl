# HAR Structure Guide

This document explains the structure of the HAR file used in this project:

- [`all-pornhub-requests.json`](/Users/mehdi/Desktop/projects/Personal/pornhub_ytdlp_repo/all-pornhub-requests.json)

It is a lightweight reference for future debugging, request analysis, and scraper/downloader tuning.

## 1) Top-Level Shape

HAR is JSON with a single main key:

```json
{
  "log": {
    "version": "...",
    "creator": { "...": "..." },
    "pages": [ ... ],
    "entries": [ ... ]
  }
}
```

In this file:

- `pages`: 26
- `entries`: 3479

## 2) `log.pages`

Each page describes one browser navigation context.

Typical page fields:

- `startedDateTime`: when navigation started
- `id`: page reference id
- `title`: URL/title at that moment
- `pageTimings`: browser page timing summary

Use `pages` when you need per-navigation grouping.

## 3) `log.entries`

Each `entry` is one network request/response.

Main fields you will use most:

- `startedDateTime`: request start time
- `time`: total duration (ms)
- `pageref`: link back to `pages[].id`
- `request`: outbound request metadata
- `response`: response metadata/content summary
- `timings`: timing breakdown

This HAR also contains browser-specific extra fields:

- `_resourceType` (document/script/image/xhr/...)
- `_initiator`, `_priority`, `_connectionId`, etc.

## 4) `entry.request`

Core fields:

- `method` (GET/POST/...)
- `url`
- `httpVersion`
- `headers[]` (name/value pairs)
- `queryString[]`
- `cookies[]`
- `headersSize`, `bodySize`

For this file, request methods are mostly:

- `GET`: 3454
- `POST`: 25

## 5) `entry.response`

Core fields:

- `status`, `statusText`
- `httpVersion`
- `headers[]`
- `cookies[]`
- `content`:
  - `size`
  - `mimeType`
  - optional `text` (sometimes omitted/truncated depending on export)
- `redirectURL`
- `headersSize`, `bodySize`

This HAR includes useful non-standard extras:

- `_transferSize`
- `_error`
- `_fetchedViaServiceWorker`

Common status values in this file:

- `200`: 3250
- `0`: 220 (typically aborted/blocked/no response capture)
- `206`: 5
- `404`: 3
- `410`: 1

## 6) `entry.timings`

Breakdown (ms):

- `blocked`
- `dns`
- `connect`
- `ssl`
- `send`
- `wait` (TTFB-like)
- `receive`

This export also has browser extras:

- `_blocked_queueing`
- `_workerStart`
- `_workerReady`
- `_workerFetchStart`
- `_workerRespondWithSettled`

## 7) Fast Practical Queries

### Find search requests

Look for URLs like:

- `/video/search?...`
- `/gay/video/search?...`

### Find request headers used by browser

Inspect `entry.request.headers`, especially:

- `user-agent`
- `referer`
- `origin`
- `sec-fetch-*`
- cookies (if present)

### Find failed requests

Filter by `response.status != 200` or `response._error`.

## 8) Project-Specific Notes

From this HAR sample:

- Traffic is heavily static-asset dominated (js/css/images), not only API/XHR.
- Search navigation appears on document URLs (not only JSON endpoints).
- Route selection matters (`/gay/video/search` vs `/video/search`).
- Header context (`Referer`, browser-like headers) can affect anti-bot/CDN behavior.

## 9) Privacy / Safety

HAR may contain sensitive data:

- Cookies
- Auth/session headers
- Tokens/query params

Before sharing externally:

1. Remove cookies and auth headers.
2. Remove personal query data.
3. Re-check raw `content.text` blocks.

## 10) Suggested Workflow for Future Analysis

1. Start with `entries` count and status distribution.
2. Isolate `document` and search URLs.
3. Compare working vs failing requests:
   - URL pattern
   - headers
   - cookies
   - timing/status
4. Apply fixes in provider/downloader headers/proxy/cookie strategy.
5. Re-capture HAR and compare.

