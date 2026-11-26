import unittest
import sqlite3
from src.contact_discovery import choose_contact, contact_pages, public_email_candidates
from discover_contacts import load_targets


class ContactDiscoveryTests(unittest.TestCase):
    def test_follows_only_same_origin_and_limited_links(self):
        html = b'<a href="/contact-us">Contact</a><a href="https://evil.example/contact">External</a><a href="/advertising">Advertising</a><a href="http://site.example/contact">Downgrade</a>'
        self.assertEqual(contact_pages(html, 'utf-8', 'https://site.example/reviews'), ['https://site.example/contact-us', 'https://site.example/advertising'])

    def test_provider_markdown_and_visible_email(self):
        html = b'<p>[Contact](https://site.example/contact/) text</p>'
        self.assertEqual(contact_pages(html, 'utf-8', 'https://site.example/reviews'), ['https://site.example/contact/'])
        self.assertEqual(public_email_candidates('contact@site.example contact@site.example noreply@site.example'), ['contact@site.example'])

    def test_contact_label_finds_nonobvious_path_but_not_external_link(self):
        html = (b'<a href="/about"><span>Get in touch</span></a>'
                b'<a href="https://other.example/about">Contact us</a>'
                b'<a href="/casino">Casino review</a>')
        self.assertEqual(contact_pages(html, 'utf-8', 'https://site.example/reviews'),
                         ['https://site.example/about'])

    def test_markdown_label_finds_nonobvious_contact_path(self):
        html = b'<p>[Advertise with us](/about-us)</p>'
        self.assertEqual(contact_pages(html, 'utf-8', 'https://site.example/reviews'),
                         ['https://site.example/about-us'])

    def test_other_company_and_ambiguous_contacts_are_not_guessed(self):
        self.assertIsNone(choose_contact(['support@casino.example'], 'https://publisher.example/contact'))
        self.assertIsNone(choose_contact(['team@publisher.example', 'help@publisher.example'], 'https://publisher.example/contact'))
        self.assertEqual(choose_contact(['support@publisher.example', 'partners@publisher.example'], 'https://publisher.example/contact'), 'partners@publisher.example')

    def test_explicit_obfuscation_is_decoded_without_inventing_addresses(self):
        text = 'Write to press [at] publisher [dot] com or sales(at)publisher.com.'
        self.assertEqual(public_email_candidates(text), ['press@publisher.com', 'sales@publisher.com'])
        self.assertEqual(public_email_candidates('Contact us on publisher.com'), [])

    def test_uncertain_cached_pages_are_included_but_rejected_pages_excluded(self):
        conn = sqlite3.connect(':memory:')
        conn.row_factory = sqlite3.Row
        conn.executescript('''CREATE TABLE observations(run_id INTEGER, url TEXT);
          CREATE TABLE pages(url TEXT, status TEXT, relevance TEXT, contact TEXT);
          CREATE TABLE page_cache(url TEXT, content BLOB, charset TEXT);''')
        for name, status, relevance in [('review', 'complete', 'needs_review'),
                                        ('blocked', 'needs_review', None),
                                        ('rejected', 'complete', 'no')]:
            url = f'https://{name}.example/article'
            conn.execute('INSERT INTO observations VALUES(?, ?)', (7, url))
            conn.execute('INSERT INTO pages VALUES(?,?,?,?)', (url, status, relevance, None))
            conn.execute('INSERT INTO page_cache VALUES(?,?,?)',
                         (url, b'<a href="/contact">Contact</a>', 'utf-8'))
        self.assertEqual(set(load_targets(conn, 7, 30)),
                         {'https://review.example/contact', 'https://blocked.example/contact'})


if __name__ == '__main__':
    unittest.main()
