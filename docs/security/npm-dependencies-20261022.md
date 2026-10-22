# npm依存ライブラリの更新・確認（2026年10月22日）

## 対象と変更

Node.js 24.22.1への更新後に検出したnpm依存ライブラリの警告を調査した。Python、OSパッケージ、AWS設定全体の再診断ではない。

| 対象 | 更新前 | 更新後 | 内容 |
|---|---|---|---|
| Next.js / eslint-config-next | 16.3.4 | 16.3.8 | ImageResponse、画像最適化、キャッシュ等の修正を含む同一16.3系パッチ |
| Vitest | 3.2.6 | 4.1.12 | mockerの修正版を含み、旧tinypool依存を除去 |
| sharp | 0.35.4 | 0.35.5 | librsvgの修正を含む |
| source-map-js | 1.2.1 | 1.2.2 | 不正なsource mapによるDoSの修正 |
| brace-expansion | 1.1.18 / 5.0.9 | 1.1.21 / 5.0.12 | ネスト・展開に伴うDoSの修正 |
| AWS CDKライブラリ | 2.266.0 | 2.274.0 | 同梱brace-expansionを修正版へ更新 |
| AWS CDK CLI | 2.1139.0 | 2.1146.0 | 更新したライブラリと組み合わせて構成生成を確認 |

Vitest設定は新しい変換処理（oxc）に合わせて変更。画面の機能・業務仕様は変更していない。

Dockerのビルド後に開発依存を除去する専用ステージを設け、稼働イメージへは実行用node_modulesをコピーする。ESLint・Vitestの設定とtestsディレクトリも稼働ステージから除去した。ビルド・開発・CIでは引き続き検査ツールを使用する。

## npm監査結果

| 範囲 | 更新前 | 更新後 |
|---|---:|---:|
| frontend全依存 | 13件（critical 3 / high 9 / moderate 1） | 5件（highのみ） |
| frontend実行用依存（omit=dev） | 今回の更新前値は未採取 | 0件 |
| infrastructure全依存 | 1件（high） | 0件 |

件数はnpm auditの依存パッケージ別集計。独立した脆弱性の数ではなく、依存元への波及を重複して含む。既知のnpmアドバイザリに対する結果であり、未知の脆弱性がない保証ではない。

### 残る5件

`eslint-config-next → @next/eslint-plugin-next → fast-glob → micromatch → braces`という開発用依存経路にある、同一のbracesのDoS指摘（GHSA-vfj7-8cjw-p6xm）が波及したもの。2026年10月22日時点でbraces 3.0.3の修正版は未公開。

当プロジェクトはESLintをローカル・CIの静的検査で使用し、Web APIとして公開していない。Next ESLintプラグインのfast-glob呼出しは設定のrootDirを処理するもの。現行設定では利用者のチャット入力等を渡していない。稼働コンテナにはこれらのライブラリを含めないことを実物で確認した。

npmが提示するeslint-config-next 14系へのダウングレードは採用しない。Next.js 16との整合を維持する。警告を無効化せず、上流の修正版が公開された時点で更新を検討する。

## 検証

- frontend: Lint、232件のテスト、Next.js製品用ビルド成功。
- infrastructure: TypeScriptビルド、CDK synth成功。
- CDK更新前後の開発環境テンプレート比較: フロントエンドイメージ参照とCDKメタデータのみ差分。IAM・DB・ネットワークの定義に変更なし。
- Dockerビルド成功。実物でNode.js 24.22.1、Next.js 16.3.8を確認。
- 稼働イメージでeslint、vitest、bracesが解決できない（未導入）ことを確認。
- コンテナ起動後、CPF入口・チャット・FAQ画面のHTTP 200を確認。これは認証済みの業務操作検証とは別。
- 自社開発環境のみデプロイ対象。実行結果はGitHub Actionsのデプロイレポートで確認する。H+検証環境にはこの時点では反映しない。

## 参照

- https://github.com/vercel/next.js/security/advisories/GHSA-vcvr-r3jv-pc5j
- https://github.com/vitest-dev/vitest/security/advisories/GHSA-qxg6-89mg-rqv8
- https://github.com/advisories/GHSA-vfj7-8cjw-p6xm
- https://github.com/advisories/GHSA-wq5f-xc86-pv6w
- https://github.com/advisories/GHSA-68fv-2mgg-jv7q
