# Implementation Plan: 行业概念板块数据导入 (Sector Data Import)

## Overview

本实现计划将行业概念板块数据导入功能分解为增量编码步骤，从数据模型和枚举定义开始，逐步构建 CSV 解析器、导入服务、查询仓储、Celery 任务、API 端点，最后接入风控和选股模块。每个步骤都在前一步基础上构建，确保无孤立代码。所有新模块独立于现有 K 线导入模块，不修改现有文件。

## Tasks

- [x] 1. Define data models, enums, and database schema
  - [x] 1.1 Create `app/models/sector.py` with SectorInfo, SectorConstituent, SectorKline ORM models and enums
    - Define `DataSource` enum (DC, TI, TDX) and `SectorType` enum (CONCEPT, INDUSTRY, REGION, STYLE) as `str, Enum`
    - Implement `SectorInfo(PGBase)` with fields: id, sector_code, name, sector_type, data_source, list_date, constituent_count, updated_at
    - Add `UniqueConstraint("sector_code", "data_source")` and `Index("sector_type", "data_source")` to SectorInfo
    - Implement `SectorConstituent(PGBase)` with fields: id, trade_date, sector_code, data_source, symbol, stock_name
    - Add `UniqueConstraint("trade_date", "sector_code", "data_source", "symbol")` and indexes on (symbol, trade_date) and (sector_code, data_source, trade_date)
    - Implement `SectorKline(TSBase)` with composite primary key (time, sector_code, data_source, freq) and OHLCV + change_pct + turnover fields
    - Add unique index on (time, sector_code, data_source, freq) and query index on (sector_code, data_source, freq, time)
    - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5, 1.6, 2.1, 2.2, 2.3, 2.4, 2.5, 2.6, 3.1, 3.2, 3.3, 3.4, 3.5, 3.6, 11.5_

  - [x] 1.2 Create Alembic migration for sector_info, sector_constituent, and sector_kline tables
    - Generate migration with `alembic revision --autogenerate -m "add sector tables"`
    - Include TimescaleDB hypertable creation for sector_kline: `SELECT create_hypertable('sector_kline', 'time')`
    - _Requirements: 1.6, 2.4, 3.4_

  - [x] 1.3 Write property test for enum validation (Property 1)
    - **Property 1: Enum validation rejects invalid values**
    - For any string not in {CONCEPT, INDUSTRY, REGION, STYLE}, SectorType SHALL reject it; for any string not in {DC, TI, TDX}, DataSource SHALL reject it
    - Test file: `tests/properties/test_sector_import_properties.py`
    - **Validates: Requirements 1.4, 1.5, 3.5**

- [x] 2. Implement SectorCSVParser — sector list parsing
  - [x] 2.1 Create `app/services/data_engine/sector_csv_parser.py` with dataclasses and core utilities
    - Define `ParsedSectorInfo`, `ParsedConstituent`, `ParsedSectorKline` dataclasses
    - Implement `_read_csv(file_path)` with auto encoding detection (UTF-8 → GBK → GB2312)
    - Implement `_extract_zip(zip_path)` for in-memory ZIP extraction returning `[(filename, csv_text), ...]`
    - Implement `_validate_ohlc(kline)` checking low ≤ open, low ≤ close, high ≥ open, high ≥ close
    - Implement `_infer_date_from_filename(filename)` extracting YYYYMMDD dates from filenames
    - Implement `_map_dc_sector_type(idx_type)` and `_map_ti_sector_type(index_type)` for type mapping
    - _Requirements: 4.10, 4.11_

  - [x] 2.2 Implement sector list parsing methods for all three data sources
    - Implement `parse_sector_list_dc(file_path)` parsing DC CSV with columns: 板块代码,交易日期,板块名称,...,idx_type,level
    - Implement `parse_sector_list_ti(file_path)` parsing TI CSV with columns: 代码,名称,成分个数,交易所,上市日期,指数类型
    - Implement `parse_sector_list_tdx(file_path)` parsing TDX CSV with columns: 板块代码,交易日期,板块名称,板块类型,成分个数,...
    - Each method returns `list[ParsedSectorInfo]` with appropriate data_source set
    - _Requirements: 4.1, 4.2, 4.3_

  - [x] 2.3 Write property test for sector list CSV parsing round-trip (Property 2)
    - **Property 2: Sector list CSV parsing round-trip**
    - For any valid sector info data, generating a CSV row in DC/TI/TDX format and parsing it back SHALL recover the original field values
    - Test file: `tests/properties/test_sector_import_properties.py`
    - **Validates: Requirements 4.1, 4.2, 4.3**

  - [x] 2.4 Write property test for encoding detection (Property 5)
    - **Property 5: Encoding detection preserves content**
    - For any valid CSV text containing Chinese characters, encoding as UTF-8, GBK, or GB2312 and reading with auto-detection SHALL produce identical parsed content
    - Test file: `tests/properties/test_sector_import_properties.py`
    - **Validates: Requirements 4.10**

  - [x] 2.5 Write property test for OHLC validation invariant (Property 6)
    - **Property 6: OHLC validation invariant**
    - For any four positive decimals, the OHLC validator SHALL return True iff low ≤ open AND low ≤ close AND high ≥ open AND high ≥ close
    - Test file: `tests/properties/test_sector_import_properties.py`
    - **Validates: Requirements 4.11**

