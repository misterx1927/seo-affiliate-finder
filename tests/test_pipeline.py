import unittest
from src.database import connect
from src.parser import extract_text, PageError, MAX_HTML_BYTES
from src.pipeline import run_offline

class ParserTests(unittest.TestCase):
    def test_visible_text_and_email(self):
        html = b"<h1>Reviews</h1><script>ignore me</script><p>" + b"Useful text " * 10 + b"<a href='mailto:hello@example.com?subject=Hi'>contact</a></p>"
        text = extract_text(html)
        self.assertIn("hello@example.com", text)
        self.assertNotIn("ignore me", text)
    def test_long_page_keeps_footer_contact(self):
        html = ("<p>" + "Useful content " * 5000 + "</p><footer>Contact footer@example.com</footer>").encode()
        self.assertIn("footer@example.com", extract_text(html))
    def test_visible_internal_contact_link_is_available_to_analyzer(self):
        html = ("<article>" + "Independent casino reviews. " * 5 + "</article>"
                "<footer><a href='/contact'>Contact us</a> "
                "<a href='https://elsewhere.example/contact'>Contact external</a> "
                "<a href='/casino'>Casino review</a> "
                "<a hidden href='/secret'>Contact secret</a></footer>").encode()
        text = extract_text(html, base_url='https://publisher.example/reviews')
        self.assertIn('https://publisher.example/contact', text)
        self.assertNotIn('https://elsewhere.example/contact', text)
        self.assertNotIn('https://publisher.example/casino', text)
        self.assertNotIn('https://publisher.example/secret', text)
    def test_short_and_large_pages_need_review(self):
        with self.assertRaises(PageError): extract_text(b"<p>Blocked</p>")
        with self.assertRaises(PageError): extract_text(b"x" * (MAX_HTML_BYTES + 1))

class PipelineTests(unittest.TestCase):
    def setUp(self):
        self.db = connect(":memory:")
        self.addCleanup(self.db.close)
    def test_end_to_end_and_cached_rerun(self):
        first = run_offline(self.db, "2026-11-24")
        second = run_offline(self.db, "2026-11-24")
        self.assertEqual((first["status"], first["analyzed"], first["observations"]), ("complete", 3, 30))
        self.assertEqual((second["analyzed"], second["reused"]), (0, 3))
        self.assertEqual(self.db.execute("SELECT count(*) FROM observations").fetchone()[0], 30)
        self.assertEqual(self.db.execute("SELECT count(*) FROM pages").fetchone()[0], 3)
        third = run_offline(self.db, "2026-11-25")
        self.assertEqual(third["reused"], 3)
        self.assertEqual(self.db.execute("SELECT count(*) FROM observations").fetchone()[0], 60)

if __name__ == "__main__": unittest.main()
