# Scholarship Chatbot Admin

This repository contains a minimal local development setup for a scholarship chatbot admin site.

## Architecture

- frontend: Next.js + TypeScript + App Router
- backend: FastAPI + Python 3.12
- database: PostgreSQL
- ORM: SQLAlchemy 2
- migrations: Alembic
- orchestration: Docker Compose

## Local development

1. Copy `.env.example` to `.env` if you need environment variables locally.
2. Run:

```bash
docker compose up --build
```

3. Open the frontend in your browser:

- `http://localhost:3000`

4. The frontend calls the backend health endpoint at `/api/v1/health`.

## Project structure

- `frontend/` - Next.js app
- `backend/` - FastAPI app and database config
- `compose.yaml` - Docker Compose definition

## Tests

- Frontend build and lint are exercised in CI
- Backend tests are executed with `pytest`

## Notes

- Do not commit `.env`
- The backend connects to PostgreSQL using `DATABASE_URL`
- Alembic is configured for future schema migrations
- CB-207の種別1～3の正式な初期値は資料上で未確定です。現在の初期値は維持し、業務担当者の確認後に別途更新します。

## CB-202 MVP decisions

- 検索条件はすべてANDで結合し、キーワードだけはタイトル・ファイル名・URLをOR部分一致で検索します。
- カテゴリ検索は正式な`category_id`への直接一致です。旧`category_name`は移行互換用として維持します。
- ページ直接移動は、項目定義書と画面画像の差を解消するMVP判断として数値入力欄を使用します。範囲外は`PAGE_NOT_FOUND`で共通Modalを表示します。
- 回答ソースが無効でも参照リンクの表示／非表示は変更できます。両トグルは確認なしで即時保存し、楽観ロックを使用します。
- 削除はMVPでは物理削除です。行削除・一括削除とも確認Modalを表示し、一括削除は全件を同一トランザクションで処理します。
- 一覧Excelは検索結果の確認用であり、未確定の一括更新用フォーマットではありません。一括更新機能はMVP対象外です。
- `data_source_classification_values`は既存CB-207テーブルへの複合一意制約追加を避け、単純な外部キーで構成します。種別値が指定種別に属することは`DataSourceService.validate_classification_assignments`で必ず検証します。
- 0002の12件は画面動作確認用サンプルです。`source_type`と`［サンプル］`付きtitleで冪等判定するMVP用seedであり、正式データ投入時に廃止または見直します。
- 実ファイルダウンロード、Web取得・再学習、Knowledge Base同期、認証・認可は未実装です。

## CB-203 local file upload MVP

- MVPの実ファイルは`UPLOAD_DIR`（Docker Composeでは`/app/storage/uploads`）へ保存し、named volumeでコンテナ再起動後も保持します。ストレージ処理はAdapterへ分離し、将来S3 Adapterへ交換できる構成です。
- 新規登録時の状態は`PREPARING`です。Bedrock Knowledge Base同期と`PREPARING`以降の自動状態遷移は実装していません。
- CB-203では任意のカテゴリを選択でき、複数ファイル登録時は同じ`category_id`を全ファイルへ設定します。`category_name`には書き込みません。
- 既存データソースと同じ元ファイル名でも別データソースとして新規登録します。UUIDベースの`storage_key`により保存済みファイルを上書きしません。
- タイトルを省略した場合は拡張子を含む元ファイル名を登録します。複数ファイルでは個別の元ファイル名をタイトルにします。
- 複数ファイル登録は全件成功または全件失敗です。失敗時はDBをロールバックし、そのリクエストで保存した一時ファイル・確定ファイルを削除します。
- 拡張子、Content-Type、基本シグネチャ、件数、合計容量、0バイト、同一リクエスト内の同名を検証します。正式なウイルススキャンは未実装です。
- 登録内容はseedではなくユーザー登録データとして`data_sources`、`data_source_files`、`data_source_classification_values`へ保存します。

## CB-204 file attribute edit MVP

