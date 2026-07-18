from __future__ import annotations

import hashlib
import json
import re
import threading
import time
import urllib.parse
import urllib.request
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Iterable, Mapping


PUBLICVPNLIST_API_URL = "https://publicvpnlist.com/api/v1/servers"
PUBLICVPNLIST_SOURCES_URL = "https://publicvpnlist.com/api/v1/sources"
PUBLICVPNLIST_TOKEN_URL = "https://publicvpnlist.com/get_token.php"
PUBLICVPNLIST_DOWNLOAD_URL = "https://publicvpnlist.com/download.php"
_PUBLICVPNLIST_HOST = "publicvpnlist.com"


class SourceError(RuntimeError):
    pass


def _bounded_int(value: Any, default: int, minimum: int, maximum: int) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return default
    return min(maximum, max(minimum, parsed))


def _bounded_float(value: Any, default: float, minimum: float, maximum: float) -> float:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return default
    return min(maximum, max(minimum, parsed))


def _clean_text(value: Any, max_length: int = 100) -> str:
    return str(value or "").strip()[:max_length]


def _slug(value: Any) -> str:
    text = _clean_text(value, 100).lower()
    return re.sub(r"[^a-z0-9]+", "-", text).strip("-")


def _as_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value != 0
    return str(value or "").strip().lower() in {"1", "true", "yes", "ok", "available", "tunnel_ok"}


def _first(mapping: Mapping[str, Any], *keys: str, default: Any = None) -> Any:
    for key in keys:
        value = mapping.get(key)
        if value not in (None, ""):
            return value
    return default


