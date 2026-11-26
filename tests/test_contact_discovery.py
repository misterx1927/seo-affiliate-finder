import unittest
from src.contact_discovery import choose_contact, contact_pages, public_email_candidates


class ContactDiscoveryTests(unittest.TestCase):
    def test_follows_only_same_origin_and_limited_links(self):
        html = b'<a href="/contact-us">Contact</a><a href="https://evil.example/contact">External</a><a href="/advertising">Advertising</a><a href="http://site.example/contact">Downgrade</a>'
        self.assertEqual(contact_pages(html, 'utf-8', 'https://site.example/reviews'), ['https://site.example/contact-us', 'https://site.example/advertising'])

    def test_provider_markdown_and_visible_email(self):
        html = b'<p>[Contact](https://site.example/contact/) text</p>'
        self.assertEqual(contact_pages(html, 'utf-8', 'https://site.example/reviews'), ['https://site.example/contact/'])
        self.assertEqual(public_email_candidates('contact@site.example contact@site.example noreply@site.example'), ['contact@site.example'])

    def test_other_company_and_ambiguous_contacts_are_not_guessed(self):
        self.assertIsNone(choose_contact(['support@casino.example'], 'https://publisher.example/contact'))
        self.assertIsNone(choose_contact(['team@publisher.example', 'help@publisher.example'], 'https://publisher.example/contact'))
        self.assertEqual(choose_contact(['support@publisher.example', 'partners@publisher.example'], 'https://publisher.example/contact'), 'partners@publisher.example')


if __name__ == '__main__':
    unittest.main()