- CB-204は既存FILEデータソースの属性編集のみを行い、ファイル差し替え、再アップロード、`file_name`、`storage_key`、`mime_type`、`size_bytes`の変更は行いません。Storage Adapterも使用しません。
- タイトルが空文字または空白のみの場合は、CB-203と同様に既存のファイル名をタイトルとして保存します。
- CB-204ではカテゴリを変更・解除でき、実値差分をdirty判定へ含めます。
- dirty状態は入力操作の有無ではなく、タイトル、カテゴリ、種別1～3、優先度、回答ソース、参照リンクの初期値との差分で判定します。差分がない場合は更新ボタンを無効化します。
- 属性更新では現在の`status`を維持し、Bedrock同期・再学習を行いません。更新対象と種別関連、`version`、`updated_at`だけを1トランザクションで更新します。

## CB-205 website URL registration MVP

- CB-205は1件のURLと任意タイトルを登録するMVPです。デザイン資料にある複数URL入力、ファイル一括入力、フォーマットダウンロードは実装しません。
- URLは`http`または`https`の絶対URLだけを許可し、文字列形式のみ検証します。DNS、到達可否、HTTP応答、SSL、リダイレクト、robots.txt、ページ内容は確認しません。
- URL上限は、タイトル省略時にURL全体を`data_sources.title(500)`へ保存できるよう500文字とします。タイトルが空文字または空白のみの場合は、登録URLをそのままタイトルとして保存します。
- 同じURLが既に存在しても、自動更新・重複排除は行わず別データソースとして新規登録します。
- CB-205ではカテゴリを任意選択でき、正式な`category_id`へ登録します。`category_name`には書き込みません。
- 登録時は`source_type=WEB`、`format=Web`、`status=PREPARING`、`size_bytes=NULL`、`character_count=NULL`、`last_fetched_at=NULL`、`version=1`です。
- Web取得、スクレイピング、本文抽出、Bedrock同期、再学習、ingestion jobは実行せず、`PREPARING`以降の自動状態遷移も行いません。

## CB-206 website attribute edit MVP

- CB-206は登録済みWEBデータソースのURL、カテゴリ、属性を編集します。カテゴリは変更・解除でき、`category_name`は更新しません。
- URLは変更できますが、Web取得、到達確認、スクレイピング、Bedrock同期、再学習は行いません。
- URL変更時も現在の`status`、`last_fetched_at`、`character_count`を維持し、`PREPARING`へ戻しません。
- タイトルが空文字または空白のみの場合は、更新後のURLをタイトルとして保存します。他のデータソースと同じURLへの更新も許可します。
- dirty状態はURL、タイトル、種別1～3、優先度、回答ソース、参照リンクの初期値との差分で判定し、差分がない場合またはURLが空の場合は更新ボタンを無効化します。

## CB-213 category list MVP

- CB-213の`categories`マスタは、NULL可の`data_sources.category_id`で1データソース1カテゴリとして正式に関連付けます。
- 暫定列`data_sources.category_name`は移行互換用に維持し、既存文字列の自動移行は行いません。
- カテゴリ削除はMVPでは物理削除です。選択したカテゴリの全子孫も同一トランザクションで削除し、参照データソースは正式カテゴリ未選択へ変更します。
- カテゴリは単一親の任意階層ツリーです。最大階層数は設けず、同一親配下（ルート同士を含む）の同名を禁止し、異なる親配下の同名は許可します。カテゴリ名は前後空白を除去した値を前提とします。
- 初期表示は全展開で、展開状態は保存しません。デザイン画像だけにある親カテゴリ絞り込みは、20260811版の画面項目定義にないため実装しません。ページング、検索、列ソートもMVP対象外です。
- D&Dは同一親配下の兄弟間だけ許可し、ドロップ時に即時保存します。異なる親への移動とD&Dによる親変更は行いません。
- 正式な初期カテゴリ値が資料にないためseedは投入しません。画像中のカテゴリ値は表示例として扱います。
- CB-214（カテゴリ新規追加）とCB-215（カテゴリ編集）は独立ページではなく、CB-213の一覧上で共通Modalを使って操作します。新規追加は1カテゴリずつ行い、カテゴリ名は前後空白を除去した1～15文字です。
- `parent_id=NULL`は第一階層を表します。新規カテゴリは同一親配下の末尾へ追加し、同一親配下（ルート同士を含む）の同名は禁止、異なる親配下の同名は許可します。
- 編集ではカテゴリ名と親カテゴリを変更できます。自分自身または子孫を親にすることは禁止し、親変更時はサブツリーを維持したまま新しい親配下の末尾へ移動し、旧親配下の表示順を詰めます。
- 編集は`version`による楽観ロックを使用します。カテゴリとデータソースの正式な関連は後述のMVP仕様で実装します。

