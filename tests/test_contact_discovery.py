import unittest
import sqlite3
from unittest.mock import patch
from src.contact_discovery import choose_contact, cloudflare_email_candidates, contact_pages, public_email_candidates
from discover_contacts import load_targets, inspect_page


class ContactDiscoveryTests(unittest.TestCase):
    @patch('discover_contacts.fetch_page')
    def test_short_contact_page_can_provide_email_but_challenge_cannot(self, fetch):
        fetch.return_value = (b'<h1>Contact</h1><p>partner@publisher.example</p>', 'utf-8')
        self.assertEqual(inspect_page('https://publisher.example/contact'),
                         ('partner@publisher.example', None))
        fetch.return_value = (b'<title>Just a moment...</title><p>Verify you are human</p>', 'utf-8')
        email, error = inspect_page('https://publisher.example/contact')
        self.assertIsNone(email)
        self.assertIn('challenge', error)

    @patch('discover_contacts.fetch_page')
    def test_percent_encoded_mailto_is_observed_without_taking_subject_as_address(self, fetch):
        fetch.return_value = (b'<h1>Contact</h1><a href="mailto:press%40publisher.com?subject=old%40publisher.com">Email us</a>', 'utf-8')
        self.assertEqual(inspect_page('https://publisher.com/contact'), ('press@publisher.com', None))

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

    def test_hidden_links_and_script_markdown_are_not_contact_pages(self):
        html = (b'<script>let x="[Contact](/obsolete-contact)"</script>'
                b'<!-- [Contact](/comment-contact) -->'
                b'<div hidden><a href="/hidden-contact">Contact</a></div>'
                b'<div style="display: none"><p>[Contact](/invisible-contact)</p></div>'
                b'<p>[Contact](/real-contact)</p>')
        self.assertEqual(contact_pages(html, 'utf-8', 'https://site.example/reviews'),
                         ['https://site.example/real-contact'])

    def test_other_company_and_ambiguous_contacts_are_not_guessed(self):
        self.assertIsNone(choose_contact(['support@casino.example'], 'https://publisher.example/contact'))
        self.assertIsNone(choose_contact(['team@publisher.example', 'help@publisher.example'], 'https://publisher.example/contact'))
        self.assertEqual(choose_contact(['support@publisher.example', 'partners@publisher.example'], 'https://publisher.example/contact'), 'partners@publisher.example')

    def test_same_mailbox_in_text_and_protected_link_is_not_ambiguous(self):
        address = 'Partners@publisher.com'
        key = 0x35
        encoded = bytes([key] + [key ^ b for b in address.lower().encode('ascii')]).hex()
        page = (f'<h1>Contact</h1><p>{address}</p>'
                f'<span data-cfemail="{encoded}">[email protected]</span>').encode()
        with patch('discover_contacts.fetch_page', return_value=(page, 'utf-8')):
            self.assertEqual(inspect_page('https://publisher.com/contact'), (address, None))
        self.assertIsNone(choose_contact(['Partners@publisher.com', 'media@publisher.com'],
                                         'https://publisher.com/contact'))

    def test_explicit_obfuscation_is_decoded_without_inventing_addresses(self):
        text = 'Write to press [at] publisher [dot] com or sales(at)publisher.com.'
        self.assertEqual(public_email_candidates(text), ['press@publisher.com', 'sales@publisher.com'])
        self.assertEqual(public_email_candidates('Contact us on publisher.com'), [])

    @patch('discover_contacts.fetch_page')
    def test_cloudflare_public_address_is_decoded_and_filtered(self, fetch):
        address = 'partners@publisher.com'
        key = 0x35
        encoded = bytes([key] + [key ^ b for b in address.encode('ascii')]).hex()
        page = (f'<h1>Contact</h1><a href="/cdn-cgi/l/email-protection#{encoded}">'
                f'<span data-cfemail="{encoded}">[email protected]</span></a>'
                '<span data-cfemail="nope">broken</span>').encode()
        self.assertEqual(cloudflare_email_candidates(page, 'utf-8'), [address])
        fetch.return_value = page, 'utf-8'
        self.assertEqual(inspect_page('https://publisher.com/contact'), (address, None))
        self.assertEqual(inspect_page('https://another.com/contact'), (None, None))

    def test_cloudflare_hidden_addresses_do_not_count_as_public_contacts(self):
        key = 0x35
        encode = lambda address: bytes([key] + [key ^ b for b in address.encode('ascii')]).hex()
        page = (f'<div hidden><span data-cfemail="{encode("old@publisher.com")}"></span></div>'
                f'<template><span data-cfemail="{encode("template@publisher.com")}"></span></template>'
                f'<span data-cfemail="{encode("press@publisher.com")}">[email protected]</span>').encode()
        self.assertEqual(cloudflare_email_candidates(page, 'utf-8'), ['press@publisher.com'])

    def test_uncertain_cached_pages_are_included_but_rejected_pages_excluded(self):
        conn = sqlite3.connect(':memory:')
        self.addCleanup(conn.close)
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
