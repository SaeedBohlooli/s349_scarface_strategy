# Real-Time Streaming Plan: `open_trades` and `contract_strikes`

## Goal

Add two new WebSocket event streams without changing existing behavior:

- `open_trades` (derived from `application_state['open_trades_dic']`)
- `contract_strikes` (derived from `global_state.option_contract_cache`)

Existing `application_state` stream must remain intact and continue emitting every 5 seconds.

---

## Current Behavior (As-Is)

## Engine startup and stream wiring

In `trading_engine/engine.py`, `TradingEngine.run()` starts:

- `StateStreamer(..., interval_sec=5)` -> emits `type: "application_state"` every 5 seconds
- `ConfigStreamer(..., interval_sec=60)`
- `engine_loop(...)` and other loops

So today:

- `application_state` publish interval = **5 seconds**
- Stream payload includes `open_trades_dic` and `global_state.option_contract_cache` as part of the big `application_state` object

## Where stream payload is built

In `trading_core/streamers/state_streamer.py`:

- `state = self.app_state.copy()`
- `state = streaming_util.sanitize_for_json(state)`
- packet:
  - `type: "application_state"`
  - `data: state`
  - `timestamp: ...`
- `await self.ws.broadcast(packet)`
- `await asyncio.sleep(self.interval_sec)` (5s from engine)

## Where the two data sources are maintained

## `open_trades_dic`

Primary write points:

- `trading_engine/order_helper.py`
  - sets/updates `application_state.setdefault('open_trades_dic', {})[symbol] = data`
- `trading_engine/exit_conditions.py`
  - modifies per-symbol open trade fields and sometimes resets to empty dict

## `global_state.option_contract_cache`

Primary write point:

- `trading_utils/ib_contract.py`
  - `get_option_contract_cached(...)` writes on cache miss:
    - `global_state.option_contract_cache[key] = qualified_contract`

Current `application_state` copy of this cache is injected in:

- `trading_core/application_state_router.py`
  - `application_state['global_state.option_contract_cache'] = global_state.stringify_option_cache(global_state.option_contract_cache)`

---

## Requested Target Behavior

Keep current stream:

- `application_state` every 5 seconds unchanged

Add new separate event types:

- `open_trades`
- `contract_strikes`

These should be available in near real-time, independent from the 5-second full-state cadence.

---

## Design Requirements (No Functional Regression)

1. **Do not remove or rename existing fields** in `application_state`.
2. **Do not change existing `application_state` interval** (5 sec).
3. **Additive-only WS change**: clients that only listen to `application_state` must continue working unchanged.
4. **JSON-safe payloads**:
   - sanitize all outgoing payloads
   - stringify non-serializable contract objects for `contract_strikes`
5. **Low risk rollout**:
   - feature flags / config-driven intervals recommended
   - allow independent disable of each new stream

---

## Recommended Implementation Approach

## 1) Add dedicated streamer classes (preferred)

Create new streamers in `trading_core/streamers/`:

- `open_trades_streamer.py`
- `contract_strikes_streamer.py`

Each streamer:

- accepts `(app_config, app_state, ws_server, interval_sec=1)`
- computes normalized payload
- optional hash/checksum to emit only when changed
- broadcasts packet with dedicated type
- sleeps on configured interval

Why this approach:

- isolates risk from `StateStreamer`
- easy to tune intervals separately
- no changes to existing packet structure

## 2) Wire new streamers in engine run loop

In `trading_engine/engine.py` `run()`:

- keep existing `state_streamer.run()` as-is
- add:
  - `open_trades_streamer.run()`
  - `contract_strikes_streamer.run()`

Example target intervals (configurable):

- `application_state`: 5 sec (existing)
- `open_trades`: 1 sec
- `contract_strikes`: 1 sec (or 2 sec if heavy)

## 3) Add event contracts

### `open_trades` event

Packet shape:

```json
{
  "type": "open_trades",
  "data": {
    "open_trades_dic": {
      "SPY": { "...": "..." },
      "QQQ": { "...": "..." }
    }
  },
  "timestamp": "YYYY-MM-DD HH:MM:SS"
}
```

### `contract_strikes` event

Use stringified cache to avoid contract-object serialization issues.

Packet shape:

```json
{
  "type": "contract_strikes",
  "data": {
    "option_contract_cache": {
      "SPX|20260307|5100|C": "Option(...)"
    },
    "count": 123
  },
  "timestamp": "YYYY-MM-DD HH:MM:SS"
}
```

