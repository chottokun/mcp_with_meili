

# **Meilisearch 分散システム実装計画書（最終版）：FastMCPとDoclingによるRAG基盤の構築**

## **1\. システム概要とアーキテクチャの再定義**

本実装計画は、高速なマイクロサービスコントローラーであるFastMCPによるセキュアなクエリゲートウェイ機能と、Doclingによる高忠実度ドキュメント変換および構造化抽出機能を追加し、Retrieval Augmented Generation（RAG）の基盤としての性能とセキュリティを向上させることを目的とします。Meilisearchは、日本語対応のHybrid検索（キーワード検索とベクトル検索の組み合わせ）機能を提供することで、RAGリトリーバルプロセスの中核を担います。

### **1.1 アーキテクチャの変更点とデータフロー**

FastMCPとDoclingの導入に伴い、システムのアーキテクチャはデータインジェスチョンパイプラインとセキュアなクエリフローの二つの主要なサブグラフに再定義されます。ウォッチャーサーバーの責務は独立したマイクロサービス群に分割され、リソースの競合を防ぎます。

改訂版アーキテクチャ図

コード スニペット

graph TD  
    subgraph Data Ingestion Pipeline (Microservices)  
        C\[クラウドストレージ\] \--\>|ファイル同期| D\[ローカルファイルシステム\]  
        D \--\>|変更検知| A  
        A \--\>|イベントキュー| A\_P(Doc-Processor Service)  
        A\_P \--\>|チャンキング依頼| G  
        A \--\>|メタデータ同期| F  
        G \--\>|構造化Doc/チャンク転送| B\[Meilisearchサーバー\]  
    end  
    subgraph Query Flow (FastMCP Secured)  
        Z\[クライアント/LLM\] \--\>|検索クエリ (Authenticated)| E  
        E \--\>|認可済みクエリ| B  
        B \--\>|リトリーバル結果| E  
        E \--\>|結果返却/LLMへ| Z  
    end  
      
    style E fill:\#f9f,stroke:\#333  
    style A\_P fill:\#afa,stroke:\#333  
    style G fill:\#ccf,stroke:\#333

### **1.2 コンポーネント構成（役割定義の拡張）**

ウォッチャーサーバーの責務は、マイクロサービスとして分離されます。

