from typing import Literal
from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # 应用配置
    app_env: Literal["development", "staging", "production"] = "development"
    app_debug: bool = False
    app_secret_key: str = "change-me-in-production"
    app_allowed_hosts: list[str] = ["localhost", "127.0.0.1"]

    # 数据库配置
    database_url: str = "postgresql+asyncpg://postgres:password@localhost:5432/quant_db"
    timescale_url: str = "postgresql+asyncpg://postgres:password@localhost:5433/quant_ts"

    # Redis / Celery
    redis_url: str = "redis://localhost:6379/0"
    celery_broker_url: str = "redis://localhost:6379/1"
    celery_result_backend: str = "redis://localhost:6379/2"

    # JWT
    jwt_secret_key: str = "change-me-in-production"
    jwt_algorithm: str = "HS256"
    jwt_access_token_expire_minutes: int = 60
    jwt_refresh_token_expire_days: int = 7

    # Tushare 数据源配置
    tushare_api_token: str = ""
    tushare_api_url: str = "http://api.tushare.pro"

    # AkShare 数据源配置
    akshare_request_timeout: float = 30.0
    akshare_max_retries: int = 3

    # 行情数据 API
    market_data_api_key: str = ""
    market_data_api_url: str = "https://api.example.com/market"

    # 券商 API
    broker_api_key: str = ""
    broker_api_secret: str = ""
    broker_api_url: str = "https://api.broker.com/trade"

    # 交易时段
    trading_start_time: str = "09:25"
    trading_end_time: str = "15:00"
    eod_screen_time: str = "15:30"

    # 风控默认参数
    max_single_stock_position: float = 0.15   # 单只个股仓位上限 15%
    max_sector_position: float = 0.30          # 单一板块仓位上限 30%
    default_stop_loss_ratio: float = 0.08      # 默认止损比例 8%

    # 默认管理员
    default_admin_username: str = "admin"
    default_admin_password: str = "admin123456"

    # 数据保留
    kline_history_years: int = 10
    audit_log_retention_days: int = 365

    # API 频率限制（每次调用间隔秒数，留 20% 余量避免触发限制）
    # Tushare: kline 500次/min→0.18s, fundamentals 200次/min→0.40s, moneyflow 300次/min→0.30s
    rate_limit_kline: float = 0.18
    rate_limit_fundamentals: float = 0.40
    rate_limit_money_flow: float = 0.30

    @field_validator("app_allowed_hosts", mode="before")
    @classmethod
    def parse_allowed_hosts(cls, v: str | list) -> list[str]:
        if isinstance(v, str):
            import json
            return json.loads(v)
        return v

    @property
    def is_production(self) -> bool:
        return self.app_env == "production"

    @property
    def is_development(self) -> bool:
        return self.app_env == "development"


settings = Settings()
