# 实现计划：行业概念板块数据导入（重构版 v2）

## 概述

将现有的单一 `SectorCSVParser` 重构为三个独立解析引擎（`BaseParsingEngine` + `DCParsingEngine` + `TIParsingEngine` + `TDXParsingEngine`），并重写 `SectorImportService` 的文件扫描和导入编排逻辑以匹配按数据源重新组织的目录结构。所有代码变更集中在 `app/services/data_engine/sector_csv_parser.py` 和 `app/services/data_engine/sector_import.py` 两个文件，现有 ORM 模型、API 端点、Celery 任务、数据库迁移均保持不变。

## 任务列表

- [x] 1. 实现 BaseParsingEngine 基类和共享数据结构
  - [x] 1.1 在 `app/services/data_engine/sector_csv_parser.py` 中重构：保留现有 dataclass（ParsedSectorInfo、ParsedConstituent、ParsedSectorKline）和辅助函数（`_normalize_symbol`、`_DATE_RE`、`_DATE_DASH_RE`），删除 `SectorCSVParser` 类，新增 `BaseParsingEngine` 基类
    - 实现 `_read_csv(file_path: Path) -> str`：自动检测编码（UTF-8 → GBK → GB2312），去除 BOM
    - 实现 `iter_zip_entries(zip_path: Path) -> Iterator[tuple[str, str]]`：逐个读取 ZIP 内文件，yield (文件名, CSV文本)
    - 实现 `_validate_ohlc(kline: ParsedSectorKline) -> bool`：验证 OHLC 保序性
    - 实现 `_infer_date_from_filename(filename: str) -> date | None`：从文件名推断日期
    - 实现 `_parse_date(raw_date: str) -> date | None`：解析日期字符串
    - 实现 `_safe_decimal(raw: str) -> Decimal | None` 和 `_safe_int(raw: str) -> int | None`
    - 这些方法大部分可从现有 `SectorCSVParser` 中迁移，确保接口签名与设计文档一致
    - _需求: 8.1, 8.2, 8.3, 8.4, 8.5, 8.6_

  - [x] 1.2 更新属性测试 P1（枚举验证）确认仍通过
    - **Property 1: Enum validation rejects invalid values**
    - **验证: 需求 1.4, 1.5**

  - [x] 1.3 更新属性测试 P5（编码检测）使用 BaseParsingEngine 替代 SectorCSVParser
    - **Property 5: Encoding detection preserves content**
    - **验证: 需求 8.1**

  - [x] 1.4 更新属性测试 P6（OHLC 验证）使用 BaseParsingEngine 替代 SectorCSVParser
    - **Property 6: OHLC validation invariant**
    - **验证: 需求 8.2**

  - [x] 1.5 更新属性测试 P7（日期推断）使用 BaseParsingEngine 替代 SectorCSVParser
    - **Property 7: Date inference round-trip from filename**
    - **验证: 需求 8.3**

- [x] 2. 实现 DCParsingEngine（东方财富解析引擎）
  - [x] 2.1 在 `app/services/data_engine/sector_csv_parser.py` 中新增 `DCParsingEngine(BaseParsingEngine)` 类
    - 实现 `parse_sector_list(file_path: Path) -> list[ParsedSectorInfo]`：解析 DC 板块列表 CSV（13列含 idx_type，少于13列默认 CONCEPT），按 sector_code 去重
    - 实现 `_map_sector_type(idx_type: str) -> SectorType`：idx_type 包含匹配（行业/地区/地域/风格/概念）
    - 实现 `parse_kline_csv(file_path: Path) -> list[ParsedSectorKline]`：解析散装/增量行情 CSV，自动检测两种列头格式：格式 A（地区板块/增量: 板块代码,交易日期,收盘点位,开盘点位,...，收盘在开盘前）和格式 B（行业板块: 日期,行业代码,开盘,收盘,...，标准 OHLC 顺序）
    - 实现 `parse_constituents_zip(zip_path: Path) -> list[ParsedConstituent]`：解析板块成分 ZIP
    - 实现 `iter_constituents_zip(zip_path: Path) -> Iterator[list[ParsedConstituent]]`：流式解析成分 ZIP
    - _需求: 5.1, 5.2, 5.3, 5.4, 5.5, 5.6, 5.7, 5.8_

  - [x] 2.2 更新属性测试 P2（板块列表解析往返）DC 部分，使用 DCParsingEngine 替代 SectorCSVParser
    - **Property 2: Sector list CSV parsing round-trip (DC)**
    - **验证: 需求 5.2, 5.3**

  - [x] 2.3 更新属性测试 P3（成分数据解析往返）DC 部分，使用 DCParsingEngine 替代 SectorCSVParser
    - **Property 3: Constituent data parsing round-trip (DC)**
    - **验证: 需求 5.6**

  - [x] 2.4 更新属性测试 P4（行情解析往返）DC 部分，使用 DCParsingEngine 替代 SectorCSVParser
    - **Property 4: Kline CSV parsing round-trip (DC)**
    - **验证: 需求 5.5**

  - [x] 2.5 更新 `tests/services/data_engine/test_sector_csv_parser.py` 中 DC 相关单元测试
    - 将 TestParseSectorListDC、TestParseConstituentsDCZip、TestParseKlineDC 中的 `SectorCSVParser` 替换为 `DCParsingEngine`
    - 更新方法调用名称（`parse_sector_list_dc` → `parse_sector_list` 等）
    - _需求: 5.2, 5.3, 5.4, 5.5, 5.6_

