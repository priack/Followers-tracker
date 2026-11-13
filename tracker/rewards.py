"""Load the output of browser/collect_rewards.js into project_details.csv and reward_snapshots/."""

import argparse
import csv
import json
import sys
from datetime import datetime

from tracker.store import Store

DETAIL_FIELDS = [
    "project_url_name",
    "creator_url_name",
    "project_id",
    "creator_id",
    "category",
    "tags",
    "min_players",
    "max_players",
    "updated_at",
]

REWARD_SNAPSHOT_FIELDS = [
    "ts_utc",
    "project_url_name",
    "hours_since_launch",
    "product_id",
    "reward_name",
    "price",
    "effective_price",
    "purchased_count",
    "is_featured",
    "is_most_popular",
    "has_limited_stock",
    "remaining_stock",
]


class InvalidPayload(Exception):
    pass


def _parse_ts(value):
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _cell(value):
    return "" if value is None else value


def _table(payload, name):
    table = payload[name]
    return [dict(zip(table["cols"], row)) for row in table["rows"]]


def fnv1a(rows):
    """Same hash as collect_rewards.js: FNV-1a over the UTF-16 code units of JSON.stringify(rows)."""
    text = json.dumps(rows, ensure_ascii=False, separators=(",", ":"))
    data = text.encode("utf-16-le")
    h = 0x811C9DC5
    for i in range(0, len(data), 2):
        h = ((h ^ (data[i] | data[i + 1] << 8)) * 0x01000193) & 0xFFFFFFFF
    return f"{h:08x}"


def validate(payload):
    if payload.get("version") != 1:
        raise InvalidPayload(f"unsupported version {payload.get('version')!r}")
    detail_rows = payload["details"]["rows"]
    reward_rows = payload["rewards"]["rows"]
    actual = {
        "details": len(detail_rows),
        "rewards": len(reward_rows),
        "fnv1a": fnv1a([detail_rows, reward_rows]),
    }
    if actual != payload["check"]:
        raise InvalidPayload(f"checksum mismatch: expected {payload['check']}, got {actual}")
    return _table(payload, "details"), _table(payload, "rewards")


def build_rows(payload, known_keys):
    """Return (detail_rows, reward_rows); project keys are matched case-insensitively to projects.csv."""
    details, rewards = validate(payload)
    ts = payload["ts_utc"]
    by_lower = {key.lower(): key for key in known_keys}

    def key(url_name):
        return by_lower.get(url_name.lower(), url_name)

    starts = {}
    detail_rows = []
    for d in details:
        starts[d["project_url_name"]] = d["campaign_start"]
        row = {field: _cell(d.get(field)) for field in DETAIL_FIELDS}
        row["project_url_name"] = key(d["project_url_name"])
        row["updated_at"] = ts
        detail_rows.append(row)

    reward_rows = []
    for r in rewards:
        start = starts.get(r["project_url_name"])
        hours = round((_parse_ts(ts) - _parse_ts(start)).total_seconds() / 3600, 2) if start else ""
        row = {field: _cell(r.get(field)) for field in REWARD_SNAPSHOT_FIELDS}
        row.update(ts_utc=ts, project_url_name=key(r["project_url_name"]), hours_since_launch=hours)
        reward_rows.append(row)

    return detail_rows, reward_rows


def save_details(store, detail_rows):
    path = store.data_dir / "project_details.csv"
    existing = {}
    if path.exists():
        with path.open(newline="", encoding="utf-8") as f:
            existing = {row["project_url_name"]: row for row in csv.DictReader(f)}
    existing.update({row["project_url_name"]: row for row in detail_rows})
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=DETAIL_FIELDS)
        writer.writeheader()
        writer.writerows(sorted(existing.values(), key=lambda row: row["project_url_name"]))


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", help="JSON file saved from collect_rewards.js")
    parser.add_argument("--data-dir", default="data")
    args = parser.parse_args(argv)

    with open(args.input, encoding="utf-8") as f:
        payload = json.load(f)

    store = Store(args.data_dir)
    try:
        detail_rows, reward_rows = build_rows(payload, store.load_projects().keys())
    except InvalidPayload as e:
        print(f"Rejected {args.input}: {e}", file=sys.stderr)
        return 1

    save_details(store, detail_rows)
    store.append_snapshots("reward_snapshots", REWARD_SNAPSHOT_FIELDS, payload["ts_utc"], reward_rows)
    for error in payload.get("errors", []):
        print(f"Warning: {error}", file=sys.stderr)
    print(f"{payload['ts_utc']}: {len(detail_rows)} projects, {len(reward_rows)} rewards")
    return 0


if __name__ == "__main__":
    sys.exit(main())