@dataclass(frozen=True)
class NodeFilters:
    node_source: str = "vpngate"
    filter_country: str = ""
    filter_source: str = ""
    filter_protocol: str = ""
    min_speed_mbps: float = 0.0
    max_latency_ms: int = 0
    ip_purity: str = "any"
    only_verified: bool = False
    only_downloadable: bool = True

    @classmethod
    def from_mapping(cls, raw: Mapping[str, Any] | None) -> "NodeFilters":
        raw = raw or {}
        node_source = _clean_text(raw.get("node_source") or "vpngate", 32).lower()
        if node_source not in {"vpngate", "publicvpnlist", "all"}:
            raise ValueError("node_source must be vpngate, publicvpnlist, or all")

        protocol = _clean_text(raw.get("filter_protocol"), 8).lower()
        if protocol not in {"", "tcp", "udp"}:
            raise ValueError("filter_protocol must be tcp, udp, or empty")

        ip_purity = _clean_text(raw.get("ip_purity") or "any", 32).lower()
        if ip_purity not in {"any", "residential", "hosting", "proxy_free"}:
            raise ValueError("ip_purity must be any, residential, hosting, or proxy_free")

        country = _clean_text(raw.get("filter_country"), 80)
        source = _clean_text(raw.get("filter_source"), 80)
        if country and not re.fullmatch(r"[A-Za-z0-9 _-]{1,80}", country):
            raise ValueError("filter_country contains unsupported characters")
        if source and not re.fullmatch(r"[A-Za-z0-9 ._()/+\-]{1,80}", source):
            raise ValueError("filter_source contains unsupported characters")

        return cls(
            node_source=node_source,
            filter_country=country,
            filter_source=source,
            filter_protocol=protocol,
            min_speed_mbps=_bounded_float(raw.get("min_speed_mbps"), 0.0, 0.0, 100000.0),
            max_latency_ms=_bounded_int(raw.get("max_latency_ms"), 0, 0, 60000),
            ip_purity=ip_purity,
            only_verified=_as_bool(raw.get("only_verified")),
            only_downloadable=_as_bool(raw.get("only_downloadable", True)),
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def cache_key(self) -> str:
        encoded = json.dumps(self.to_dict(), ensure_ascii=True, sort_keys=True).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()


def apply_node_filters(
    nodes: Iterable[dict[str, Any]],
    filters: NodeFilters,
    *,
    include_ip_purity: bool = True,
) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    wanted_country = _slug(filters.filter_country)
    wanted_source = filters.filter_source.casefold()

    for node in nodes:
        if wanted_country:
            node_country = _slug(node.get("country_slug") or node.get("country") or node.get("country_short"))
            if node_country != wanted_country:
                continue
        if wanted_source and str(node.get("source") or "").casefold() != wanted_source:
            continue
        if filters.filter_protocol and str(node.get("proto") or "").lower() != filters.filter_protocol:
            continue
        if filters.only_downloadable and not _as_bool(node.get("downloadable", bool(node.get("config_text")))):
            continue
        if filters.only_verified and not _as_bool(node.get("verified")):
            continue

        speed = _bounded_float(node.get("speed_mbps"), 0.0, 0.0, 100000.0)
        latency = _bounded_int(
            node.get("reported_latency_ms", node.get("latency_ms")),
            0,
            0,
            60000,
        )
        if filters.min_speed_mbps and speed < filters.min_speed_mbps:
            continue
        if filters.max_latency_ms and (latency <= 0 or latency > filters.max_latency_ms):
            continue

        if include_ip_purity and filters.ip_purity != "any":
            ip_type = str(node.get("ip_type") or "unknown").lower()
            if filters.ip_purity == "residential" and ip_type not in {"residential", "mobile", "normal"}:
                continue
            if filters.ip_purity == "hosting" and ip_type != "hosting":
                continue
            if filters.ip_purity == "proxy_free" and ip_type not in {"residential", "mobile", "normal"}:
                continue

        result.append(node)
    return result


def normalize_publicvpnlist_payload(payload: Mapping[str, Any]) -> list[dict[str, Any]]:
    if payload.get("ok") is not True:
        raise SourceError("PublicVPNList returned ok != true")
    items = payload.get("items")
    if not isinstance(items, list):
        raise SourceError("PublicVPNList response is missing an items array")

    nodes: list[dict[str, Any]] = []
    seen: set[str] = set()
    now = time.time()
    for item in items:
        if not isinstance(item, Mapping):
            continue
        raw_endpoints = item.get("endpoints")
        if isinstance(raw_endpoints, list):
            endpoints = raw_endpoints
        elif isinstance(raw_endpoints, Mapping):
            endpoints = [value for value in raw_endpoints.values() if isinstance(value, Mapping)]
        else:
            endpoints = [item]
        for endpoint in endpoints:
            if not isinstance(endpoint, Mapping):
                continue
            legacy_id = _first(endpoint, "legacy_id", "legacyId", "id", default=_first(item, "legacy_id", "legacyId", "id"))
            try:
                legacy_id_int = int(legacy_id)
            except (TypeError, ValueError):
                continue

            host = _clean_text(_first(endpoint, "resolved_ip", "resolvedIp", "host", "ip", default=_first(item, "resolved_ip", "host", "ip")), 255)
            port = _bounded_int(_first(endpoint, "port", default=_first(item, "port")), 0, 0, 65535)
            proto = _clean_text(_first(endpoint, "transport_protocol", "transportProtocol", "proto", default=_first(item, "transport_protocol", "proto")), 8).lower()
            if not host or port <= 0 or proto not in {"tcp", "udp"}:
                continue

            source = _clean_text(_first(endpoint, "source", default=_first(item, "source")), 80)
            country = _clean_text(_first(endpoint, "countryName", "country_name", "country", default=_first(item, "countryName", "country_name", "country")), 100)
            country_slug = _slug(_first(endpoint, "country", "country_slug", default=_first(item, "country", "country_slug", default=country)))
            latency = _bounded_int(_first(endpoint, "latency_ms", "latencyMs", default=_first(item, "latency_ms", "latencyMs")), 0, 0, 60000)
            speed = _bounded_float(_first(endpoint, "download_mbps", "downloadMbps", default=_first(item, "download_mbps", "downloadMbps")), 0.0, 0.0, 100000.0)
            checker_status = _clean_text(_first(endpoint, "checker_status", "checkerStatus", default=_first(item, "checker_status", "checkerStatus")), 40).lower()
            verified = _as_bool(_first(endpoint, "isVerified", "verified", default=_first(item, "isVerified", "verified"))) or checker_status == "tunnel_ok"
            downloadable = _as_bool(_first(endpoint, "downloadable", "configAvailable", default=_first(item, "downloadable", "configAvailable")))

            node_id = f"pvl_{legacy_id_int}_{proto}_{port}"
            if node_id in seen:
                continue
            seen.add(node_id)
            nodes.append(
                {
                    "id": node_id,
                    "legacy_id": legacy_id_int,
                    "catalog_source": "publicvpnlist",
                    "source": source,
                    "protocol": "openvpn",
                    "country": country,
                    "country_slug": country_slug,
                    "country_short": "",
                    "ip": host,
                    "remote_host": host,
                    "remote_port": port,
                    "proto": proto,
                    "speed": int(speed * 1_000_000),
                    "speed_mbps": speed,
                    "reported_latency_ms": latency,
                    "latency_ms": latency,
                    "score": int(speed * 1000) - latency,
                    "sessions": 0,
                    "owner": "",
                    "asn": "",
                    "as_name": "",
                    "location": "",
                    "ip_type": "",
                    "quality": "",
                    "verified": verified,
                    "downloadable": downloadable,
                    "checker_status": checker_status,
                    "config_text": "",
                    "fetched_at": now,
                    "probe_status": "not_checked",
                    "probe_message": "",
                    "probed_at": 0,
                }
            )
    return nodes


class PublicVPNListClient:
    def __init__(
        self,
        *,
        page_size: int = 100,
        max_pages: int = 20,
        metadata_ttl: int = 900,
        timeout: float = 12.0,
        cache_path: Path | None = None,
        opener: Any = None,
    ) -> None:
        self.page_size = _bounded_int(page_size, 100, 1, 100)
        self.max_pages = _bounded_int(max_pages, 20, 1, 100)
        self.metadata_ttl = _bounded_int(metadata_ttl, 900, 0, 86400)
        self.timeout = max(1.0, min(float(timeout), 60.0))
        self.cache_path = cache_path
        self.opener = opener or urllib.request.build_opener()
        self._cache_lock = threading.Lock()

    @staticmethod
    def _validate_url(url: str, *, download: bool = False) -> None:
        parsed = urllib.parse.urlsplit(url)
        if parsed.scheme != "https" or parsed.hostname != _PUBLICVPNLIST_HOST:
            raise SourceError("PublicVPNList returned an untrusted URL")
        if download and parsed.path != "/download.php":
            raise SourceError("PublicVPNList returned an unexpected download path")

    def _request(self, request: urllib.request.Request) -> bytes:
        self._validate_url(request.full_url, download=request.full_url.startswith(PUBLICVPNLIST_DOWNLOAD_URL))
        try:
            with self.opener.open(request, timeout=self.timeout) as response:
                return response.read()
        except Exception as exc:
            raise SourceError(f"PublicVPNList request failed ({type(exc).__name__})") from exc

    def _get_json(self, url: str) -> dict[str, Any]:
        request = urllib.request.Request(
            url,
            headers={"Accept": "application/json", "User-Agent": "AimiliVPN/3.0"},
        )
        raw = self._request(request)
        try:
            payload = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise SourceError("PublicVPNList returned invalid JSON") from exc
        if not isinstance(payload, dict):
            raise SourceError("PublicVPNList returned a non-object JSON response")
        return payload

    def _read_cache(self, filters: NodeFilters) -> list[dict[str, Any]] | None:
        if self.cache_path is None or self.metadata_ttl <= 0:
            return None
        with self._cache_lock:
            try:
                payload = json.loads(self.cache_path.read_text(encoding="utf-8"))
                if payload.get("key") != filters.cache_key() or float(payload.get("expires_at", 0)) <= time.time():
                    return None
                nodes = payload.get("nodes")
                if isinstance(nodes, list):
                    return [node for node in nodes if isinstance(node, dict)]
            except (OSError, ValueError, TypeError, json.JSONDecodeError):
                return None
        return None

    def _write_cache(self, filters: NodeFilters, nodes: list[dict[str, Any]]) -> None:
        if self.cache_path is None or self.metadata_ttl <= 0:
            return
        payload = {
            "key": filters.cache_key(),
            "expires_at": time.time() + self.metadata_ttl,
            "nodes": nodes,
        }
        with self._cache_lock:
            try:
                self.cache_path.parent.mkdir(parents=True, exist_ok=True)
                temp_path = self.cache_path.with_suffix(self.cache_path.suffix + ".tmp")
                temp_path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
                temp_path.replace(self.cache_path)
            except OSError:
                pass

    def fetch_candidates(
        self,
        filters: NodeFilters,
        *,
        max_candidates: int = 300,
        force_refresh: bool = False,
    ) -> list[dict[str, Any]]:
        if not force_refresh:
            cached = self._read_cache(filters)
            if cached is not None:
                return cached[:max_candidates]

        nodes: list[dict[str, Any]] = []
        seen: set[str] = set()
        total = None
        for page in range(1, self.max_pages + 1):
            query: dict[str, Any] = {"page": page, "page_size": self.page_size}
            if filters.filter_country:
                query["country"] = _slug(filters.filter_country)
            if filters.filter_source:
                query["source"] = filters.filter_source
            url = PUBLICVPNLIST_API_URL + "?" + urllib.parse.urlencode(query)
            payload = self._get_json(url)
            page_nodes = normalize_publicvpnlist_payload(payload)
            page_nodes = apply_node_filters(page_nodes, filters, include_ip_purity=False)
            for node in page_nodes:
                node_id = str(node.get("id") or "")
                if node_id and node_id not in seen:
                    nodes.append(node)
                    seen.add(node_id)
                    if len(nodes) >= max_candidates:
                        break
            if len(nodes) >= max_candidates:
                break

            raw_items = payload.get("items")
            if not isinstance(raw_items, list) or not raw_items:
                break
            pagination = payload.get("pagination")
            if isinstance(pagination, Mapping):
                total = _bounded_int(pagination.get("total"), 0, 0, 10_000_000)
            if total is not None and page * self.page_size >= total:
                break

        self._write_cache(filters, nodes)
        return nodes

    def fetch_source_names(self) -> list[str]:
        payload = self._get_json(PUBLICVPNLIST_SOURCES_URL)
        raw_sources = payload.get("items", payload.get("sources", payload.get("data", [])))
        if not isinstance(raw_sources, list):
            raise SourceError("PublicVPNList sources response is missing an array")
        names: set[str] = set()
        for item in raw_sources:
            if isinstance(item, str):
                name = _clean_text(item, 80)
            elif isinstance(item, Mapping):
                name = _clean_text(_first(item, "name", "source", "label"), 80)
            else:
                name = ""
            if name and re.fullmatch(r"[A-Za-z0-9 ._()/+\-]{1,80}", name):
                names.add(name)
        return sorted(names, key=str.casefold)

    def download_openvpn_config(self, legacy_id: int) -> str:
        if legacy_id <= 0:
            raise SourceError("PublicVPNList node has an invalid legacy_id")
        body = urllib.parse.urlencode({"id": legacy_id}).encode("ascii")
        token_request = urllib.request.Request(
            PUBLICVPNLIST_TOKEN_URL,
            data=body,
            method="POST",
            headers={
                "Content-Type": "application/x-www-form-urlencoded",
                "X-Requested-With": "XMLHttpRequest",
                "Accept": "application/json,text/plain,*/*",
                "User-Agent": "AimiliVPN/3.0",
            },
        )
        raw_token = self._request(token_request).decode("utf-8", errors="replace").strip()
        download_url = self._extract_download_url(raw_token)
        self._validate_url(download_url, download=True)
        config_request = urllib.request.Request(
            download_url,
            headers={
                "Accept": "application/x-openvpn-profile,text/plain,*/*",
                "User-Agent": "AimiliVPN/3.0",
            },
        )
        config = self._request(config_request).decode("utf-8", errors="replace")
        validate_openvpn_profile(config)
        return config

    @staticmethod
    def _extract_download_url(raw_token: str) -> str:
        payload: Any = None
        try:
            payload = json.loads(raw_token)
        except json.JSONDecodeError:
            pass
        if isinstance(payload, Mapping):
            direct = _first(payload, "download_url", "downloadUrl", "url")
            if direct:
                return urllib.parse.urljoin(PUBLICVPNLIST_DOWNLOAD_URL, str(direct))
            token = _first(payload, "token", "download_token")
            if token:
                return PUBLICVPNLIST_DOWNLOAD_URL + "?" + urllib.parse.urlencode({"token": str(token)})
        if raw_token.startswith("https://"):
            return raw_token
        match = re.search(r"(?:^|[?&])token=([A-Za-z0-9._~-]+)", raw_token)
        if match:
            return PUBLICVPNLIST_DOWNLOAD_URL + "?" + urllib.parse.urlencode({"token": match.group(1)})
        if re.fullmatch(r"[A-Za-z0-9._~-]{8,512}", raw_token):
            return PUBLICVPNLIST_DOWNLOAD_URL + "?" + urllib.parse.urlencode({"token": raw_token})
        raise SourceError("PublicVPNList token response did not contain a download URL")


_UNSAFE_OPENVPN_DIRECTIVES = {
    "auth-user-pass-verify",
    "client-connect",
    "client-disconnect",
    "down",
    "ipchange",
    "learn-address",
    "management",
    "management-client",
    "plugin",
    "route-pre-down",
    "route-up",
    "script-security",
    "tls-verify",
    "up",
}


def validate_openvpn_profile(config: str) -> None:
    if len(config.encode("utf-8")) > 2 * 1024 * 1024:
        raise SourceError("OpenVPN profile is larger than 2 MiB")
    has_remote = False
    for raw_line in config.splitlines():
        line = raw_line.strip()
        if not line or line.startswith(("#", ";", "<")):
            continue
        directive = line.split(None, 1)[0].lstrip("-").lower()
        if directive == "remote":
            has_remote = True
        if directive in _UNSAFE_OPENVPN_DIRECTIVES:
            raise SourceError(f"OpenVPN profile contains unsafe directive: {directive}")
    if not has_remote:
        raise SourceError("OpenVPN profile does not contain a remote directive")
