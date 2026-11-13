"""Load the output of browser/collect_rewards.js into project_details.csv and reward_snapshots/.

The browser sends full rows only for rewards it has not sent before (or whose static fields changed);
the rest arrive as counts and are completed from data/reward_catalog.csv.
"""

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

CATALOG_FIELDS = [
    "product_id",
    "project_url_name",
    "reward_name",
    "price",
    "effective_price",
    "is_featured",
    "is_most_popular",
    "has_limited_stock",
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
    if payload.get("version") != 2:
        raise InvalidPayload(f"unsupported version {payload.get('version')!r}")
    tables = [payload[name]["rows"] for name in ("details", "rewards", "counts")]
    actual = {
        "details": len(tables[0]),
        "rewards": len(tables[1]),
        "counts": len(tables[2]),
        "fnv1a": fnv1a(tables),
    }
    if actual != payload["check"]:
        raise InvalidPayload(f"checksum mismatch: expected {payload['check']}, got {actual}")
    return _table(payload, "details"), _table(payload, "rewards"), _table(payload, "counts")


def build_rows(payload, projects, catalog):
    """Return (detail_rows, reward_rows, catalog_rows).

    `projects` is projects.csv keyed by project_url_name (matched case-insensitively and used for
    campaign start dates); `catalog` is reward_catalog.csv keyed by product_id.
    """
    details, rewards, counts = validate(payload)
    ts = payload["ts_utc"]
    by_lower = {key.lower(): key for key in projects}

    def key(url_name):
        return by_lower.get(url_name.lower(), url_name)

    starts = {key: project.get("campaign_start") for key, project in projects.items()}
    detail_rows = []
    for d in details:
        row = {field: _cell(d.get(field)) for field in DETAIL_FIELDS}
        row["project_url_name"] = key(d["project_url_name"])
        row["updated_at"] = ts
        detail_rows.append(row)
        if d["campaign_start"]:
            starts[row["project_url_name"]] = d["campaign_start"]

    catalog_rows = []
    snapshots = []
    for r in rewards:
        row = {field: _cell(r.get(field)) for field in CATALOG_FIELDS}
        row.update(project_url_name=key(r["project_url_name"]), updated_at=ts)
        catalog_rows.append(row)
        snapshots.append((row, r["purchased_count"], r["remaining_stock"]))

    missing = [str(c["product_id"]) for c in counts if str(c["product_id"]) not in catalog]
    if missing:
        raise InvalidPayload(
            f"{len(missing)} rewards are not in reward_catalog.csv (e.g. {', '.join(missing[:3])}); "
            "the browser's memory is out of sync, clear it and collect again"
        )
    for c in counts:
        snapshots.append((catalog[str(c["product_id"])], c["purchased_count"], c["remaining_stock"]))

    reward_rows = []
    for static, purchased, remaining in snapshots:
        start = starts.get(static["project_url_name"])
        hours = round((_parse_ts(ts) - _parse_ts(start)).total_seconds() / 3600, 2) if start else ""
        row = {field: static.get(field, "") for field in REWARD_SNAPSHOT_FIELDS}
        row.update(ts_utc=ts, hours_since_launch=hours, purchased_count=_cell(purchased),
                   remaining_stock=_cell(remaining))
        reward_rows.append(row)

    return detail_rows, reward_rows, catalog_rows


def _load_csv(path, key):
    if not path.exists():
        return {}
    with path.open(newline="", encoding="utf-8") as f:
        return {row[key]: row for row in csv.DictReader(f)}


def _upsert_csv(path, fields, key, rows):
    existing = _load_csv(path, key)
    existing.update({str(row[key]): row for row in rows})
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(sorted(existing.values(), key=lambda row: str(row[key])))


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", help="JSON file saved from collect_rewards.js")
    parser.add_argument("--data-dir", default="data")
    args = parser.parse_args(argv)

    with open(args.input, encoding="utf-8") as f:
        payload = json.load(f)

    store = Store(args.data_dir)
    catalog_path = store.data_dir / "reward_catalog.csv"
    try:
        detail_rows, reward_rows, catalog_rows = build_rows(
            payload, store.load_projects(), _load_csv(catalog_path, "product_id")
        )
    except InvalidPayload as e:
        print(f"Rejected {args.input}: {e}", file=sys.stderr)
        return 1

    _upsert_csv(store.data_dir / "project_details.csv", DETAIL_FIELDS, "project_url_name", detail_rows)
    _upsert_csv(catalog_path, CATALOG_FIELDS, "product_id", catalog_rows)
    store.append_snapshots("reward_snapshots", REWARD_SNAPSHOT_FIELDS, payload["ts_utc"], reward_rows)
    for error in payload.get("errors", []):
        print(f"Warning: {error}", file=sys.stderr)
    print(
        f"{payload['ts_utc']}: {len(reward_rows)} rewards ({len(catalog_rows)} new or changed), "
        f"{len(detail_rows)} project details updated"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
