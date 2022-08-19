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
