// Collects reward tiers and project details for every live Gamefound campaign.
//
// Run inside a gamefound.com tab (the internal endpoints only answer same-origin browser requests).
// Evaluates to a compact JSON string; save it verbatim and load it with `python -m tracker.rewards`.
(async () => {
  const DELAY_MS = 400; // between requests, to stay light on the site
  const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

  async function search(pageIndex) {
    const response = await fetch("/api/projectSearch/searchProjectsForCards", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ pageSize: 24, pageIndex, projectPhaseSearchTypes: ["Crowdfunding"] }),
    });
    if (!response.ok) throw new Error(`searchProjectsForCards page ${pageIndex}: HTTP ${response.status}`);
    return (await response.json()).projects;
  }

  const cards = [];
  for (let pageIndex = 0; ; pageIndex++) {
    const page = await search(pageIndex);
    cards.push(...page.pagedItems);
    if (pageIndex + 1 >= page.totalPageCount) break;
    await sleep(DELAY_MS);
  }

  const details = [];
  const rewards = [];
  const errors = [];
  for (const card of cards) {
    const props = card.projectProperties || {};
    details.push([
      card.projectUrlName,
      card.creator?.urlName ?? null,
      card.projectID,
      card.creator?.creatorID ?? null,
      card.catalogCategory?.name ?? null,
      (card.projectTags || []).map((tag) => tag.name).join("|"),
      props.minPlayers ?? null,
      props.maxPlayers ?? null,
      card.campaignStart,
    ]);

    await sleep(DELAY_MS);
    try {
      const response = await fetch(`/api/projectContents/getRewards?projectID=${card.projectID}`);
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      for (const reward of (await response.json()).data?.rewards || []) {
        rewards.push([
          card.projectUrlName,
          reward.productID,
          reward.name,
          reward.price,
          reward.effectivePrice,
          reward.purchasedCopiesCount,
          reward.isFeatured,
          reward.isMostPopular,
          reward.hasLimitedStock,
          reward.remainingStockLimit,
        ]);
      }
    } catch (e) {
      errors.push(`${card.projectUrlName}: ${e.message}`);
    }
  }

  // FNV-1a over the UTF-16 code units of the serialized rows; tracker/rewards.py recomputes it.
  const body = JSON.stringify([details, rewards]);
  let hash = 0x811c9dc5;
  for (let i = 0; i < body.length; i++) {
    hash = Math.imul(hash ^ body.charCodeAt(i), 0x01000193) >>> 0;
  }

  // Kept on the page so a rejected copy can be re-read without collecting again.
  window.__rewardsPayload = JSON.stringify({
    version: 1,
    ts_utc: new Date().toISOString().replace(/\.\d+Z$/, "Z"),
    details: {
      cols: ["project_url_name", "creator_url_name", "project_id", "creator_id", "category", "tags",
             "min_players", "max_players", "campaign_start"],
      rows: details,
    },
    rewards: {
      cols: ["project_url_name", "product_id", "reward_name", "price", "effective_price", "purchased_count",
             "is_featured", "is_most_popular", "has_limited_stock", "remaining_stock"],
      rows: rewards,
    },
    errors,
    // Lets the loader detect a truncated or mistyped copy of this output.
    check: {
      details: details.length,
      rewards: rewards.length,
      fnv1a: hash.toString(16).padStart(8, "0"),
    },
  });
  return window.__rewardsPayload;
})();
