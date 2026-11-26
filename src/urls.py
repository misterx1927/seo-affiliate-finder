"""URL normalization; remove known advertising parameters, preserve functional ones."""
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

TRACKING = {"gclid", "fbclid", "msclkid", "dclid", "mc_cid", "mc_eid"}

def normalize_url(url: str) -> str:
    parts = urlsplit(url.strip())
    if parts.scheme.lower() not in {"http", "https"} or not parts.hostname or parts.username or parts.password:
        raise ValueError("Expected a public HTTP(S) URL without credentials")
    host = parts.hostname.lower().encode("idna").decode("ascii")
    if ":" in host:
        host = f"[{host}]"
    port = parts.port
    netloc = host + (f":{port}" if port and (parts.scheme.lower(), port) not in {("http", 80), ("https", 443)} else "")
    params = [(k, v) for k, v in parse_qsl(parts.query, keep_blank_values=True)
              if not (k.lower().startswith("utm_") or k.lower() in TRACKING)]
    return urlunsplit((parts.scheme.lower(), netloc, parts.path or "/", urlencode(params, doseq=True), ""))
