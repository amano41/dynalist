#!/usr/bin/env python3

import argparse
import errno
import html
import json
import os
import re
import sys
from dataclasses import dataclass, field
from os import PathLike
from pathlib import Path, PurePosixPath
from re import Pattern
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


def find_item(token: str, pattern: str, output: TextIO = sys.stdout) -> None:

    item = _fetch_item(token)

    if not item:
        return

    def _find_item(item: Item, pattern: Pattern):

        if pattern.search(item.path.name):
            output.write(f"{item.path}\t{item.id}\n")

        if item.type == "folder":
            for child in item.children:
                _find_item(child, pattern)

    _find_item(item, re.compile(pattern))


def list_items(token: str, root_id: Optional[str] = None, output: TextIO = sys.stdout) -> None:

    item = _fetch_item(token, root_id)

    if not item:
        return

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


def _write_document(json_data: dict, root_node: bool = False, output: TextIO = sys.stdout) -> None:

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

    output.write(OPML_HEAD.format(json_data["title"]))

    node_table = {x["id"]: x for x in json_data["nodes"]}
    if root_node:
        _write_node("root", node_table, 2, output)
    else:
        root = node_table["root"]
        if "children" in root:
            for child_id in root["children"]:
                _write_node(child_id, node_table, 2, output)

    output.write(OPML_TAIL)


def export_document(
    token: str, document_id: str, root_node: bool = False, dest_file: Union[str, PathLike] = "-"
) -> None:

    d = Dynalist(token)
    try:
        json_data = d.read_doc(document_id)
    except Exception as e:
        _error(str(e))
        return

    if dest_file == "-":
        _write_document(json_data, root_node, sys.stdout)
        return

    if dest_file == "":
        p = Path(json_data["title"] + ".opml")
    else:
        p = Path(dest_file)

    with p.open("w", encoding="utf-8") as f:
        _write_document(json_data, root_node, f)


def export_folder(token: str, folder_id: str, dest_dir: Union[str, PathLike] = ".") -> None:

    dest_path = Path(dest_dir)

    if not dest_path.exists():
        dest_path.mkdir()
    elif not dest_path.is_dir():
        _error(f"Not a directory: {dest_path}")
        return

    item = _fetch_item(token, folder_id)

    if not item:
        _error(f"Item not found: {folder_id}")
        return

    if item.type != "folder":
        _error(f"Not a folder: {folder_id}")
        return

    def _export_item(item: Item, parent: Path):

        if item.type == "document":
            p = parent.joinpath(item.path.name + ".opml")
            export_document(token, item.id, False, p)

        elif item.type == "folder":
            p = parent.joinpath(item.path.name)
            if not p.exists():
                p.mkdir()
            for c in item.children:
                _export_item(c, p)

        else:
            _error(f"Unknown type: {item.type}: {item.id}")
            return

    for child in item.children:
        _export_item(child, dest_path)


def _get_remote_status(token: str, root_id: str) -> Optional[dict[str, dict]]:

    root_item = _fetch_item(token, root_id)

    if not root_item:
        _error(f"Folder not found on Dynalist: {root_id}")
        return None

    def _collect_document_id_path(item: Item):
        if item.type == "document":
            yield item.id, item.path
        elif item.type == "folder":
            for child in item.children:
                for i, p in _collect_document_id_path(child):
                    yield i, p
        else:
            _error(f"Unknown type: {item.type}: {item.id}")

    # document_id -> path の dict
    paths = {}
    for i, p in _collect_document_id_path(root_item):
        paths[i] = str(p.relative_to(root_item.path))

    document_ids = list(paths.keys())

    # document_id -> version の dict
    d = Dynalist(token)
    versions = d.check_for_updates(document_ids)["versions"]

    status = {}
    for i in document_ids:
        status[i] = {"path": paths[i], "version": versions[i]}

    return status


def _load_settings() -> dict:

    p = Path.cwd().joinpath(".dynalist.json")

    if not p.exists():
        raise FileNotFoundError(errno.ENOENT, os.strerror(errno.ENOENT), p)

    with p.open("r", encoding="utf-8") as f:
        settings = json.load(f)

    return settings


