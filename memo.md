# 実装状況メモ

## 概要

`docs/next_plan.md` に記載された実装計画のフェーズ1を実行しました。
主な目的は、既存のデータ投入パイプラインをマイクロサービスアーキテクチャに刷新し、FastMCPによるセキュアな検索ゲートウェイを構築することです。

## 1. アーキテクチャの変更点

-   単一の `ingester.py` スクリプトを廃止し、責務を分割した以下の3つのマイクロサービスに再設計しました。
    -   `file-watcher`
    -   `doc-processor`
    -   `meili-ingester`
-   サービス間の連携には、メッセージキューとして **RabbitMQ** を導入しました。これにより、各サービスの独立性とスケーラビリティが向上しています。
-   `docker-compose.yml` を全面的に更新し、新しいマイクロサービス群とRabbitMQ、FastMCPを定義しました。

## 2. 実装されたサービス詳細

### データ投入パイプライン

1.  **`services/watcher/` (`file-watcher`サービス)**
    -   **役割:** `input/` ディレクトリのファイル変更を監視します。
    -   **実装:** `watchdog` を使用し、新規ファイルが作成されると、そのファイルのパスと種類を含むメッセージをRabbitMQの `file_events` キューに送信します。

2.  **`services/processor/` (`doc-processor`サービス)**
    -   **役割:** ファイルの内容を処理・変換します。
    -   **実装:** `file_events` キューからメッセージを受信します。
        -   PDFファイルの場合: `docling` ライブラリを使用してMarkdown形式に変換します。
        -   JSONファイルの場合: 内容をそのまま次のキューに渡します。
    -   処理後のドキュメントデータをRabbitMQの `processed_documents` キューに送信します。

3.  **`services/ingester/` (`meili-ingester`サービス)**
    -   **役割:** 処理済みデータをMeilisearchに登録します。
    -   **実装:** `processed_documents` キューからメッセージを受信し、Meilisearchクライアントを使用してドキュメントをインデックスに追加します。

### セキュリティゲートウェイ

1.  **`services/fastmcp/` (`fastmcp`サービス)**
    -   **役割:** Meilisearchへの直接アクセスを防ぎ、認証と検索クエリの中継を行います。
    -   **実装:** `FastAPI` を使用して構築。
        -   **認証:** リクエストヘッダーの `Authorization: Bearer <token>` を検証するミドルウェアを実装。現在は固定トークン (`super-secret-token`) での検証となっています。
        -   **エンドポイント:** `/search/{index_name}` を提供し、認証済みリクエストをMeilisearchの検索APIに転送して結果を返却します。

## 3. テスト

-   **`tests/test_integration.py`**
    -   新しいマイクロサービスアーキテクチャ全体のエンドツーエンドテストを実装しました。
    -   テストシナリオは以下の通りです。
        1.  テスト用のJSONファイルを `input/json` に作成。
        2.  パイプラインによるデータ処理とMeilisearchへの登録を待機。
        3.  `fastmcp` サービスの検索エンドポイントを介して、データが正しく検索できることを確認。

## 4. 現在の状況とブロッカー

-   **テスト実行のブロッキング:**
    -   統合テストの実行に必要なDockerイメージ（`rabbitmq`, `meilisearch`）をDocker Hubからプルする際に、**レート制限エラー** が発生しました。
    -   これにより、テスト環境を `docker compose up` で起動できず、実装した `test_integration.py` を実行できていません。
    -   これはコードの問題ではなく、実行環境に起因するブロッカーです。

上記内容で実装は完了しています。ご確認のほど、よろしくお願いいたします。