## Data source category relationship MVP

- 1データソースにつきカテゴリは0件または1件です。`data_sources.category_id`はNULL可で、第一階層・中間階層・最下層のすべてを選択できます。複数カテゴリには対応しません。
- CB-202のカテゴリ検索は指定した`category_id`への直接一致です。親カテゴリを指定しても子孫カテゴリは検索対象へ含めません。
- 一覧・詳細・CB-202 Excelのカテゴリ表示は、Backendで生成した第一階層からの`/`区切りフルパスです。
- 使用中カテゴリを削除する場合は、削除対象サブツリーを参照するデータソースを行ロックし、`category_id=NULL`、`version + 1`、`updated_at`更新後にカテゴリを削除します。全処理は同一トランザクションです。
- `data_sources.category_name`は移行互換用として残します。新規登録・更新では書き込まず、正式`category_id`がない旧データだけ表示のフォールバックに使用します。既存文字列の自動移行は行いません。
- 全環境の移行完了後に`category_name`廃止を別途検討します。0004をdowngradeすると、正式`category_id`だけを持つデータのカテゴリ関連は失われます。

## CB-212 FAQ classification MVP

- FAQ区分はデータソース用`classification_types`／`classification_values`と分離した専用マスタです。CB-207の種別テーブル・APIには影響しません。
- 区分は`FAQ_TYPE_1`〜`FAQ_TYPE_4`の4つで固定し、区分自体の追加・削除は行いません。表示ラベルは編集できます。
- 20260811版には正式な初期区分値が定義されていないため、区分値seedは投入しません。デザイン画像の値は表示例として扱います。
- 20260811版CB-212に記載された正式なデフォルトラベル「区分1」〜「区分4」を初期値とします。「問合せ区分」「質問区分」「年度」「キャンパス」は運用上編集可能な表示例です。
- 区分値は0件以上で、追加・編集・物理削除・D&D並び替えができます。同一区分内の同名は禁止し、異なる区分間の同名は許可します。
- D&Dは同一区分内だけで許可し、ドロップ時に即時保存します。順序が変わった値だけ`version`と`updated_at`を更新し、失敗時は画面順を元に戻します。
- ラベル編集、値編集・削除、D&Dは`version`による楽観ロックを使用します。新規値の`version`は1です。
- 区分値の文字数に正式な業務上限がないため、MVPでは空文字禁止と前後空白除去だけを適用し、DBの`VARCHAR`にも任意の文字数上限を設けません。
- FAQ本体は未実装です。FAQ本体実装後は、使用中区分値の削除可否と関連解除方法を再検討します。
- FAQの下書き機能は20260811版で削除済みのため、今後のFAQ実装でも下書き状態・下書き保存ボタンを追加しません。

## CB-208 FAQ list MVP

