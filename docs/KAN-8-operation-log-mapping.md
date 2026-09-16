# KAN-8 操作ログの選択分類と操作種別名の対応表

確認日：2026-09-16。現在の実装をもとに記載しています。

## 回答

5つの選択肢は操作の大分類です。ただし、現在の分類は操作名称ではなく、リクエストのURLとHTTPメソッドで判定しているため、画面上の操作の意味と一致しない例外があります。

| 選択項目 | 現在の判定条件 |
| --- | --- |
| ダウンロード | URL末尾が `.csv`、`.xlsx`、`/export`、`/import-template` |
| アップロード | 上記以外でURL末尾が `/import`、またはURLに `/files` を含む |
| 登録 | 上記以外のPOST |
| 更新 | 上記以外のPUT・PATCH |
| 削除 | 上記以外のDELETE |

**注意：FAQ・カテゴリ・データソースの一括削除はPOSTのため「登録」で抽出されます。個別削除は「削除」です。** また、「データソース一覧更新」「FAQ一覧登録/更新」はアップロードに分類され、ファイル登録も登録ではなくアップロードに分類されます。本対応では分類ロジック自体は変更していません。

## 全対応表

同じ操作種別名でも実行方法により分類が異なるものを、別の行で記載しています。HTTPメソッドとURLは確認用です。

| 選択項目 | 操作ログの操作種別名 | HTTPメソッド | URL |
| --- | --- | --- | --- |
| 登録 | 種別設定登録 | POST | `/api/v1/data-source-types/{type_id}/values` |
| 登録 | データソース（Webサイト）登録 | POST | `/api/v1/data-sources/websites` |
| 登録 | データソース（Webサイト）登録 | POST | `/api/v1/data-sources/websites/bulk` |
| 登録 | データ取り込み処理を今すぐ実行 | POST | `/api/v1/data-sources/ingestion/run-now` |
| 登録 | データソースを登録 | POST | `/api/v1/data-sources/{data_source_id}/recrawl` |
| 登録 | データソース削除 | POST | `/api/v1/data-sources/bulk-delete` |
| 登録 | カテゴリ登録 | POST | `/api/v1/categories` |
| 登録 | カテゴリ削除 | POST | `/api/v1/categories/bulk-delete` |
| 登録 | 区分設定登録 | POST | `/api/v1/faq-classifications/{type_id}/values` |
| 登録 | FAQを登録 | POST | `/api/v1/faqs` |
| 登録 | FAQ削除 | POST | `/api/v1/faqs/bulk-delete` |
| 登録 | 管理サイトアクセス／チャットサイトアクセス | POST | `/api/v1/analytics/accesses` |
| 登録 | 管理データを登録 | POST | `/api/v1/analytics/chat-sessions` |
| 登録 | 管理データを登録 | POST | `/api/v1/chat/messages` |
| 更新 | 種別設定更新 | PATCH | `/api/v1/data-source-types/{type_id}` |
| 更新 | 種別設定更新 | PATCH | `/api/v1/data-source-types/{type_id}/values/{value_id}` |
| 更新 | 種別設定更新 | PUT | `/api/v1/data-source-types/{type_id}/values/order` |
| 更新 | データソース（ファイル）更新／データソース（Webサイト）更新 | PUT | `/api/v1/data-sources/{data_source_id}` |
| 更新 | データソースを更新 | PATCH | `/api/v1/data-sources/{data_source_id}/answer-source` |
| 更新 | データソースを更新 | PATCH | `/api/v1/data-sources/{data_source_id}/reference-link` |
| 更新 | カテゴリ更新 | PATCH | `/api/v1/categories/order` |
| 更新 | カテゴリ更新 | PUT | `/api/v1/categories/{category_id}` |
| 更新 | 区分設定更新 | PATCH | `/api/v1/faq-classifications/{type_id}` |
| 更新 | 区分設定更新 | PUT | `/api/v1/faq-classifications/{type_id}/values/{value_id}` |
| 更新 | 区分設定更新 | PATCH | `/api/v1/faq-classifications/{type_id}/values/order` |
| 更新 | FAQを更新 | PUT | `/api/v1/faqs/{faq_id}` |
| 更新 | 管理データを更新 | PATCH | `/api/v1/chat/sessions/{session_id}` |
| 削除 | 種別設定削除 | DELETE | `/api/v1/data-source-types/{type_id}/values/{value_id}` |
| 削除 | データソース削除 | DELETE | `/api/v1/data-sources/{data_source_id}` |
| 削除 | カテゴリ削除 | DELETE | `/api/v1/categories/{category_id}` |
| 削除 | 区分設定削除 | DELETE | `/api/v1/faq-classifications/{type_id}/values/{value_id}` |
| 削除 | FAQ削除 | DELETE | `/api/v1/faqs/{faq_id}` |
| 削除 | 管理データを削除 | DELETE | `/api/v1/chat/sessions/{session_id}` |
| ダウンロード | 種別一覧ダウンロード | GET | `/api/v1/data-source-types/export` |
| ダウンロード | データソース一覧ダウンロード | GET | `/api/v1/data-sources/export` |
| ダウンロード | データソースをダウンロード | GET | `/api/v1/data-sources/websites/import-template` |
| ダウンロード | カテゴリ一覧ダウンロード | GET | `/api/v1/categories/export` |
| ダウンロード | 区分一覧ダウンロード | GET | `/api/v1/faq-classifications/export` |
| ダウンロード | FAQ一覧ダウンロード | GET | `/api/v1/faqs/export` |
| ダウンロード | FAQをダウンロード | GET | `/api/v1/faqs/import-template` |
| ダウンロード | チャット履歴ダウンロード | GET | `/api/v1/chat-history/export.xlsx` |
| ダウンロード | ユーザリストダウンロード | GET | `/api/v1/usage/users.xlsx` |
| ダウンロード | アクセスログダウンロード | GET | `/api/v1/usage/access-logs.xlsx` |
| ダウンロード | アクセスログダウンロード | GET | `/api/v1/usage/access-logs.csv` |
| ダウンロード | 操作ログダウンロード | GET | `/api/v1/usage/operation-logs.xlsx` |
| ダウンロード | 操作ログダウンロード | GET | `/api/v1/usage/operation-logs.csv` |
| アップロード | データソース一覧更新 | POST | `/api/v1/data-sources/import` |
| アップロード | データソース（ファイル）登録 | POST | `/api/v1/data-sources/files` |
| アップロード | データソース（Webサイト）登録 | POST | `/api/v1/data-sources/websites/import` |
| アップロード | FAQ一覧登録/更新 | POST | `/api/v1/faqs/import` |

## 補足

- 未選択の場合は操作種別で絞り込みません。期間・権限・ユーザーの条件は別途適用されます。
- 失敗した操作もログ記録対象です。成功／失敗はHTTPステータスで確認できます。
- 「管理データを登録／更新／削除」は現在の実装上の名称です。チャットの質問送信や履歴操作などでも使用されます。
- 認証API、データ全削除API、一部分析APIはこの操作ログの対象外です。
- 過去のログに保存された名称は当時の実装に依存します。この表は現在の新規記録に対する対応です。

実装箇所：`backend/app/api/v1/reporting.py`（operation_kind / operation_description）、`backend/app/main.py`（記録対象）、`backend/app/api/v1/data_sources.py`（編集時の名称）。
