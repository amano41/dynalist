#!/usr/bin/env python3

import argparse
import html
import json
import os
import sys
from dataclasses import dataclass, field
from os import PathLike
from pathlib import Path, PurePosixPath
from typing import Final, Optional, TextIO, Union

from dynalist import Dynalist


@dataclass
class Item:
    id: str
    type: str
    path: PurePosixPath
    children: list = field(default_factory=list)


def _fetch_item(token: str, root_id: Optional[str] = None) -> Optional[Item]:

    d = Dynalist(token)
    try:
        json_data = d.list_files()
    except Exception as e:
        _error(str(e))
        return None

    item_table = {x["id"]: x for x in json_data["files"]}

    root_item = item_table[json_data["root_file_id"]]
    root_item["title"] = "/"

    def _make_item(item_id: str, item_table: dict[str, dict], parent_path: PurePosixPath) -> Optional[Item]:

        if item_id not in item_table:
            _error("Item not found: {item_id}")
            return None

        data = item_table[item_id]
        path = parent_path.joinpath(data["title"])

        item = Item(data["id"], data["type"], path)

        if "children" in data:
            for child_id in data["children"]:
                child_item = _make_item(child_id, item_table, path)
                if child_item:
                    item.children.append(child_item)

        return item

    if root_id:
        item = _make_item(root_id, item_table, PurePosixPath())
    else:
        item = _make_item(json_data["root_file_id"], item_table, PurePosixPath())

    return item


def _write_item(item: Item, indent_level: int = 0, output: TextIO = sys.stdout) -> None:

    if str(item.path) == "/":
        title = "/"
    else:
        title = item.path.name

    indent = "\t" * indent_level

    if item.type == "document":
        output.write(f"{indent}{title} ({item.id})\n")

    elif item.type == "folder":
        output.write(f"{indent}[{title}] ({item.id})\n")
        for child_node in item.children:
            _write_item(child_node, indent_level + 1, output)

    else:
        _error(f"Unknown type: {item.type}: {item.id}")


def list_items(token: str, root_id: Optional[str] = None, output: TextIO = sys.stdout) -> None:

    item = _fetch_item(token, root_id)

    if item:
        _write_item(item, 0, output)


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


def export_folder(token: str, folder_id: str, dest_dir: Union[str, PathLike]) -> None:

    dest_path = Path(dest_dir)

    if not dest_path.exists():
        _error(f"Directory not found: {dest_path}")
        return

    if not dest_path.is_dir():
        _error(f"Not a directory: {dest_path}")
        return

    item = _fetch_item(token, folder_id)

    if not item:
        _error(f"Item not found: {folder_id}")
        return

    if item.type != "folder":
        _error(f"Not a folder: {folder_id}")
        return

    def _export_item(item: Item, dest_path: Path) -> None:

        dest_dir = dest_path.joinpath(*item.path.parts[1:-1])

        if item.type == "document":
            file_path = dest_dir.joinpath(item.path.name + ".opml")
            with file_path.open("w", encoding="utf-8") as f:
                export_document(token, item.id, output=f)

        elif item.type == "folder":
            dir_path = dest_dir.joinpath(item.path.name)
            if not dir_path.exists():
                dir_path.mkdir()
            for child in item.children:
                _export_item(child, dest_dir)

        else:
            _error(f"Unknown type: {item.type}: {item.id}")
            return

    for child in item.children:
        _export_item(child, dest_path)


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
