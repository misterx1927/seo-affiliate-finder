"""Conservative discovery of public email contacts on the same site.

Addresses are candidates for manual review, not verified partnership contacts.
"""
from html.parser import HTMLParser
import re
from urllib.parse import urljoin, urlsplit, urlunsplit

_EMAIL = re.compile(r"(?<![\w.+-])([A-Z0-9.!#$%&'*+/=?^_`{|}~-]+@[A-Z0-9.-]+\.[A-Z]{2,})(?![\w@-]|\.[A-Z0-9])", re.I)
_TERMS = re.compile(r"contact|partner|advertis|media|business|work-with-us", re.I)
_OUTREACH = re.compile(r"advertis|partner|business|media|editor|contact", re.I)


class _Links(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.urls = []
    def handle_starttag(self, tag, attrs):
        if tag == 'a':
            self.urls.extend(value for key, value in attrs if key == 'href' and value)


def contact_pages(content: bytes, charset: str, page_url: str, limit: int = 2) -> list[str]:
    """Return at most two URLs on the same origin; never follow external links."""
    if not 1 <= limit <= 2:
        raise ValueError('Contact page limit must be one or two')
    page = urlsplit(page_url)
    if page.scheme not in ('https', 'http') or not page.hostname or page.username or page.password:
        return []
    try:
        html = content.decode(charset, errors='replace')
    except LookupError:
        return []
    parser = _Links()
    try:
        parser.feed(html)
    except (ValueError, RecursionError):
        return []
    # Provider markdown may be stored inside a safe, escaped HTML container.
    from html import unescape
    markdown = unescape(html)
    links = parser.urls + re.findall(r'\[[^\]\n]{1,150}\]\((https?://[^\s)]+|/[^\s)]+)\)', markdown, re.I)
    candidates = []
    for link in links:
        try:
            full = urlsplit(urljoin(page_url, link))
            if full.scheme != page.scheme or full.hostname != page.hostname or full.port != page.port or full.username or full.password:
                continue
            if not _TERMS.search(full.path):
                continue
            url = urlunsplit((full.scheme, full.netloc, full.path, full.query, ''))
            if url != page_url and url not in candidates:
                candidates.append(url)
        except ValueError:
            continue
    candidates.sort(key=lambda url: (0 if re.search(r'contact', urlsplit(url).path, re.I) else 1, url))
    return candidates[:limit]


def public_email_candidates(text: str) -> list[str]:
    """Return email addresses literally present in visible content, deduplicated."""
    emails, seen = [], set()
    for match in _EMAIL.finditer(text):
        email = match.group(1).rstrip('.')
        local, _, host = email.partition('@')
        if host.lower() in ('example.com', 'example.org', 'example.net') or local.lower() in ('noreply', 'no-reply', 'donotreply'):
            continue
        if email.casefold() not in seen:
            seen.add(email.casefold())
            emails.append(email)
    return emails


def choose_contact(emails: list[str], source_url: str) -> str | None:
    """Only accept same-host mailboxes and never guess between ambiguous ones."""
    host = (urlsplit(source_url).hostname or '').lower().removeprefix('www.')
    if not host:
        return None
    same_host = [value for value in emails if value.partition('@')[2].lower() == host]
    if len(same_host) == 1:
        return same_host[0]
    selected = [value for value in same_host if _OUTREACH.search(value.partition('@')[0])]
    return selected[0] if len(selected) == 1 else None
