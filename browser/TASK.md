# Rewards collection task

Instructions for the scheduled Claude task that collects reward tiers from a real browser.
Gamefound's reward data is only reachable from a gamefound.com page, so this part cannot run in GitHub Actions.

Repository: `E:\OneDrive\git\Followers tracker`

1. `git pull --rebase` in the repository (GitHub Actions commits hourly).
2. Open `https://gamefound.com/en/projects/search?projectPhaseSearchTypes=Crowdfunding` in the built-in browser
   and wait until the page has loaded.
   If Gamefound shows a Cloudflare challenge, a CAPTCHA or an error page, stop and report it. Do not try to get past it.
3. Run the full contents of `browser/collect_rewards.js` in that tab with the JavaScript tool.
   It takes about 20 seconds and returns a JSON string.
4. Save that string verbatim (decoded, no surrounding quotes) to `rewards.json` in the scratchpad directory.
5. Run `python -m tracker.rewards <path to rewards.json> --data-dir data`.
   If it reports a checksum mismatch, re-read the payload with `window.__rewardsPayload` in the same tab,
   save it again and retry once. Do not edit the data by hand to make the check pass.
6. Commit and push only the browser-collected files:
   ```
   git add data/project_details.csv data/reward_snapshots
   git commit -m "data: rewards snapshot <ts_utc from the payload>"
   git pull --rebase && git push
   ```
7. Reply with the loader's summary line and any warnings.
