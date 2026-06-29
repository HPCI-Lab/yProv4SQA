"""
yprov4sqa/_github.py
====================
Shared GitHub API helper used by _fetcher, _compare, and _provenance.

Centralises:
  - Rate-limit retry logic
  - Authentication header construction
  - A proper exception type (GitHubRateLimitError) instead of sys.exit()

Token resolution order (per-call):
  1. The ``token`` keyword argument passed directly to ``github_get``
  2. The ``GITHUB_TOKEN`` environment variable (read at call time, not at import)
"""

import os
import time
import requests


class GitHubRateLimitError(RuntimeError):
    """Raised when the GitHub API rate limit is exceeded and cannot be recovered."""


def github_get(url: str, params=None, *, token: str = None, max_wait: int = 3600):
    """
    GET a GitHub API URL with automatic rate-limit retry.

    Parameters
    ----------
    url       : Full URL to request.
    params    : Optional query-string dict forwarded to requests.get.
    token     : Optional GitHub token.  Falls back to the GITHUB_TOKEN
                environment variable if not supplied.  Read at call time
                so that token rotation and late env-var injection both work.
    max_wait  : Maximum seconds to wait for a rate-limit reset (default 1 h).

    Returns
    -------
    requests.Response — status 200 or 404 (callers decide what to do with 404).

    Raises
    ------
    GitHubRateLimitError  — rate limit hit and wait exceeds max_wait.
    requests.HTTPError    — any non-200/403/404/429 response.
    """
    # Resolve token at call time — never at module load
    resolved_token = token or os.getenv("GITHUB_TOKEN")

    while True:
        headers = {"Authorization": f"token {resolved_token}"} if resolved_token else {}
        r = requests.get(url, params=params, headers=headers, timeout=30)

        if r.status_code in (403, 429):
            reset_ts = int(r.headers.get("X-RateLimit-Reset", 0))
            remain   = int(r.headers.get("X-RateLimit-Remaining", 0))
            if remain == 0 and reset_ts:
                wait_sec = reset_ts - int(time.time()) + 2
                if 0 < wait_sec <= max_wait:
                    print(
                        f"\nGitHub rate-limit hit. "
                        f"Waiting {wait_sec}s until "
                        f"{time.strftime('%H:%M:%S', time.gmtime(reset_ts))} …"
                    )
                    time.sleep(wait_sec)
                    continue
            raise GitHubRateLimitError(
                "GitHub rate limit exceeded. "
                "Try again later or set the GITHUB_TOKEN environment variable."
            )

        if r.status_code == 404:
            return r  # callers handle 404 themselves

        r.raise_for_status()
        return r