- [x] 3. 实现 TIParsingEngine（同花顺解析引擎）
  - [x] 3.1 在 `app/services/data_engine/sector_csv_parser.py` 中新增 `TIParsingEngine(BaseParsingEngine)` 类
    - 实现 `parse_sector_list(file_path: Path) -> list[ParsedSectorInfo]`：解析 TI 板块列表 CSV（6列：代码,名称,成分个数,交易所,上市日期,指数类型）
    - 实现 `_map_sector_type(index_type: str) -> SectorType`：指数类型映射
    - 实现 `parse_kline_csv(file_path: Path) -> list[ParsedSectorKline]`：解析散装/增量行情 CSV（12列，标准 OHLC 顺序）
    - 实现 `parse_constituents_summary(file_path: Path, trade_date: date | None = None) -> list[ParsedConstituent]`：解析5列成分汇总 CSV
    - 实现 `parse_constituents_per_sector(file_path: Path, trade_date: date | None = None) -> list[ParsedConstituent]`：解析3列散装成分 CSV
    - _需求: 6.1, 6.2, 6.3, 6.4, 6.5, 6.6, 6.7_

  - [x] 3.2 更新属性测试 P2（板块列表解析往返）TI 部分，使用 TIParsingEngine
    - **Property 2: Sector list CSV parsing round-trip (TI)**
    - **验证: 需求 6.2**

  - [x] 3.3 更新属性测试 P3（成分数据解析往返）TI 部分，使用 TIParsingEngine
    - **Property 3: Constituent data parsing round-trip (TI)**
    - **验证: 需求 6.4, 6.5**

  - [x] 3.4 更新属性测试 P4（行情解析往返）TI 部分，使用 TIParsingEngine
    - **Property 4: Kline CSV parsing round-trip (TI)**
    - **验证: 需求 6.3**

  - [x] 3.5 更新 `tests/services/data_engine/test_sector_csv_parser.py` 中 TI 相关单元测试
    - 将 TestParseSectorListTI、TestParseConstituentsTICSV、TestParseKlineTI 中的 `SectorCSVParser` 替换为 `TIParsingEngine`
    - 更新方法调用名称（`parse_sector_list_ti` → `parse_sector_list` 等）
    - _需求: 6.2, 6.3, 6.4, 6.5_

- [x] 4. 检查点 - 确保 DC 和 TI 解析引擎测试通过
  - 确保所有测试通过，如有问题请向用户确认。

