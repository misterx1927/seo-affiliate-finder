import unittest
from unittest.mock import patch, MagicMock
from src.fetcher import FetchError, _public_addresses, fetch_page, fetch_with_retry
from src.parser import extract_text, PageError

class FetchTests(unittest.TestCase):
    def test_rejects_private_addresses(self):
        with patch("src.fetcher.socket.getaddrinfo", return_value=[(2, 1, 6, "", ("127.0.0.1", 80))]):
            with self.assertRaises(FetchError): _public_addresses("localhost", 80)
    def test_redirect_to_private_ip_is_blocked(self):
        response = MagicMock()
        response.status = 302
        response.getheader.return_value = "http://127.0.0.1/private"
        connection = MagicMock()
        connection.getresponse.return_value = response
        def addresses(host, port):
            if host == "127.0.0.1": raise FetchError("Non-public address blocked")
            return ["8.8.8.8"]
        with patch("src.fetcher._public_addresses", side_effect=addresses), patch("src.fetcher._PinnedHTTPS", return_value=connection):
            with self.assertRaises(FetchError): fetch_page("https://public.example/")
        connection.close.assert_called_once()

    def test_only_transient_failures_are_retried(self):
        with patch("src.fetcher.fetch_page", side_effect=[FetchError("timeout", transient=True), (b"ok", "utf-8")]) as fetch:
            self.assertEqual(fetch_with_retry("https://example.com", delay=0), (b"ok", "utf-8"))
            self.assertEqual(fetch.call_count, 2)
        with patch("src.fetcher.fetch_page", side_effect=FetchError("blocked")) as fetch:
            with self.assertRaises(FetchError): fetch_with_retry("https://example.com", delay=0)
            self.assertEqual(fetch.call_count, 1)

    def test_rejects_unsafe_urls_before_connecting(self):
        for url in ("file:///etc/passwd", "http://user:pass@example.com", "http://example.com:8080/"):
            with self.subTest(url=url), self.assertRaises(FetchError): fetch_page(url)

    def test_falls_back_to_second_public_address_after_connection_failure(self):
        broken, working = MagicMock(), MagicMock()
        broken.request.side_effect = ConnectionRefusedError()
        response = working.getresponse.return_value
        response.status = 200
        response.getheader.side_effect = lambda name, default=None: {"Content-Type": "text/html", "Content-Length": "12"}.get(name, default)
        response.read.return_value = b"<p>hello</p>"
        response.headers.get_content_charset.return_value = "utf-8"
        with patch("src.fetcher._public_addresses", return_value=["8.8.8.8", "1.1.1.1"]), patch("src.fetcher._PinnedHTTPS", side_effect=[broken, working]):
            self.assertEqual(fetch_page("https://example.com/caf\u00e9?q=\u00e9"), (b"<p>hello</p>", "utf-8"))
        self.assertEqual(working.request.call_args.args[1], "/caf%C3%A9?q=%C3%A9")
        broken.close.assert_called_once()
        working.close.assert_called_once()

    def test_http_block_does_not_try_another_address(self):
        connection = MagicMock()
        connection.getresponse.return_value.status = 403
        with patch("src.fetcher._public_addresses", return_value=["8.8.8.8", "1.1.1.1"]), patch("src.fetcher._PinnedHTTPS", return_value=connection) as factory:
            with self.assertRaisesRegex(FetchError, "HTTP 403"):
                fetch_page("https://example.com/")
        self.assertEqual(factory.call_count, 1)

    def test_large_static_page_within_bound_can_be_parsed(self):
        content = b"<html><script>" + b"x" * 2_100_000 + b"</script><p>" + b"readable text " * 10 + b"</p></html>"
        self.assertIn("readable text", extract_text(content))

    def test_challenge_and_regional_notice_require_review(self):
        for message in ("Hmm... Are You a Robot? Let's Check.",
                        "Verify you are human to continue.",
                        "This page is not available in your region."):
            html = ("<html><body>" + message + " Please wait. " * 12 + "</body></html>").encode()
            with self.subTest(message=message), self.assertRaisesRegex(PageError, "manual review"):
                extract_text(html)

    def test_javascript_robot_gate_with_boilerplate_requires_review(self):
        html = ("<h1>JavaScript is disabled</h1><p>In order to continue, "
                "we need to verify that you're not a robot. Enable JavaScript "
                "and reload the page.</p><footer>" + "Navigation. " * 120 + "</footer>").encode()
        with self.assertRaisesRegex(PageError, "manual review"):
            extract_text(html)

    def test_regional_gate_with_title_and_message_requires_review(self):
        html = ("<title>Not available in your area | Gambling Sage</title>"
                "<h1>Not available in your area</h1><p>This page isn't available in your area.</p>"
                "<footer>Go to the homepage</footer>").encode()
        with self.assertRaisesRegex(PageError, "regional mismatch"):
            extract_text(html)

    def test_javascript_article_without_robot_gate_is_not_blocked(self):
        html = ("<article><h1>JavaScript is disabled</h1>" +
                "This review discusses browser settings. " * 100 + "</article>").encode()
        self.assertIn("browser settings", extract_text(html))

    def test_security_discussion_inside_long_article_is_not_a_challenge(self):
        html = ("<article><h1>Casino security</h1><p>" + "Detailed review. " * 200 +
                "The sign-in page may ask, are you a robot? " + "Details. " * 30 + "</p></article>").encode()
        self.assertIn("are you a robot", extract_text(html))

    def test_long_challenge_with_matching_title_requires_review(self):
        html = ("<title>Just a moment...</title><main>Checking if the site connection is secure. " +
                "Please wait while we verify your browser. " * 150 + "</main>").encode()
        with self.assertRaisesRegex(PageError, "manual review"):
            extract_text(html)

    def test_article_with_challenge_title_alone_is_not_blocked(self):
        html = ("<title>Just a moment...</title><article>" +
                "A casino review with useful information. " * 150 + "</article>").encode()
        self.assertIn("casino review", extract_text(html))

    def test_article_discussing_challenge_is_not_blocked(self):
        html = ("<title>How security checks work</title><article>" +
                "Verify you are human is a common security message. " * 100 + "</article>").encode()
        self.assertIn("security checks", extract_text(html))

    def test_challenge_in_script_is_not_visible_page_content(self):
        html = ("<script>var label = 'verify you are human';</script><p>" +
                "Useful casino review. " * 20 + "</p>").encode()
        self.assertIn("Useful casino review", extract_text(html))

    def test_hidden_content_is_not_sent_as_evidence_to_the_analyzer(self):
        html = ("<div hidden><div>HiddenCasino</div><br>fake@site.example</div>"
                "<div style='color: red; display: none !important'><p>OtherCasino</p></div>"
                "<div style='visibility: hidden'>HiddenBrand</div>"
                "<article>" + "A visible casino review with independent information. " * 3 + "</article>").encode()
        text = extract_text(html)
        for hidden in ("HiddenCasino", "fake@site.example", "OtherCasino", "HiddenBrand"):
            self.assertNotIn(hidden, text)
        self.assertIn("visible casino review", text)

    def test_insufficient_visible_text_is_not_rescued_by_hidden_content(self):
        html = ("<p>Loading...</p><div hidden>" + "Imaginary casino review. " * 50 + "</div>").encode()
        with self.assertRaisesRegex(PageError, "Insufficient readable content"):
            extract_text(html)

    def test_advertised_oversized_page_is_not_downloaded(self):
        connection = MagicMock()
        response = connection.getresponse.return_value
        response.status = 200
        response.getheader.side_effect = lambda name, default=None: {"Content-Type": "text/html", "Content-Length": "8000001"}.get(name, default)
        with patch("src.fetcher._public_addresses", return_value=["8.8.8.8"]), patch("src.fetcher._PinnedHTTPS", return_value=connection):
            with self.assertRaisesRegex(FetchError, "size limit"):
                fetch_page("https://example.com/")
        response.read.assert_not_called()
        connection.close.assert_called_once()

    def test_contact_fetch_refuses_cross_origin_redirect(self):
        response, connection = MagicMock(), MagicMock()
        response.status = 302
        response.getheader.return_value = 'https://other.example/contact'
        connection.getresponse.return_value = response
        with patch('src.fetcher._public_addresses', return_value=['8.8.8.8']) as dns, patch('src.fetcher._PinnedHTTPS', return_value=connection):
            with self.assertRaisesRegex(FetchError, 'Cross-origin redirect blocked'):
                fetch_page('https://publisher.example/contact', same_origin_only=True)
        self.assertEqual(dns.call_count, 1)
        connection.close.assert_called_once()

    def test_page_fetch_does_not_attribute_another_site_to_the_original_url(self):
        response, connection = MagicMock(), MagicMock()
        response.status = 302
        response.getheader.return_value = 'https://different.example/casino'
        connection.getresponse.return_value = response
        with patch('src.fetcher._public_addresses', return_value=['8.8.8.8']) as dns, patch('src.fetcher._PinnedHTTPS', return_value=connection):
            with self.assertRaisesRegex(FetchError, 'Cross-host redirect requires manual review'):
                fetch_page('https://publisher.example/casino')
        self.assertEqual(dns.call_count, 1)

    def test_page_fetch_allows_www_canonical_redirect(self):
        first, second = MagicMock(), MagicMock()
        first_response = first.getresponse.return_value
        first_response.status = 301
        first_response.getheader.return_value = 'https://www.example.com/casino'
        second_response = second.getresponse.return_value
        second_response.status = 200
        second_response.getheader.side_effect = lambda name, default=None: {'Content-Type': 'text/html'}.get(name, default)
        second_response.read.return_value = b'<p>page</p>'
        second_response.headers.get_content_charset.return_value = 'utf-8'
        with patch('src.fetcher._public_addresses', return_value=['8.8.8.8']), patch('src.fetcher._PinnedHTTPS', side_effect=[first, second]):
            self.assertEqual(fetch_page('https://example.com/casino'), (b'<p>page</p>', 'utf-8'))

if __name__ == "__main__": unittest.main()