- FAQ本体、類似質問、FAQ区分割当のDB基盤を追加し、CB-208 FAQ一覧を実装します。FAQはカテゴリおよびCB-207のデータソース種別を使用せず、CB-212専用のFAQ区分1～4だけを任意で関連付けます。
- 複数検索条件はAND、キーワード内部は`question`／`answer`のOR部分一致です。類似質問はキーワード検索対象に含めません。
- FAQ数は既存CB-202の件数表示と揃え、現在の検索条件に一致する`total_count`を表示します。
- FAQ削除はMVPでは物理削除です。単体・一括削除とも`version`による楽観ロックを使い、類似質問と区分割当はcascade削除します。一括削除は全件を1トランザクションで処理します。
- `question` 500文字、`answer` 1000文字、類似質問500文字をMVP上限とし、類似質問の最大件数はDB上制限しません。FAQ登録・編集APIはCB-209／CB-210で実装します。
- 一覧のチャット利用は保存済み値を「公開／非公開」で表示するだけとし、CB-208からの直接変更は行いません。
- FAQ一括登録／更新、登録フォーマット、CB-211参照Modal、AI同期、Bedrock、OpenSearchは未実装です。該当操作は未実装Modalまたは共通未実装ページで案内します。
- 20260811版で削除された下書き機能は、DB列、状態、検索条件、ボタンのいずれにも追加しません。

## CB-209 FAQ registration MVP

- CB-209で質問、回答、0件以上の類似質問、任意のFAQ区分1～4、チャット利用を新規登録します。登録成功後はCB-208 FAQ一覧へ遷移します。
- 質問は500文字、回答は1000文字、各類似質問は500文字を上限とし、保存時に前後空白を除去します。回答内部の改行・文中空白はプレーンテキストのまま保持します。
- 類似質問の件数上限と重複禁止は設けません。類似質問0件は許可しますが、画面で追加した空行は登録できません。表示順は入力順に1から採番します。
- FAQ区分1～4はMVPではすべて任意です。Backend Serviceで区分値の存在と`FAQ_TYPE_1`～`FAQ_TYPE_4`への所属を検証します。
- 20260811版でチャット利用の初期値を確定できないため、MVPでは「公開（`chat_enabled=true`）」を初期値とします。
- FAQ本体、類似質問、区分割当は1トランザクションで登録し、一部だけが残る状態を作りません。
- 入力内容に実差分がある場合は、一覧へ戻る操作、キャンセル、Sidebar遷移、ブラウザ更新・終了に未保存確認を適用します。
- 下書き保存・下書き状態・draft列は実装しません。登録後のBedrock、Knowledge Base、OpenSearch、embedding等のAI同期も行いません。

## CB-210 FAQ editing MVP

- CB-210では`GET /api/v1/faqs/{id}`の詳細を初期表示し、`PUT /api/v1/faqs/{id}`で質問、回答、類似質問一覧、任意のFAQ区分1～4、チャット利用を一括更新します。
- 類似質問は画面上の一覧全体を送り、追加・編集・削除・順序を1トランザクションで置き換えます。区分は別の値への変更と未選択への解除が可能です。
- 更新は`id`と`version`による楽観ロックを行い、成功時に`version + 1`と現在の`updated_at`を設定します。`created_at`は変更しません。
- dirtyは初期取得値との実差分で判定し、類似質問の内容と順番も比較します。未変更時または入力不正時は更新ボタンを無効化します。
- 未保存状態の一覧・キャンセル・Sidebar遷移とブラウザ更新／終了には離脱確認を適用します。更新成功後はCB-208 FAQ一覧へ遷移します。
- FAQ更新後のBedrock、Knowledge Base、OpenSearch等へのAI同期は行いません。下書き状態・下書き保存・draft APIも実装しません。

## CB-211 FAQ reference MVP

- CB-211は独立ページではなく、CB-208 FAQ一覧の「参照」から開く読み取り専用Modalです。既存の`GET /api/v1/faqs/{id}`で詳細を取得します。
- 回答はプレーンテキストとして改行を保持し、`http`／`https` URLだけを安全にリンク表示します。HTMLやJavaScriptは解釈しません。
- Modal内の編集操作はCB-210へ遷移し、削除操作は参照Modalを閉じて既存のFAQ削除確認Modalと`DELETE /api/v1/faqs/{id}?version=`を利用します。
- 参照Modalを閉じてもCB-208の検索、ソート、ページ、表示件数、選択状態を維持します。削除成功時は一覧とFAQ総数を再取得します。
- FAQ参照時に下書き状態やAI検索、Bedrock、OpenSearch等の処理は追加しません。