- [x] 5. 实现 TDXParsingEngine（通达信解析引擎）
  - [x] 5.1 在 `app/services/data_engine/sector_csv_parser.py` 中新增 `TDXParsingEngine(BaseParsingEngine)` 类
    - 实现 `parse_sector_list(file_path: Path) -> list[ParsedSectorInfo]`：解析 TDX 板块列表 CSV（9列），按 sector_code 去重
    - 实现 `_map_sector_type(raw_type: str) -> SectorType`：板块类型映射
    - 实现 `parse_kline_csv(file_path: Path) -> list[ParsedSectorKline]`：解析散装/增量行情 CSV（格式 B，38列，收盘在开盘前）
    - 实现 `parse_kline_zip(zip_path: Path) -> list[ParsedSectorKline]`：解析历史行情 ZIP（格式 A）
    - 实现 `iter_kline_zip(zip_path: Path) -> Iterator[list[ParsedSectorKline]]`：流式解析历史行情 ZIP
    - 实现 `_infer_freq_from_filename(filename: str) -> str`：从 ZIP 文件名推断频率（日k→1d、周k→1w、月k→1M）
    - 实现双格式自动检测：格式 A（历史 ZIP 内: 日期,代码,名称,开盘,收盘,...）和格式 B（散装/增量: 板块代码,交易日期,收盘点位,开盘点位,...）
    - 实现 `parse_constituents_zip(zip_path: Path) -> list[ParsedConstituent]`：解析板块成分 ZIP
    - _需求: 7.1, 7.2, 7.3, 7.4, 7.5, 7.6, 7.7, 7.8, 7.9, 7.10_

  - [x] 5.2 更新属性测试 P2（板块列表解析往返）TDX 部分，使用 TDXParsingEngine
    - **Property 2: Sector list CSV parsing round-trip (TDX)**
    - **验证: 需求 7.2**

  - [x] 5.3 更新属性测试 P3（成分数据解析往返）TDX 部分，使用 TDXParsingEngine
    - **Property 3: Constituent data parsing round-trip (TDX)**
    - **验证: 需求 7.9**

  - [x] 5.4 更新属性测试 P4（行情解析往返）TDX 部分，使用 TDXParsingEngine（覆盖格式 A 和格式 B）
    - **Property 4: Kline CSV parsing round-trip (TDX)**
    - **验证: 需求 7.4, 7.5, 7.6**

  - [x] 5.5 新增属性测试 P8（频率推断）使用 TDXParsingEngine
    - **Property 8: Frequency inference from ZIP filename**
    - **验证: 需求 7.7**

  - [x] 5.6 新增属性测试 P9（流式 ZIP 等价性）使用 TDXParsingEngine
    - **Property 9: Streaming ZIP produces identical results**
    - **验证: 需求 7.8, 8.4, 11.2**

  - [x] 5.7 更新 `tests/services/data_engine/test_sector_csv_parser.py` 中 TDX 相关单元测试
    - 将 TestParseSectorListTDX、TestParseConstituentsTDXZip、TestParseKlineTDX 中的 `SectorCSVParser` 替换为 `TDXParsingEngine`
    - 更新方法调用名称，新增 TDX 格式 B（38列散装行情）和双格式自动检测的测试用例
    - _需求: 7.2, 7.4, 7.5, 7.6, 7.9_

  - [x] 5.8 新增属性测试 P10（畸形行跳过）覆盖三个引擎
    - **Property 10: Malformed CSV rows are skipped without affecting valid rows**
    - **验证: 需求 8.6**

- [x] 6. 检查点 - 确保所有解析引擎测试通过
  - 确保所有测试通过，如有问题请向用户确认。