- [x] 3. Implement SectorCSVParser — constituent and kline parsing
  - [x] 3.1 Implement constituent parsing methods for all three data sources
    - Implement `parse_constituents_dc_zip(zip_path)` extracting CSV files from ZIP, parsing trade_date from filename, extracting sector_code, symbol, stock_name
    - Implement `parse_constituents_ti_csv(file_path, trade_date)` parsing TI CSV with columns: 指数代码,指数名称,指数类型,股票代码,股票名称
    - Implement `parse_constituents_tdx_zip(zip_path)` extracting CSV files from ZIP, parsing sector_code, trade_date, symbol, stock_name
    - Each method returns `list[ParsedConstituent]` with appropriate data_source set
    - _Requirements: 4.4, 4.5, 4.6_

  - [x] 3.2 Implement kline parsing methods for all three data sources
    - Implement `parse_kline_dc_csv(file_path)` parsing DC CSV with columns: 日期,概念代码,开盘,收盘,最高,最低,成交量,成交额,振幅,涨跌幅,涨跌额,换手率
    - Implement `parse_kline_ti_csv(file_path)` parsing TI CSV with columns: 指数代码,交易日期,开盘点位,最高点位,最低点位,收盘点位,...,涨跌幅,...,换手率
    - Implement `parse_kline_tdx_csv(file_path)` parsing TDX CSV with columns: 日期,代码,名称,开盘,收盘,最高,最低,成交量,成交额,...
    - Apply `_validate_ohlc` to each parsed kline record, skipping invalid rows
    - Each method returns `list[ParsedSectorKline]` with appropriate data_source and freq="1d"
    - _Requirements: 4.7, 4.8, 4.9, 4.11_

  - [x] 3.3 Write property test for constituent data parsing round-trip (Property 3)
    - **Property 3: Constituent data parsing round-trip**
    - For any valid constituent data, generating CSV/ZIP content in DC/TI/TDX format and parsing it back SHALL recover the original field values
    - Test file: `tests/properties/test_sector_import_properties.py`
    - **Validates: Requirements 4.4, 4.5, 4.6**

  - [x] 3.4 Write property test for kline CSV parsing round-trip (Property 4)
    - **Property 4: Kline CSV parsing round-trip**
    - For any valid sector kline data where OHLC invariant holds, generating a CSV row in DC/TI/TDX format and parsing it back SHALL recover the original OHLCV values
    - Test file: `tests/properties/test_sector_import_properties.py`
    - **Validates: Requirements 4.7, 4.8, 4.9**

  - [x] 3.5 Write unit tests for SectorCSVParser
    - Test file: `tests/services/test_sector_csv_parser.py`
    - Test each data source's sector list parsing with sample CSV data
    - Test constituent parsing from ZIP and CSV formats
    - Test kline parsing with OHLC validation
    - Test encoding fallback (GBK file parsed correctly)
    - Test corrupted ZIP handling (BadZipFile)
    - Test rows with insufficient fields are skipped
    - _Requirements: 4.1–4.11_

