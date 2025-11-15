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

    def get_settings(self, index_name):
        return self.client.index(index_name).get_settings()

    def update_settings(self, index_name, searchable_attrs=None, settings=None):
        msgs = []
        if searchable_attrs:
            self.client.index(index_name).update_searchable_attributes(searchable_attrs)
            msgs.append(f"searchable: {searchable_attrs}")
        if settings:
            self.client.index(index_name).update_settings(settings)

            # settingsの内容をよしなに整形してメッセージに追加
            if "locales" in settings:
                msgs.append(f"locales: {settings['locales']}")
            if "embedders" in settings:
                embedder_names = list(settings['embedders'].keys())
                msgs.append(f"embedders: {', '.join(embedder_names)}")

        return f"設定更新: {index_name} → {', '.join(msgs)}"

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

    # show_settings
    p = sub.add_parser('show_settings', help='設定表示')
    p.add_argument('name', help='インデックス名')

    # settings
    p = sub.add_parser('settings', help='インデックス設定 (Meilisearch v1.10+)')
    p.add_argument('name', help='インデックス名')
    p.add_argument('--searchable', nargs='+', help='例: title content')
    p.add_argument('--settings-json', help='設定をJSON文字列で指定. 例: \'{"localizedAttributes": [{"attributePatterns": ["*"], "locales": ["jpn"]}], "embedders": {"default": {"source": "huggingFace", "model": "cl-nagoya/ruri-v3-30m"}}}\'')

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
    elif args.cmd == 'show_settings':
        import json
        print(json.dumps(manager.get_settings(args.name), indent=2))
    elif args.cmd == 'settings':
        import json
        settings = json.loads(args.settings_json) if args.settings_json else None
        print(manager.update_settings(args.name, searchable_attrs=args.searchable, settings=settings))
    else:
        parser.print_help()

if __name__ == '__main__':
    main()
