from __future__ import annotations

from collections.abc import Iterator

import requests

_API_ROOT = "https://api.github.com"

_session = requests.Session()  # reused across calls to avoid reconnecting per request


def _headers(settings) -> dict:
    headers = {
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    if settings.github_token:
        headers["Authorization"] = f"Bearer {settings.github_token}"
    return headers


def _get(settings, url: str, params: "dict | None" = None) -> requests.Response:
    resp = _session.get(url, headers=_headers(settings), params=params, timeout=60)
    resp.raise_for_status()
    return resp


def _post(settings, url: str, payload: dict) -> requests.Response:
    resp = _session.post(url, headers=_headers(settings), json=payload, timeout=60)
    resp.raise_for_status()
    return resp


def _patch(settings, url: str, payload: dict) -> requests.Response:
    resp = _session.patch(url, headers=_headers(settings), json=payload, timeout=60)
    resp.raise_for_status()
    return resp


def _delete(settings, url: str) -> requests.Response:
    resp = _session.delete(url, headers=_headers(settings), timeout=60)
    resp.raise_for_status()
    return resp


def _paginate(settings, url: str) -> "Iterator[dict]":
    page = 1
    while True:
        batch = _get(settings, url, params={"per_page": 100, "page": page}).json()
        if not batch:
            return
        yield from batch
        if len(batch) < 100:
            return
        page += 1
