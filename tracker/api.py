"""Thin client for Gamefound's public API (https://help.gamefound.com/article/425-gamefound-public-api)."""

import json
import os
import urllib.error
import urllib.request

BASE_URL = "https://gamefound.com/api/public"
# GITHUB_REPOSITORY ("owner/repo") is set inside GitHub Actions; it lets Gamefound see who is calling.
_REPO = os.environ.get("GITHUB_REPOSITORY")
USER_AGENT = "FollowersTracker/1.0" + (f" (+https://github.com/{_REPO})" if _REPO else "")
TIMEOUT_SECONDS = 60


class ApiError(Exception):
    pass


def _get(path):
    request = urllib.request.Request(
        f"{BASE_URL}/{path}",
        headers={"User-Agent": USER_AGENT, "Accept": "application/json"},
    )
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT_SECONDS) as response:
            body = response.read().decode("utf-8")
    except urllib.error.HTTPError as e:
        raise ApiError(f"{path}: HTTP {e.code}") from e
    except urllib.error.URLError as e:
        raise ApiError(f"{path}: {e.reason}") from e
    try:
        return json.loads(body)
    except json.JSONDecodeError as e:
        # Cloudflare challenge pages come back as HTML.
        raise ApiError(f"{path}: response is not JSON ({body[:80]!r})") from e


def get_upcoming_projects():
    """Published projects whose campaign hasn't started yet."""
    return _get("projects/getUpcomingCrowdfundingProjects")


def get_active_projects():
    """Projects currently in their crowdfunding campaign."""
    return _get("projects/getActiveCrowdfundingProjects")
