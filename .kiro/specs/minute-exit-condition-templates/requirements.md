# 需求文档：分钟级平仓条件模版

## 简介

在策略回测功能中，新增 10 个基于常用技术指标的分钟级（minute-frequency）系统内置平仓条件模版。这些模版作为预定义的 `ExitConditionConfig` 对象，供用户在配置自定义平仓条件时快速选择，覆盖 RSI、MACD、布林带、均线、DMA 等常用指标在分钟K线频率下的典型平仓策略。

系统已有 5 个日K线频率的系统内置模版（RSI 超买平仓、MACD 死叉平仓、布林带上轨突破回落、均线空头排列、量价背离）。本次新增的 10 个模版专注于分钟级频率（1min、5min、15min、30min、60min），利用已修复的分钟级指标索引对齐功能，为用户提供更精细的日内平仓信号。

## 术语表

- **System（系统）**: 策略回测平台的后端服务
- **Template_Registry（模版注册表）**: 系统内置平仓条件模版的数据存储，使用 `exit_condition_template` 表中 `is_system=TRUE` 的记录
- **Exit_Condition_Config（平仓条件配置）**: `ExitConditionConfig` dataclass，包含条件列表和逻辑运算符
- **Template_API（模版API）**: `GET /api/v1/backtest/exit-templates` 端点，返回系统模版和用户模版列表
- **Minute_Frequency（分钟频率）**: 分钟级K线数据频率，包括 1min、5min、15min、30min、60min
- **Seed_Migration（种子迁移）**: Alembic 数据迁移脚本，用于向数据库插入系统内置模版数据
- **Frontend_Template_Selector（前端模版选择器）**: `BacktestView.vue` 中的模版选择下拉框组件

## 需求

### 需求 1：分钟级模版数据定义

**用户故事：** 作为量化交易用户，我希望系统提供 10 个基于常用技术指标的分钟级平仓条件模版，以便我能快速选择适合日内交易的平仓策略。

#### 验收标准

1. THE Template_Registry SHALL contain exactly 10 minute-frequency system exit condition templates, each with `is_system=TRUE`
2. WHEN a minute-frequency template is retrieved, THE System SHALL return an `ExitConditionConfig` where every condition's `freq` field is one of: `1min`, `5min`, `15min`, `30min`, `60min`
3. THE Template_Registry SHALL include templates covering at least 5 distinct indicator types from the supported set: `ma`, `macd_dif`, `macd_dea`, `macd_histogram`, `boll_upper`, `boll_middle`, `boll_lower`, `rsi`, `dma`, `ama`, `close`, `volume`, `turnover`
4. THE Template_Registry SHALL include templates using at least 3 distinct minute frequencies from: `1min`, `5min`, `15min`, `30min`, `60min`
5. THE Template_Registry SHALL include templates demonstrating at least 3 distinct operator types from: `>`, `<`, `>=`, `<=`, `cross_up`, `cross_down`
6. WHEN a minute-frequency template contains multiple conditions, THE Exit_Condition_Config SHALL specify a `logic` field of either `AND` or `OR`
7. THE System SHALL assign each minute-frequency template a unique, descriptive Chinese name (≤ 100 characters) and a Chinese description (≤ 500 characters) explaining the strategy logic and applicable scenarios

### 需求 2：模版数据持久化

**用户故事：** 作为系统管理员，我希望分钟级模版通过数据库迁移自动部署，以便新环境和现有环境都能获得这些模版。

#### 验收标准

1. THE Seed_Migration SHALL insert 10 minute-frequency templates into the `exit_condition_template` table with `is_system=TRUE`
2. THE Seed_Migration SHALL use the fixed system user UUID `00000000-0000-0000-0000-000000000000` as `user_id` for all minute-frequency templates
3. THE Seed_Migration SHALL use `ON CONFLICT DO NOTHING` to ensure idempotent execution
4. THE Seed_Migration SHALL set `downgrade()` to delete only the 10 newly inserted minute-frequency templates without affecting existing system templates
5. WHEN the Seed_Migration is executed on a database with existing system templates, THE System SHALL preserve all 5 existing daily-frequency system templates unchanged

### 需求 3：模版与现有系统集成

**用户故事：** 作为量化交易用户，我希望新增的分钟级模版与现有模版管理功能无缝集成，以便我能在同一界面中浏览和使用所有模版。

#### 验收标准

1. WHEN the Template_API returns the template list, THE System SHALL include all 10 minute-frequency templates alongside existing daily-frequency templates
2. WHEN the Template_API returns the template list, THE System SHALL sort system templates before user templates, with `is_system DESC, updated_at DESC` ordering
3. WHEN a user selects a minute-frequency template from the Frontend_Template_Selector, THE System SHALL load the template's `ExitConditionConfig` into the exit condition configuration panel
4. THE System SHALL prevent modification and deletion of minute-frequency system templates through the API, returning HTTP 403 with appropriate error messages
5. WHEN a user loads a minute-frequency template, THE Frontend_Template_Selector SHALL allow the user to modify the loaded conditions and save as a new user-defined template

### 需求 4：模版数据完整性

**用户故事：** 作为开发者，我希望每个分钟级模版的数据结构都符合 `ExitConditionConfig` 的序列化规范，以便模版能被正确反序列化和评估。

#### 验收标准

1. FOR ALL minute-frequency templates, parsing the stored `exit_conditions` JSONB via `ExitConditionConfig.from_dict()` then serializing via `to_dict()` SHALL produce an equivalent object (round-trip property)
2. FOR ALL minute-frequency templates, every condition's `indicator` field SHALL be a member of the `VALID_INDICATORS` set
3. FOR ALL minute-frequency templates, every condition's `operator` field SHALL be a member of the `VALID_OPERATORS` set
4. FOR ALL minute-frequency templates using `cross_up` or `cross_down` operators, the condition SHALL include a non-null `cross_target` field with a valid indicator name
5. FOR ALL minute-frequency templates using the `ma` indicator, the condition's `params` SHALL include a `period` key with a positive integer value

### 需求 5：前端模版展示区分

**用户故事：** 作为量化交易用户，我希望在模版选择界面中能清晰区分日K线模版和分钟级模版，以便我能快速找到适合的模版类型。

#### 验收标准

1. WHEN the Frontend_Template_Selector displays minute-frequency system templates, THE System SHALL show a frequency tag (e.g., `[5分钟]`, `[15分钟]`) alongside the `[系统]` label to indicate the template's data frequency
2. WHEN the Frontend_Template_Selector groups templates, THE System SHALL display daily-frequency system templates and minute-frequency system templates in the same system template section, sorted by `updated_at DESC`
3. WHEN a user hovers over or selects a minute-frequency template, THE Frontend_Template_Selector SHALL display the template's Chinese description as a tooltip or inline text

