# Gamefound followers tracker

Hourly snapshots of Gamefound crowdfunding projects, collected by GitHub Actions from the
[Gamefound public API](https://help.gamefound.com/article/425-gamefound-public-api):

- **Upcoming projects**: follower count and planned launch date (`getUpcomingCrowdfundingProjects`).
- **Live campaigns**: backers, funds raised, followers, comments, updates and reward count (`getActiveCrowdfundingProjects`).

Every run records everything; downsample when analysing.

## Data

| File | Contents |
|---|---|
| `data/projects.csv` | One row per project, updated each run: names, URLs, currency, goal, dates, `status` (`upcoming`, `live`, `ended`, `gone`) and when each milestone was first seen. |
| `data/follower_snapshots/YYYY-MM.csv` | `ts_utc, project_url_name, follower_count, campaign_start` for every upcoming project. |
| `data/campaign_snapshots/YYYY-MM.csv` | `ts_utc, project_url_name, hours_since_launch, backers, funds_gathered, follower_count, comment_count, update_count, reward_count` for every live campaign. |

All timestamps are UTC. `funds_gathered` and `goal` are in the project's own `currency`.
`project_url_name` joins all tables.

## Running locally

Requires Python 3.10+, no dependencies.

```bash
python -m tracker --data-dir data
python -m unittest discover -s tests -t .
```
