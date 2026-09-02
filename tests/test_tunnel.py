import unittest

from xq.tunnel import normalize_server_url, parse_tunnel_url


class TunnelHelpersTests(unittest.TestCase):
    def test_cloudflare_log_url_becomes_secure_websocket(self):
        line = "INF Your quick Tunnel has been created! Visit it at https://blue-tree.trycloudflare.com"
        self.assertEqual(parse_tunnel_url(line), "wss://blue-tree.trycloudflare.com")

    def test_unrelated_log_line_has_no_url(self):
        self.assertIsNone(parse_tunnel_url("INF Starting tunnel"))

    def test_server_address_normalization(self):
        self.assertEqual(normalize_server_url("192.168.1.2", 8765), "ws://192.168.1.2:8765")
        self.assertEqual(normalize_server_url("https://game.example.com/", 1234), "wss://game.example.com")
        self.assertEqual(normalize_server_url("wss://abc.trycloudflare.com/", 1234), "wss://abc.trycloudflare.com")


if __name__ == "__main__":
    unittest.main()