- [x] 7. 重写 SectorImportService 文件扫描逻辑
  - [x] 7.1 在 `app/services/data_engine/sector_import.py` 中重写 `SectorImportService.__init__` 和文件扫描方法
    - 将 `self.parser = SectorCSVParser()` 替换为 `self.dc_engine = DCParsingEngine()`、`self.ti_engine = TIParsingEngine()`、`self.tdx_engine = TDXParsingEngine()`
    - 更新 import 语句：从 `sector_csv_parser` 导入三个引擎类替代 `SectorCSVParser`
    - 重写 `_scan_sector_list_files(source: DataSource) -> list[Path]`：
      - DC: `东方财富/东方财富_板块列表.csv` + `东方财富_概念板块/概念板块列表.csv` + `东方财富_行业板块/行业板块列表.csv` + 增量 `东方财富_增量数据/东方财富_概念板块/YYYY-MM/*.csv`
      - TI: `同花顺/同花顺_板块列表.csv`
      - TDX: `通达信/通达信_板块列表.csv` + `通达信_板块信息汇总/*.csv` + 增量 `通达信_增量数据/通达信_板块信息/YYYY-MM/*.csv`
    - 重写 `_scan_kline_files(source: DataSource) -> list[Path]`：
      - DC: 三个散装 CSV 目录（`东方财富_概念板块/概念板块行情/*.csv`、`东方财富_行业板块/行业板块行情/*.csv`、`东方财富_地区板块/地区板块行情/*.csv`）+ 增量 `东方财富_增量数据/东方财富_板块行情/YYYY-MM/*.csv`
      - TI: `同花顺_板块指数行情/*.csv` + 增量 `增量数据/同花顺_板块指数行情/YYYY-MM/*.csv`
      - TDX: `通达信_板块行情汇总/*.csv` + 四个历史行情 ZIP 目录 + 增量 `通达信_增量数据/通达信_板块行情/YYYY-MM/*.csv`
    - 重写 `_scan_constituent_files(source: DataSource) -> list[Path]`：
      - DC: `东方财富_板块成分/YYYY-MM/*.zip`
      - TI: 概念/行业板块成分汇总 CSV + 散装成分 CSV + 增量成分 CSV
      - TDX: `通达信_板块成分汇总/YYYY-MM/*.zip`
    - 数据源子目录不存在时记录警告并跳过，功能子目录不存在时返回空列表
    - _需求: 4.1, 4.2, 4.3, 4.4, 4.5, 4.6, 4.7, 4.8, 4.9, 4.10, 4.11, 4.12, 4.13, 4.14, 4.15_

  - [x] 7.2 更新 `tests/services/test_sector_import.py` 中 TestFileScanning 测试类
    - 重写 `_build_dir_structure(base)` 辅助函数以匹配新目录结构（`东方财富/`、`同花顺/`、`通达信/` 子目录）
    - 更新所有文件扫描测试的预期文件数量和路径
    - 新增散装 CSV 目录扫描测试（验证 `*.csv` 文件被正确发现）
    - 新增缺失数据源子目录的优雅降级测试
    - _需求: 4.1, 4.14, 4.15_

- [x] 8. 重写 SectorImportService 导入编排逻辑
  - [x] 8.1 在 `app/services/data_engine/sector_import.py` 中重写导入方法，使用新引擎类
    - 重写 `_import_sector_list(data_sources)`：根据数据源选择对应引擎调用 `parse_sector_list()`
    - 重写 `_import_constituents(data_sources)`：
      - DC: 调用 `dc_engine.iter_constituents_zip()` 流式处理
      - TI: 区分汇总 CSV（`parse_constituents_summary`）和散装 CSV（`parse_constituents_per_sector`），逐文件处理散装目录
      - TDX: 调用 `tdx_engine.parse_constituents_zip()`
    - 重写 `_import_klines(data_sources)`：
      - DC/TI 散装 CSV 目录：逐文件调用 `parse_kline_csv()`，每个文件处理完后写入数据库并释放内存
      - TDX 散装 CSV：同上逐文件处理
      - TDX 历史行情 ZIP：调用 `tdx_engine.iter_kline_zip()` 流式处理
      - 增量 CSV：使用对应引擎的 `parse_kline_csv()`
    - 新增 `_import_klines_from_dir(engine, csv_dir, source)` 方法：逐文件处理散装 CSV 目录
    - 保持现有 `_bulk_upsert_sector_info`、`_bulk_insert_constituents`、`_bulk_insert_klines` 不变
    - 保持现有进度追踪和停止信号逻辑不变
    - 每个文件处理之间检查停止信号并更新进度
    - _需求: 9.1, 9.2, 9.3, 9.4, 9.5, 9.6, 9.7, 11.1, 11.2, 11.3, 11.4_

  - [x] 8.2 更新 `tests/services/test_sector_import.py` 中错误处理和增量导入测试
    - 更新 TestErrorHandling 测试类中的 mock 对象（`svc.parser.xxx` → `svc.dc_engine.xxx` / `svc.ti_engine.xxx` / `svc.tdx_engine.xxx`）
    - 更新增量导入跳过已导入文件的测试
    - 新增散装 CSV 目录逐文件处理的测试（验证每个文件独立处理、失败文件被跳过）
    - _需求: 9.5, 9.6, 10.1, 10.2, 11.1_

- [x] 9. 检查点 - 确保文件扫描和导入编排测试通过
  - 确保所有测试通过，如有问题请向用户确认。

