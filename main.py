"""
JMA（気象庁）の気温速報CSVを定期的に取得し、
  1. 生データをGCSに保存（バックアップ）
  2. パースしてBigQueryへロード
するCloud Function。

トリガー: Cloud Scheduler から HTTP 経由で定期起動（例: 毎時5分）

環境変数:
  GCS_BUCKET   : 生CSVの保存先バケット名（必須）
  BQ_DATASET   : ロード先データセット名（必須）
  BQ_TABLE     : ロード先テーブル名（必須）
  SOURCE_URL   : 取得元URL（省略時は下記デフォルトを使用）
"""

import os
import logging
from datetime import datetime, timezone, timedelta

import requests
from google.cloud import storage, bigquery

from parser import parse_csv
from schema import SCHEMA

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

DEFAULT_SOURCE_URL = (
    "https://www.data.jma.go.jp/stats/data/mdrr/tem_rct/alltable/mxtemsadext00_rct.csv"
)
JST = timezone(timedelta(hours=9))


def fetch_and_store(request=None):
    """Cloud Functions のエントリポイント（HTTPトリガー用）"""

    bucket_name = os.environ.get("GCS_BUCKET")
    dataset_id = os.environ.get("BQ_DATASET")
    table_id = os.environ.get("BQ_TABLE")
    missing = [k for k, v in {
        "GCS_BUCKET": bucket_name, "BQ_DATASET": dataset_id, "BQ_TABLE": table_id
    }.items() if not v]
    if missing:
        msg = f"環境変数が不足しています: {', '.join(missing)}"
        logger.error(msg)
        return (msg, 500)

    source_url = os.environ.get("SOURCE_URL", DEFAULT_SOURCE_URL)

    # 1. CSVを取得
    try:
        resp = requests.get(source_url, timeout=30)
        resp.raise_for_status()
    except requests.RequestException as e:
        msg = f"CSV取得に失敗しました: {e}"
        logger.error(msg)
        return (msg, 502)

    content = resp.content
    now_jst = datetime.now(JST)

    # 2. 生データをGCSへバックアップ保存
    try:
        storage_client = storage.Client()
        bucket = storage_client.bucket(bucket_name)
        date_path = now_jst.strftime("%Y/%m/%d")
        filename = f"mxtemsadext00_rct_{now_jst.strftime('%Y%m%d%H%M')}.csv"
        blob_path = f"mxtemsadext00_rct/{date_path}/{filename}"
        bucket.blob(blob_path).upload_from_string(content, content_type="text/csv")
        logger.info("GCS保存完了: gs://%s/%s", bucket_name, blob_path)
    except Exception as e:
        msg = f"GCSへのアップロードに失敗しました: {e}"
        logger.error(msg)
        return (msg, 500)

    # 3. パース
    try:
        records = parse_csv(content, ingested_at=datetime.now(timezone.utc))
    except Exception as e:
        msg = f"CSVのパースに失敗しました: {e}"
        logger.error(msg)
        return (msg, 500)

    if not records:
        msg = "パース結果が0件でした（データ形式が変わった可能性があります）"
        logger.warning(msg)
        return (msg, 200)

    # 4. BigQueryへロード
    try:
        bq_client = bigquery.Client()
        table_ref = f"{bq_client.project}.{dataset_id}.{table_id}"
        job_config = bigquery.LoadJobConfig(
            schema=SCHEMA,
            write_disposition=bigquery.WriteDisposition.WRITE_APPEND,
            source_format=bigquery.SourceFormat.NEWLINE_DELIMITED_JSON,
        )
        job = bq_client.load_table_from_json(records, table_ref, job_config=job_config)
        job.result()  # 完了待ち・エラー時は例外を送出
    except Exception as e:
        msg = f"BigQueryへのロードに失敗しました: {e}"
        logger.error(msg)
        return (msg, 500)

    msg = (
        f"完了: GCS保存 gs://{bucket_name}/{blob_path} / "
        f"BigQuery {len(records)}件ロード -> {table_ref}"
    )
    logger.info(msg)
    return (msg, 200)
