import pytest
from unittest.mock import MagicMock
from manage_index import IndexManager

@pytest.fixture
def mock_meili_client():
    """Meilisearchクライアントのモックを返すフィクスチャ"""
    mock_client = MagicMock()
    mock_index = MagicMock()
    mock_client.index.return_value = mock_index

    # Mocking the result of get_indexes to be a dictionary with a 'results' key
    mock_index_info1 = MagicMock()
    mock_index_info1.uid = 'index1'
    mock_index_info2 = MagicMock()
    mock_index_info2.uid = 'index2'

    mock_client.get_indexes.return_value = {'results': [mock_index_info1, mock_index_info2]}
    return mock_client

@pytest.fixture
def index_manager(mock_meili_client):
    """IndexManagerのインスタンスを返すフィクスチャ"""
    return IndexManager(mock_meili_client)

def test_create_index(index_manager, mock_meili_client):
    """インデックス作成のテスト"""
    index_name = "test_index"
    result = index_manager.create_index(index_name)

    mock_meili_client.create_index.assert_called_once_with(index_name)
    assert result == f"インデックス作成: {index_name}"

def test_delete_index(index_manager, mock_meili_client):
    """インデックス削除のテスト"""
    index_name = "test_index"
    result = index_manager.delete_index(index_name)

    mock_meili_client.index.assert_called_once_with(index_name)
    mock_meili_client.index(index_name).delete.assert_called_once()
    assert result == f"インデックス削除: {index_name}"

def test_list_indexes(index_manager, mock_meili_client):
    """インデックス一覧のテスト"""
    result = index_manager.list_indexes()

    mock_meili_client.get_indexes.assert_called_once()
    assert result == ['index1', 'index2']

def test_update_settings(index_manager, mock_meili_client):
    """設定更新のテスト"""
    index_name = "test_index"
    searchable_attrs = ["title", "content"]
    result = index_manager.update_settings(index_name, searchable_attrs)

    mock_meili_client.index.assert_called_once_with(index_name)
    mock_meili_client.index(index_name).update_searchable_attributes.assert_called_once_with(searchable_attrs)
    assert result == f"設定更新: {index_name} → searchable: {searchable_attrs}"
