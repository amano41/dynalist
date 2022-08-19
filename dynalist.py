"""
Wrapper class for Dyanlist API
"""

import json
import sys
from collections import OrderedDict
from typing import Final, Literal, Optional
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


class Dynalist:

    END_POINT: Final[str] = "https://dynalist.io/api/v1/"

    def __init__(self, token):
        self.token = token

    def _post(self, method: str, json_data: dict) -> dict:

        url = self.END_POINT + method
        data = json.dumps(json_data).encode("utf-8")
        headers = {"Content-Type": "application/json", "User-Agent": "Mozilla/5.0"}

        request = Request(url, data, headers)

        try:
            with urlopen(request) as response:
                body = response.read().decode("utf-8")
                result = json.loads(body, object_pairs_hook=OrderedDict)
        except HTTPError as e:
            print(f"error: HTTP {e.code} {e.reason}", file=sys.stderr)
            raise
        except URLError as e:
            print(f"error: {e.reason}", file=sys.stderr)
            raise

        if result["_code"].lower() != "ok":
            print(f"error: {result['_msg']}", file=sys.stderr)

        return result

    def list_files(self) -> dict:

        method = "file/list"
        json_data = {"token": self.token}

        return self._post(method, json_data)

    def edit_file(self, changes: list[dict]) -> dict:

        method = "file/edit"
        json_data = {"token": self.token, "changes": changes}

        return self._post(method, json_data)

    def move_file(self, file_type: Literal["folder", "document"], file_id: str, parent_id: str, index: int) -> dict:

        changes = [{"action": "move", "type": file_type, "file_id": file_id, "parent_id": parent_id, "index": index}]

        return self.edit_file(changes)

    def rename_file(self, file_type: Literal["folder", "document"], file_id: str, title: str) -> dict:

        changes = [{"action": "edit", "type": file_type, "file_id": file_id, "title": title}]

        return self.edit_file(changes)

    def create_file(
        self, file_type: Literal["folder", "document"], parent_id: str, index: int, title: Optional[str] = None
    ) -> dict:

        changes = [{"action": "create", "type": file_type, "parent_id": parent_id, "index": index}]

        if title is not None:
            changes[0]["title"] = title

        return self.edit_file(changes)

    def read_doc(self, document_id: str) -> dict:

        method = "doc/read"
        json_data = {"token": self.token, "file_id": document_id}

        return self._post(method, json_data)

    def check_for_updates(self, document_ids: list[str]) -> dict:

        method = "doc/check_for_updates"
        json_data = {"token": self.token, "file_ids": document_ids}

        return self._post(method, json_data)

    def edit_doc(self, document_id: str, changes: list[dict]) -> dict:

        method = "doc/edit"
        json_data = {"token": self.token, "file_id": document_id, "changes": changes}

        return self._post(method, json_data)

    def insert_node(
        self,
        document_id: str,
        parent_node_id: str,
        index: int,
        content: str,
        note: Optional[str] = None,
        checked: bool = False,
        checkbox: bool = False,
        heading: int = 0,
        color: int = 0,
    ) -> dict:

        changes = [
            {
                "action": "insert",
                "parent_id": parent_node_id,
                "index": index,
                "content": content,
                "checked": checked,
                "checkbox": checkbox,
                "heading": heading,
                "color": color,
            }
        ]

        if note is not None:
            changes[0]["note"] = note

        return self.edit_doc(document_id, changes)

    def update_node(
        self,
        document_id: str,
        target_node_id: str,
        content: Optional[str] = None,
        note: Optional[str] = None,
        checked: bool = False,
        checkbox: bool = False,
        heading: int = 0,
        color: int = 0,
    ) -> dict:

        changes = [
            {
                "action": "edit",
                "node_id": target_node_id,
                "checked": checked,
                "checkbox": checkbox,
                "heading": heading,
                "color": color,
            }
        ]

        if content is not None:
            changes[0]["content"] = content

        if note is not None:
            changes[0]["note"] = note

        return self.edit_doc(document_id, changes)

    def move_node(self, document_id: str, target_node_id: str, parent_node_id: str, index: int) -> dict:

        changes = [{"action": "move", "node_id": target_node_id, "parent_id": parent_node_id, "index": index}]

        return self.edit_doc(document_id, changes)

    def delete_node(self, document_id: str, target_node_id: str) -> dict:

        changes = [{"action": "delete", "node_id": target_node_id}]

        return self.edit_doc(document_id, changes)

    def add_to_inbox(
        self,
        index: int,
        content: str,
        note: Optional[str] = None,
        checked: bool = False,
        checkbox: bool = False,
        heading: int = 0,
        color: int = 0,
    ) -> dict:

        method = "inbox/add"
        json_data = {
            "token": self.token,
            "index": index,
            "content": content,
            "checked": checked,
            "checkbox": checkbox,
            "heading": heading,
            "color": color,
        }

        if note is not None:
            json_data["note"] = note

        return self._post(method, json_data)

    def upload_file(self, file_name: str, content_type: str, base64_data: str) -> dict:

        method = "upload"
        json_data = {"token": self.token, "filename": file_name, "content_type": content_type, "data": base64_data}

        return self._post(method, json_data)

    def get_pref(self, key: Literal["inbox_location", "inbox_move_position"]) -> dict:

        method = "pref/get"
        json_data = {"token": self.token, "key": key}

        return self._post(method, json_data)

    def set_pref(self, key: Literal["inbox_location", "inbox_move_position"], value: str) -> dict:

        method = "pref/set"
        json_data = {"token": self.token, "key": key, "value": value}

        return self._post(method, json_data)
