# Screener State Persistence Bugfix Design

## Overview

The screener page's "一键执行选股" (run screening) button loses its `running` / `runError` state when the user navigates away, because both values are component-local `ref()` inside `ScreenerView.vue`. When the component unmounts, the state is destroyed. The fix moves `running`, `runError`, and the `runScreen` API call logic into the Pinia screener store (`useScreenerStore`), so the Promise and its state survive component lifecycle. When the component remounts, it reads the persisted state from the store and renders accordingly.

## Glossary

- **Bug_Condition (C)**: The user navigates away from the screener page while a screening API call (`POST /screen/run`) is in progress, causing the `running` state to be destroyed
- **Property (P)**: The `running` and `runError` state SHALL persist in the Pinia store across component mount/unmount cycles, and the UI SHALL accurately reflect the store state on remount
- **Preservation**: All existing screener behaviors (success navigation, error display, button idle state, button disabled state, other feature interactions) must remain unchanged
- **`runScreen`**: The async function in `ScreenerView.vue` (~line 1805) that sets `running = true`, calls `POST /screen/run`, and either navigates to `/screener/results` on success or sets `runError` on failure
- **`useScreenerStore`**: The Pinia store in `frontend/src/stores/screener.ts` that manages screener results, strategies, and factor registry — currently has no `running` state
- **`ScreenerView.vue`**: The page component at `frontend/src/views/ScreenerView.vue` that renders the screener UI and currently owns the `running` / `runError` refs locally

## Bug Details

### Bug Condition

The bug manifests when the user initiates a screening execution via the "一键执行选股" button and then navigates to a different route before the `POST /screen/run` API call completes. The `ScreenerView` component unmounts, destroying the local `ref(false)` for `running` and `ref('')` for `runError`. When the user navigates back, the component remounts with fresh `running = ref(false)`, showing the idle button state even though the API call may still be in flight.

**Formal Specification:**
```
FUNCTION isBugCondition(input)
  INPUT: input of type { screeningInProgress: boolean, componentMounted: boolean }
  OUTPUT: boolean

  RETURN input.screeningInProgress = true
         AND input.componentMounted = false
END FUNCTION
```

### Examples

- **Navigate away during screening**: User clicks "一键执行选股", then clicks "大盘概况" in the sidebar. The API call is still pending. On return to `/screener`, the button shows "🚀 一键执行选股" instead of "选股中..." — **bug**.
- **Navigate back after API completes**: User clicks "一键执行选股", navigates away, API succeeds while away. On return, the button shows idle state — this is correct behavior (no bug), but the results should be available and `runError` should be empty.
- **Navigate back after API fails**: User clicks "一键执行选股", navigates away, API fails while away. On return, the button shows idle state with no error message — **bug** (error is lost).
- **Stay on page during screening**: User clicks "一键执行选股" and waits. Button shows "选股中..." until API completes, then navigates to `/screener/results` — this is existing correct behavior and must be preserved.

## Expected Behavior

### Preservation Requirements

**Unchanged Behaviors:**
- When the user stays on the screener page and the API call succeeds, the app navigates to `/screener/results` as before
- When the user stays on the screener page and the API call fails, the error message is displayed and the button resets to idle
- When no screening is in progress, the button shows "🚀 一键执行选股" in idle state
- The button is disabled (`:disabled="running"`) while a screening is in progress, preventing duplicate submissions
- All other screener features (strategy selection, factor editing, module management, saving, import/export) function identically

**Scope:**
All interactions that do NOT involve the `running` / `runError` state should be completely unaffected by this fix. This includes:
- Strategy CRUD operations (create, rename, delete, activate, import, export)
- Factor condition editing (add, remove, modify factors)
- Module management (enable/disable modules)
- Configuration saving
- Realtime screening toggle
- Schedule status display

## Hypothesized Root Cause

Based on the bug description and code analysis, the root cause is:

1. **Component-local state**: `running` is declared as `const running = ref(false)` at line ~1098 of `ScreenerView.vue`. This ref exists only while the component is mounted. Vue's reactivity system destroys it on unmount.

2. **No store persistence**: The Pinia screener store (`frontend/src/stores/screener.ts`) has no `running` or `runError` state. There is no mechanism to persist the screening execution state outside the component.

3. **API call tied to component scope**: The `runScreen()` function (line ~1805) is defined inside the component's `<script setup>` block. While the `async` function's Promise continues executing after unmount (the API call itself is not cancelled), its `.then` / `.catch` handlers write to the now-destroyed local refs, so the state updates are lost.

4. **No re-sync on mount**: The `onMounted` hook does not check whether a screening is currently in progress. Even if the API call were tracked externally, the component has no logic to read that state on remount.

## Correctness Properties

Property 1: Bug Condition - Running state persists across component unmount

_For any_ store state where `running` is `true` (screening in progress), unmounting and remounting the `ScreenerView` component SHALL NOT reset `running` to `false`. The store's `running` value SHALL remain `true` until the API call resolves.

**Validates: Requirements 2.1, 2.2**

Property 2: Preservation - API outcome updates store correctly

_For any_ API call outcome (success with any valid response, or failure with any error message string), the store's `runScreen` action SHALL set `running = false` after completion, and SHALL set `runError` to the error message on failure or `''` on success.

**Validates: Requirements 2.3, 3.1, 3.2**

Property 3: Preservation - Idle state when no screening initiated

_For any_ initial store state (freshly created store), `running` SHALL be `false` and `runError` SHALL be `''`, ensuring the button renders in idle state.

**Validates: Requirements 3.3, 3.4**

Property 4: Preservation - Button disabled state reflects store running