def _save_settings(json_data: dict) -> None:

    p = Path.cwd().joinpath(".dynalist.json")

    with p.open("w", encoding="utf-8") as f:
        json.dump(json_data, f, indent=2, ensure_ascii=False)


def status(token: str, output: TextIO = sys.stdout) -> None:

    try:
        settings = _load_settings()
    except FileNotFoundError as e:
        _error(str(e))
        return

    if "status" in settings:
        local_status = settings["status"]
    else:
        local_status = dict()

    remote_status = _get_remote_status(token, settings["root"])
    if not remote_status:
        remote_status = dict()

    # 辞書のキー（dict_key）は並び順が保持されている
    local_items = local_status.keys()
    remote_items = remote_status.keys()

    # 並び順を保つため set ではなく list を使う
    # dict_key を集合演算すると set になり並び順が崩れる
    remote_only_items = []
    local_only_items = []
    remote_newer_items = []
    local_newer_items = []
    same_version_items = []
    replace_existing = []

    for id in remote_items:

        if id not in local_items:
            remote_only_items.append(id)
            continue

        lv = local_status[id]["version"]
        rv = remote_status[id]["version"]
        if lv > rv:
            local_newer_items.append(id)
        elif lv < rv:
            remote_newer_items.append(id)
        else:
            same_version_items.append(id)

    for id in local_items:

        if id not in remote_items:
            local_only_items.append(id)

        lp = local_status[id]["path"]
        for r in remote_status:
            rp = remote_status[r]["path"]
            if lp == rp and id != r:
                replace_existing.append(r)

    def _write_items(heading: str, item_ids: list[str]):

        output.write(f"{heading}:\n\n")

        for id in item_ids:

            if id in local_status:
                lp = local_status[id]["path"]
                output.write(f"\t{lp}")

                if id in remote_status:
                    rp = remote_status[id]["path"]
                    if lp != rp:
                        output.write(f" => {rp}")

            elif id in remote_status:
                rp = remote_status[id]["path"]
                output.write(f"\t{rp}")

            if id in replace_existing:
                output.write(" *")

            output.write("\n")

        output.write("\n")

    if remote_only_items:
        _write_items("New (found only on remote)", remote_only_items)

    if local_only_items:
        _write_items("Deleted (found only on local)", local_only_items)

    if remote_newer_items:
        _write_items("Modified (remote is newer than local)", remote_newer_items)

    if local_newer_items:
        _write_items("Outdated (local is newer than remote)", local_newer_items)

    if same_version_items:
        _write_items("No Changes", same_version_items)


def update(token: str) -> None:

    try:
        settings = _load_settings()
    except FileNotFoundError as e:
        _error(str(e))
        return

    if "root" in settings:
        root_id = settings["root"]
    else:
        _error("Invalid settings file")
        return

    if "dest" in settings:
        dest_dir = Path(settings["dest"])
    else:
        dest_dir = Path.cwd()

    export_folder(token, root_id, dest_dir)

    settings["status"] = _get_remote_status(token, root_id)
    _save_settings(settings)


def _parse_args() -> argparse.Namespace:

    parser = argparse.ArgumentParser()
    parser.add_argument("-t", "--token", type=str, default=None)

    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("-l", "--list", action="store_true")
    group.add_argument("-e", "--export", type=str, dest="document_id", default=None)

    return parser.parse_args()


def _load_token() -> str:

    # プロジェクトの設定ファイル
    try:
        settings = _load_settings()
    except FileNotFoundError:
        settings = None

    if settings and "token" in settings:
        return settings["token"]

    # 環境変数
    token = os.getenv("DYNALIST_TOKEN")
    if token:
        return token

    def _read_token(file_path: Path) -> Optional[str]:
        if not file_path.exists():
            return None
        with file_path.open("r", encoding="utf-8") as f:
            token = f.readline().strip()
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