- [x] 10. 更新剩余属性测试
  - [x] 10.1 更新属性测试 P11（SectorInfo UPSERT 幂等性）确认仍通过
    - **Property 11: SectorInfo UPSERT idempotence**
    - **验证: 需求 1.2, 9.2**

  - [x] 10.2 更新属性测试 P12（成分和行情 INSERT 幂等性）确认仍通过
    - **Property 12: Insert idempotence for constituents and klines**
    - **验证: 需求 2.2, 3.2, 9.3**

  - [x] 10.3 更新属性测试 P13（增量检测正确性）确认仍通过
    - **Property 13: Incremental detection correctness**
    - **验证: 需求 10.1, 10.2**

- [x] 11. 最终检查点 - 确保所有测试通过
  - 确保所有测试通过，如有问题请向用户确认。

- [x] 12. 实现导入错误统计与记录
  - [x] 12.1 在 `app/services/data_engine/sector_import.py` 中新增错误统计功能
    - 新增 `REDIS_ERRORS_KEY = "sector_import:errors"` 常量
    - 新增 `_record_error(file, line, error_type, message, raw_data)` 方法：将错误详情 JSON 追加到 Redis 列表，递增进度中的 `error_count`
    - 新增 `_clear_errors()` 方法：清空错误列表（在 `import_full` / `import_incremental` 开始时调用）
    - 新增 `get_errors(offset, limit)` 方法：从 Redis 列表分页读取错误详情
    - 新增 `get_error_count()` 方法：返回错误总数
    - 在 `_import_sector_list`、`_import_constituents`、`_import_klines` 的 except 块中调用 `_record_error`
    - 在 `_bulk_upsert_sector_info`、`_bulk_insert_constituents`、`_bulk_insert_klines` 的 except 块中调用 `_record_error`
    - 错误类型枚举：`parse_error`（解析失败）、`ohlc_invalid`（OHLC 验证失败）、`db_error`（数据库写入失败）
    - `raw_data` 字段截断至 200 字符
    - _需求: 17.1, 17.2, 17.3, 17.9, 17.10_

  - [x] 12.2 在 `app/api/v1/sector.py` 中新增错误查询和导出端点
    - 更新 `ImportStatusResponse` 模型：新增 `error_count: int = 0` 和 `failed_files: list[dict] = []` 字段
    - 新增 `GET /sector/import/errors` 端点：分页返回错误详情列表（query params: offset, limit）
    - 新增 `GET /sector/import/errors/export` 端点：以 CSV 格式导出全部错误详情（StreamingResponse，列: file, line, error_type, message, raw_data）
    - _需求: 17.4, 17.5, 17.6_

  - [x] 12.3 更新前端导入进度页面展示错误统计
    - 更新 `frontend/src/stores/localImport.ts` 中 `SectorImportProgress` 接口：新增 `error_count: number | null` 和 `failed_files: Array<{file: string, error: string}> | null`
    - 更新 `frontend/src/views/LocalImportView.vue` 板块导入进度区域：
      - 在"已导入记录数"卡片右侧新增"出错记录数"卡片，使用红色高亮（`class="stat-value error"`）
      - 当 `error_count > 0` 时显示"导出错误报告"按钮，点击调用 `/sector/import/errors/export` 下载 CSV
    - _需求: 17.7, 17.8_

  - [x] 12.4 新增错误统计相关单元测试
    - 在 `tests/services/test_sector_import.py` 中新增 `TestErrorTracking` 测试类
    - 测试 `_record_error` 正确写入 Redis 列表
    - 测试 `_clear_errors` 清空列表
    - 测试 `get_errors` 分页读取
    - 测试导入过程中解析失败时 `error_count` 递增
    - _需求: 17.1, 17.2, 17.3_

  - [x] 12.5 新增错误导出 API 测试
    - 在 `tests/api/test_sector_api.py` 中新增错误查询和 CSV 导出端点测试
    - _需求: 17.5, 17.6_

- [x] 13. 检查点 - 确保错误统计功能测试通过
  - 确保所有测试通过，如有问题请向用户确认。

