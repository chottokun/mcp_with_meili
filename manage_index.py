#!/usr/bin/env python3
import os
from meilisearch import Client
import argparse

class IndexManager:
    def __init__(self, client):
        self.client = client

    def create_index(self, index_name):
        self.client.create_index(index_name)
        return f"インデックス作成: {index_name}"

    def delete_index(self, index_name):
        self.client.index(index_name).delete()
        return f"インデックス削除: {index_name}"

    def list_indexes(self):
        return [idx.uid for idx in self.client.get_indexes()['results']]

    def update_settings(self, index_name, searchable_attrs):
        self.client.index(index_name).update_searchable_attributes(searchable_attrs)
        return f"設定更新: {index_name} → searchable: {searchable_attrs}"

def main():
    parser = argparse.ArgumentParser(description='Meilisearch Index 管理')
    sub = parser.add_subparsers(dest='cmd')

    # create
    p = sub.add_parser('create', help='インデックス作成')
    p.add_argument('name', help='インデックス名')

    # delete
    p = sub.add_parser('delete', help='インデックス削除')
    p.add_argument('name', help='インデックス名')

    # list
    sub.add_parser('list', help='インデックス一覧')

    # settings
    p = sub.add_parser('settings', help='検索可能属性設定')
    p.add_argument('name', help='インデックス名')
    p.add_argument('--searchable', nargs='+', help='例: title content')

    args = parser.parse_args()
    client = Client(os.getenv('MEILISEARCH_URL', 'http://localhost:7700'),
                    os.getenv('MEILISEARCH_API_KEY'))

    manager = IndexManager(client)

    if args.cmd == 'create':
        print(manager.create_index(args.name))
    elif args.cmd == 'delete':
        print(manager.delete_index(args.name))
    elif args.cmd == 'list':
        for idx_name in manager.list_indexes():
            print(idx_name)
    elif args.cmd == 'settings' and args.searchable:
        print(manager.update_settings(args.name, args.searchable))
    else:
        parser.print_help()

if __name__ == '__main__':
    main()
