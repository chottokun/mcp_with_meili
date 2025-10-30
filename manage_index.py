#!/usr/bin/env python3
import os
import sys
from meilisearch import Client
import argparse

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

    if args.cmd == 'create':
        client.create_index(args.name)
        print(f"インデックス作成: {args.name}")
    elif args.cmd == 'delete':
        client.index(args.name).delete()
        print(f"インデックス削除: {args.name}")
    elif args.cmd == 'list':
        for idx in client.get_indexes()['results']:
            print(idx['uid'])
    elif args.cmd == 'settings' and args.searchable:
        client.index(args.name).update_searchable_attributes(args.searchable)
        print(f"設定更新: {args.name} → searchable: {args.searchable}")
    else:
        parser.print_help()

if __name__ == '__main__':
    main()
