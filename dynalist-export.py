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


def _fetch_item_list(token: str) -> dict:
    """fetch list of all documents and folders"""

    d = Dynalist(token)
    try:
        json_data = d.list_files()
    except Exception:
        raise
    return json_data


def _build_item_tree(json_data: dict, root_id: str) -> Item:
    """build a tree structure from a list of items in json data"""

    def _create_node(item_id: str, item_table: dict, parent_path: PurePosixPath) -> Item:

        if item_id not in item_table:
            raise RuntimeError(f"Invalid item ID: {root_id}")

        entry = item_table[item_id]

        path = parent_path.joinpath(entry["title"])
        item = Item(entry["id"], entry["type"], path)

        if "children" in entry:
            for child in entry["children"]:
                try:
                    child_item = _create_node(child, item_table, path)
                except Exception as e:
                    _error(str(e))
                    continue
                item.children.append(child_item)

        return item

    item_table = {x["id"]: x for x in json_data["files"]}
    item_table[json_data["root_file_id"]]["title"] = "/"

    try:
        item = _create_node(root_id, item_table, PurePosixPath())
    except Exception:
        raise
    return item


def _fetch_item(token: str, root_id: Optional[str] = None) -> Item:
    """fetch a document or folder and its descendants as an item tree"""

    try:
        json_data = _fetch_item_list(token)
        if root_id:
            item = _build_item_tree(json_data, root_id)
        else:
            item = _build_item_tree(json_data, json_data["root_file_id"])
    except Exception:
        raise

    return item


def list_items(token: str, root_id: Optional[str] = None, sort: bool = False, output: TextIO = sys.stdout):
    """display a list of items with their IDs"""

    def _list(item: Item, sort: bool, output: TextIO):
        if item.type == "document":
            output.write(f"{item.path} [{item.id}]\n")
        elif item.type == "folder":
            if str(item.path) == "/":
                output.write(f"{item.path} [{item.id}]\n")
            else:
                output.write(f"{item.path}/ [{item.id}]\n")
            if sort:
                children = sorted(item.children, key=lambda x: x.path)
            else:
                children = item.children
            for child in children:
                _list(child, sort, output)
        else:
            _error(f"Unknown type: {item.type}: {item.path} [{item.id}]")

    try:
        item = _fetch_item(token, root_id)
    except Exception as e:
        _error(str(e))
        return

    _list(item, sort, output)


def tree_items(token: str, root_id: Optional[str] = None, sort: bool = False, output: TextIO = sys.stdout):
    """display a tree of items with their IDs"""

    def _tree(item: Item, indent: str, last_child: bool, sort: bool, output: TextIO):
        if last_child:
            branch = "└─"
        else:
            branch = "├─"
        if item.type == "document":
            output.write(f"{indent}{branch} {item.path.name} [{item.id}]\n")
        elif item.type == "folder":
            output.write(f"{indent}{branch} {item.path.name}/ [{item.id}]\n")
            if last_child:
                indent = indent + "　　"
            else:
                indent = indent + "│　"
            if sort:
                children = sorted(item.children, key=lambda x: x.path)
            else:
                children = item.children
            num = len(children)
            for index, child in enumerate(children):
                _tree(child, indent, index == num - 1, sort, output)
        else:
            _error(f"Unknown type: {item.type}: {item.id}")

    try:
        item = _fetch_item(token, root_id)
    except Exception as e:
        _error(str(e))
        return

    if item.type == "document":
        output.write(f"{item.path.name} [{item.id}]\n")
    elif item.type == "folder":
        output.write(f"{item.path.name}/ [{item.id}]\n")
        if sort:
            children = sorted(item.children, key=lambda x: x.path)
        else:
            children = item.children
        num = len(children)
        for index, child in enumerate(children):
            _tree(child, "", index == num - 1, sort, output)
    else:
        _error(f"Unknown type: {item.type}: {item.path} [{item.id}]")


def find_item(token: str, pattern: str, ignore_case: bool = False, sort: bool = False, output: TextIO = sys.stdout):
    """display items whose names match the pattern with their IDs"""

    def _find(item: Item, pattern: Pattern, sort: bool, output: TextIO):
        if pattern.search(item.path.name):
            if item.type == "document":
                output.write(f"{item.path} [{item.id}]\n")
            elif item.type == "folder":
                output.write(f"{item.path}/ [{item.id}]\n")
            else:
                _error(f"Unknown type: {item.type}: {item.path} [{item.id}]")
        if item.type == "folder":
            if sort:
                children = sorted(item.children, key=lambda x: x.path)
            else:
                children = item.children
            for child in children:
                _find(child, pattern, sort, output)

    try:
        item = _fetch_item(token)
    except Exception as e:
        _error(str(e))
        return

    if ignore_case:
        _find(item, re.compile(pattern, re.IGNORECASE), sort, output)
    else:
        _find(item, re.compile(pattern), sort, output)


