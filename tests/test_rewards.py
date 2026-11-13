import copy
import json
import tempfile
import unittest
from pathlib import Path

from tracker.rewards import InvalidPayload, build_rows, fnv1a, main

DETAILS = [["Mixed-Case-Game", "maker", 42, 7, "Board & card games", "Fantasy|Dice Game", 1, 4, "2026-11-13T10:00:00Z"]]
REWARDS = [
    ["Mixed-Case-Game", 1001, "⛵ All-in \"Deluxe\"", 120, 99.95, 300, True, False, False, None],
    ["Mixed-Case-Game", 1002, "Base Game", 60, 49, 150, False, False, True, 25],
]


def payload(details=(), rewards=(), counts=(), ts="2026-11-14T10:00:00Z"):
    details, rewards, counts = copy.deepcopy([list(details), list(rewards), list(counts)])
    return {
        "version": 2,
        "ts_utc": ts,
        "details": {
            "cols": ["project_url_name", "creator_url_name", "project_id", "creator_id", "category", "tags",
                     "min_players", "max_players", "campaign_start"],
            "rows": details,
        },
        "rewards": {
            "cols": ["project_url_name", "product_id", "reward_name", "price", "effective_price",
                     "purchased_count", "is_featured", "is_most_popular", "has_limited_stock", "remaining_stock"],
            "rows": rewards,
        },
        "counts": {"cols": ["product_id", "purchased_count", "remaining_stock"], "rows": counts},
        "errors": [],
        "check": {
            "details": len(details),
            "rewards": len(rewards),
            "counts": len(counts),
            "fnv1a": fnv1a([details, rewards, counts]),
        },
    }


PROJECTS = {"mixed-case-game": {"project_url_name": "mixed-case-game", "campaign_start": "2026-11-13T10:00:00Z"}}


class RewardsTest(unittest.TestCase):
    def test_hash_matches_browser_implementation(self):
        # Reference value computed in the browser with the collect_rewards.js hash.
        rows = [[["a-b", "Auerstädt", 8165, None, "x|y", 1.5, 264.95, 67.23, True, False]],
                [["p", 1, "⛵ Expansion \"Deluxe\" \\ é 🏝️", 100.84, 90, 0, True, None, 6000]]]
        self.assertEqual(fnv1a(rows), "3f305bd0")

    def test_full_rows_keyed_to_known_projects_case_insensitively(self):
        details, rewards, catalog = build_rows(payload(DETAILS, REWARDS), PROJECTS, {})
        self.assertEqual(details[0]["project_url_name"], "mixed-case-game")
        self.assertEqual([c["product_id"] for c in catalog], [1001, 1002])
        self.assertEqual(rewards[0]["project_url_name"], "mixed-case-game")
        self.assertEqual(rewards[0]["hours_since_launch"], 24.0)
        self.assertEqual(rewards[0]["remaining_stock"], "")
        self.assertEqual(rewards[1]["remaining_stock"], 25)

    def test_altered_copy_is_rejected(self):
        altered = payload(DETAILS, REWARDS)
        altered["rewards"]["rows"][0][2] = "⛵ All-in \"Deluxe \""
        with self.assertRaises(InvalidPayload):
            build_rows(altered, PROJECTS, {})

    def test_counts_without_catalog_entry_are_rejected(self):
        with self.assertRaisesRegex(InvalidPayload, "out of sync"):
            build_rows(payload(counts=[[1001, 310, None]]), PROJECTS, {})

    def test_counts_only_run_rebuilds_full_snapshot_rows(self):
        with tempfile.TemporaryDirectory() as tmp:
            data = Path(tmp) / "data"
            data.mkdir()
            (data / "projects.csv").write_text(
                "project_url_name,campaign_start\nmixed-case-game,2026-11-13T10:00:00Z\n", encoding="utf-8"
            )
            first, second = Path(tmp) / "first.json", Path(tmp) / "second.json"
            first.write_text(json.dumps(payload(DETAILS, REWARDS)), encoding="utf-8")
            second.write_text(
                json.dumps(payload(counts=[[1001, 320, None], [1002, 160, 15]], ts="2026-11-14T22:00:00Z")),
                encoding="utf-8",
            )

            self.assertEqual(main([str(first), "--data-dir", str(data)]), 0)
            self.assertEqual(main([str(second), "--data-dir", str(data)]), 0)

            lines = (data / "reward_snapshots" / "2026-11.csv").read_text(encoding="utf-8").splitlines()
            self.assertEqual(len(lines), 5)
            self.assertEqual(
                lines[3],
                '2026-11-14T22:00:00Z,mixed-case-game,36.0,1001,"⛵ All-in ""Deluxe""",120,99.95,320,True,False,False,',
            )
            self.assertEqual(lines[4], "2026-11-14T22:00:00Z,mixed-case-game,36.0,1002,Base Game,60,49,160,False,False,True,15")


if __name__ == "__main__":
    unittest.main()
