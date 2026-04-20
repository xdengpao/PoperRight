# Bugfix Requirements Document

## Introduction

智能选股（Smart Screening）页面中，用户点击「一键执行选股」后，若导航到其他页面再返回，选股执行状态（按钮显示"选股中..."及 spinner）会丢失。根本原因是 `running` 状态以组件局部 `ref()` 存储在 `ScreenerView.vue` 中，组件卸载时状态被销毁。对于量化交易用户而言，无法准确感知当前选股任务是否仍在执行，可能导致重复提交或误判系统状态。

## Bug Analysis

### Current Behavior (Defect)

1.1 WHEN the user clicks "一键执行选股" and then navigates away from the screener page before the API call completes THEN the system destroys the `running` state because it is stored as a local `ref(false)` inside the component

1.2 WHEN the user navigates back to the screener page while the screening API call (`POST /screen/run`) is still in progress THEN the system shows the button as "🚀 一键执行选股" (idle state) instead of "选股中..." (running state), because the component remounts with `running = ref(false)`

1.3 WHEN the user sees the idle button state and clicks "一键执行选股" again while a previous screening is still running THEN the system submits a duplicate screening request, potentially causing unnecessary server load or conflicting results

### Expected Behavior (Correct)

2.1 WHEN the user clicks "一键执行选股" and then navigates away from the screener page THEN the system SHALL persist the screening execution state in the Pinia screener store so it survives component unmount/remount cycles

2.2 WHEN the user navigates back to the screener page while the screening API call is still in progress THEN the system SHALL display the button as "选股中..." with the spinner animation, accurately reflecting the ongoing execution

2.3 WHEN the screening API call completes (success or failure) while the user is on a different page THEN the system SHALL update the store state accordingly, so that returning to the screener page shows the correct final state (idle on success, error message on failure)

### Unchanged Behavior (Regression Prevention)

3.1 WHEN the user clicks "一键执行选股" and stays on the screener page until the API call succeeds THEN the system SHALL CONTINUE TO navigate to `/screener/results` as before

3.2 WHEN the user clicks "一键执行选股" and the API call fails while the user is on the screener page THEN the system SHALL CONTINUE TO display the error message and reset the button to idle state

3.3 WHEN the user has not initiated any screening execution THEN the system SHALL CONTINUE TO show the button as "🚀 一键执行选股" in idle state with no spinner

3.4 WHEN the screening API call is in progress THEN the system SHALL CONTINUE TO disable the "一键执行选股" button to prevent duplicate submissions

3.5 WHEN the user interacts with other screener features (strategy selection, factor editing, module management) THEN the system SHALL CONTINUE TO function identically regardless of where the running state is stored

---

## Bug Condition

```pascal
FUNCTION isBugCondition(X)
  INPUT: X of type NavigationEvent
  OUTPUT: boolean
  
  // The bug triggers when the user navigates away from the screener page
  // while a screening execution is in progress
  RETURN X.screeningInProgress = true AND X.navigatedAwayFromScreenerPage = true
END FUNCTION
```

## Fix Checking Property

```pascal
// Property: Fix Checking - Running state persists across navigation
FOR ALL X WHERE isBugCondition(X) DO
  state ← screenerStore.running
  ASSERT state = true
  // After navigating back, the UI reflects the running state
  uiState ← remountedScreenerView.running
  ASSERT uiState = true AND button.disabled = true AND button.text = "选股中..."
END FOR
```

## Preservation Checking Property

```pascal
// Property: Preservation Checking - Non-navigation behavior unchanged
FOR ALL X WHERE NOT isBugCondition(X) DO
  ASSERT F(X) = F'(X)
  // When user stays on page, behavior is identical
  // When no screening is running, button shows idle state
END FOR
```
