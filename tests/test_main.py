import unittest

from tracker.main import update

UPCOMING = {
    "projectUrlName": "soon-game",
    "projectName": "Soon Game",
    "creatorUrlName": "maker",
    "creatorName": "Maker",
    "projectType": 1,
    "projectHomeUrl": "https://gamefound.com/projects/maker/soon-game",
    "campaignStartDate": None,
    "publishedDate": "2026-10-01T10:00:00Z",
    "followerCount": 100,
}

ACTIVE = {
    "projectUrlName": "live-game",
    "projectName": "Live Game",
    "creatorUrlName": "maker",
    "creatorName": "Maker",
    "projectType": 1,
    "projectHomeUrl": "https://gamefound.com/projects/maker/live-game",
    "campaignStartDate": "2026-11-13T10:00:00Z",
    "campaignEndDate": "2026-12-13T10:00:00Z",
    "campaignGoal": 1000.0,
    "currencyShortName": "EUR",
    "backerCount": 50,
    "fundsGathered": 4321.5,
    "commentCount": 3,
    "updateCount": 1,
    "rewardCount": 4,
}


class UpdateTest(unittest.TestCase):
    def test_snapshots_and_project_rows(self):
        projects = {}
        followers, campaigns = update(projects, "2026-11-13T16:30:00Z", [UPCOMING], [ACTIVE])

        self.assertEqual(followers[0]["follower_count"], 100)
        self.assertEqual(campaigns[0]["hours_since_launch"], 6.5)
        self.assertEqual(campaigns[0]["follower_count"], "")  # field not deployed yet
        self.assertEqual(projects["soon-game"]["status"], "upcoming")
        self.assertEqual(projects["soon-game"]["launch_date_first_seen_at"], "")
        self.assertEqual(projects["live-game"]["first_seen_live_at"], "2026-11-13T16:30:00Z")

    def test_launch_date_announcement_and_launch(self):
        projects = {}
        update(projects, "2026-11-01T00:00:00Z", [UPCOMING], [])
        update(projects, "2026-11-02T00:00:00Z", [dict(UPCOMING, campaignStartDate="2026-11-10T14:00:00Z")], [])
        launched = dict(ACTIVE, projectUrlName="soon-game", campaignStartDate="2026-11-10T14:00:00Z")
        update(projects, "2026-11-10T15:00:00Z", [], [launched])

        project = projects["soon-game"]
        self.assertEqual(project["first_seen_upcoming_at"], "2026-11-01T00:00:00Z")
        self.assertEqual(project["launch_date_first_seen_at"], "2026-11-02T00:00:00Z")
        self.assertEqual(project["first_seen_live_at"], "2026-11-10T15:00:00Z")
        self.assertEqual(project["status"], "live")

    def test_status_changes_only_when_both_lists_fetched(self):
        projects = {}
        update(projects, "2026-11-01T00:00:00Z", [UPCOMING], [ACTIVE])

        update(projects, "2026-11-01T01:00:00Z", None, [])
        self.assertEqual(projects["live-game"]["status"], "live")

        update(projects, "2026-11-01T02:00:00Z", [], [])
        self.assertEqual(projects["live-game"]["status"], "ended")
        self.assertEqual(projects["soon-game"]["status"], "gone")


if __name__ == "__main__":
    unittest.main()
