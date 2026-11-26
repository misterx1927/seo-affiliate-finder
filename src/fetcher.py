"""Bounded public-page downloader. Redirects are checked before every connection."""
import http.client
import ipaddress
import socket
import ssl
from urllib.parse import quote, urljoin, urlsplit
from .parser import MAX_HTML_BYTES, PageError
from .tls import tls_context

class FetchError(PageError):
    def __init__(self, message: str, transient: bool = False):
        super().__init__(message)
        self.transient = transient

class _PinnedHTTP(http.client.HTTPConnection):
    def __init__(self, host, port, ip, timeout):
        super().__init__(host, port, timeout=timeout)
        self.ip = ip
    def connect(self):
        self.sock = socket.create_connection((self.ip, self.port), self.timeout)

class _PinnedHTTPS(_PinnedHTTP):
    def connect(self):
        super().connect()
        self.sock = tls_context().wrap_socket(self.sock, server_hostname=self.host)

def _public_addresses(host: str, port: int) -> list[str]:
    try:
        addresses = list(dict.fromkeys(info[4][0] for info in socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)))
    except OSError as exc:
        raise FetchError("DNS lookup failed", transient=True) from exc
    if not addresses or any(not ipaddress.ip_address(address).is_global for address in addresses):
        raise FetchError("Non-public address blocked")
    return addresses


def _request_response(parts, host, port, addresses, target, timeout):
    """Try a few verified addresses if a connection fails, closing each failed socket."""
    last_error = None
    for address in addresses[:3]:
        connection = (_PinnedHTTPS if parts.scheme == "https" else _PinnedHTTP)(host, port, address, timeout)
        try:
            connection.request("GET", target, headers={"User-Agent": "SEOAffiliateFinder/0.1 (+manual research)", "Accept": "text/html,application/xhtml+xml", "Accept-Encoding": "identity"})
            return connection, connection.getresponse()
        except (OSError, http.client.HTTPException) as exc:
            last_error = exc
            connection.close()
    if isinstance(last_error, ssl.SSLCertVerificationError):
        detail = "TLS certificate verification failed"
    elif isinstance(last_error, (TimeoutError, socket.timeout)):
        detail = "Page connection timed out"
    elif isinstance(last_error, ConnectionRefusedError):
        detail = "Page connection refused"
    else:
        detail = "Page connection failed"
    raise FetchError(detail, transient=True) from last_error

def fetch_page(url: str, timeout: int = 15, max_redirects: int = 3, *, same_origin_only: bool = False) -> tuple[bytes, str]:
    """Fetch a public HTTP(S) page with fixed-IP connections, size/time limits, no cookies."""
    origin = None
    for _ in range(max_redirects + 1):
        parts = urlsplit(url)
        if parts.scheme not in ("http", "https") or not parts.hostname or parts.username or parts.password:
            raise FetchError("Invalid page URL")
        try:
            port = parts.port or (443 if parts.scheme == "https" else 80)
        except ValueError as exc:
            raise FetchError("Invalid port") from exc
        if port not in (80, 443): raise FetchError("Nonstandard port blocked")
        host = parts.hostname.encode("idna").decode("ascii")
        current_origin = (parts.scheme, host.lower(), port)
        if origin is None:
            origin = current_origin
        elif same_origin_only and current_origin != origin:
            raise FetchError("Cross-origin redirect blocked")
        addresses = _public_addresses(host, port)
        # HTTP request targets are ASCII; preserve existing escapes and encode Unicode.
        target = quote(parts.path or "/", safe="/%:@!$&'()*+,;=-._~")
        if parts.query: target += "?" + quote(parts.query, safe="/%:@!$&'()*+,;=?-._~")
        connection, response = _request_response(parts, host, port, addresses, target, timeout)
        try:
            if response.status in (301, 302, 303, 307, 308):
                location = response.getheader("Location")
                if not location: raise FetchError("Redirect missing location")
                url = urljoin(url, location)
                continue
            if response.status != 200: raise FetchError(f"Page returned HTTP {response.status}", transient=response.status in (408, 429, 500, 502, 503, 504))
            ctype = response.getheader("Content-Type", "")
            if "text/html" not in ctype.lower() and "application/xhtml+xml" not in ctype.lower():
                raise FetchError("Page is not HTML")
            length = response.getheader("Content-Length")
            if length and length.isdigit() and int(length) > MAX_HTML_BYTES: raise FetchError("Page exceeds size limit")
            content = response.read(MAX_HTML_BYTES + 1)
            if len(content) > MAX_HTML_BYTES: raise FetchError("Page exceeds size limit")
            charset = response.headers.get_content_charset() or "utf-8"
            return content, charset
        except (OSError, http.client.HTTPException) as exc:
            raise FetchError("Page connection failed", transient=True) from exc
        finally:
            connection.close()
    raise FetchError("Too many redirects")


def fetch_with_retry(url: str, attempts: int = 2, delay: float = 0.5):
    """Retry transient public-page failures only, with a strict cap."""
    import time
    if not 1 <= attempts <= 3: raise ValueError("Invalid retry count")
    for index in range(attempts):
        try:
            return fetch_page(url)
        except FetchError as exc:
            if not exc.transient or index + 1 == attempts: raise
            time.sleep(delay * (2 ** index))
