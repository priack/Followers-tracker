"""CSV storage: one upserted projects table plus append-only monthly snapshot tables."""

import csv
from pathlib import Path

PROJECT_FIELDS = [
    "project_url_name",
    "creator_url_name",
    "name",
    "creator_name",
    "project_type",
    "home_url",
    "currency",
    "goal",
    "published_date",
    "campaign_start",
    "campaign_end",
    "status",  # upcoming | live | ended | gone
    "first_seen_upcoming_at",
    "launch_date_first_seen_at",
    "first_seen_live_at",
    "last_seen_at",
]

FOLLOWER_SNAPSHOT_FIELDS = [
    "ts_utc",
    "project_url_name",
    "follower_count",
    "campaign_start",
]

CAMPAIGN_SNAPSHOT_FIELDS = [
    "ts_utc",
    "project_url_name",
    "hours_since_launch",
    "backers",
    "funds_gathered",
    "follower_count",
    "comment_count",
    "update_count",
    "reward_count",
]


class Store:
    def __init__(self, data_dir):
        self.data_dir = Path(data_dir)

    @property
    def projects_path(self):
        return self.data_dir / "projects.csv"

    def load_projects(self):
        if not self.projects_path.exists():
            return {}
        with self.projects_path.open(newline="", encoding="utf-8") as f:
            return {row["project_url_name"]: row for row in csv.DictReader(f)}

    def save_projects(self, projects):
        self.projects_path.parent.mkdir(parents=True, exist_ok=True)
        rows = sorted(projects.values(), key=lambda p: p["project_url_name"])
        with self.projects_path.open("w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=PROJECT_FIELDS, extrasaction="ignore")
            writer.writeheader()
            writer.writerows(rows)

    def append_snapshots(self, table, fields, ts, rows):
        """Append rows to data/<table>/YYYY-MM.csv (monthly files keep each file small)."""
        if not rows:
            return
        path = self.data_dir / table / f"{ts[:7]}.csv"
        path.parent.mkdir(parents=True, exist_ok=True)
        is_new = not path.exists()
        with path.open("a", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fields)
            if is_new:
                writer.writeheader()
            writer.writerows(rows)
