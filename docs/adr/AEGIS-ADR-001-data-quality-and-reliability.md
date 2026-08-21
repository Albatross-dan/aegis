# AEGIS Architecture Decision Record — ADR-001

**Title:** Data Quality, Reasoning Reliability, and Operational Observability Remediation
**Status:** Approved
**Date:** 2026-08-18
**Author:** Claude (Chief Systems Architect)
**Approved by:** Daniel Oguda (Founder)
**Amends:** AEGIS Engineering Handbook, Doc 02 (Guiding Principles), Doc 06 (Data Flow & Decision Pipeline), Doc 09 (Development Roadmap)

---

## 1. Context

A full-system review was conducted after completion of Phase 1 (Market Intelligence Layer), Phase 2 (Feature Engineering), and the first AI Council expert (Trend Intelligence AI) in Phase 3. The review's purpose was to identify gaps between current implementation and the handbook's own stated principles — specifically Doc 02 SS1 (correctness before speed), Doc 02 SS8 (reproducibility), Doc 02 SS13 (observability), and Doc 02 SS14 (adaptability) — before further complexity (additional AI experts, Chief Strategist, Risk Engine) is layered on top of an unverified foundation.

This ADR does not reverse any prior architectural decision. It records identified gaps and defines a prioritized remediation sequence, to be executed before Phase 3 continues.

## 2. Findings

### 2.1 Critical — directly degrades decision quality

