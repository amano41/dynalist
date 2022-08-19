#!/usr/bin/env python3

import argparse
import os
import sys


def _create_item_map(item_list):
    map = dict()
    for item in item_list:
        map[item["id"]] = item
    return map


def _find_root_folder(item_map):
    def _is_root_folder(id):
        for item in item_map.values():
            if "children" not in item:
                continue
            if id in item["children"]:
                return False
        return True

    for id in item_map.keys():
        if _is_root_folder(id):
            return id

    abort("root folder not found")


def _find_files(root_file_id, item_map):
    def _find_files_recursive(file_id, path):

        item = item_map[file_id]
        type = item["type"]
        path = path + "/" + item["title"]

        if type == "document":
            yield (file_id, path)
        elif type == "folder":
            yield (file_id, path + "/")
            for child_id in item["children"]:
                yield from _find_files_recursive(child_id, path)
        else:
            error("unknown file type: {} ({})".format(type, path))
            yield (file_id, path)

    item = item_map[root_file_id]
    for child_id in item["children"]:
        yield from _find_files_recursive(child_id, "")


def _escape(text):

    if not hasattr(_escape, "table"):
        table = {"&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&apos;"}
        _escape.table = str.maketrans(table)

    return text.translate(_escape.table)


def _write_node(node_id, level, item_map, file=sys.stdout):

    node = item_map[node_id]

    attr = ' text="{}"'.format(_escape(node["content"]))

    if "note" in node and node["note"] != "":
        attr = attr + ' note="{}"'.format(_escape(node["note"]))

    if "checked" in node and node["checked"] == "true":
        attr = attr + ' checked="true"'

    if "collapsed" in node and node["collapsed"] == "true":
        attr = attr + ' collapsed="true"'

    indent = "\t" * level

    if "children" in node:
        file.write(indent + "<outline" + attr + ">\n")
        level = level + 1
        for child_id in node["children"]:
            _write_node(child_id, level, item_map, file)
        file.write(indent + "</outline>\n")
    else:
        file.write(indent + "<outline" + attr + "/>\n")


def print_file_list(token, file=sys.stdout):

    json_data = file_list(token)
    item_map = _create_item_map(json_data["files"])

    root_file_id = json_data["root_file_id"]

    if root_file_id not in item_map:
        root_file_id = _find_root_folder(item_map)

    for id, path in _find_files(root_file_id, item_map):
        file.write("{}\t{}\n".format(id, path))


def export_document(token, file_id, file=sys.stdout):

    opml_head = (
        '<?xml version="1.0" encoding="utf-8"?>\n'
        '<opml version="2.0">\n'
        "\t<head>\n"
        "\t\t<title>{}</title>\n"
        "\t\t<flavor>dynalist</flavor>\n"
        "\t\t<source>https://dynalist.io</source>\n"
        "\t</head>\n"
        "\t<body>\n"
    )

    opml_tail = "\t</body>\n" "</opml>\n"

    json_data = doc_read(token, file_id)
    item_map = _create_item_map(json_data["nodes"])

    opml_head = opml_head.format(json_data["title"])

    file.write(opml_head)

    root_node = item_map["root"]
    if "children" in root_node:
        for child_id in root_node["children"]:
            _write_node(child_id, 2, item_map, file)

    file.write(opml_tail)


def _parse_args():

    parser = argparse.ArgumentParser()
    parser.add_argument("-t", "--token", type=str, default=None)

    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("-l", "--list", action="store_true")
    group.add_argument("-e", "--export", type=str, dest="document_id", default=None)

    return parser.parse_args()


def _load_token(filename):

    if not os.path.exists(filename):
        abort("settings file not found: {}".format(filename))

    with open(filename, "r") as f:
        token = f.readline().strip()

    return token


def error(message):
    print("error: " + message, file=sys.stderr)


def abort(message):
    error(message)
    sys.exit(1)


def main():

    args = _parse_args()

    token = args.token

    if token is None:
        filename = os.path.expanduser("~/.dynalistrc")
        token = _load_token(filename)

    if args.list:
        print_file_list(token)

    if args.document_id is not None:
        export_document(token, args.document_id)


if __name__ == "__main__":
    main()
