"""
JMA 気温速報CSV の列定義。

CSVのヘッダーは「25日の最高気温(℃)」のように当日の日付が列名に
埋め込まれており日次で変化するため、ヘッダー文字列ではなく
「列の位置（0始まりインデックス）」を基準にパースする。

COLUMNS: (CSV列インデックス, BigQueryのフィールド名, 型)
  型は 'STR' | 'INT' | 'FLOAT' のいずれか
"""

from google.cloud import bigquery

COLUMNS = [
    (0, "station_no", "STR"),
    (1, "pref", "STR"),
    (2, "station_name", "STR"),
    (3, "intl_station_no", "STR"),
    (4, "obs_year", "INT"),
    (5, "obs_month", "INT"),
    (6, "obs_day", "INT"),
    (7, "obs_hour", "INT"),
    (8, "obs_minute", "INT"),
    (9, "max_temp_c", "FLOAT"),
    (10, "max_temp_quality", "STR"),
    (11, "max_temp_hour", "INT"),
    (12, "max_temp_minute", "INT"),
    (13, "max_temp_time_quality", "STR"),
    (14, "diff_from_normal_c", "FLOAT"),
    (15, "diff_from_prev_day_c", "FLOAT"),
    (16, "ten_day_period_month", "INT"),
    (17, "ten_day_period", "STR"),
    (18, "extreme_update_flag", "STR"),
    (19, "extreme_update_under_10y_flag", "STR"),
    (20, "this_year_max_flag", "STR"),
    (21, "year_max_temp_c", "FLOAT"),
    (22, "year_max_temp_quality", "STR"),
    (23, "year_max_temp_date_year", "INT"),
    (24, "year_max_temp_date_month", "INT"),
    (25, "year_max_temp_date_day", "INT"),
    (26, "alltime_max_temp_c", "FLOAT"),
    (27, "alltime_max_temp_quality", "STR"),
    (28, "alltime_max_temp_date_year", "INT"),
    (29, "alltime_max_temp_date_month", "INT"),
    (30, "alltime_max_temp_date_day", "INT"),
    (31, "month_max_temp_c", "FLOAT"),
    (32, "month_max_temp_quality", "STR"),
    (33, "month_max_temp_date_year", "INT"),
    (34, "month_max_temp_date_month", "INT"),
    (35, "month_max_temp_date_day", "INT"),
    (36, "stats_start_year", "INT"),
]

_BQ_TYPE_MAP = {"STR": "STRING", "INT": "INT64", "FLOAT": "FLOAT64"}

# BigQueryテーブルのスキーマ（テーブル作成に使用）
SCHEMA = [bigquery.SchemaField(name, _BQ_TYPE_MAP[kind]) for _, name, kind in COLUMNS] + [
    bigquery.SchemaField("source_date", "DATE", description="データが対象とする日付（JST）"),
    bigquery.SchemaField("ingested_at", "TIMESTAMP", description="Cloud Functionが取得した時刻"),
]
