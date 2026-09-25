# JMA気温速報データ 定期取得 → GCS保存 + BigQueryロード

気象庁の気温速報CSVを、Cloud Functions + Cloud Scheduler で定期取得し、
1. 生CSVをGCSにバックアップ保存
2. パースしてBigQueryにロード（分析用）
する構成です。

## 注意: CSVのヘッダーは日付依存
「25日の最高気温(℃)」のように列名に当日の日付が入っているため、
`parser.py` ではヘッダー文字列ではなく**列の位置（インデックス）**でパースしています
（`schema.py` の `COLUMNS` に位置とBigQueryフィールド名の対応を定義）。
気象庁側でCSVの列構成自体が変わった場合は `schema.py` の修正が必要です。

## 構成
- **Cloud Functions (2nd gen, HTTPトリガー)**: 取得 → GCS保存 → パース → BigQueryロード
- **Cloud Scheduler**: 毎時、Cloud FunctionをHTTPで呼び出す
- **GCS**: 生データのバックアップ (`mxtemsadext00_rct/YYYY/MM/DD/*.csv`)
- **BigQuery**: 構造化データ（日付パーティション、都道府県/観測所でクラスタリング）

## 1. GCSバケット作成（未作成の場合）
```bash
gsutil mb -l asia-northeast1 gs://YOUR_BUCKET_NAME
```

## 2. BigQuery データセット・テーブル作成
```bash
pip install google-cloud-bigquery --break-system-packages  # ローカル実行時のみ
export GOOGLE_CLOUD_PROJECT=YOUR_PROJECT_ID
python create_table.py --dataset jma_data --table temperature_hourly
```

## 3. Cloud Functionのデプロイ
```bash
gcloud functions deploy jma-mxtem-to-bq \
  --gen2 \
  --region=asia-northeast1 \
  --runtime=python312 \
  --source=. \
  --entry-point=fetch_and_store \
  --trigger-http \
  --no-allow-unauthenticated \
  --set-env-vars=GCS_BUCKET=YOUR_BUCKET_NAME,BQ_DATASET=jma_data,BQ_TABLE=temperature_hourly \
  --memory=256Mi \
  --timeout=60s
```

## 4. サービスアカウントの権限
Cloud Functionのランタイム用サービスアカウントに以下を付与:
```bash
# GCSへの書き込み
gsutil iam ch serviceAccount:YOUR_FUNCTION_SA@YOUR_PROJECT_ID.iam.gserviceaccount.com:roles/storage.objectCreator gs://YOUR_BUCKET_NAME

# BigQueryへの書き込み
gcloud projects add-iam-policy-binding YOUR_PROJECT_ID \
  --member="serviceAccount:YOUR_FUNCTION_SA@YOUR_PROJECT_ID.iam.gserviceaccount.com" \
  --role="roles/bigquery.dataEditor"
gcloud projects add-iam-policy-binding YOUR_PROJECT_ID \
  --member="serviceAccount:YOUR_FUNCTION_SA@YOUR_PROJECT_ID.iam.gserviceaccount.com" \
  --role="roles/bigquery.jobUser"
```

## 5. Cloud Scheduler呼び出し用サービスアカウント
```bash
gcloud iam service-accounts create jma-scheduler-invoker \
  --display-name="JMA Scheduler Invoker"

gcloud functions add-invoker-policy-binding jma-mxtem-to-bq \
  --region=asia-northeast1 \
  --member="serviceAccount:jma-scheduler-invoker@YOUR_PROJECT_ID.iam.gserviceaccount.com"
```

## 6. Cloud Schedulerジョブ作成（毎時5分に実行）
```bash
FUNCTION_URL=$(gcloud functions describe jma-mxtem-to-bq \
  --region=asia-northeast1 --format="value(serviceConfig.uri)")

gcloud scheduler jobs create http jma-mxtem-hourly \
  --location=asia-northeast1 \
  --schedule="5 * * * *" \
  --time-zone="Asia/Tokyo" \
  --uri="${FUNCTION_URL}" \
  --http-method=GET \
  --oidc-service-account-email="jma-scheduler-invoker@YOUR_PROJECT_ID.iam.gserviceaccount.com"
```

## 動作確認
```bash
gcloud scheduler jobs run jma-mxtem-hourly --location=asia-northeast1
gcloud functions logs read jma-mxtem-to-bq --region=asia-northeast1 --limit=20

# BigQueryで確認
bq query --use_legacy_sql=false \
  'SELECT * FROM `YOUR_PROJECT_ID.jma_data.temperature_hourly` ORDER BY ingested_at DESC LIMIT 10'
```

## 補足
- `WRITE_APPEND` で毎時追記するため、同じ観測所・同じ時刻のデータが重複ロードされないよう、
  Scheduler側のリトライ設定や重複排除（`ingested_at` によるDISTINCT等）を運用に応じて検討してください。
- パース失敗行（列数不足）はスキップしてログにWARNINGを出すのみで、処理全体は継続します。
- コスト最適化のため、GCS側にライフサイクルルール（例: 90日でNearline移行）の設定を推奨します。