| コンポーネント | 既存の役割 | 拡張された役割 |
| :---- | :---- | :---- |
| **データインジェスチョン・パイプライン** | ファイル監視、基本処理 | **責務を分離したマイクロサービス群で構成** (File-Watcher, Doc-Processor, Chunker-Embedderなど)。**Doclingによる高忠実度解析** \[1\]、将来的なLLM/LangChain機能ホスト \[2\]。 |
| **Meilisearchサーバー** | 検索エンジン、インデックス管理 | \*\*日本語対応Dockerによる([https://github.com/meilisearch/meilisearch/pull/3882](https://github.com/meilisearch/meilisearch/pull/3882) )によるHybrid検索（キーワード/ベクトル）を提供。**リードレプリカ、手動シャーディング**を見据えた設計。 |
| **MCP Server** | 検索クエリ転送 | **FastMCP認証ミドルウェア実装** \[3\]、認可フィルタリング、**レートリミット**、アクセスログ監査。 |
| **Embedding Service** | ベクトル生成 | ruri-v3-30mによる高性能なセマンティックベクトル生成、バッチ処理最適化。 |

---

## **2\. 詳細設計：高度なデータインジェスチョンパイプライン**

### **2.1 Docling統合：高忠実度Markdown変換と構造化抽出**

サポート対象の入力形式として、従来のPDF/DOCX/TXTに加え、**Markdown (.md)** および**JSON (.json)** ファイルを追加します。

#### **2.1.1 Doclingの採用理由とRAG性能への影響**

Doclingは複雑なドキュメントレイアウトを構造化されたMarkdownに変換する能力に優れており 4、見出しやリストといった構造情報が失われることを防ぎます。これにより、ナイーブな抽出と比較して、**コンテキスト認識型のチャンキング戦略** を実現するための高品質な構造的基盤が築かれます。

#### **2.1.2 LLM連携を見据えた構造化データ抽出と拡張 (LangChain統合の将来計画)**

Doclingの構造化抽出機能（\[🧪 beta\]機能） 5 を利用し、タイトル、作成者、発行日などの基本メタデータを抽出します。

**LangChainによる拡張（将来的に組み込み）：** LangChainの summarization chain やカスタムプロンプト を活用し、**要約（Summary）や重要キーワード**を生成する LLM-Processor サービスを設計します。この拡張処理は、RAGの**二段階リトリーバル (Two-Step Retrieval)** の基盤 6 となり、MeilisearchのsearchableAttributesにsummaryフィールドを追加することで利用可能となります。

#### **2.1.3 データインジェスチョン・パイプラインのマイクロサービス化**

ウォッチャーサーバーの責務を機能単位で分離し、**マイクロサービスアーキテクチャ**を採用します。これにより、Doclingの潜在的なTorch依存 やEmbedding生成によるGPU負荷 \[5.1\] が単一ノードで競合するリスクを低減し、各コンポーネントを独立してスケール可能にします。各サービスは非同期メッセージキューを介して連携します。

### **2.2 Context-Aware Chunking戦略（Docling連携）**

Doclingによって実現される階層的コンテキスト認識型チャンキング 7 は、RAGの精度向上に寄与します。この機能は、設定ファイルで柔軟に制御できるように実装します。

#### **2.2.1 階層的コンテキスト認識型チャンキングの制御 (ON/OFF)**

この高度なチャンキング機能は、以下のパラメータで**ON/OFF制御**できるように実装します。

* **enable\_hierarchical\_chunking (ON/OFF制御):** 階層的チャンキング機能全体の有効/無効を制御します。  
* **respect\_headers (ON/OFF制御):** 階層的チャンキングが有効な場合、Doclingによって変換されたMarkdownの見出し (\#, \#\#) をチャンク境界として尊重するかどうかを個別に制御します。

#### **2.2.2 改訂されたChunking設定（YAML）**

YAML

chunking:  
  strategies:  
    hierarchical: \# Doclingの構造を利用する高度な戦略  
      max\_token\_size: 256  
      overlap\_tokens: 25  
      priority\_breaks:  
        \- markdown\_header\_level\_2  
        \- markdown\_header\_level\_3  
        \- paragraph\_break  
      context\_metadata\_depth: 2   
      enable\_hierarchical\_chunking: true   
      respect\_headers: true   
        
  rules:  
    \- format: pdf  
      strategy: hierarchical   
      params:  
        max\_token\_size: 512  
        enable\_hierarchical\_chunking: true   
        respect\_headers: true  
          
    \- format: md \# Markdownファイルの処理  
      strategy: hierarchical  
      params:  
        max\_token\_size: 256  
        enable\_hierarchical\_chunking: true   
        respect\_headers: true  
          
    \- format: json \# JSONファイルの処理  
      strategy: token   
      params:  
        max\_tokens: 1024   
        enable\_hierarchical\_chunking: false   
        respect\_headers: false

### **2.3 Meilisearchサーバー設計**

#### **2.3.1 インデックス設定とHybrid検索対応**

Meilisearchサーバーは、日本語対応Dockerイメージの利用を前提とし、キーワード検索とベクトル検索を組み合わせたHybrid Searchを提供します。

**Hybrid Searchパラメータ:** Hybrid検索の挙動は、semanticRatioパラメータ（0.0: 純粋なキーワード検索、1.0: 純粋なベクトル検索）によって制御されます 3。

### **2.4 Meilisearchのスケーラビリティと高可用性計画**

Meilisearchは現行バージョンではネイティブなクラスタリングをサポートしていませんが、大容量データと高トラフィックへの対応を見据え、初期デプロイメント段階からスケーラビリティを確保するための戦略を計画します。

1. **リードレプリカ（検索負荷分散）の検討:** 検索トラフィックの増加が見込まれる場合、読み取り専用のMeilisearchインスタンス（リードレプリカ）を複数設定し、MCP Serverからこれらのレプリカへ検索クエリを負荷分散させます。  
2. **手動シャーディング戦略の検討:** 将来的にデータ量が著しく増加する場合、ドキュメントの種類やテナントIDなどに基づいてインデックスを手動で分割し、複数のMeilisearchインスタンス（シャーディング）に分散させる設計を検討します。

## **3\. FastMCPによるサービス連携とセキュリティ設計**

### **3.1 MCP Serverの役割と責務**

* **セキュリティゲートウェイ:** Meilisearchへの直接アクセスを遮断し、APIキーの露出を防ぎます 。  
* **認可ベースのフィルタリング:** 認証されたユーザーIDに基づき、Meilisearch検索リクエストにアクセス制御用の認可フィルタを強制的に追加します。

### **3.2 FastMCP認証ミドルウェアの実装詳細**

FastMCPのカスタムミドルウェア (UserAuthMiddleware) は、HTTP Authorizationヘッダーに格納されたBearerトークンを使用してユーザーを認証するミドルウェアとして実装されます 。

Python

from fastmcp.server.dependencies import get\_http\_headers  
\#... (Middlewareクラス定義と on\_call\_tool メソッド)

class UserAuthMiddleware(Middleware):  
    async def on\_call\_tool(self, context: MiddlewareContext, call\_next):  
        headers \= get\_http\_headers() \#   
        \#... (トークン検証ロジック)   
        context.fastmcp\_context.set\_state("user\_id", user\_id)  
        return await call\_next(context)

### **3.2.3 FastMCPセキュリティ強化（レートリミットと監査）**

実運用環境での安定性とセキュリティ維持のため、以下の制御をFastMCPレイヤーに追加します。

1. **レートリミット (Rate Limiting):** 特定のユーザーまたはIPアドレスからの検索リクエストが過剰になった場合、FastMCPミドルウェアでリクエストを制限し、サービス拒否（DoS）攻撃やリソース枯渇を防ぎます。  
2. **アクセスログ監査 (Access Log Audit):** すべての認証済みおよび拒否されたクエリについて、ユーザーID、リクエスト時刻、クエリ内容、応答コードなどの詳細情報をログ集約システムに記録し、セキュリティ監査や不正利用の追跡を可能にします。

---

## **4\. 実装計画とオブザーバビリティ**

### **4.1 フェーズ1: 基盤構築とFastMCPセキュリティプロトコル（2週間）**

1. **環境設定:** Meilisearchサーバーに日本語対応Dockerイメージを導入 \[5.1\]。ウォッチャーサーバーのマイクロサービス環境（キュー、コンテナ）を構築。  
2. **FastMCPコア実装:** UserAuthMiddlewareの認証ロジックを実装。Meilisearch Hybrid検索をラップしたFastMCP検索ツールを開発。  
3. **オブザーバビリティ基盤セットアップ:** PrometheusとGrafana、およびログ集約システム（例: Fluentd）を導入し、基本的なサービスメトリクスとログの収集を開始します。

### **4.2 フェーズ2: コア機能実装と早期プロトタイピング（4週間）**

1. **Docling統合とマイクロサービス実装:** Doclingをインストールし、Doc-Processor、Chunker-Embedderサービスを実装。  
2. **チャンキング機能の実装:** hierarchicalチャンキング戦略、およびON/OFF制御ロジックを実装 \[2.2.1\]。  
3. **Docling/LLMプロトタイプの実装:** DoclingのMarkdown出力を利用し、**LangChainを用いたLLMによる要約・キーワード抽出（LLM-Processorサービス）の初期プロトタイプを開発**します。  
4. **代替ライブラリ検証:** Doclingの構造化抽出機能（Beta）のリスク 5 に備え、**unstructured.ioなどの代替オープンソースライブラリ**の技術検証を行い、リスク時の移行パスを確立します。

### **4.3 フェーズ3: 最適化、拡張、運用テスト（2週間）**

1. **認可フィルタの組み込み:** FastMCP認可ロジック（Meilisearchフィルタ注入）を本稼働させます。  
2. **性能最適化:** Embeddingバッチ処理 \[10.1\] や処理の並列化によるインジェスチョン速度を最適化します。  
3. **分散トレーシング導入:** OpenTelemetryを導入し、エンドツーエンドの処理フローのボトルネックを特定・改善します。  
4. **検索品質評価テスト:** フェーズ6.3で定義された評価データセットと指標に基づき、Hybrid検索のsemanticRatioやチャンキング戦略を最適化するためのテストを実施します。

### **4.4 オブザーバビリティ（可観測性）の計画**

※将来的な実装とします。

システム全体の健全性を継続的に監視するため、以下のツールと戦略を導入します。

1. **メトリクス監視 (Prometheus & Grafana):** 各マイクロサービス（Chunker-Embedderのキューの長さ、GPU使用率）、Meilisearchの検索レイテンシ、FastMCPの応答時間などの性能メトリクスを収集・可視化します。  
2. **ログ集約 (Fluentd, Lokiなど):** 全コンポーネントからのログを一元的に集約し、検索・分析可能にします。  
3. **分散トレーシング (OpenTelemetry):** ファイル投入からインデックス化まで、およびクエリ発行から応答までのエンドツーエンドの処理フローを追跡し、ボトルネックを特定します。

### **4.3.1 リスク分析：Docling構造化抽出機能が\[🧪 beta\]であることへの対応策**

| リスク | 影響度 | 発生確率 | 緩和策 |
| :---- | :---- | :---- | :---- |
| Doclingの構造化抽出機能が本番で不安定、またはスキーマが頻繁に変更される 5 | 中〜高 (フィルタリング精度低下、開発コスト増) | 中 | **代替技術の検証:** フェーズ2でunstructured.ioなどの代替ライブラリを並行検証し、Docling Beta機能が不安定な場合は迅速に代替策へ移行します。Docling Beta機能は、主要な認可機能とは切り離し、システム全体の依存度を低く保つ。 |
| Doclingとruri-v3-30mのTorch依存関係によるGPUリソース競合 | 高 (処理遅延、システムクラッシュ) | 高 | **マイクロサービスによる分離:** Doc-ProcessorとChunker-Embedderを分離し、リソース（GPU VRAM）の分離を図ることで競合リスクを最小化します 。 |
| FastMCP認証の外部IDP依存によるレイテンシ増加 \[3\] | 中 (UX低下) | 中 | Redis等の高速キャッシュ層を導入し、トークン検証結果を短期間キャッシュする戦略を採用し、認証の平均応答時間を削減する。 |

---

## **5\. デプロイメント**

### **5.1 必要環境**

#### **Meilisearchサーバー**

* Ubuntu Server 22.04 LTS  
* 8GB RAM以上  
* SSD storage  
* **日本語対応Meilisearch Dockerイメージ (Kuromoji等の形態素解析対応版)**

#### **データインジェスチョン・パイプライン（ウォッチャーサーバー群）**

* Python 3.9+  
* NVIDIA GPU（CUDA対応、VRAM 8GB以上推奨）  
* **高可用性コンテナオーケストレーション環境（Kubernetes等）**

### **5.2 デプロイ手順**

1. Meilisearchサーバー

Bash

\# 日本語対応Meilisearch Dockerイメージの利用を想定 (Kuromoji等)  
docker run \-d \-p 7700:7700 \\  
    \-e MEILI\_MASTER\_KEY='YOUR\_MASTER\_KEY' \\  
   getmeili/meilisearch:prototype-japanese-13

2. データインジェスチョン・パイプライン（ウォッチャーサーバー群）

Bash

\# CUDA Toolkitのインストール（Ubuntu）  
wget https://developer.download.nvidia.com/compute/cuda/11.8.0/local\_installers/cuda\_11.8.0\_520.61.05\_linux.run  
sudo sh cuda\_11.8.0\_520.61.05\_linux.run

\# 依存関係インストール (各サービスコンテナに組み込む)  
python \-m pip install watchdog aiohttp sqlalchemy torch torchvision torchaudio  
python \-m pip install sentence-transformers  
python \-m pip install "ruri-v3-30m @ git+https://github.com/user/ruri-v3-30m.git"  
python \-m pip install docling pydantic  
python \-m pip install langchain \# LLMProcessorサービス用

## **6\. テスト計画**

### **6.1 単体テスト**

* ドキュメントプロセッサ  
* チャンキングロジック（enable\_hierarchical\_chunking、respect\_headersのON/OFF制御を含む）

### **6.2 統合テスト**

* ファイル監視→マイクロサービス連携→インデックス化のフルパイプラインテスト。  
* FastMCP認証→Hybrid検索（semanticRatio設定）→認可フィルタリングの一連のフロー。

### **6.3 検索品質評価テストの導入**

RAGシステムの核となる「検索品質」を定量的かつ客観的に評価するためのテストを導入します。

1. **評価データセットの作成:** 事前に「特定のクエリに対して、どのドキュメント（チャンク）が返されるべきか」という正解データセットを作成します。  
2. **評価指標の導入:** 以下の指標を用いて、チャンキング戦略やHybrid検索のsemanticRatio設定の変更が検索品質に与える影響を評価します。  
   * Hit Rate：正解チャンクが検索結果に含まれたかどうか。  
   * MRR（Mean Reciprocal Rank）：正解チャンクが検索結果のより上位に位置するかどうか。  
   * NDCG（Normalized Discounted Cumulative Gain）：検索結果の全体的な関連性。

## **7\. 設定パラメータ**

### **7.1 ウォッチャー設定**

YAML

watcher:  
  watch\_path: /path/to/watch  
  polling\_interval: 1.0  
  batch\_size: 100  
  supported\_formats:  
    \- pdf  
    \- docx  
    \- txt  
    \- md   
    \- json 

meilisearch:  
  host: http://meilisearch-server:7700  
  api\_key: ${MEILISEARCH\_API\_KEY}  
  index\_name: documents  
  default\_semantic\_ratio: 0.5 

### **7.2 処理ルール**

YAML

processing\_rules:  
  \- format: pdf  
    extract\_metadata: true  
    extract\_text: true  
    max\_file\_size: 100MB  
  \- format: md \# Markdownルール  
    extract\_metadata: true  
    extract\_text: true  
    max\_file\_size: 5MB  
  \- format: docx  
    extract\_metadata: true  
    extract\_text: true  
    max\_file\_size: 50MB

---

## **8\. その他の設計要素**

### **8.1 エラーハンドリング**

* Slack通知、メール通知、ログ集約による迅速なエラー検出。  
* リトライ戦略による一時的な障害からの自動回復。

### **8.2 パフォーマンス最適化**

* **バッチ処理:** ドキュメント処理、Embedding生成、インデックス登録の各ステップでバッチ処理を適用し、スループットを最大化 \[10.1\]。  
* **キャッシュ戦略:** ファイルメタデータ、処理結果、Embeddingベクトルのキャッシュにより、冗長な計算を排除 \[10.2\]。

#### **引用文献**

1. PDF Data Extraction Benchmark 2025: Comparing Docling, Unstructured, and LlamaParse for Document Processing Pipelines \- Procycons, 11月 1, 2025にアクセス、 [https://procycons.com/en/blogs/pdf-data-extraction-benchmark/](https://procycons.com/en/blogs/pdf-data-extraction-benchmark/)  
2. Implementing Authentication in a Remote MCP Server with Python ..., 11月 1, 2025にアクセス、 [https://gelembjuk.com/blog/post/authentication-remote-mcp-server-python/](https://gelembjuk.com/blog/post/authentication-remote-mcp-server-python/)  
3. Docling vs. LLMWhisperer: The Best Docling Alternative → Unstract.com, 11月 1, 2025にアクセス、 [https://unstract.com/blog/docling-alternative/](https://unstract.com/blog/docling-alternative/)  
4. docling-project/docling: Get your documents ready for gen AI \- GitHub, 11月 1, 2025にアクセス、 [https://github.com/docling-project/docling](https://github.com/docling-project/docling)  
5. Chunking \- IBM, 11月 1, 2025にアクセス、 [https://www.ibm.com/architectures/papers/rag-cookbook/chunking](https://www.ibm.com/architectures/papers/rag-cookbook/chunking)  
6. RHEL AI 1.3 Docling context aware chunking: What you need to know, 11月 1, 2025にアクセス、 [https://www.redhat.com/en/blog/rhel-13-docling-context-aware-chunking-what-you-need-know](https://www.redhat.com/en/blog/rhel-13-docling-context-aware-chunking-what-you-need-know)  
7. From RAG to riches: Building a practical workflow with Meilisearch's all-in-one tool, 11月 1, 2025にアクセス、 [https://www.meilisearch.com/blog/rag-with-meilisearch](https://www.meilisearch.com/blog/rag-with-meilisearch)  
8. [https://github.com/meilisearch/meilisearch/pull/3882](https://github.com/meilisearch/meilisearch/pull/3882)  
   Japanese specialized Meilisearch Docker Image