- [x] 4. Checkpoint — Ensure all parser tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [x] 5. Implement SectorImportService — bulk write and file scanning
  - [x] 5.1 Create `app/services/data_engine/sector_import.py` with SectorImportService class
    - Define class constants: BATCH_SIZE=5000, REDIS_PROGRESS_KEY, REDIS_INCREMENTAL_KEY, REDIS_STOP_KEY, PROGRESS_TTL, HEARTBEAT_TIMEOUT
    - Implement `__init__(self, base_dir)` with default path `/Volumes/light/行业概念板块`
    - Implement `_scan_sector_list_files(source)`: DC scans `概念板块列表_东财.csv` from root + `东方财富_*板块_历史行情数据/` list CSVs + `增量数据/概念板块_东财/YYYY-MM/YYYY-MM-DD.csv`; TI scans `行业概念板块_同花顺.csv` from root; TDX scans `通达信板块列表.csv` + `板块信息_通达信.zip` from root + `增量数据/板块信息_通达信/YYYY-MM/YYYY-MM-DD.csv`
    - Implement `_scan_constituent_files(source)`: DC scans `概念板块_东财.zip` from root + `板块成分_东财/YYYY-MM/板块成分_DC_YYYYMMDD.zip`; TI scans root CSVs (`概念板块成分汇总_同花顺.csv`, `行业板块成分汇总_同花顺.csv`) + `概念板块成分_同花顺.zip` + `板块成分_同花顺/*/YYYY-MM/*.csv`; TDX scans `板块成分_通达信/YYYY-MM/板块成分_TDX_YYYYMMDD.zip`
    - Implement `_scan_kline_files(source)`: DC scans `板块行情_东财.zip` from root + `东方财富_*板块_历史行情数据/*.zip` + `增量数据/板块行情_东财/YYYY-MM/YYYY-MM-DD.csv`; TI scans `板块指数行情_同花顺.zip` from root + `增量数据/板块指数行情_同花顺/YYYY-MM/YYYY-MM-DD.csv`; TDX scans `板块行情_通达信.zip` from root + `通达信_*板块_历史行情数据/*.zip` + `增量数据/板块行情_通达信/YYYY-MM/YYYY-MM-DD.csv`
    - _Requirements: 5.1, 11.1, 11.2, 12.1, 12.2, 12.3, 12.4, 12.14_

  - [x] 5.2 Implement bulk write methods
    - Implement `_bulk_upsert_sector_info(items)` using PostgreSQL UPSERT (ON CONFLICT DO UPDATE) in batches of BATCH_SIZE
    - Implement `_bulk_insert_constituents(items)` using ON CONFLICT DO NOTHING in batches of BATCH_SIZE
    - Implement `_bulk_insert_klines(items)` using ON CONFLICT DO NOTHING in batches of BATCH_SIZE, writing to TimescaleDB
    - Use `AsyncSessionPG` for sector_info and sector_constituent, `AsyncSessionTS` for sector_kline
    - _Requirements: 5.3, 5.4, 5.5, 5.6_

  - [x] 5.3 Implement progress tracking and stop signal
    - Implement `update_progress(**kwargs)` writing JSON to Redis with heartbeat timestamp
    - Implement `is_running()` checking Redis progress status with heartbeat timeout detection (120s)
    - Implement `request_stop()` setting Redis stop signal key
    - Implement `_check_stop_signal()` reading Redis stop signal key
    - Use independent Redis key prefix `sector_import:` separate from K-line import
    - _Requirements: 5.8, 7.3, 7.4, 7.5, 11.2_

  - [x] 5.4 Write property test for SectorInfo UPSERT idempotence (Property 7)
    - **Property 7: SectorInfo UPSERT idempotence**
    - For any valid SectorInfo record, inserting via UPSERT twice (second time with modified mutable fields) SHALL result in exactly one record with updated values
    - Test file: `tests/properties/test_sector_import_properties.py`
    - **Validates: Requirements 1.2, 5.3, 6.6**

  - [x] 5.5 Write property test for SectorConstituent conflict-ignore idempotence (Property 8)
    - **Property 8: SectorConstituent conflict-ignore idempotence**
    - For any valid SectorConstituent record, inserting via ON CONFLICT DO NOTHING twice SHALL result in exactly one record
    - Test file: `tests/properties/test_sector_import_properties.py`
    - **Validates: Requirements 2.2, 5.4, 6.5**

  - [x] 5.6 Write property test for SectorKline conflict-ignore idempotence (Property 9)
    - **Property 9: SectorKline conflict-ignore idempotence**
    - For any valid SectorKline record, inserting via ON CONFLICT DO NOTHING twice SHALL result in exactly one record
    - Test file: `tests/properties/test_sector_import_properties.py`
    - **Validates: Requirements 3.2, 5.5, 6.4**

