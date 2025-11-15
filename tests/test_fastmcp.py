import pytest
from unittest.mock import MagicMock
from fastapi.testclient import TestClient
import numpy as np
from fastmcp.main import app, get_model, get_meili_client

# --- モックのセットアップ ---

# モックのSentenceTransformerモデル
mock_model = MagicMock()
mock_model.encode.return_value = np.array([0.1, 0.2, 0.3])

# モックのMeilisearchクライアント
mock_meili_index = MagicMock()
mock_meili_index.search.return_value = {
    'hits': [
        {'content': 'chunk1', 'source': 'doc1.pdf', '_semanticScore': 0.9},
        {'content': 'chunk2', 'source': 'doc2.txt', '_semanticScore': 0.8}
    ]
}
mock_meili_client = MagicMock()
mock_meili_client.index.return_value = mock_meili_index

# 依存関係のオーバーライド
app.dependency_overrides[get_model] = lambda: mock_model
app.dependency_overrides[get_meili_client] = lambda: mock_meili_client

# --- テスト ---

@pytest.fixture
def client():
    """FastAPIテストクライアントのフィクスチャ"""
    return TestClient(app)

def test_rag_search_endpoint(client):
    """/rag/searchエンドポイントのテスト"""
    # APIリクエスト
    response = client.post(
        "/rag/search",
        json={"query": "テストクエリ", "top_k": 2}
    )

    # アサーション
    assert response.status_code == 200

    # 内部のメソッド呼び出しを検証
    mock_model.encode.assert_called_once_with("テストクエリ")
    mock_meili_client.index.assert_called_once_with("documents") # .envがないテスト環境ではデフォルト値が使われる
    mock_meili_index.search.assert_called_once_with(
        "テストクエリ",
        {
            'vector': [0.1, 0.2, 0.3],
            'limit': 2
        }
    )

    # レスポンスボディを検証
    response_json = response.json()
    assert response_json == {
        "results": [
            {"content": "chunk1", "source": "doc1.pdf", "score": 0.9},
            {"content": "chunk2", "source": "doc2.txt", "score": 0.8}
        ]
    }
