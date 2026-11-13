"""Hourly collection run: fetch upcoming and live projects, update projects.csv, append snapshots."""

import argparse
import sys
from datetime import datetime, timezone

from tracker import api
from tracker.store import CAMPAIGN_SNAPSHOT_FIELDS, FOLLOWER_SNAPSHOT_FIELDS, PROJECT_FIELDS, Store


def _parse_ts(value):
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _value(item, key):
    value = item.get(key)
    return "" if value is None else value


def _warn(message):
    # "::warning::" shows up as an annotation on the GitHub Actions run.
    print(f"::warning::{message}", file=sys.stderr)


def _project(projects, item, ts):
    key = item["projectUrlName"]
    project = projects.setdefault(key, dict.fromkeys(PROJECT_FIELDS, "") | {"project_url_name": key})
    project.update(
        creator_url_name=_value(item, "creatorUrlName"),
        name=_value(item, "projectName"),
        creator_name=_value(item, "creatorName"),
        project_type=_value(item, "projectType"),
        home_url=_value(item, "projectHomeUrl"),
        last_seen_at=ts,
    )
    return project


def update(projects, ts, upcoming, active):
    """Apply one run's API results to `projects` in place; return (follower_rows, campaign_rows).

    `upcoming` / `active` are None when that endpoint could not be fetched this run.
    """
    follower_rows = []
    campaign_rows = []

    for item in upcoming or []:
        project = _project(projects, item, ts)
        start = _value(item, "campaignStartDate")
        project.update(
            published_date=_value(item, "publishedDate"),
            campaign_start=start,
            status="upcoming",
        )
        if not project.get("first_seen_upcoming_at"):
            project["first_seen_upcoming_at"] = ts
        if start and not project.get("launch_date_first_seen_at"):
            project["launch_date_first_seen_at"] = ts
        follower_rows.append(
            {
                "ts_utc": ts,
                "project_url_name": project["project_url_name"],
                "follower_count": _value(item, "followerCount"),
                "campaign_start": start,
            }
        )

    for item in active or []:
        project = _project(projects, item, ts)
        start = _value(item, "campaignStartDate")
        project.update(
            currency=_value(item, "currencyShortName"),
            goal=_value(item, "campaignGoal"),
            campaign_start=start,
            campaign_end=_value(item, "campaignEndDate"),
            status="live",
        )
        if not project.get("first_seen_live_at"):
            project["first_seen_live_at"] = ts
        hours = ""
        if start:
            hours = round((_parse_ts(ts) - _parse_ts(start)).total_seconds() / 3600, 2)
        campaign_rows.append(
            {
                "ts_utc": ts,
                "project_url_name": project["project_url_name"],
                "hours_since_launch": hours,
                "backers": _value(item, "backerCount"),
                "funds_gathered": _value(item, "fundsGathered"),
                "follower_count": _value(item, "followerCount"),
                "comment_count": _value(item, "commentCount"),
                "update_count": _value(item, "updateCount"),
                "reward_count": _value(item, "rewardCount"),
            }
        )

    # Projects that dropped out of a list: only conclude anything when both lists were fetched,
    # otherwise an upcoming project that just launched could look like it vanished.
    if upcoming is not None and active is not None:
        seen = {item["projectUrlName"] for item in upcoming} | {item["projectUrlName"] for item in active}
        for key, project in projects.items():
            if key in seen:
                continue
            if project.get("status") == "live":
                project["status"] = "ended"
            elif project.get("status") == "upcoming":
                project["status"] = "gone"  # unpublished, or launched and ended between runs

    return follower_rows, campaign_rows


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", default="data")
    args = parser.parse_args(argv)

    ts = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")

    results = {}
    for name, fetch in (("upcoming", api.get_upcoming_projects), ("active", api.get_active_projects)):
        try:
            results[name] = fetch()
        except api.ApiError as e:
            _warn(f"Skipping {name} projects: {e}")
            results[name] = None

    if results["upcoming"] is None and results["active"] is None:
        print("Both endpoints failed; nothing recorded.", file=sys.stderr)
        return 1

    store = Store(args.data_dir)
    projects = store.load_projects()
    follower_rows, campaign_rows = update(projects, ts, results["upcoming"], results["active"])
    store.save_projects(projects)
    store.append_snapshots("follower_snapshots", FOLLOWER_SNAPSHOT_FIELDS, ts, follower_rows)
    store.append_snapshots("campaign_snapshots", CAMPAIGN_SNAPSHOT_FIELDS, ts, campaign_rows)

    print(f"{ts}: {len(follower_rows)} upcoming, {len(campaign_rows)} live, {len(projects)} projects total")
    return 0


if __name__ == "__main__":
    sys.exit(main())