---

## Real-Time Strategy

There are two safe options. Option A is simplest and lowest-risk.

## Option A: Fast polling streamers (recommended first)

- Emit every 1s (or configured interval)
- Compute a stable hash of payload and only broadcast on change
- Very low code coupling with existing mutators

Pros:

- minimal invasive changes
- resilient even if future write points are added

Cons:

- not truly event-push at write time (up to interval latency)

## Option B: Event-driven push hooks

Emit immediately at mutation points:

- `order_helper.py` and `exit_conditions.py` when `open_trades_dic` changes
- `ib_contract.py` when option cache gets new strike contract

Pros:

- lower latency than polling

Cons:

- many write paths, easier to miss one
- higher coupling and regression risk

Recommendation:

- start with Option A + change-detection
- later add Option B selectively if needed

---

## Exact Files To Touch (Planned)

1. `trading_core/streamers/open_trades_streamer.py` (new)
2. `trading_core/streamers/contract_strikes_streamer.py` (new)
3. `trading_engine/engine.py`
   - instantiate and run both new streamers in `asyncio.gather`
4. `configs/config-common.yaml` or portfolio config
   - add intervals and enable flags, e.g.:
     - `interval_seconds.open_trades_streamer: 1`
     - `interval_seconds.contract_strikes_streamer: 1`
     - `streams.enable_open_trades: true`
     - `streams.enable_contract_strikes: true`
5. UI consumer config (optional but recommended)
   - `ui-control-panel/ui-dashboard/src/config/configLoader.js`
   - ensure `messageTypes.contractStrikes` exists (it already has `openTrades`)

No required changes to:

- `trading_core/streamers/state_streamer.py` behavior
- existing `application_state` payload fields

---

## Backward Compatibility Checklist

- `application_state` still emitted every 5 sec
- `application_state.data.open_trades_dic` still present
- `application_state.data['global_state.option_contract_cache']` still present
- new events are additive only
- old UI pages listening only to `application_state` remain functional

---

## Validation / Test Plan

## Functional tests

1. Start engine, connect WS client, verify message types observed:
   - `application_state`
   - `open_trades`
   - `contract_strikes`
2. Verify `application_state` cadence remains ~5 sec.
3. Trigger trade open/close:
   - `open_trades` should update within configured interval.
4. Trigger option-contract cache growth:
   - `contract_strikes` count should increase accordingly.

## Regression tests

1. Existing UI pages (application state, positions, open orders) continue to work.
2. No JSON serialization errors on WS broadcast.
3. CPU/memory overhead acceptable with 1s streamers.

## Observability

Add concise logs:

- `[OpenTradesStreamer] changed=<bool> size=<n>`
- `[ContractStrikesStreamer] changed=<bool> count=<n>`

---

## Risk Notes and Mitigations

1. **Payload size growth** (`contract_strikes` can become large)
   - mitigate with change-only broadcast
   - include count and optional truncation if needed
2. **Serialization errors**
   - always stringify option cache keys/values before emit
   - always run `sanitize_for_json`
3. **Duplicate data across streams**
   - expected by design for backward compatibility
   - can deprecate later only after client migration

---

## Suggested Rollout Sequence

1. Implement new streamers + config flags (default enabled in dev).
2. Run engine and verify all three streams.
3. Update UI listeners for optional dedicated views/subscriptions:
   - `useWebSocket('open_trades')`
   - `useWebSocket('contract_strikes')`
4. Keep old `application_state` consumers unchanged.
5. After stabilization, optionally reduce heavy fields in `application_state` (future phase only, not now).

---

## Direct Answers To Your Questions

- **After how much interval does it stream `application_state` now?**
  - Every **5 seconds** (`StateStreamer(... interval_sec=5)` in `engine.py`).

- **Can `open_trades` and `contract_strikes` be sent in real time while `application_state` stays 5 sec?**
  - Yes. Add separate streamer events at 1-second cadence with change-detection (safe path), or event-driven hooks (faster but riskier).

- **How to send `open_trades_dic` and `global_state.option_contract_cache` as separate events without breaking existing functionality?**
  - Keep them inside `application_state` as-is and add additive WS events:
    - `type: "open_trades"` from `open_trades_dic`
    - `type: "contract_strikes"` from stringified `option_contract_cache`