| # | Finding | Handbook conflict |
|---|---|---|
| F1 | `candles_1m` is built from sparse 5-second polling (some candles have `tick_count = 1`), not genuine tick coverage. OHLC values on low-count candles are not statistically meaningful. | Doc 02 SS8 (reproducibility/evidence integrity), Doc 06 SS3 (accurate observation) |
| F2 | Trend AI's confidence formula (`\|close - sma\| / atr`) is an untested heuristic. It has not been validated against historical outcomes and may correlate poorly, or inversely, with actual predictive reliability in ranging markets. | Doc 02 SS2 (no strategy/logic enters production without evidence) |
| F3 | Trend AI reasons from a single latest candle (`LIMIT 1`), with no multi-period confirmation that a trend condition is persisting rather than momentary noise. | Doc 05 SS5 (trend continuation vs. false breakout is Trend AI's known weak point) |

### 2.2 Serious — will cause silent failures over time

| # | Finding | Handbook conflict |
|---|---|---|
| F4 | `SYMBOL_CONFIG` price/spread bounds in `validation.py` are static, current-market snapshots. As prices move (e.g. USDJPY trending past 170), valid data will begin being silently quarantined with no alert. | Doc 02 SS14 (Adaptability — static assumptions degrade as markets evolve) |
| F5 | No alerting exists. Failures (feed disconnects, cron job failures, backend crashes) are only visible via manual log inspection. | Doc 02 SS13 (Observability requires alerting, not just logging) |
| F6 | Job sequencing between `compute_features` and `trend_ai` is encoded as a hardcoded `sleep 15` in crontab — an invisible, fragile dependency. | Doc 08 SS9 (orchestration), Doc 02 SS9 (documented, version-controlled dependencies) |
| F7 | No automated tests exist anywhere in the codebase. All verification to date has been manual. | Doc 08 SS14 (Pytest is the designated standard), Doc 02 SS9 (testability) |

### 2.3 Noted — lower urgency, tracked for future work

| # | Finding |
|---|---|
| F8 | No explicit handling for market-closed periods (weekends); indistinguishable from a feed outage under current staleness logic. |
| F9 | Duplicate detection catches only exact repeats, not near-duplicate anomalies. |
| F10 | Database credentials have appeared in plaintext in terminal history throughout development. Acceptable for solo localhost use; must be rotated and confirmed `.env`-gitignored before any shared/production use. |

## 3. Decision

The following remediation sequence is adopted, in priority order, to be completed before Phase 3 continues with additional AI experts:

1. **F1** — Increase tick sampling frequency (investigate true MT5 tick-streaming vs. current 5s poll) so `candles_1m` reflects genuine intraminute price action.
2. **F3** — Extend Trend AI (and all future experts) to reason over a short window of recent candles (e.g. last 3-5), not a single latest row.
3. **F7** — Introduce a baseline Pytest suite covering validation logic (`validation.py`) and feature computation (`compute_features.py`) before further logic is added on top.
4. **F4** — Replace static `SYMBOL_CONFIG` bounds with either a documented manual-review cadence or a rolling historical-range-based bound.
5. **F5** — Add a minimal heartbeat/alerting mechanism (e.g. "no tick for symbol X in >2 min" check).
6. **F6** — Replace crontab `sleep`-based sequencing with an explicit dependency mechanism once a second scheduled job is added (candidate trigger point for adopting Prefect per Doc 08 SS9).
7. **F2** — Defer formal validation of the confidence formula to Phase 5 (Research Laboratory / Backtesting), where it can be measured against real historical outcomes rather than adjusted speculatively.

F8, F9, F10 are logged as tracked technical debt, to be addressed opportunistically or before any multi-user/production milestone (consistent with the existing deferral of auth/CI-CD/DigitalOcean deployment).

## 4. Consequences

- Phase 3 AI Council expansion (additional experts, Chief Strategist) is paused until items 1-3 above are complete, since every additional expert would otherwise inherit the same data-quality and single-point-reasoning weaknesses.
- This introduces near-term schedule cost but directly serves Doc 02 SS1's "correctness over speed" mandate and Doc 10 SS16's Founder Commitment to "prioritizing engineering quality over rushing features."
- No prior code is being discarded; all fixes are additive or corrective refinements to existing modules (`validation.py`, `trend_ai.py`, crontab configuration).

---

*This ADR is a living amendment. Future ADRs should reference this one where relevant rather than re-litigating settled findings.*

---

## 5. Remediation Log

### F1 — Resolved (2026-08-20)

**Root cause identified:** two compounding issues.
1. Poll interval (5s) was far coarser than Exness demo feed's true tick rate (~0.9-1.2 ticks/sec measured empirically), so most real ticks were never sampled.
2. A ~5-second-per-request delay was traced to Windows resolving `localhost` via IPv6 first, timing out, then falling back to IPv4 - unrelated to poll interval, but compounding the same symptom.

**Fix applied:**
- Reduced poll interval to 0.5s with change-detection (`tick.time_msc` comparison) to avoid duplicate sends.
- Changed `BACKEND_URL` from `http://localhost:8000` to `http://127.0.0.1:8000`, eliminating the IPv6 fallback delay.

**Verification:** raw tick ingestion rate increased from ~3-4 ticks/minute/symbol to 25-50+ ticks/minute/symbol. `candles_1m` `tick_count` increased correspondingly from 1-2 to 32-56 per candle. Confirmed via direct query against both `market_ticks` and `candles_1m` post-fix.

**Files changed:** `C:\aegis-bridge\price_feed.py` (Windows bridge).

### F3 — Resolved (2026-08-20)

**Fix applied:** Trend Intelligence AI (`trend_ai.py`) now requires multi-candle confirmation instead of reasoning from a single latest candle. Fetches the last 5 candles, classifies each individually (buy/sell/hold based on close vs EMA20 vs SMA20 structure), and only assigns a directional call if at least 4 of 5 candles agree. Confidence blends persistence (agreement toward the winning direction, 60% weight) with magnitude (price divergence from SMA relative to ATR, 40% weight). Model version bumped to trend_ai_v2 per Doc 02 §9.

**Bug found and fixed during implementation:** initial version calculated persistence using hold_count when no direction reached threshold, producing near-certain confidence (~0.99) for a "no signal" result — backwards, since hold should never carry high confidence. Corrected to use max(buy_count, sell_count) / window_size regardless of final direction, so hold results correctly show moderate confidence reflecting how close the market came to a real signal, not false certainty in the absence of one.

**Verification:** confirmed against live data across all 6 symbols. Genuine 5/5 directional agreement (GBPUSD buy, USDJPY sell) correctly retained confidence 1.0. All hold-direction results now show moderate confidence (0.25-0.53) rather than the pre-fix bug's near-0 or near-1 extremes.

**Files changed:** backend/app/ai_council/trend_ai.py.

### F4 — Resolved (2026-08-20)

**Fix applied:** Replaced static, hardcoded price bounds in SYMBOL_CONFIG with a dynamic function get_dynamic_price_bounds() that queries market_ticks for each symbol's real bid history over the last 30 days, computing bounds as [min(bid) * 0.85, max(bid) * 1.15]. Falls back to static bounds if fewer than 100 historical ticks exist for a symbol (e.g. newly added symbols with no history yet). check_price_sanity now requires a db session parameter to support this query. Spread bounds (max_spread) remain static in SYMBOL_CONFIG, as spread is a different class of check (transient anomaly detection) not suited to historical adaptation.

**Verification:** confirmed against live data. EURUSD dynamic bounds computed as 0.92225-1.34473 from observed range 1.085-1.16933. USDJPY dynamic bounds computed as 134.77-183.618 from observed range 158.553-159.668. Both ranges are sane - wide enough to absorb real market movement, but still bounded enough to catch obviously bad prices.

**Files changed:** backend/app/core/validation.py, backend/app/main.py, backend/tests/test_validation.py.
