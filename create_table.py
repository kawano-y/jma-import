"""
BigQueryのデータセット・テーブルを初回作成するためのセットアップスクリプト。
ローカルまたはCloud Shellから一度だけ実行する。

使い方:
  export GOOGLE_CLOUD_PROJECT=your-project-id
  python create_table.py --dataset jma_data --table temperature_hourly
"""

import argparse
from google.cloud import bigquery

from schema import SCHEMA


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", required=True)
    parser.add_argument("--table", required=True)
    parser.add_argument("--location", default="asia-northeast1")
    args = parser.parse_args()

    client = bigquery.Client()

    dataset_ref = bigquery.Dataset(f"{client.project}.{args.dataset}")
    dataset_ref.location = args.location
    client.create_dataset(dataset_ref, exists_ok=True)
    print(f"データセット準備完了: {client.project}.{args.dataset}")

    table_ref = bigquery.Table(f"{client.project}.{args.dataset}.{args.table}", schema=SCHEMA)
    # source_date（当日の日付）でパーティション分割し、地点で絞り込みやすくクラスタリング
    table_ref.time_partitioning = bigquery.TimePartitioning(
        type_=bigquery.TimePartitioningType.DAY, field="source_date"
    )
    table_ref.clustering_fields = ["pref", "station_no"]

    table = client.create_table(table_ref, exists_ok=True)
    print(f"テーブル準備完了: {table.full_table_id}")


if __name__ == "__main__":
    main()