- [x] 6. Implement SectorImportService — full and incremental import
  - [x] 6.1 Implement full import orchestration
    - Implement `import_full(data_sources)` orchestrating: _import_sector_list → _import_constituents → _import_klines
    - Implement `_import_sector_list(data_sources)` scanning and parsing sector list files per source, calling `_bulk_upsert_sector_info`
    - Implement `_import_constituents(data_sources)` scanning and parsing constituent files per source, calling `_bulk_insert_constituents`
    - Implement `_import_klines(data_sources)` scanning and parsing kline files per source, calling `_bulk_insert_klines`
    - Check stop signal between files, update progress after each file
    - Log errors and skip failed files, continue processing remaining files
    - _Requirements: 5.1, 5.2, 5.3, 5.4, 5.5, 5.7, 5.8_

  - [x] 6.2 Implement incremental import
    - Implement `check_incremental(file_path)` checking Redis hash for file path + mtime
    - Implement `mark_imported(file_path)` storing file path + mtime in Redis hash
    - Implement `import_incremental(data_sources)` scanning all files but skipping already-imported ones via `check_incremental`
    - _Requirements: 6.1, 6.2, 6.3, 6.4, 6.5, 6.6_

  - [x] 6.3 Write property test for incremental detection correctness (Property 10)
    - **Property 10: Incremental detection correctness**
    - For any file path, after `mark_imported(path)`, `check_incremental(path)` SHALL return True; for unmarked paths SHALL return False
    - Test file: `tests/properties/test_sector_import_properties.py`
    - **Validates: Requirements 6.3**

  - [x] 6.4 Write unit tests for SectorImportService
    - Test file: `tests/services/test_sector_import.py`
    - Test file scanning discovers correct files per data source
    - Test batch size splitting logic
    - Test progress update and heartbeat
    - Test stop signal detection
    - Test zombie task detection (heartbeat timeout)
    - Test error handling: skip failed files, continue processing
    - _Requirements: 5.1–5.8, 6.1–6.6_

- [x] 7. Checkpoint — Ensure all import service tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [x] 8. Implement SectorRepository and Celery tasks
  - [x] 8.1 Create `app/services/data_engine/sector_repository.py` with SectorRepository
    - Implement `get_sector_list(sector_type, data_source)` querying SectorInfo with optional filters
    - Implement `get_constituents(sector_code, data_source, trade_date)` querying SectorConstituent, defaulting to latest trade_date if not specified
    - Implement `get_sectors_by_stock(symbol, trade_date)` querying SectorConstituent by symbol, defaulting to latest trade_date
    - Implement `get_sector_kline(sector_code, data_source, freq, start, end)` querying SectorKline from TimescaleDB
    - Implement `get_latest_trade_date(data_source)` returning the most recent trade_date from SectorConstituent
    - _Requirements: 8.1, 8.2, 8.3, 8.4, 8.5_

  - [x] 8.2 Create `app/tasks/sector_sync.py` with Celery tasks
    - Implement `sector_import_full(data_sources, base_dir)` task on `data_sync` queue, calling `SectorImportService.import_full()`
    - Implement `sector_import_incremental(data_sources)` task on `data_sync` queue, calling `SectorImportService.import_incremental()`
    - Use `_run_async` pattern from existing `data_sync.py` for running async code in Celery worker
    - Register with independent task names: `app.tasks.sector_sync.sector_import_full`, `app.tasks.sector_sync.sector_import_incremental`
    - _Requirements: 7.6, 11.3, 11.4_

- [x] 9. Implement Sector API endpoints
  - [x] 9.1 Create `app/api/v1/sector.py` with import management endpoints
    - Implement `POST /api/v1/sector/import/full` triggering full import Celery task, accepting optional data_sources and base_dir params
    - Implement `POST /api/v1/sector/import/incremental` triggering incremental import Celery task
    - Implement `GET /api/v1/sector/import/status` returning import progress from Redis
    - Implement `POST /api/v1/sector/import/stop` sending stop signal via `SectorImportService.request_stop()`
    - Return 409 Conflict when import task is already running
    - Define Pydantic request/response models for each endpoint
    - _Requirements: 7.1, 7.2, 7.3, 7.4, 7.5_

  - [x] 9.2 Add data query endpoints to `app/api/v1/sector.py`
    - Implement `GET /api/v1/sector/list` with optional sector_type and data_source query params
    - Implement `GET /api/v1/sector/{code}/constituents` with data_source and optional trade_date params
    - Implement `GET /api/v1/sector/by-stock/{symbol}` with optional trade_date param
    - Implement `GET /api/v1/sector/{code}/kline` with data_source, freq, start, end params
    - Default to latest trade_date when date param is not specified
    - Return empty list (HTTP 200) when no data found
    - _Requirements: 8.1, 8.2, 8.3, 8.4, 8.5_

  - [x] 9.3 Register sector router in the API module
    - Import and include the sector router in `app/api/v1/__init__.py`
    - Ensure prefix `/api/v1/sector` does not conflict with existing routes
    - _Requirements: 11.6_

  - [x] 9.4 Write unit tests for Sector API endpoints
    - Test file: `tests/api/test_sector_api.py`
    - Test sector list query with type and source filters
    - Test constituent query by sector code and date
    - Test stock-to-sector reverse lookup
    - Test kline query with date range
    - Test default date behavior (latest trade date)
    - Test 409 response when import already running
    - _Requirements: 7.1–7.5, 8.1–8.5_

