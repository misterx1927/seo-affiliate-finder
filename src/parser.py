"""Extract bounded, readable text from HTML without executing page scripts."""
from html.parser import HTMLParser
import re
from urllib.parse import unquote, urljoin, urlsplit, urldefrag

# Some ordinary pages include several megabytes of inline scripts and metadata.
# Keep a hard bound on the download/parser while accepting those pages.
MAX_HTML_BYTES = 8_000_000
MAX_TEXT_CHARS = 40_000

class PageError(ValueError):
    pass

def _check_interstitial(text: str, title: str = "") -> None:
    """Reject recognisable short challenge/region notices, not ordinary articles.

    A 200 status does not mean the requested page was returned. These limited
    heuristics are intentionally conservative; other interstitials can still
    require manual review.
    """
    # Challenges can contain long navigation or legal text. A distinctive
    # title plus a matching visible message is stronger evidence than length.
    # Require both so an article discussing CAPTCHAs is not discarded.
    challenge_title = title.casefold().strip()
    if (re.search(r"^(?:just a moment(?:\.\.\.|…|!)?|attention required\s*!?\s*(?:\|\s*cloudflare)?)$", challenge_title)
            and any(phrase in text[:8_000].casefold() for phrase in (
                "verify you are human", "checking your browser", "checking if the site connection is secure",
                "enable javascript and cookies to continue", "performing security verification"))):
        raise PageError("Possible access challenge; manual review required")
    if len(text) > 3_000:
        return
    opening = text[:1_000].casefold()
    # Some providers return a 200 response with a browser-check page padded
    # by navigation or legal text. The combination is specific to the gate;
    # an ordinary article mentioning JavaScript or robots alone is not enough.
    if ("verify that you're not a robot" in opening and
            ("javascript is disabled" in opening or "enable javascript" in opening)):
        raise PageError("Possible access challenge; manual review required")
    challenge = (
        "are you a robot", "êtes-vous un robot", "verify you are human",
        "checking your browser before accessing",
    )
    if any(phrase in opening for phrase in challenge):
        raise PageError("Possible access challenge; manual review required")
    if any(phrase in opening for phrase in ("ist in deinem gebiet", "not available in your region")):
        raise PageError("Possible regional mismatch; manual review required")

class _TextExtractor(HTMLParser):
    HIDDEN = {"script", "style", "noscript", "svg", "template", "iframe"}
    VOID = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "param", "source", "track", "wbr"}
    BLOCK = {"p", "div", "li", "h1", "h2", "h3", "h4", "section", "article", "br", "footer", "header"}
    def __init__(self, base_url=None):
        super().__init__(convert_charrefs=True)
        self.hidden = []
        self.parts = []
        self.in_title = False
        self.title_parts = []
        self.base_url = base_url
        self.anchor = None
    def handle_starttag(self, tag, attrs):
        attributes = {key.lower(): value for key, value in attrs}
        style = attributes.get("style") or ""
        explicitly_hidden = ("hidden" in attributes
                             or re.search(r"(?:^|;)\s*(?:display\s*:\s*none|visibility\s*:\s*hidden)\s*(?:!important\s*)?(?:;|$)", style, re.I))
        if self.hidden:
            if tag not in self.VOID:
                self.hidden.append(tag)
            return
        if tag in self.HIDDEN or explicitly_hidden:
            if tag not in self.VOID:
                self.hidden.append(tag)
            return
        if tag == "title" and not self.hidden:
            self.in_title = True
        if not self.hidden:
            if tag in self.BLOCK:
                self.parts.append("\n")
            if tag == "a":
                self.anchor = {"href": attributes.get("href") or "", "label": []}
                for key, value in attrs:
                    if key == "href" and value and value.lower().startswith("mailto:"):
                        # Percent-encoded addresses are common in public mailto
                        # links. Decode the address only, never the subject or body.
                        self.parts.append(" " + unquote(value[7:].split("?", 1)[0]) + " ")
    def handle_endtag(self, tag):
        if self.hidden:
            if tag in self.hidden:
                index = len(self.hidden) - 1 - self.hidden[::-1].index(tag)
                del self.hidden[index:]
            return
        if tag == "a" and self.anchor is not None:
            self._append_contact_link()
            self.anchor = None
        if tag == "title":
            self.in_title = False
        if tag in self.BLOCK:
            self.parts.append("\n")
    def handle_data(self, data):
        if not self.hidden:
            self.parts.append(data)
            if self.anchor is not None:
                self.anchor["label"].append(data)
            if self.in_title:
                self.title_parts.append(data)

    def _append_contact_link(self):
        """Preserve visible publisher contact links, not arbitrary outbound links."""
        if not self.base_url:
            return
        href = self.anchor["href"].strip()
        label = " ".join(self.anchor["label"]).casefold()
        if (not href or href.startswith(("#", "?")) or
                not re.search(r"\b(contact|advertis(?:e|ing)|partners?(?:hips?)?)\b", label)):
            return
        try:
            target = urldefrag(urljoin(self.base_url, href)).url
            origin, destination = urlsplit(self.base_url), urlsplit(target)
            if (origin.scheme not in ("http", "https") or destination.scheme not in ("http", "https")
                    or not origin.hostname or not destination.hostname or destination.username or destination.password
                    or destination.port not in (None, 80, 443)
                    or origin.hostname.lower().removeprefix("www.") != destination.hostname.lower().removeprefix("www.")):
                return
            if not destination.path or destination.path == "/":
                return
        except ValueError:
            return
        self.parts.append(" " + target + " ")

def extract_text(content: bytes, charset: str = "utf-8", *, base_url: str | None = None,
                 min_text_chars: int = 80) -> str:
    if min_text_chars < 1:
        raise ValueError("Minimum text length must be positive")
    if len(content) > MAX_HTML_BYTES:
        raise PageError("Page exceeds size limit")
    try:
        html = content.decode(charset, errors="replace")
    except LookupError as exc:
        raise PageError("Unsupported page encoding") from exc
    parser = _TextExtractor(base_url)
    try:
        parser.feed(html)
        parser.close()
    except (ValueError, RecursionError) as exc:
        raise PageError("Could not parse page") from exc
    text = re.sub(r"\s+", " ", " ".join(parser.parts)).strip()
    _check_interstitial(text, " ".join(parser.title_parts))
    if len(text) < min_text_chars:
        raise PageError("Insufficient readable content; manual review needed")
    if len(text) > MAX_TEXT_CHARS:
        return text[:30_000] + " [...] " + text[-9_993:]
    return text
