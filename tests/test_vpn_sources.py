from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from vpn_sources import (
    NodeFilters,
    PublicVPNListClient,
    SourceError,
    apply_node_filters,
    normalize_publicvpnlist_payload,
    validate_openvpn_profile,
)


def sample_payload(*, page: int = 1, total: int = 1) -> dict:
    legacy_id = 1000 + page
    return {
        "ok": True,
        "items": [
            {
                "country": "japan",
                "countryName": "Japan",
                "isVerified": True,
                "configAvailable": True,
                "endpoints": [
                    {
                        "legacy_id": legacy_id,
                        "resolved_ip": f"192.0.2.{page}",
                        "port": 443,
                        "transport_protocol": "tcp",
                        "source": "VPNGate",
                        "latency_ms": 40 + page,
                        "download_mbps": 80.5,
                        "checker_status": "tunnel_ok",
                        "downloadable": True,
                    }
                ],
            }
        ],
        "pagination": {"page": page, "page_size": 1, "total": total},
    }


class FakePublicVPNListClient(PublicVPNListClient):
    def __init__(self, pages: dict[int, dict], **kwargs) -> None:
        super().__init__(**kwargs)
        self.pages = pages
        self.requested_pages: list[int] = []

    def _get_json(self, url: str) -> dict:
        from urllib.parse import parse_qs, urlsplit

        page = int(parse_qs(urlsplit(url).query)["page"][0])
        self.requested_pages.append(page)
        return self.pages.get(page, {"ok": True, "items": [], "pagination": {}})


class NodeFilterTests(unittest.TestCase):
    def test_normalizes_publicvpnlist_endpoint(self) -> None:
        nodes = normalize_publicvpnlist_payload(sample_payload())
        self.assertEqual(len(nodes), 1)
        node = nodes[0]
        self.assertEqual(node["catalog_source"], "publicvpnlist")
        self.assertEqual(node["protocol"], "openvpn")
        self.assertEqual(node["proto"], "tcp")
        self.assertEqual(node["speed_mbps"], 80.5)
        self.assertEqual(node["reported_latency_ms"], 41)
        self.assertTrue(node["verified"])
        self.assertTrue(node["downloadable"])
        self.assertEqual(node["config_text"], "")

    def test_filters_protocol_speed_latency_and_verification(self) -> None:
        nodes = normalize_publicvpnlist_payload(sample_payload())
        filters = NodeFilters.from_mapping(
            {
                "node_source": "publicvpnlist",
                "filter_country": "japan",
                "filter_source": "VPNGate",
                "filter_protocol": "tcp",
                "min_speed_mbps": 50,
                "max_latency_ms": 80,
                "only_verified": True,
                "only_downloadable": True,
            }
        )
        self.assertEqual(len(apply_node_filters(nodes, filters)), 1)
        rejected = NodeFilters.from_mapping({**filters.to_dict(), "max_latency_ms": 20})
        self.assertEqual(apply_node_filters(nodes, rejected), [])

    def test_unknown_ip_is_not_proxy_free(self) -> None:
        nodes = normalize_publicvpnlist_payload(sample_payload())
        filters = NodeFilters.from_mapping({"node_source": "publicvpnlist", "ip_purity": "proxy_free"})
        self.assertEqual(apply_node_filters(nodes, filters), [])
        nodes[0]["ip_type"] = "normal"
        self.assertEqual(len(apply_node_filters(nodes, filters)), 1)

    def test_rejects_invalid_filter_values(self) -> None:
        with self.assertRaises(ValueError):
            NodeFilters.from_mapping({"node_source": "unknown"})
        with self.assertRaises(ValueError):
            NodeFilters.from_mapping({"filter_protocol": "quic"})


class PublicVPNListClientTests(unittest.TestCase):
    def test_paginates_until_total(self) -> None:
        client = FakePublicVPNListClient(
            {1: sample_payload(page=1, total=2), 2: sample_payload(page=2, total=2)},
            page_size=1,
            max_pages=10,
            metadata_ttl=0,
        )
        nodes = client.fetch_candidates(NodeFilters(node_source="publicvpnlist"), max_candidates=10)
        self.assertEqual(len(nodes), 2)
        self.assertEqual(client.requested_pages, [1, 2])

    def test_metadata_cache_avoids_second_fetch(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            client = FakePublicVPNListClient(
                {1: sample_payload()},
                page_size=100,
                max_pages=2,
                metadata_ttl=900,
                cache_path=Path(directory) / "cache.json",
            )
            filters = NodeFilters(node_source="publicvpnlist")
            first = client.fetch_candidates(filters)
            second = client.fetch_candidates(filters)
            self.assertEqual(first, second)
            self.assertEqual(client.requested_pages, [1])

    def test_extracts_token_without_logging_or_persisting_it(self) -> None:
        url = PublicVPNListClient._extract_download_url('{"token":"abc_12345678"}')
        self.assertEqual(url, "https://publicvpnlist.com/download.php?token=abc_12345678")

    def test_normalizes_relative_download_url_from_api(self) -> None:
        url = PublicVPNListClient._extract_download_url(
            '{"download_url":"/download.php?token=abc_12345678"}'
        )
        self.assertEqual(url, "https://publicvpnlist.com/download.php?token=abc_12345678")
        PublicVPNListClient._validate_url(url, download=True)

    def test_relative_download_url_cannot_escape_publicvpnlist(self) -> None:
        url = PublicVPNListClient._extract_download_url(
            '{"download_url":"//example.com/download.php?token=abc_12345678"}'
        )
        with self.assertRaises(SourceError):
            PublicVPNListClient._validate_url(url, download=True)


class OpenVPNProfileTests(unittest.TestCase):
    def test_accepts_basic_profile(self) -> None:
        validate_openvpn_profile("client\nremote 192.0.2.10 443 tcp\n<ca>\ncert\n</ca>\n")

    def test_rejects_command_directives(self) -> None:
        with self.assertRaises(SourceError):
            validate_openvpn_profile("client\nremote 192.0.2.10 443\nscript-security 2\nup /tmp/run.sh\n")


if __name__ == "__main__":
    unittest.main()