- [x] 10. Checkpoint — Ensure all API and task tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [x] 11. Integrate sector data into risk controller
  - [x] 11.1 Add sector concentration check to `app/services/risk_controller.py`
    - Import `SectorRepository` from `app.services.data_engine.sector_repository`
    - Add `check_sector_concentration(positions)` method that:
      - Queries each position's stock sectors via `get_sectors_by_stock`
      - Calculates per-sector holding count ratio (持仓股票数 / 成分股总数)
      - Calculates per-sector holding market value ratio (板块持仓市值 / 总持仓市值)
      - Generates concentration warning when either ratio exceeds configured threshold (default 30%)
    - Wrap in try/except: if sector data unavailable, log warning and skip check without blocking other risk flows
    - _Requirements: 9.1, 9.2, 9.3, 9.4, 9.5_

  - [x] 11.2 Write property test for sector concentration warning threshold (Property 11)
    - **Property 11: Sector concentration warning threshold**
    - For any portfolio and sector data, if holding count ratio OR market value ratio exceeds threshold, a warning SHALL be generated; if both below, no warning
    - Test file: `tests/properties/test_sector_import_properties.py`
    - **Validates: Requirements 9.2, 9.3**

- [x] 12. Integrate sector data into screener
  - [x] 12.1 Add sector strength filtering to screener module
    - Import `SectorRepository` from `app.services.data_engine.sector_repository`
    - Add sector strength calculation: load sector kline data, compute short-term change_pct (5d/10d), rank sectors by change_pct
    - Add sector strength filter: retain only candidate stocks belonging to top-N sectors
    - Wrap in try/except: if sector data unavailable, log warning and skip sector filter, continue with other conditions
    - _Requirements: 10.1, 10.2, 10.3, 10.4, 10.5_

  - [x] 12.2 Write property test for sector strength ranking consistency (Property 12)
    - **Property 12: Sector strength ranking consistency**
    - For any set of sector kline data, a sector with higher change_pct SHALL rank higher (or equal) than one with lower change_pct
    - Test file: `tests/properties/test_sector_import_properties.py`
    - **Validates: Requirements 10.2**

  - [x] 12.3 Write property test for sector strength filtering correctness (Property 13)
    - **Property 13: Sector strength filtering correctness**
    - For any candidate stock list and top-N ranking, filtered result SHALL contain only stocks in at least one top-N sector
    - Test file: `tests/properties/test_sector_import_properties.py`
    - **Validates: Requirements 10.3**

