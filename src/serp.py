"""DataForSEO response adapter; deliberately contains no network client yet."""
from dataclasses import dataclass
from .urls import normalize_url
from urllib.parse import urlsplit

class SerpError(ValueError):
    """An unusable or unsuccessful response, safe to surface to the operator."""

@dataclass(frozen=True)
class OrganicResult:
    position: int
    url: str

def build_task(keyword: str, depth: int = 10) -> dict:
    if not isinstance(keyword, str) or not keyword.strip():
        raise ValueError("Keyword must not be empty")
    if type(depth) is not int or depth not in (10, 20, 40):
        raise ValueError("Depth must be 10, 20 or 40")
    return {"keyword": keyword.strip(), "location_name": "Canada", "language_code": "en",
            "device": "mobile", "os": "android", "se_domain": "google.ca", "depth": depth,
            "resolve_goto_urls": True}

def is_google_redirect(url: str) -> bool:
    parts = urlsplit(url)
    host = (parts.hostname or "").lower()
    return (host == "google.ca" or host.endswith(".google.ca") or host == "google.com" or host.endswith(".google.com")) and parts.path.rstrip("/") in ("/goto", "/url")

def parse_response(payload: object) -> list[OrganicResult]:
    if not isinstance(payload, dict) or payload.get("status_code") != 20000:
        raise SerpError("DataForSEO response failed or has an invalid status")
    tasks = payload.get("tasks")
    if not isinstance(tasks, list) or len(tasks) != 1 or not isinstance(tasks[0], dict):
        raise SerpError("Expected exactly one task")
    task = tasks[0]
    if task.get("status_code") != 20000:
        raise SerpError("DataForSEO task failed")
    results = task.get("result")
    if not isinstance(results, list) or len(results) != 1 or not isinstance(results[0], dict):
        raise SerpError("Missing search result")
    items = results[0].get("items")
    if not isinstance(items, list):
        raise SerpError("Missing result items")
    found, positions = [], set()
    for item in items:
        if not isinstance(item, dict):
            raise SerpError("Invalid result item")
        if item.get("type") != "organic":
            continue
        rank, url = item.get("rank_group"), item.get("url")
        if type(rank) is not int or rank < 1 or not isinstance(url, str):
            raise SerpError("Invalid organic result")
        if rank > 10:
            continue
        if rank in positions:
            raise SerpError("Duplicate organic rank")
        try:
            normalized = normalize_url(url)
        except ValueError as exc:
            raise SerpError("Invalid organic URL") from exc
        positions.add(rank)
        found.append(OrganicResult(rank, normalized))
    if not found:
        raise SerpError("No organic results; refusing to overwrite existing data")
    return sorted(found, key=lambda result: result.position)