- [x] 14. 修复 TDX 历史行情 ZIP 解析缺少 .TDX 后缀问题
  - [x] 14.1 修改 `TDXParsingEngine._parse_kline_text_format_a` 方法，追加 .TDX 后缀
    - 在 `app/services/data_engine/sector_csv_parser.py` 中修改 `_parse_kline_text_format_a` 方法
    - 在解析 `sector_code = row[1].strip()` 之后，检查是否已包含 `.TDX` 后缀
    - 若不包含则自动追加 `.TDX` 后缀：`if not sector_code.endswith(".TDX"): sector_code += ".TDX"`
    - 此修改同时影响 `parse_kline_zip` 和 `iter_kline_zip`（它们都调用 `_parse_kline_text_format_a`）
    - _需求: 18.1, 18.2_

  - [x] 14.2 编写 TDX 后缀修复属性测试 — Property 14: TDX sector_code 后缀不变量
    - **Property 14: TDX sector_code suffix invariant**
    - **验证: 需求 18.1, 18.2, 18.6**
    - 在 `tests/properties/test_sector_parser_fix_properties.py` 中创建测试
    - 使用 Hypothesis 生成随机 sector_code（带/不带 .TDX 后缀）
    - 构造格式 A 的 CSV 文本，调用 `_parse_kline_text_format_a` 解析
    - 验证所有输出的 sector_code 均以 `.TDX` 结尾
    - 验证幂等性：已带 `.TDX` 后缀的不会变成 `.TDX.TDX`
    - `@settings(max_examples=100)`

  - [x] 14.3 编写 TDX 后缀修复单元测试
    - 在 `tests/services/test_sector_parser_fix.py` 中创建测试
    - 测试不带后缀的 sector_code（如 `880201`）被追加为 `880201.TDX`
    - 测试已带后缀的 sector_code（如 `880201.TDX`）保持不变
    - 测试完整的 `parse_kline_zip` 流程（构造临时 ZIP 文件）
    - _需求: 18.1, 18.2_

- [x] 15. 修复 DC 简版板块列表解析错误
  - [x] 15.1 修改 `DCParsingEngine.parse_sector_list` 方法，增加简版格式检测
    - 在 `app/services/data_engine/sector_csv_parser.py` 中修改 `parse_sector_list` 方法
    - 读取列头后检测格式：列数 ≤ 2 或列头为 `名称,代码` 时识别为简版格式
    - 简版格式使用独立解析逻辑 `_parse_sector_list_simple`：第 1 列为 name，第 2 列为 sector_code
    - 对 sector_code 进行 BK 前缀校验：不以 `BK` 开头的行跳过并记录 WARNING 日志
    - 简版格式默认 sector_type 为 CONCEPT
    - 确保 sector_code 带 `.DC` 后缀
    - 标准格式（≥3 列）继续使用现有解析逻辑
    - _需求: 19.1, 19.2_

  - [x] 15.2 编写 DC 简版格式解析属性测试 — Property 15: DC 简版格式 BK 校验
    - **Property 15: DC simple format parsing with BK validation**
    - **验证: 需求 19.1, 19.2, 19.5**
    - 在 `tests/properties/test_sector_parser_fix_properties.py` 中添加测试
    - 使用 Hypothesis 生成随机 2 列 CSV 数据（混合 BK 开头和非 BK 开头的 sector_code）
    - 写入临时文件，调用 `parse_sector_list` 解析
    - 验证所有输出的 sector_code 以 `BK` 开头且以 `.DC` 结尾
    - 验证非 BK 开头的行被排除
    - `@settings(max_examples=100)`

  - [x] 15.3 编写 DC 简版格式解析单元测试
    - 在 `tests/services/test_sector_parser_fix.py` 中添加测试
    - 测试 2 列 CSV（`名称,代码`）被正确识别为简版格式
    - 测试 BK 开头的代码被正确解析（如 `BK0001` → `BK0001.DC`）
    - 测试非 BK 开头的代码被跳过（如日期格式 `2024-01-01`）
    - 测试标准 13 列 CSV 不受影响（仍按原逻辑解析）
    - _需求: 19.1, 19.2_

- [x] 16. 创建数据清理脚本
  - [x] 16.1 创建 `scripts/cleanup_sector_data.py` 清理脚本
    - 实现 `cleanup_tdx_kline_without_suffix()` 函数：删除 sector_kline 表中 data_source='TDX' 且 sector_code 不以 '.TDX' 结尾的记录
    - 实现 `cleanup_dc_info_garbage()` 函数：删除 sector_info 表中 data_source='DC' 且 sector_code 不以 'BK' 开头的记录
    - 每个函数输出删除的记录数量
    - 实现 `main()` 函数，依次调用两个清理函数并输出汇总报告
    - _需求: 18.3, 18.4, 19.3, 19.4_

- [x] 17. 检查点 - 确保数据修复测试通过
  - 运行 `tests/properties/test_sector_parser_fix_properties.py` 和 `tests/services/test_sector_parser_fix.py`
  - 确保所有解析修复测试通过，如有问题请向用户确认。

