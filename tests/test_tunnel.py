import unittest
import urllib.error
from unittest.mock import patch

from xq.tunnel import (
    DIRECT_DOWNLOAD_URL,
    QuickTunnel,
    is_edge_dns_error,
    normalize_server_url,
    parse_tunnel_url,
)


class TunnelHelpersTests(unittest.TestCase):
    def test_cloudflare_log_url_becomes_secure_websocket(self):
        line = "INF Your quick Tunnel has been created! Visit it at https://blue-tree.trycloudflare.com"
        self.assertEqual(parse_tunnel_url(line), "wss://blue-tree.trycloudflare.com")

    def test_unrelated_log_line_has_no_url(self):
        self.assertIsNone(parse_tunnel_url("INF Starting tunnel"))

    def test_cloudflare_srv_lookup_failure_is_detected_for_region_fallback(self):
        message = (
            "Could not lookup srv records on _v2-origintunneld._tcp.argotunnel.com: "
            "lookup argotunnel.com: no such host"
        )
        self.assertTrue(is_edge_dns_error(message))
        self.assertFalse(is_edge_dns_error("Cloudflare HTTP 530"))

    def test_backup_region_command_forces_ipv4_http2(self):
        command = QuickTunnel._cloudflared_command("cloudflared.exe", 8765, "us")

        self.assertIn("http2", command)
        self.assertIn("4", command)
        self.assertEqual(command[command.index("--region") + 1], "us")
        self.assertEqual(command[-1], "http://127.0.0.1:8765")

    def test_server_address_normalization(self):
        self.assertEqual(normalize_server_url("192.168.1.2", 8765), "ws://192.168.1.2:8765")
        self.assertEqual(normalize_server_url("https://game.example.com/", 1234), "wss://game.example.com")
        self.assertEqual(normalize_server_url("wss://abc.trycloudflare.com/", 1234), "wss://abc.trycloudflare.com")

    @patch("xq.tunnel.urllib.request.urlopen")
    def test_rate_limited_api_falls_back_to_official_direct_download(self, urlopen):
        urlopen.side_effect = urllib.error.HTTPError(
            "https://api.github.com", 403, "rate limit exceeded", {}, None
        )
        statuses = []

        url, size, digest = QuickTunnel._download_source(statuses.append)

        self.assertEqual(url, DIRECT_DOWNLOAD_URL)
        self.assertEqual((size, digest), (0, ""))
        self.assertTrue(any("官方最新版直链" in text for text in statuses))

    @patch("xq.tunnel.urllib.request.urlopen")
    def test_websocket_upgrade_response_means_public_route_is_ready(self, urlopen):
        urlopen.side_effect = urllib.error.HTTPError(
            "https://blue-tree.trycloudflare.com", 426, "Upgrade Required", {}, None
        )

        ready, error = QuickTunnel._probe_public_url("wss://blue-tree.trycloudflare.com")

        self.assertTrue(ready)
        self.assertEqual(error, "")

    @patch("xq.tunnel.urllib.request.urlopen")
    def test_certificate_mismatch_keeps_public_route_waiting(self, urlopen):
        urlopen.side_effect = urllib.error.URLError("certificate hostname mismatch")

        ready, error = QuickTunnel._probe_public_url("wss://blue-tree.trycloudflare.com")

        self.assertFalse(ready)
        self.assertIn("hostname mismatch", error)

    @patch("xq.tunnel.urllib.request.urlopen")
    def test_cloudflare_530_keeps_public_route_waiting(self, urlopen):
        urlopen.side_effect = urllib.error.HTTPError(
            "https://blue-tree.trycloudflare.com", 530, "Tunnel unavailable", {}, None
        )

        ready, error = QuickTunnel._probe_public_url("wss://blue-tree.trycloudflare.com")

        self.assertFalse(ready)
        self.assertEqual(error, "Cloudflare HTTP 530")


if __name__ == "__main__":
    unittest.main()
