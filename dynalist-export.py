#!/usr/bin/env python3

import argparse
import html
import json
import os
import sys
from pathlib import Path
from typing import Final, Optional, TextIO

from dynalist import Dynalist


def _write_item(item_id: str, item_table: dict[str, dict], indent_level: int = 0, output: TextIO = sys.stdout) -> None:

    if item_id not in item_table:
        _error(f"Item not found: {item_id}")
        return

    item = item_table[item_id]
    title = item["title"]
    indent = "\t" * indent_level

    if item["type"] == "document":
        output.write(f"{indent}{title} ({item_id})\n")

    elif item["type"] == "folder":
        output.write(f"{indent}[{title}] ({item_id})\n")
        for child_id in item["children"]:
            _write_item(child_id, item_table, indent_level + 1, output)

    else:
        _error(f"Unknown item type: {item['type']}")
        _error(f"\t{item['title']}")
        _error(f"\t{item_id}")


def list_items(token: str, root_id: Optional[str] = None, output: TextIO = sys.stdout) -> None:

    d = Dynalist(token)
    try:
        json_data = d.list_files()
    except Exception as e:
        _error(str(e))
        return

    item_table = {x["id"]: x for x in json_data["files"]}

    if root_id and root_id != json_data["root_file_id"]:
        _write_item(root_id, item_table, 0, output)
    else:
        root = item_table[json_data["root_file_id"]]
        output.write(f"[/] ({root['id']})\n")
        for child_id in root["children"]:
            _write_item(child_id, item_table, 1, output)


def _write_node(node_id: str, node_table: dict[str, dict], indent_level: int = 0, output: TextIO = sys.stdout) -> None:

    if node_id not in node_table:
        _error(f"Node not found: {node_id}")
        return

    node = node_table[node_id]

    tag = "outline"
    items = [tag]

    if "content" in node:
        text = html.escape(node["content"])
        items.append(f'text="{text}"')

    if "note" in node and node["note"]:
        note = html.escape(node["note"])
        items.append(f'_note="{note}"')

    if "checkbox" in node and node["checkbox"]:
        items.append('checkbox="true"')

    if "checked" in node and node["checked"]:
        items.append('complete="true"')

    if "color" in node and node["color"] != 0:
        color = node["color"]
        items.append(f'colorLabel="{color}"')

    if "numbered" in node and node["numbered"]:
        items.append('listStyle="arabic"')

    if "collapsed" in node and node["collapsed"]:
        items.append('collapsed="true"')

    elem = " ".join(items)
    indent = "\t" * indent_level

    if "children" in node:
        output.write(indent + "<" + elem + ">\n")
        for c in node["children"]:
            _write_node(c, node_table, indent_level + 1, output)
        output.write(indent + "</" + tag + ">\n")
    else:
        output.write(indent + "<" + elem + "/>\n")


def export_document(token: str, document_id: str, include_root: bool = False, output: TextIO = sys.stdout) -> None:

    OPML_HEAD: Final[str] = (
        '<?xml version="1.0" encoding="utf-8"?>\n'
        '<opml version="2.0">\n'
        "\t<head>\n"
        "\t\t<title>{}</title>\n"
        "\t\t<flavor>dynalist</flavor>\n"
        "\t\t<source>https://dynalist.io</source>\n"
        "\t</head>\n"
        "\t<body>\n"
    )

    OPML_TAIL: Final[str] = "\t</body>\n</opml>\n"

    d = Dynalist(token)
    try:
        json_data = d.read_doc(document_id)
    except Exception as e:
        _error(str(e))
        return

    output.write(OPML_HEAD.format(json_data["title"]))

    node_table = {x["id"]: x for x in json_data["nodes"]}
    if include_root:
        _write_node("root", node_table, 2, output)
    else:
        root = node_table["root"]
        if "children" in root:
            for child_id in root["children"]:
                _write_node(child_id, node_table, 2, output)

    output.write(OPML_TAIL)


def _parse_args() -> argparse.Namespace:

    parser = argparse.ArgumentParser()
    parser.add_argument("-t", "--token", type=str, default=None)

    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("-l", "--list", action="store_true")
    group.add_argument("-e", "--export", type=str, dest="document_id", default=None)

    return parser.parse_args()


def _load_token() -> str:
    def _read_token(file_path: Path) -> Optional[str]:
        if not file_path.exists():
            return None
        p = file_path.resolve()
        with p.open("r", encoding="utf-8") as f:
            token = f.readline().strip()
        return token

    # プロジェクトの JSON ファイル
    p = Path.cwd().joinpath(".dynalist.json")
    if p.exists():
        with p.open("r", encoding="utf-8") as f:
            data = json.load(f)
            if "token" in data:
                return data["token"]

    # 環境変数
    token = os.getenv("DYNALIST_TOKEN")
    if token:
        return token

    # 作業ディレクトリの設定ファイル
    p = Path.cwd().joinpath(".dynalistrc")
    token = _read_token(p)
    if token:
        return token

    # ホームディレクトリの設定ファイル
    p = Path.home().joinpath(".dynalistrc")
    token = _read_token(p)
    if token:
        return token

    raise RuntimeError("API token not found.")


def _error(message: str) -> None:
    print("error: " + message, file=sys.stderr)


def _abort(message: str) -> None:
    _error(message)
    sys.exit(1)


def main():

    args = _parse_args()

    token = args.token

    if token is None:
        try:
            token = _load_token()
        except RuntimeError as e:
            _abort(str(e))

    if args.list:
        list_items(token)

    if args.document_id is not None:
        export_document(token, args.document_id)


if __name__ == "__main__":
    main()