def _write_node(node_id: str, node_table: dict, indent_level: int = 0, output: TextIO = sys.stdout):
    """output a document node as an OPML element"""

    if node_id not in node_table:
        raise RuntimeError(f"Invalid node ID: {node_id}")

    node = node_table[node_id]

    name = "outline"
    parts = [name]

    if "content" in node:
        text = html.escape(node["content"])
        parts.append(f'text="{text}"')

    if "note" in node and node["note"]:
        note = html.escape(node["note"])
        parts.append(f'_note="{note}"')

    if "checkbox" in node and node["checkbox"]:
        parts.append('checkbox="true"')

    if "checked" in node and node["checked"]:
        parts.append('complete="true"')

    if "color" in node and node["color"] != 0:
        color = node["color"]
        parts.append(f'colorLabel="{color}"')

    if "numbered" in node and node["numbered"]:
        parts.append('listStyle="arabic"')

    if "collapsed" in node and node["collapsed"]:
        parts.append('collapsed="true"')

    indent = "\t" * indent_level

    if "children" in node:
        s = "<" + " ".join(parts) + ">"
        e = "</" + name + ">"
        output.write(indent + s + "\n")
        for c in node["children"]:
            _write_node(c, node_table, indent_level + 1, output)
        output.write(indent + e + "\n")
    else:
        e = "<" + " ".join(parts) + "/>"
        output.write(indent + e + "\n")


def _write_document(json_data: dict, root_node: bool = False, output: TextIO = sys.stdout):
    """output a document in OPML fromat"""

    # fmt: off
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

    OPML_TAIL: Final[str] = (
        "\t</body>\n"
        "</opml>\n"
    )
    # fmt: on

    node_table = {x["id"]: x for x in json_data["nodes"]}

    output.write(OPML_HEAD.format(json_data["title"]))
    if root_node:
        _write_node("root", node_table, 2, output)
    else:
        node = node_table["root"]
        if "children" in node:
            for child_id in node["children"]:
                _write_node(child_id, node_table, 2, output)
    output.write(OPML_TAIL)


def export_document(
    token: str, document_id: str, root_node: bool = False, dest_file: Union[str, PathLike] = ""
) -> None:

    d = Dynalist(token)
    try:
        json_data = d.read_doc(document_id)
    except Exception:
        raise

    if dest_file == "-":
        _write_document(json_data, root_node, sys.stdout)
        return

    if dest_file == "":
        p = Path(json_data["title"] + ".opml")
    else:
        p = Path(dest_file)

    with p.open("w", encoding="utf-8") as f:
        _write_document(json_data, root_node, f)


def export_folder(token: str, folder_id: str, dest_dir: Union[str, PathLike] = "") -> None:

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


def export(token: str, item_id: str, dest_path: Union[str, PathLike] = "") -> None:

    try:
        json_data = _fetch_item_list(token)
    except Exception:
        raise

    for item in json_data["files"]:
        if item["id"] == item_id:
            item_type = item["type"]
            break
    else:
        _error(f"Item not found: {item_id}")
        return

    if item_type == "document":
        export_document(token, item_id, False, dest_path)
    elif item_type == "folder":
        export_folder(token, item_id, dest_path)
    else:
        _error(f"Unknown type: {item_type}: {item_id}")


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
    try:
        json_data = d.check_for_updates(document_ids)
    except Exception:
        raise
    versions = json_data["versions"]

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

    parser.add_argument("-T", "--token")

    group = parser.add_argument_group("exporting", "export a single document or by a folder")
    group.add_argument("-e", "--export", metavar="ID")
    group.add_argument("-o", "--out", metavar="PATH")

    group = parser.add_argument_group("querying", "retrieve a list of items or search for items")
    group.add_argument("-l", "--list", metavar="ID", nargs="?", const="root")
    group.add_argument("-t", "--tree", metavar="ID", nargs="?", const="root")
    group.add_argument("-U", "--no-sort", action="store_false", dest="sort")
    group.add_argument("-f", "--find", metavar="PATTERN")
    group.add_argument("-i", "--ignore-case", action="store_true")

    group = parser.add_argument_group("mirroring", "mirror a remote folder to a local directory")
    group.add_argument("-s", "--status", action="store_true")
    group.add_argument("-u", "--update", action="store_true")

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

    if args.token:
        token = args.token
    else:
        try:
            token = _load_token()
        except Exception as e:
            print(e)
            return

    if args.list:
        if args.list == "root":
            list_items(token, None, args.sort)
        else:
            list_items(token, args.list, args.sort)
        return

    if args.tree:
        if args.tree == "root":
            tree_items(token, None, args.sort)
        else:
            tree_items(token, args.tree, args.sort)
        return

    if args.find:
        find_item(token, args.find, args.ignore_case, args.sort)
        return

    if args.export:
        if args.out:
            export(token, args.export, args.out)
        else:
            export(token, args.export)

    if args.status:
        status(token)

    if args.update:
        update(token)


if __name__ == "__main__":
    main()
