"""Conservative discovery of public email contacts on the same site.

Addresses are candidates for manual review, not verified partnership contacts.
"""
from html.parser import HTMLParser
import re
from urllib.parse import urljoin, urlsplit, urlunsplit

_EMAIL = re.compile(r"(?<![\w.+-])([A-Z0-9.!#$%&'*+/=?^_`{|}~-]+@[A-Z0-9.-]+\.[A-Z]{2,})(?![\w@-]|\.[A-Z0-9])", re.I)
_TERMS = re.compile(r"contact|partner|advertis|media|business|work-with-us", re.I)
_LINK_LABEL = re.compile(r"\b(?:contact(?:\s+us)?|get\s+in\s+touch|partnerships?|advertis(?:e|ing)|media\s+inquiries|work\s+with\s+us)\b", re.I)
_OUTREACH = re.compile(r"advertis|partner|business|media|editor|contact", re.I)


class _Links(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.urls = []
        self.link = None
        self.label = []
    def handle_starttag(self, tag, attrs):
        if tag == 'a':
            self.link = next((value for key, value in attrs if key == 'href' and value), None)
            self.label = []
    def handle_data(self, text):
        if self.link is not None:
            self.label.append(text)
    def handle_endtag(self, tag):
        if tag == 'a' and self.link is not None:
            self.urls.append((self.link, ' '.join(self.label)))
            self.link, self.label = None, []


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
    links = parser.urls + [(url, label) for label, url in re.findall(r'\[([^\]\n]{1,150})\]\((https?://[^\s)]+|/[^\s)]+)\)', markdown, re.I)]
    candidates = []
    for link, label in links:
        try:
            full = urlsplit(urljoin(page_url, link))
            if full.scheme != page.scheme or full.hostname != page.hostname or full.port != page.port or full.username or full.password:
                continue
            if not _TERMS.search(full.path) and not _LINK_LABEL.search(label):
                continue
            url = urlunsplit((full.scheme, full.netloc, full.path, full.query, ''))
            if url != page_url and url not in candidates:
                candidates.append(url)
        except ValueError:
            continue
    candidates.sort(key=lambda url: (0 if re.search(r'contact', urlsplit(url).path, re.I) else 1, url))
    return candidates[:limit]


def public_email_candidates(text: str) -> list[str]:
    """Return observed addresses, including explicit [at]/[dot] obfuscation."""
    # Decode only explicit bracketed separators. Never generate mailbox names
    # or guess an address from a domain or a generic contact page.
    text = re.sub(r'(?<=\w)\s*(?:\[at\]|\(at\))\s*(?=\w)', '@', text, flags=re.I)
    text = re.sub(r'(?<=\w)\s*(?:\[dot\]|\(dot\))\s*(?=\w)', '.', text, flags=re.I)
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


def cloudflare_email_candidates(content: bytes, charset: str) -> list[str]:
    """Decode public Cloudflare-protected email links in fetched HTML.

    Only explicit email-protection attributes are considered; these addresses
    remain unverified candidates just like addresses visible as plain text.
    """
    try:
        html = content.decode(charset, errors='replace')
    except LookupError:
        return []

    class ProtectedEmails(HTMLParser):
        def __init__(self):
            super().__init__(convert_charrefs=True)
            self.encoded = []

        def handle_starttag(self, tag, attrs):
            if tag not in ('a', 'span'):
                return
            for key, value in attrs:
                if not value:
                    continue
                if key == 'data-cfemail':
                    self.encoded.append(value)
                elif key == 'href' and '/cdn-cgi/l/email-protection#' in value:
                    self.encoded.append(value.rsplit('#', 1)[-1])

    parser = ProtectedEmails()
    try:
        parser.feed(html)
    except (ValueError, RecursionError):
        return []
    decoded = []
    for value in parser.encoded:
        try:
            raw = bytes.fromhex(value)
            if len(raw) < 2 or len(raw) > 255:
                continue
            address = bytes(char ^ raw[0] for char in raw[1:]).decode('ascii')
        except (ValueError, UnicodeDecodeError):
            continue
        if _EMAIL.fullmatch(address):
            decoded.extend(public_email_candidates(address))
    return list(dict.fromkeys(decoded))


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
