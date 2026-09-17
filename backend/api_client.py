"""
Faithful port of soft.py's API interaction.
- POST {BASE_URL}/search  with {"type","query","page"} + Bearer auth
- If response has "id" -> poll GET {BASE_URL}/search/{id} until response is not None
  (HTTP 501 means "still processing")
- GET {BASE_URL}/me  -> key info
API key comes ONLY from env: JITLER_API_KEY.
"""

import os
import time
import requests

BASE_URL = os.environ.get("JITLER_BASE_URL", "https://api.jitler.top")
POLL_TIMEOUT = int(os.environ.get("JITLER_POLL_TIMEOUT", "60"))
POLL_INTERVAL = 3

VALID_SEARCH_TYPES = ("number", "vks", "sherlock")


def _api_key() -> str:
    return os.environ.get("JITLER_API_KEY", "")


def _json_headers() -> dict:
    return {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {_api_key()}",
    }


def _auth_headers() -> dict:
    return {"Authorization": f"Bearer {_api_key()}"}


def _wait_for_result(task_id) -> dict:
    url = f"{BASE_URL}/search/{task_id}"
    start = time.time()
    while time.time() - start < POLL_TIMEOUT:
        try:
            resp = requests.get(url, headers=_auth_headers(), timeout=10)
        except requests.RequestException as e:
            return {"error": "NETWORK_ERROR", "detail": str(e)}

        if resp.status_code == 501:
            time.sleep(POLL_INTERVAL)
            continue
        if resp.status_code != 200:
            return {"error": "API_ERROR", "status_code": resp.status_code}

        try:
            data = resp.json()
        except ValueError:
            return {"error": "INVALID_API_RESPONSE"}

        if data.get("result") is True:
            response = data.get("response")
            if response is not None:
                return {"data": response}
            time.sleep(POLL_INTERVAL)
            continue
        return {"error": "API_ERROR", "detail": data}

    return {"error": "API_TIMEOUT"}


def search_request(search_type: str, query: str, page: int = 1) -> dict:
    """
    Mirrors soft.py::search_request.
    Returns {"data": <response>} on success, or {"error": ..., ...} on failure.
    """
    if search_type not in VALID_SEARCH_TYPES:
        return {"error": "INVALID_SEARCH_TYPE"}
    if not query:
        return {"error": "EMPTY_QUERY"}
    if not _api_key():
        return {"error": "SERVER_MISCONFIGURED", "detail": "JITLER_API_KEY missing"}

    url = f"{BASE_URL}/search"
    payload = {"type": search_type, "query": query, "page": page}

    try:
        resp = requests.post(
            url, headers=_json_headers(), json=payload, timeout=30
        )
    except requests.RequestException as e:
        return {"error": "NETWORK_ERROR", "detail": str(e)}

    if resp.status_code != 200:
        return {"error": "API_ERROR", "status_code": resp.status_code}

    try:
        result = resp.json()
    except ValueError:
        return {"error": "INVALID_API_RESPONSE"}

    if result.get("result") is not True:
        return {"error": "API_ERROR", "detail": result}

    if "id" in result:
        return _wait_for_result(result["id"])

    return {"data": result.get("response", [])}


def get_me() -> dict:
    if not _api_key():
        return {"error": "SERVER_MISCONFIGURED", "detail": "JITLER_API_KEY missing"}
    try:
        resp = requests.get(
            f"{BASE_URL}/me", headers=_auth_headers(), timeout=10
        )
    except requests.RequestException as e:
        return {"error": "NETWORK_ERROR", "detail": str(e)}

    if resp.status_code != 200:
        return {"error": "API_ERROR", "status_code": resp.status_code}
    try:
        return {"data": resp.json()}
    except ValueError:
        return {"error": "INVALID_API_RESPONSE"}
