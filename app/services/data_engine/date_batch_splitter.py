"""日期范围拆分器：将大日期范围按步长拆分为连续无重叠的子区间。

纯函数工具类，无副作用，可被 _process_batched_by_date 和双重分批场景复用。

对应需求：2.1, 2.2, 2.3, 2.4, 2.5, 2.6, 2.7
"""

from __future__ import annotations

from datetime import datetime, timedelta


class DateBatchSplitter:
    """日期范围拆分器：将大日期范围按步长拆分为连续无重叠的子区间。"""

    @staticmethod
    def split(
        start_date: str,
        end_date: str,
        chunk_days: int,
    ) -> list[tuple[str, str]]:
        """将日期范围拆分为子区间。

        Args:
            start_date: 起始日期 YYYYMMDD
            end_date: 结束日期 YYYYMMDD
            chunk_days: 每个子区间的天数（正整数）

        Returns:
            [(chunk_start, chunk_end), ...] 列表，YYYYMMDD 格式

        Raises:
            ValueError: start_date > end_date 或 chunk_days <= 0
        """
        if chunk_days <= 0:
            raise ValueError(
                f"chunk_days 必须为正整数，当前值: {chunk_days}"
            )

        start = datetime.strptime(start_date, "%Y%m%d").date()
        end = datetime.strptime(end_date, "%Y%m%d").date()

        if start > end:
            raise ValueError(
                f"start_date ({start_date}) 不能大于 end_date ({end_date})"
            )

        chunks: list[tuple[str, str]] = []
        cursor = start
        while cursor <= end:
            chunk_end = min(cursor + timedelta(days=chunk_days - 1), end)
            chunks.append((cursor.strftime("%Y%m%d"), chunk_end.strftime("%Y%m%d")))
            cursor = chunk_end + timedelta(days=1)

        return chunks
