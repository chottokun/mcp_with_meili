import pytest
import os
import subprocess
import time
from meilisearch import Client

# 環境変数からMeilisearchの接続情報を取得
MEILI_URL = "http://meilisearch:7700"
MEILI_API_KEY = os.getenv('MEILISEARCH_API_KEY')

@pytest.fixture(scope="module")
def client():
    """テストモジュール用のMeilisearchクライアントを提供"""
    test_client = Client(MEILI_URL, MEILI_API_KEY)
    yield test_client
    # モジュール全体のテスト終了後にクリーンアップ
    indexes = test_client.get_indexes()['results']
    for index in indexes:
        if index.uid.startswith('test_'):
            test_client.index(index.uid).delete()

@pytest.fixture(autouse=True)
def cleanup_indexes_after_test(client):
    """各テストの後にテスト用インデックスをクリーンアップ"""
    yield
    indexes = client.get_indexes()['results']
    for index in indexes:
        if index.uid.startswith('test_'):
            client.index(index.uid).delete()

def run_script(command):
    """manage_index.pyスクリプトを実行するヘルパー関数"""
    env = {
        **os.environ,
        'MEILISEARCH_URL': MEILI_URL,
        'MEILISEARCH_API_KEY': MEILI_API_KEY,
    }
    process = subprocess.run(
        ['python3', 'manage_index.py'] + command,
        capture_output=True,
        text=True,
        env=env,
        check=False
    )
    return process

def test_create_index(client):
    """'create'コマンドのテスト"""
    index_name = "test_movies"
    result = run_script(['create', index_name])

    assert result.returncode == 0, f"STDOUT: {result.stdout}\nSTDERR: {result.stderr}"
    assert f"インデックス作成: {index_name}" in result.stdout
    assert client.get_index(index_name) is not None

def test_list_indexes(client):
    """'list'コマンドのテスト"""
    index1 = "test_list_1"
    index2 = "test_list_2"
    client.create_index(index1)
    client.create_index(index2)

    result = run_script(['list'])

    assert result.returncode == 0, f"STDOUT: {result.stdout}\nSTDERR: {result.stderr}"
    assert index1 in result.stdout
    assert index2 in result.stdout

def test_delete_index(client):
    """'delete'コマンドのテスト"""
    index_name = "test_to_delete"
    client.create_index(index_name)
    time.sleep(0.5)  # インデックス作成の非同期処理を待つ
    assert client.get_index(index_name) is not None

    result = run_script(['delete', index_name])

    assert result.returncode == 0, f"STDOUT: {result.stdout}\nSTDERR: {result.stderr}"
    assert f"インデックス削除: {index_name}" in result.stdout
    with pytest.raises(Exception):
        client.get_index(index_name)

def test_settings_index(client):
    """'settings'コマンドのテスト"""
    index_name = "test_settings"
    client.create_index(index_name, {'primaryKey': 'id'})
    client.index(index_name).add_documents([{'id': 1, 'title': 'Hello', 'content': 'World'}])

    searchable_attrs = ['title', 'content']
    result = run_script(['settings', index_name, '--searchable'] + searchable_attrs)

    assert result.returncode == 0, f"STDOUT: {result.stdout}\nSTDERR: {result.stderr}"
    assert f"設定更新: {index_name} → searchable: {searchable_attrs}" in result.stdout
    settings = client.index(index_name).get_searchable_attributes()
    assert settings == searchable_attrs

def test_no_command():
    """コマンドなしでスクリプトを実行するテスト"""
    result = run_script([])
    assert result.returncode == 0, f"STDOUT: {result.stdout}\nSTDERR: {result.stderr}"
    assert 'usage: manage_index.py' in result.stdout
