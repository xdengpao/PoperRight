# Implementation Plan

- [x] 1. Write bug condition exploration test
  - **Property 1: Bug Condition** - Store missing `running` state causes undefined on navigation
  - **CRITICAL**: This test MUST FAIL on unfixed code — failure confirms the bug exists
  - **DO NOT attempt to fix the test or the code when it fails**
  - **NOTE**: This test encodes the expected behavior — it will validate the fix when it passes after implementation
  - **GOAL**: Surface counterexamples that demonstrate the bug exists
  - **Scoped PBT Approach**: The bug is deterministic — the Pinia store has no `running` field, so `screenerStore.running` is always `undefined`. Scope the property to this concrete case.
  - Create test file `frontend/src/stores/__tests__/screener-running.property.test.ts`
  - Use `fast-check` to generate arbitrary strategy IDs (non-empty strings) and verify that after calling `screenerStore.runScreen(...)`, the store's `running` state is `true` (a boolean, not `undefined`)
  - Property: `fc.assert(fc.property(fc.string({ minLength: 1 }), async (strategyId) => { ... }))` — for any strategy ID, calling `runScreen` should set `running` to `true`
  - On unfixed code: `screenerStore.runScreen` is `undefined` (action does not exist), so the test will throw — **this confirms the bug exists**
  - Counterexample: `screenerStore.running === undefined` and `screenerStore.runScreen === undefined` on the current store
  - Mock `apiClient.post` to return a delayed promise so `running` can be observed mid-flight
  - Use `createPinia()` + `setActivePinia()` for isolated store instances
  - Run test on UNFIXED code
  - **EXPECTED OUTCOME**: Test FAILS (this is correct — it proves the bug exists)
  - Document counterexamples found to understand root cause
  - Mark task complete when test is written, run, and failure is documented
  - _Requirements: 1.1, 1.2, 2.1, 2.2_

- [x] 2. Write preservation property tests (BEFORE implementing fix)
  - **Property 2: Preservation** - Existing store behavior unchanged for non-running features
  - **IMPORTANT**: Follow observation-first methodology
  - Create test file `frontend/src/stores/__tests__/screener-preservation.property.test.ts`
  - Observe on UNFIXED code: `useScreenerStore()` exposes `results`, `strategies`, `loading`, `lastUpdated`, `factorRegistry`, `strategyExamples`, `sectorCoverage` as reactive refs, plus `fetchResults`, `fetchStrategies`, `activateStrategy`, `fetchFactorRegistry`, `fetchStrategyExamples`, `fetchSectorCoverage` as actions
  - Observe: `fetchResults()` sets `loading = true`, calls `GET /screen/results`, sets `results` and `lastUpdated`, then sets `loading = false`
  - Observe: fresh store has `results = []`, `strategies = []`, `loading = false`, `lastUpdated = null`
  - Write property-based tests with fast-check:
    - **P2a**: For any array of `ScreenItem` objects returned by the API, `fetchResults()` stores them in `results` and sets `lastUpdated` to a `Date` — generate random arrays of screen items
    - **P2b**: For any array of `StrategyTemplate` objects returned by the API, `fetchStrategies()` stores them in `strategies` — generate random strategy arrays
    - **P2c**: Fresh store initial state is always `results = []`, `strategies = []`, `loading = false`, `lastUpdated = null` — no inputs needed, just verify invariant
  - Mock `apiClient.get` to return generated data
  - Verify all tests pass on UNFIXED code
  - **EXPECTED OUTCOME**: Tests PASS (this confirms baseline behavior to preserve)
  - Mark task complete when tests are written, run, and passing on unfixed code
  - _Requirements: 3.1, 3.2, 3.3, 3.5_

- [x] 3. Fix: Move `running`/`runError` state and `runScreen` action to Pinia store

  - [x] 3.1 Add `running`, `runError` state and `runScreen` action to `frontend/src/stores/screener.ts`
    - Add `const running = ref(false)` to the store setup function
    - Add `const runError = ref('')` to the store setup function
    - Add `async function runScreen(params: { strategyId?: string; strategyConfig?: object })` action that:
      - Sets `running.value = true` and `runError.value = ''`
      - Calls `apiClient.post('/screen/run', { strategy_id, strategy_config, screen_type: 'EOD' }, { timeout: 120_000 })`
      - On success: sets `running.value = false` and returns `{ success: true }`
      - On failure: sets `running.value = false`, sets `runError.value` to the error message, and returns `{ success: false }`
    - Export `running`, `runError`, and `runScreen` in the store's return object
    - _Bug_Condition: isBugCondition(input) where input.screeningInProgress = true AND input.componentMounted = false — state was component-local_
    - _Expected_Behavior: running/runError persist in Pinia store across component mount/unmount cycles_
    - _Preservation: All existing store exports (results, strategies, loading, etc.) remain unchanged_
    - _Requirements: 2.1, 2.3, 3.1, 3.2, 3.3, 3.4, 3.5_

  - [x] 3.2 Update `frontend/src/views/ScreenerView.vue` to use store state
    - Remove local `const running = ref(false)` and `const runError = ref('')` declarations (~line 1098–1099)
    - Import `storeToRefs` from `pinia` and destructure `const { running, runError } = storeToRefs(screenerStore)`
    - Replace the local `runScreen()` function body: call `const result = await screenerStore.runScreen({ strategyId: activeStrategyId.value || undefined, strategyConfig: activeStrategyId.value ? undefined : buildStrategyConfig() })`, then `if (result.success) router.push('/screener/results')`
    - Template bindings (`:disabled="running"`, `v-if="runError"`, `{{ running ? '选股中...' : '🚀 一键执行选股' }}`) continue to work because `running` / `runError` now come from `storeToRefs`
    - _Requirements: 2.1, 2.2, 2.3, 3.1, 3.2_

  - [x] 3.3 Verify bug condition exploration test now passes
    - **Property 1: Expected Behavior** - Store `running` state persists across component lifecycle
    - **IMPORTANT**: Re-run the SAME test from task 1 — do NOT write a new test
    - The test from task 1 encodes the expected behavior (store has `running` field, `runScreen` action exists and sets `running = true`)
    - Run: `npm test -- --run frontend/src/stores/__tests__/screener-running.property.test.ts`
    - **EXPECTED OUTCOME**: Test PASSES (confirms bug is fixed)
    - _Requirements: 2.1, 2.2_

  - [x] 3.4 Verify preservation tests still pass
    - **Property 2: Preservation** - Existing store behavior unchanged
    - **IMPORTANT**: Re-run the SAME tests from task 2 — do NOT write new tests
    - Run: `npm test -- --run frontend/src/stores/__tests__/screener-preservation.property.test.ts`
    - **EXPECTED OUTCOME**: Tests PASS (confirms no regressions)
    - Confirm all preservation tests still pass after fix (no regressions)
    - _Requirements: 3.1, 3.2, 3.3, 3.5_

- [x] 4. Checkpoint — Ensure all tests pass
  - Run full frontend test suite: `npm test` (from `frontend/` directory)
  - Ensure all tests pass, ask the user if questions arise
