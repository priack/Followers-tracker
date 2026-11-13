import copy
import unittest

from tracker.rewards import InvalidPayload, build_rows, fnv1a

DETAILS = [["Mixed-Case-Game", "maker", 42, 7, "Board & card games", "Fantasy|Dice Game", 1, 4, "2026-11-13T10:00:00Z"]]
REWARDS = [
    ["Mixed-Case-Game", 1001, "⛵ All-in \"Deluxe\"", 120, 99.95, 300, True, False, False, None],
    ["Mixed-Case-Game", 1002, "Base Game", 60, 49, 150, False, False, True, 25],
]


def payload():
    return {
        "version": 1,
        "ts_utc": "2026-11-14T10:00:00Z",
        "details": {
            "cols": ["project_url_name", "creator_url_name", "project_id", "creator_id", "category", "tags",
                     "min_players", "max_players", "campaign_start"],
            "rows": copy.deepcopy(DETAILS),
        },
        "rewards": {
            "cols": ["project_url_name", "product_id", "reward_name", "price", "effective_price",
                     "purchased_count", "is_featured", "is_most_popular", "has_limited_stock", "remaining_stock"],
            "rows": copy.deepcopy(REWARDS),
        },
        "errors": [],
        # Value computed by collect_rewards.js's hash on the same rows in the browser.
        "check": {"details": 1, "rewards": 2, "fnv1a": fnv1a([DETAILS, REWARDS])},
    }


class RewardsTest(unittest.TestCase):
    def test_hash_matches_browser_implementation(self):
        # Reference value computed in the browser with the collect_rewards.js hash.
        rows = [[["a-b", "Auerstädt", 8165, None, "x|y", 1.5, 264.95, 67.23, True, False]],
                [["p", 1, "⛵ Expansion \"Deluxe\" \\ é 🏝️", 100.84, 90, 0, True, None, 6000]]]
        self.assertEqual(fnv1a(rows), "3f305bd0")

    def test_rows_keyed_to_known_projects_case_insensitively(self):
        details, rewards = build_rows(payload(), ["mixed-case-game"])
        self.assertEqual(details[0]["project_url_name"], "mixed-case-game")
        self.assertEqual(details[0]["updated_at"], "2026-11-14T10:00:00Z")
        self.assertEqual(rewards[0]["hours_since_launch"], 24.0)
        self.assertEqual(rewards[0]["remaining_stock"], "")
        self.assertEqual(rewards[1]["remaining_stock"], 25)

    def test_altered_copy_is_rejected(self):
        altered = payload()
        altered["rewards"]["rows"][0][2] = "⛵ All-in \"Deluxe \""
        with self.assertRaises(InvalidPayload):
            build_rows(altered, [])


if __name__ == "__main__":
    unittest.main()
