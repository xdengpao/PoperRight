# Implementation Plan

## Phase 1: Bug Condition Exploration Tests

- [x] 1. Write bug condition exploration test
  - **Property 1: Bug Condition** - 日线数据时间戳不一致
  - **CRITICAL**: This test MUST FAIL on unfixed code - failure confirms the bug exists
  - **DO NOT attempt to fix the test or the code when it fails**
  - **NOTE**: This test encodes the expected behavior - it will validate the fix when it passes after implementation
  - **GOAL**: Surface counterexamples that demonstrate the bug exists
  - **Scoped PBT Approach**: Scope the property to concrete failing cases: 日线数据解析后时间戳应为 00:00:00 UTC
  - Test `_parse_datetime("2024-01-15")` returns datetime with `hour=0, minute=0, second=0, tzinfo=timezone.utc`
  - Test `_parse_trade_date(20240115)` returns datetime with `hour=0, minute=0, second=0, tzinfo=timezone.utc`
  - Run test on UNFIXED code
  - **EXPECTED OUTCOME**: Test FAILS (naive datetime without timezone info)
  - Document counterexamples found to understand root cause
  - Mark task complete when test is written, run, and failure is documented
  - _Requirements: 2.1, 2.4_

- [x] 2. Write preservation property tests (BEFORE implementing fix)
  - **Property 2: Preservation** - 分钟级数据时间戳保持不变
  - **IMPORTANT**: Follow observation-first methodology
  - Observe: `_parse_datetime("2024-01-15 09:30:00")` returns `datetime(2024, 1, 15, 9, 30, 0)` on unfixed code
  - Write property-based test: for all minute-level time strings, parsed time components (hour, minute) are preserved
  - Verify test passes on UNFIXED code
  - **EXPECTED OUTCOME**: Tests PASS (this confirms baseline behavior to preserve)
  - Mark task complete when tests are written, run, and passing on unfixed code
  - _Requirements: 3.3_

## Phase 2: Data Cleanup

- [x] 3. Create data cleanup script
  - Create `scripts/cleanup_duplicate_kline.py`
  - Implement `find_duplicates()` function to query all `time.hour = 16` daily K-line records
  - Implement `cleanup_duplicates()` function with dry-run and execute modes
  - Use batch processing (10,000 records per batch) to avoid memory issues
  - Add progress logging and summary report
  - _Bug_Condition: isBugCondition(record) where record.time.hour = 16 AND record.freq = '1d'_
  - _Expected_Behavior: Delete 16:00:00 UTC records when 00:00:00 UTC exists, otherwise update timestamp_
  - _Requirements: 2.2_

- [x] 4. Test cleanup script in dry-run mode
  - Run `python scripts/cleanup_duplicate_kline.py --dry-run`
  - Verify the script correctly identifies duplicate records
  - Review the summary report for accuracy
  - Confirm no actual data is modified
  - _Requirements: 2.2_

- [x] 5. Execute data cleanup
  - Run `python scripts/cleanup_duplicate_kline.py --execute`
  - Monitor progress and verify completion
  - Verify cleanup results match dry-run preview
  - _Requirements: 2.2_

## Phase 3: Code Fix Implementation

- [ ] 6. Fix for K-line timezone handling

  - [x] 6.1 Fix `_parse_datetime` in `local_kline_import.py`
    - Add `from datetime import timezone` import
    - Modify function to return `dt.replace(tzinfo=timezone.utc)` for all parsed datetime objects
    - Ensure daily data (date-only formats) returns `00:00:00 UTC` timestamp
    - Ensure minute-level data preserves time components with UTC timezone
    - _Bug_Condition: isBugCondition(input) where naive datetime is created_
    - _Expected_Behavior: expectedBehavior(result) returns datetime with tzinfo=timezone.utc_
    - _Preservation: Minute-level time components unchanged_
    - _Requirements: 2.1, 2.3, 2.4_

  - [ ] 6.2 Fix `_parse_trade_date` in `tushare_adapter.py`
    - Add `from datetime import timezone` import
    - Modify function to return `dt.replace(tzinfo=timezone.utc)` for parsed dates
    - Update fallback `datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)`
    - _Bug_Condition: isBugCondition(input) where naive datetime is created_
    - _Expected_Behavior: expectedBehavior(result) returns datetime with tzinfo=timezone.utc, time=00:00:00_
    - _Requirements: 2.1, 2.4_

  - [x] 6.3 Fix `_parse_kline_response` in `market_adapter.py`
    - Add `from datetime import timezone` import
    - Replace `datetime.utcfromtimestamp(ts)` with `datetime.fromtimestamp(ts, tz=timezone.utc)`
    - Add timezone handling for ISO string parsing: `bar_time.replace(tzinfo=timezone.utc)` if naive
    - _Bug_Condition: isBugCondition(input) where naive datetime is created from timestamp_
    - _Expected_Behavior: expectedBehavior(result) returns datetime with tzinfo=timezone.utc_
    - _Requirements: 2.1_

  - [x] 6.4 Verify bug condition exploration test now passes
    - **Property 1: Expected Behavior** - 日线数据时间戳标准化
    - **IMPORTANT**: Re-run the SAME test from task 1 - do NOT write a new test
    - The test from task 1 encodes the expected behavior
    - When this test passes, it confirms the expected behavior is satisfied
    - Run bug condition exploration test from step 1
    - **EXPECTED OUTCOME**: Test PASSES (confirms bug is fixed)
    - _Requirements: 2.1, 2.4_

  - [x] 6.5 Verify preservation tests still pass
    - **Property 2: Preservation** - 分钟级数据时间戳保持不变
    - **IMPORTANT**: Re-run the SAME tests from task 2 - do NOT write new tests
    - Run preservation property tests from step 2
    - **EXPECTED OUTCOME**: Tests PASS (confirms no regressions)
    - Confirm all tests still pass after fix (no regressions)

## Phase 4: Integration Tests

- [x] 7. Write integration tests for K-line import
  - Test local CSV import with daily data, verify `00:00:00 UTC` timestamp in database
  - Test local CSV import with minute-level data, verify time components preserved
  - Test Tushare API import with daily data, verify `00:00:00 UTC` timestamp in database
  - Test query API returns no duplicate records for the same trading day
  - _Requirements: 2.1, 3.1, 3.2, 3.3_

- [x] 8. Run full test suite
  - Run `pytest tests/` to ensure no regressions
  - Run `pytest tests/properties/` for property-based tests
  - Verify all tests pass
  - _Requirements: 3.1, 3.2, 3.3, 3.4_

## Phase 5: Checkpoint

- [x] 9. Checkpoint - Ensure all tests pass
  - Ensure all unit tests pass
  - Ensure all property-based tests pass
  - Ensure all integration tests pass
  - Verify frontend K-line chart displays correctly without duplicates
  - Ask the user if questions arise
