import ssl
import unittest
from src.tls import tls_context

class TLSTests(unittest.TestCase):
    def test_verification_is_enabled(self):
        context = tls_context()
        self.assertTrue(context.check_hostname)
        self.assertEqual(context.verify_mode, ssl.CERT_REQUIRED)

if __name__ == "__main__": unittest.main()
