# Implementation Plan: 分钟级平仓条件模版

## Overview

新增 10 个分钟级系统内置平仓条件模版，通过 Alembic 种子迁移部署到 `exit_condition_template` 表，并在前端模版选择器中增加频率标签和 tooltip 描述显示。实现分为数据迁移、前端展示增强、属性测试三个阶段，每阶段结束设置检查点。

## Tasks

- [x] 1. Create Alembic seed migration for 10 minute-frequency templates
  - [x] 1.1 Create `alembic/versions/008_seed_minute_exit_templates.py` with 10 minute-frequency template definitions
    - Follow the pattern established in `007_seed_system_exit_templates.py`
    - Define `MINUTE_TEMPLATES` list with all 10 templates from the design document (5分钟RSI超买平仓, 15分钟MACD死叉平仓, 1分钟价格跌破布林中轨, 30分钟均线空头排列, 60分钟DMA死叉平仓, 5分钟布林上轨突破回落, 15分钟RSI超卖反弹失败, 1分钟放量下跌, 30分钟MACD柱状体缩短, 60分钟价格跌破MA20)
    - Each template must have: Chinese `name` (≤100 chars), Chinese `description` (≤500 chars), valid `exit_conditions` JSON matching `ExitConditionConfig` schema
    - Set `revision = "008"`, `down_revision = "007"`
    - Use `SYSTEM_USER_ID = "00000000-0000-0000-0000-000000000000"` and `is_system=TRUE`
    - `upgrade()`: INSERT with `ON CONFLICT DO NOTHING` for idempotent execution
    - `downgrade()`: DELETE only the 10 newly inserted templates by exact name match (not all `is_system=TRUE` rows), preserving existing 5 daily templates
    - Ensure coverage: ≥5 distinct indicator types, ≥3 distinct minute frequencies, ≥3 distinct operator types
    - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5, 1.6, 1.7, 2.1, 2.2, 2.3, 2.4, 2.5_

  - [x] 1.2 Write property tests for template data integrity
    - Create `tests/properties/test_exit_condition_templates.py`
    - **Property 1: ExitConditionConfig round-trip** — Generate random `ExitConditionConfig` with minute-frequency conditions using Hypothesis, verify `ExitConditionConfig.from_dict(config.to_dict()).to_dict() == config.to_dict()`
    - **Validates: Requirements 4.1**

  - [x] 1.3 Write property test for ExitCondition structure validity
    - In `tests/properties/test_exit_condition_templates.py`
    - **Property 2: ExitCondition structure validity** — Generate random `ExitCondition` with minute frequencies, verify: `indicator` ∈ `VALID_INDICATORS`, `operator` ∈ `VALID_OPERATORS`, cross operators have valid `cross_target`, `ma` indicator has `period` param
    - **Validates: Requirements 1.2, 1.6, 4.2, 4.3, 4.4, 4.5**

  - [x] 1.4 Write example-based tests for template metadata and coverage
    - In `tests/properties/test_exit_condition_templates.py`
    - **Property 3: Template metadata validity** — Verify all 10 seed templates: names non-empty and ≤100 chars, descriptions ≤500 chars, names unique
    - Verify template coverage: ≥5 indicator types, ≥3 frequencies, ≥3 operator types
    - Verify each template parses via `ExitConditionConfig.from_dict()` without error
    - **Validates: Requirements 1.1, 1.3, 1.4, 1.5, 1.7**

- [x] 2. Checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [x] 3. Add frontend frequency label helper and template display enhancements
  - [x] 3.1 Add `getTemplateFreqLabel()` helper function in `frontend/src/stores/backtest.ts`
    - Export a function that extracts the primary minute frequency from an `ExitTemplate`'s conditions
    - Use `FREQ_LABEL_MAP` to map freq values to Chinese labels (`1min` → `1分钟`, `5min` → `5分钟`, etc.)
    - Return `null` for daily-only templates, the Chinese label for single-frequency templates, `多频率` for multi-frequency templates
    - _Requirements: 5.1_

  - [x] 3.2 Update `BacktestView.vue` template selector to show frequency tags and tooltip
    - Modify the system template `<option>` rendering to show `[系统·{频率}]` prefix using `getTemplateFreqLabel()`
    - Daily-frequency templates continue to show `[系统]` without frequency tag
    - Add `:title="tpl.description || ''"` attribute to system template options for tooltip on hover
    - _Requirements: 5.1, 5.2, 5.3_

  - [x] 3.3 Write frontend unit tests for frequency label display
    - Update `frontend/src/views/__tests__/BacktestView.test.ts` with tests for:
      - Minute-frequency system templates show frequency tag (e.g., `[系统·5分钟]`)
      - Daily-frequency system templates show `[系统]` without frequency tag
      - Template description appears as tooltip (`title` attribute)
    - _Requirements: 5.1, 5.3_

  - [x] 3.4 Write frontend property test for `getTemplateFreqLabel()`
    - Create `frontend/src/views/__tests__/BacktestView.property.test.ts`
    - Use fast-check to generate random `ExitTemplate` objects, verify `getTemplateFreqLabel()` returns correct label based on condition frequencies
    - _Requirements: 5.1_

- [x] 4. Final checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- Each task references specific requirements for traceability
- Checkpoints ensure incremental validation
- Property tests validate universal correctness properties from the design document
- Unit tests validate specific examples and edge cases
- No backend API or ORM model changes are needed — the existing `GET /api/v1/backtest/exit-templates` endpoint automatically returns the new templates
- The design uses Python (backend) and TypeScript (frontend), so no language selection was needed
