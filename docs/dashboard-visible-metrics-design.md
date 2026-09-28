# ダッシュボード基本指標の表示設定

設定UIは追加せず、環境別設定ファイルで全管理者共通の表示項目を指定する。実装済み。AWS反映にはデプロイが必要。

## 設定方法

```json
"dashboardBasicMetrics": {
  "chat_count": { "name": "チャット数", "visible": 1 },
  "chat_user_count": { "name": "チャットユーザ数", "visible": 0 }
}
```

全21項目を日本語名付きで環境別JSONへ記載してある。通常変更するのはvisibleだけ。1は表示、0は非表示。nameは設定時の説明用で、画面の名称や表示順は変更しない。

- H+さん：infrastructure/config/customer-validation.json
- 自社AWS開発：infrastructure/config/development-ci.json
- ローカル：.env の DASHBOARD_BASIC_METRICS（同じオブジェクトをJSON文字列で指定）。全項目の例は.env.example。

AWSはコミット・Pushによるデプロイ成功後に反映する。ローカルは `docker compose up -d --no-deps backend` で設定を再反映する。開いている画面は再読み込みまたは再集計する。

キー・環境変数未指定なら全項目を表示。個別の項目を省略した場合も、その項目は表示する。空オブジェクトも全表示となる。全非表示にする場合は全21項目を0にする。不明なID、nameの欠落や空欄、visibleの欠落・1/0以外・文字列・真偽値、配列やnullはエラー。CDKでデプロイ前に検出し、直接環境変数を設定した場合もAPIが設定エラーを返す。

## 配置

表示する項目を現行順で左上から右へ詰める。「有効回答数」「満足度」の前の強制改行は撤廃。画面幅1400px超は6列、760px超1400px以下は3列、760px以下は2列。項目幅・文字サイズは現行どおりで、少数項目を引き伸ばさない。最終行の右側は空きになる。

パネルは必要な行数だけの高さとし、下部の集計パネルも上に移動する。全非表示なら基本指標パネル自体を描画しない。値が0でも項目は残し、算出不可は従来どおり「－」。

## 集計とAPI

基本指標の集計式や分母、期間指定、下部の回答種別・時間帯・曜日パネルは変更しない。設定による非表示はアクセス制御ではない。バックエンドは従来どおり全指標を集計する。

管理者用GET /api/v1/dashboardにvisible_basic_metricsを追加し、表示項目IDを固定順で返す。response_time_averageは平均秒数、response_time_rangeは最短・最長の組に対応する。旧APIとの切替時に追加フィールドがない場合は全項目を表示する。

## 全項目と初期値

```json
{
  "dashboardBasicMetrics": {
    "access_count": {
      "name": "アクセス数",
      "visible": 1
    },
    "access_user_count": {
      "name": "アクセスユーザ数",
      "visible": 1
    },
    "chat_count": {
      "name": "チャット数",
      "visible": 1
    },
    "chat_user_count": {
      "name": "チャットユーザ数",
      "visible": 1
    },
    "average_chats_per_day": {
      "name": "1日平均チャット数",
      "visible": 1
    },
    "average_chats_per_user": {
      "name": "1人あたりチャット数",
      "visible": 1
    },
    "response_count": {
      "name": "応答数",
      "visible": 1
    },
    "average_responses_per_chat": {
      "name": "1チャットあたり平均応答数",
      "visible": 1
    },
    "average_responses_per_user": {
      "name": "1人あたり平均応答数",
      "visible": 1
    },
    "response_time_average": {
      "name": "応答時間（平均／秒）",
      "visible": 1
    },
    "response_time_range": {
      "name": "応答時間（最短 - 最長／秒）",
      "visible": 1
    },
    "valid_answer_count": {
      "name": "有効回答数",
      "visible": 1
    },
    "no_answer_count": {
      "name": "回答NG数",
      "visible": 1
    },
    "answer_rate": {
      "name": "回答率",
      "visible": 1
    },
    "good_count": {
      "name": "Good数",
      "visible": 1
    },
    "bad_count": {
      "name": "Bad数",
      "visible": 1
    },
    "unrated_count": {
      "name": "評価なし",
      "visible": 1
    },
    "satisfaction_rate": {
      "name": "満足度",
      "visible": 1
    },
    "comment_count": {
      "name": "コメント総数",
      "visible": 1
    },
    "good_comment_count": {
      "name": "コメント数（Good）",
      "visible": 1
    },
    "bad_comment_count": {
      "name": "コメント数（Bad）",
      "visible": 1
    }
  }
}
```

## 確認

フロントの選択表示・全非表示・既存表示、バックエンドの既定値・不正値・全非表示でも集計値が変わらないことをテストする。CDKでも全環境の21項目と不正値の検証を行う。設定変更は利用者個人の設定ではなく環境全体へ適用される。
