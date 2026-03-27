"""
Locust 性能测试

模拟 50 并发用户，验证：
- 盘后选股接口响应 ≤ 3 秒（P99）
- 实时选股刷新 ≤ 1 秒（P99）
- 页面操作响应 ≤ 500ms（P99）

运行方式：
    locust -f tests/performance/locustfile.py --host http://localhost:8000

需求 18.1, 18.2, 18.3
"""

from __future__ import annotations

from locust import HttpUser, between, task


class ScreenerUser(HttpUser):
    """模拟选股用户行为。

    权重较高的任务：查看选股结果、查看大盘概况
    权重较低的任务：执行盘后选股（较重操作）
    """

    wait_time = between(1, 3)

    @task(3)
    def view_screen_results(self):
        """查看选股结果 — 预期 ≤ 500ms（需求 18.3）"""
        with self.client.get(
            "/api/v1/screen/results",
            catch_response=True,
            name="GET /screen/results",
        ) as resp:
            if resp.elapsed.total_seconds() > 0.5:
                resp.failure(f"Response too slow: {resp.elapsed.total_seconds():.3f}s > 500ms")

    @task(3)
    def view_market_overview(self):
        """查看大盘概况 — 预期 ≤ 500ms（需求 18.3）"""
        with self.client.get(
            "/api/v1/market/overview",
            catch_response=True,
            name="GET /market/overview",
        ) as resp:
            if resp.elapsed.total_seconds() > 0.5:
                resp.failure(f"Response too slow: {resp.elapsed.total_seconds():.3f}s > 500ms")

    @task(1)
    def run_eod_screen(self):
        """执行盘后选股 — 预期 ≤ 3 秒（需求 18.1）"""
        payload = {
            "strategy_config": {
                "factors": [
                    {"factor_name": "ma_trend", "operator": ">=", "threshold": 80.0}
                ],
                "logic": "AND",
                "weights": {"ma_trend": 1.0},
            }
        }
        with self.client.post(
            "/api/v1/screen/run",
            json=payload,
            catch_response=True,
            name="POST /screen/run (EOD)",
        ) as resp:
            if resp.elapsed.total_seconds() > 3.0:
                resp.failure(f"EOD screen too slow: {resp.elapsed.total_seconds():.3f}s > 3s")


class RealtimeScreenerUser(HttpUser):
    """模拟盘中实时选股刷新用户。

    每 1-2 秒刷新一次实时选股结果，验证 ≤ 1 秒响应。
    """

    wait_time = between(1, 2)

    @task
    def refresh_realtime_screen(self):
        """实时选股刷新 — 预期 ≤ 1 秒（需求 18.2）"""
        with self.client.get(
            "/api/v1/screen/results?type=realtime",
            catch_response=True,
            name="GET /screen/results (realtime)",
        ) as resp:
            if resp.elapsed.total_seconds() > 1.0:
                resp.failure(f"Realtime refresh too slow: {resp.elapsed.total_seconds():.3f}s > 1s")


class TraderUser(HttpUser):
    """模拟交易员操作。

    包含查看持仓、查看委托记录等页面操作。
    """

    wait_time = between(2, 5)

    @task(2)
    def view_positions(self):
        """查看持仓 — 预期 ≤ 500ms"""
        with self.client.get(
            "/api/v1/trade/positions",
            catch_response=True,
            name="GET /trade/positions",
        ) as resp:
            if resp.elapsed.total_seconds() > 0.5:
                resp.failure(f"Response too slow: {resp.elapsed.total_seconds():.3f}s > 500ms")

    @task(1)
    def view_orders(self):
        """查看委托记录 — 预期 ≤ 500ms"""
        with self.client.get(
            "/api/v1/trade/orders",
            catch_response=True,
            name="GET /trade/orders",
        ) as resp:
            if resp.elapsed.total_seconds() > 0.5:
                resp.failure(f"Response too slow: {resp.elapsed.total_seconds():.3f}s > 500ms")