_For any_ store state where `running` is `true`, the rendered button SHALL have `disabled = true` and display text "选股中...". For any store state where `running` is `false`, the button SHALL have `disabled = false` and display text "🚀 一键执行选股".

**Validates: Requirements 3.4, 2.2**

## Fix Implementation

### Changes Required

Assuming our root cause analysis is correct:

**File**: `frontend/src/stores/screener.ts`

**Changes**:
1. **Add `running` state**: Add `const running = ref(false)` to the store's setup function
2. **Add `runError` state**: Add `const runError = ref('')` to the store's setup function
3. **Add `runScreen` action**: Move the API call logic from `ScreenerView.vue` into a store action. The action accepts `{ strategyId?: string, strategyConfig?: object }`, sets `running = true`, calls `POST /screen/run`, and on completion sets `running = false`. On failure, it sets `runError` to the error message. The action returns a Promise so the component can optionally `await` it for navigation.
4. **Export new state and action**: Add `running`, `runError`, and `runScreen` to the store's return object

**File**: `frontend/src/views/ScreenerView.vue`

**Changes**:
1. **Remove local refs**: Delete `const running = ref(false)` and `const runError = ref('')` (around line 1098)
2. **Read from store**: Replace `running` and `runError` references with `screenerStore.running` and `screenerStore.runError`, or destructure with `storeToRefs`
3. **Delegate to store action**: Replace the local `runScreen()` function body with a call to `screenerStore.runScreen(...)`. The component still handles the `router.push('/screener/results')` on success (since the router is component-scoped), but the API call and state management live in the store
4. **No changes to template bindings**: The template already references `running` and `runError` — these just need to point to the store refs instead of local refs

## Testing Strategy

### Validation Approach

The testing strategy follows a two-phase approach: first, surface counterexamples that demonstrate the bug on unfixed code, then verify the fix works correctly and preserves existing behavior. Property-based tests use fast-check to generate diverse inputs.

### Exploratory Bug Condition Checking

**Goal**: Surface counterexamples that demonstrate the bug BEFORE implementing the fix. Confirm or refute the root cause analysis. If we refute, we will need to re-hypothesize.

**Test Plan**: Write tests that verify the store's `running` state behavior. On unfixed code, the store has no `running` state at all, so any test accessing `screenerStore.running` will get `undefined`.

**Test Cases**:
1. **Store state existence test**: Access `screenerStore.running` — will be `undefined` on unfixed code
2. **Store state persistence test**: Set `running = true` in store, simulate unmount/remount — will fail because store has no `running` field
3. **Store action existence test**: Call `screenerStore.runScreen(...)` — will throw because action doesn't exist

**Expected Counterexamples**:
- `screenerStore.running` is `undefined` (state not in store)
- `screenerStore.runScreen` is `undefined` (action not in store)
- Possible cause confirmed: state is component-local, not in Pinia store

### Fix Checking

**Goal**: Verify that for all inputs where the bug condition holds, the fixed function produces the expected behavior.

**Pseudocode:**
```
FOR ALL input WHERE isBugCondition(input) DO
  result := screenerStore.running
  ASSERT result = true
  // Store state persists regardless of component lifecycle
  unmountComponent()
  ASSERT screenerStore.running = true
  remountComponent()
  ASSERT screenerStore.running = true
END FOR
```

### Preservation Checking

**Goal**: Verify that for all inputs where the bug condition does NOT hold, the fixed function produces the same result as the original function.

**Pseudocode:**
```
FOR ALL input WHERE NOT isBugCondition(input) DO
  ASSERT runScreen_original(input).running_behavior = runScreen_fixed(input).running_behavior
  // When user stays on page: success → navigate, failure → show error
  // When no screening: button is idle
END FOR
```

**Testing Approach**: Property-based testing with fast-check is recommended because:
- It generates many API outcome scenarios (success, various error types, timeouts)
- It catches edge cases in error message formatting
- It provides strong guarantees that state transitions are correct for all inputs

**Test Plan**: Extract the store's state transition logic into testable pure functions, then use fast-check to verify properties across generated inputs.

**Test Cases**:
1. **API success preservation**: Verify `running` transitions from `true` → `false` and `runError` stays `''` on success
2. **API failure preservation**: Verify `running` transitions from `true` → `false` and `runError` contains the error message on failure
3. **Initial state preservation**: Verify fresh store has `running = false` and `runError = ''`
4. **Button state preservation**: Verify button disabled/text reflects `running` state for any boolean value

### Unit Tests

- Test that `useScreenerStore` exposes `running`, `runError`, and `runScreen`
- Test `runScreen` action sets `running = true` before API call
- Test `runScreen` action sets `running = false` after successful API call
- Test `runScreen` action sets `running = false` and `runError` to message after failed API call
- Test that `ScreenerView` reads `running` from store (not local ref)
- Test that button is disabled when `screenerStore.running = true`

### Property-Based Tests

- Generate random error message strings and verify `runError` stores them correctly after API failure (Property 2)
- Generate random sequences of `runScreen` calls and verify `running` state transitions are always correct (Property 1)
- Generate random initial store states and verify the idle/running UI rendering is consistent (Property 4)
- Generate random API response scenarios (success, network error, timeout, 4xx, 5xx) and verify state transitions (Property 2)

### Integration Tests

- Test full flow: click run → navigate away → navigate back → verify running state displayed
- Test full flow: click run → navigate away → API completes → navigate back → verify idle state
- Test full flow: click run → navigate away → API fails → navigate back → verify error displayed
- Test that `router.push('/screener/results')` still occurs on success when component is mounted
