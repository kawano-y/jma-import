"""JMA気温速報CSVのパース処理"""

import csv
import io
import logging
from datetime import datetime, timezone, timedelta

from schema import COLUMNS

logger = logging.getLogger(__name__)
JST = timezone(timedelta(hours=9))

EXPECTED_MIN_COLS = max(idx for idx, _, _ in COLUMNS) + 1  # 37


def _decode(raw_bytes: bytes) -> str:
    """JMAのCSVは Shift_JIS(cp932) が基本だが念のためUTF-8も試す"""
    for enc in ("cp932", "utf-8"):
        try:
            return raw_bytes.decode(enc)
        except UnicodeDecodeError:
            continue
    return raw_bytes.decode("cp932", errors="replace")


def _cast(raw: str, kind: str):
    if raw is None:
        return None
    raw = raw.strip()
    if raw == "":
        return None
    try:
        if kind == "INT":
            return int(float(raw))
        if kind == "FLOAT":
            return float(raw)
        return raw
    except ValueError:
        logger.warning("値の変換に失敗しました: %r (kind=%s)", raw, kind)
        return None


def parse_csv(raw_bytes: bytes, ingested_at: datetime = None):
    """CSVバイト列を BigQuery insert 用の dict のリストに変換する"""

    text = _decode(raw_bytes)
    reader = csv.reader(io.StringIO(text))

    rows = list(reader)
    if not rows:
        return []

    data_rows = rows[1:]  # 先頭行はヘッダーとしてスキップ
    ingested_at = ingested_at or datetime.now(timezone.utc)
    source_date = datetime.now(JST).date()

    results = []
    for i, row in enumerate(data_rows):
        if len(row) < EXPECTED_MIN_COLS:
            logger.warning("列数が不足している行をスキップします (row=%d, cols=%d)", i, len(row))
            continue

        record = {name: _cast(row[idx], kind) for idx, name, kind in COLUMNS}
        record["source_date"] = source_date.isoformat()
        record["ingested_at"] = ingested_at.isoformat()
        results.append(record)

    return results
