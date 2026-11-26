"""Verified TLS with a current CA bundle when the optional certifi package is installed."""
import ssl

def tls_context() -> ssl.SSLContext:
    try:
        import certifi
    except ImportError:
        return ssl.create_default_context()
    return ssl.create_default_context(cafile=certifi.where())