- [x] 13. Final checkpoint — Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [x] 14. Adapt file scanning and parsing to actual file system layout
  - [x] 14.1 Rewrite `_scan_sector_list_files` to match actual directory structure
    - DC: scan `概念板块列表_东财.csv` from root, `东方财富*板块列表.csv` from historical kline dirs, `增量数据/概念板块_东财/YYYY-MM/YYYY-MM-DD.csv` for incremental
    - TI: scan `行业概念板块_同花顺.csv` from root
    - TDX: scan `通达信板块列表.csv` and `板块信息_通达信.zip` from root, `增量数据/板块信息_通达信/YYYY-MM/YYYY-MM-DD.csv` for incremental
    - Remove dependency on `_SOURCE_DIR_MAP` subdirectory structure (files are in root, not in `东方财富/` etc.)
    - _Requirements: 12.1, 12.14_

  - [x] 14.2 Rewrite `_scan_constituent_files` to match actual directory structure
    - DC: scan `板块成分_东财/YYYY-MM/板块成分_DC_YYYYMMDD.zip`
    - TI: scan root `概念板块成分汇总_同花顺.csv`, `行业板块成分汇总_同花顺.csv`, `概念板块成分_同花顺.zip`, and `板块成分_同花顺/*/YYYY-MM/*.csv` for incremental
    - TDX: scan `板块成分_通达信/YYYY-MM/板块成分_TDX_YYYYMMDD.zip`
    - _Requirements: 12.2_

  - [x] 14.3 Rewrite `_scan_kline_files` to match actual directory structure
    - DC: scan `板块行情_东财.zip` from root, `增量数据/板块行情_东财/YYYY-MM/YYYY-MM-DD.csv` for incremental
    - TI: scan `板块指数行情_同花顺.zip` from root, `增量数据/板块指数行情_同花顺/YYYY-MM/YYYY-MM-DD.csv` for incremental
    - TDX: scan `板块行情_通达信.zip` from root, `通达信_*板块_历史行情数据/*.zip` for historical, `增量数据/板块行情_通达信/YYYY-MM/YYYY-MM-DD.csv` for incremental
    - _Requirements: 12.3, 12.4_

  - [x] 14.4 Update `parse_kline_dc_csv` to handle ZIP files and actual CSV column order
    - Add ZIP support: if file_path is `.zip`, extract and parse each internal CSV
    - Fix column order: actual data has `板块代码,交易日期,收盘点位,开盘点位,...` (close before open)
    - Extract to `_parse_kline_dc_text` helper for reuse between ZIP and CSV paths
    - _Requirements: 12.5, 12.6_

  - [x] 14.5 Update `parse_kline_ti_csv` to handle ZIP files
    - Add ZIP support: if file_path is `.zip`, extract and parse each internal CSV
    - Extract to `_parse_kline_ti_text` helper
    - Handle optional empty fields gracefully
    - _Requirements: 12.5_

  - [x] 14.6 Update `parse_kline_tdx_csv` to handle ZIP files and dual CSV formats
    - Add ZIP support: if file_path is `.zip`, extract and parse each internal CSV
    - Auto-detect format A (historical ZIP: `日期,代码,名称,开盘,收盘,...`) vs format B (incremental: `板块代码,交易日期,收盘点位,开盘点位,...`)
    - Extract to `_parse_kline_tdx_text` helper
    - _Requirements: 12.5, 12.7_

  - [x] 14.7 Update `parse_sector_list_dc` to handle fewer columns
    - Relax minimum column requirement from 13 to 3
    - Default to CONCEPT when `idx_type` column is missing
    - _Requirements: 12.9_

  - [x] 14.8 Update `parse_sector_list_tdx` to handle ZIP files
    - Add ZIP support: if file_path is `.zip`, extract and parse each internal CSV, then deduplicate by sector_code
    - Extract to `_parse_sector_list_tdx_text` helper
    - _Requirements: 12.10_

  - [x] 14.9 Update `parse_constituents_ti_csv` to handle ZIP files and dual column formats
    - Add ZIP support: if file_path is `.zip`, extract and parse each internal CSV
    - Auto-detect 5-column format (summary CSV: `指数代码,指数名称,指数类型,股票代码,股票名称`) vs 3-column format (ZIP internal: `指数代码,股票代码,股票名称`)
    - Extract to `_parse_constituents_ti_text` helper
    - _Requirements: 12.11, 12.12_

  - [x] 14.10 Update `_infer_date_from_filename` to support YYYY-MM-DD format
    - Add `_DATE_DASH_RE` regex for `YYYY-MM-DD` pattern
    - Try YYYY-MM-DD first, then fall back to YYYYMMDD
    - _Requirements: 12.8_

  - [x] 14.11 Update `_map_dc_sector_type` to use contains-matching
    - Change from exact match (`idx_type == "概念"`) to contains match (`"概念" in idx_type`)
    - Supports values like `概念板块`, `行业板块` etc.
    - _Requirements: 12.13_

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- Each task references specific requirements for traceability
- Checkpoints ensure incremental validation
- Property tests validate universal correctness properties from the design document (13 properties)
- Unit tests validate specific examples and edge cases
- All new code is in independent files — no modifications to existing K-line import, data API, or model files
- The actual file system layout has data files organized by function (板块列表/成分/行情) in the root directory, NOT by data source subdirectories (no `东方财富/`, `同花顺/`, `通达信/` dirs). Incremental data is under `增量数据/` with `YYYY-MM/YYYY-MM-DD.csv` naming
- The project uses Python with Hypothesis for property-based tests and pytest for unit tests
- All ORM models use the existing dual-database pattern: PGBase for PostgreSQL, TSBase for TimescaleDB
- Redis keys use `sector_import:` prefix to avoid conflicts with existing `import:local_kline:` keys