- [x] 18. 修复 DC 行业板块行情 sector_code 缺少 .DC 后缀问题
  - [x] 18.1 修改 `DCParsingEngine._parse_kline_text` 方法，对格式 B 解析追加 .DC 后缀
    - 在 `app/services/data_engine/sector_csv_parser.py` 中修改 `_parse_kline_text` 方法
    - 在格式 B 分支中，解析 `sector_code = row[1].strip()` 之后，检查是否已包含 `.DC` 后缀
    - 若不包含则自动追加 `.DC` 后缀：`if not sector_code.endswith(".DC"): sector_code += ".DC"`
    - 同时对格式 A 分支增加相同的防御性后缀检查（格式 A 的 sector_code 通常已带 `.DC` 后缀）
    - 此修改与需求 18（TDX 历史行情 ZIP 缺少 `.TDX` 后缀）的修复模式完全一致
    - _需求: 20.1, 20.2_

  - [x] 18.2 编写 DC 行情后缀修复属性测试 — Property 16: DC sector_code 行情后缀不变量
    - **Property 16: DC sector_code kline suffix invariant**
    - **验证: 需求 20.1, 20.2, 20.6**
    - 在 `tests/properties/test_sector_parser_fix_properties.py` 中添加测试
    - 使用 Hypothesis 生成随机 sector_code（带/不带 .DC 后缀）
    - 分别构造格式 A 和格式 B 的 CSV 文本，调用 `_parse_kline_text` 解析
    - 验证所有输出的 sector_code 均以 `.DC` 结尾
    - 验证幂等性：已带 `.DC` 后缀的不会变成 `.DC.DC`
    - `@settings(max_examples=100)`

  - [x] 18.3 编写 DC 行情后缀修复单元测试
    - 在 `tests/services/test_sector_parser_fix.py` 中添加 `TestDCKlineSuffixFix` 测试类
    - 测试格式 B（行业板块行情）不带后缀的 sector_code（如 `BK0420`）被追加为 `BK0420.DC`
    - 测试格式 B 已带后缀的 sector_code（如 `BK0420.DC`）保持不变
    - 测试格式 A（地区板块/增量行情）的 sector_code 后缀处理
    - 测试混合带/不带后缀的多行 CSV 均统一为 `.DC` 结尾
    - 测试后缀修复不影响其他字段（日期、OHLCV 等）的解析
    - _需求: 20.1, 20.2_

  - [x] 18.4 更新 `scripts/cleanup_sector_data.py` 清理脚本，新增 DC 行情清理
    - 新增 `cleanup_dc_kline_without_suffix()` 函数：删除 sector_kline 表中 data_source='DC' 且 sector_code 不以 '.DC' 结尾的记录
    - 输出删除的记录数量
    - 更新 `main()` 函数，将清理步骤从 2 步增加到 3 步（TDX kline → DC kline → DC info）
    - 更新汇总报告输出
    - _需求: 20.3, 20.4_

- [x] 19. 检查点 - 确保 DC 行情后缀修复测试通过
  - 运行 `tests/properties/test_sector_parser_fix_properties.py` 和 `tests/services/test_sector_parser_fix.py`
  - 确保所有解析修复测试通过（包括需求 18、19、20 的修复），如有问题请向用户确认。

## 备注

- 标记 `*` 的子任务为可选，可跳过以加速交付
- 每个任务引用了具体的需求编号以确保可追溯性
- 属性测试验证设计文档中定义的正确性属性（Property 1–13）
- 属性测试使用 Hypothesis（`tests/properties/test_sector_import_properties.py`）
- 数据修复属性测试（Property 14–16）使用 Hypothesis（`tests/properties/test_sector_parser_fix_properties.py`）
- 现有 ORM 模型（`app/models/sector.py`）、API 端点（`app/api/v1/sector.py`）、Celery 任务（`app/tasks/sector_sync.py`）、数据库迁移、查询仓储（`sector_repository.py`）均保持不变，不在任务范围内
- 核心代码变更集中在两个文件：`sector_csv_parser.py`（解析引擎）和 `sector_import.py`（导入服务）
- 数据清理脚本：`scripts/cleanup_sector_data.py`（需求 18.3-18.4、19.3-19.4、20.3-20.4）
