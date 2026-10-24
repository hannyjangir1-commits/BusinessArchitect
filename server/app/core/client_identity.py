"""Trusted reverse-proxy client identity extraction and validation."""

import ipaddress
import logging
from typing import List, Optional, Union
from fastapi import Request

logger = logging.getLogger(__name__)

# Fallback identity sentinels for missing or invalid client contexts.
# CRITICAL: These sentinels are rate-limited like any other client identity,
# preventing attacker-controlled bypasses.
CLIENT_ID_MISSING = "missing_client"
CLIENT_ID_MALFORMED = "malformed_client"

MAX_FORWARDED_HEADER_LENGTH = 512
MAX_FORWARDED_HOPS = 10


def _clean_ip_string(raw: str) -> str:
    """Strip whitespace, enclosing brackets, or port numbers from an IP string."""
    cleaned = raw.strip()
    if cleaned.startswith("[") and "]" in cleaned:
        cleaned = cleaned[1:cleaned.index("]")]
    elif ":" in cleaned and cleaned.count(":") == 1:
        # IPv4 with port, e.g. '192.0.2.1:8000'
        cleaned = cleaned.split(":")[0]
    return cleaned.strip()


def parse_trusted_networks(trusted_proxies: Optional[List[str]]) -> List[Union[ipaddress.IPv4Network, ipaddress.IPv6Network]]:
    """Parse configured trusted proxy strings/CIDRs into IP network objects."""
    if not trusted_proxies:
        return []
    networks = []
    for item in trusted_proxies:
        if not item or not isinstance(item, str):
            continue
        cleaned = item.strip()
        if not cleaned:
            continue
        if cleaned.lower() in ("testclient", "localhost"):
            cleaned = "127.0.0.1"
        try:
            net = ipaddress.ip_network(cleaned, strict=False)
            networks.append(net)
        except ValueError:
            logger.warning("Ignoring invalid trusted proxy network entry: %s", cleaned[:64])
    return networks


def is_ip_trusted(ip_obj: Union[ipaddress.IPv4Address, ipaddress.IPv6Address], trusted_networks: List[Union[ipaddress.IPv4Network, ipaddress.IPv6Network]]) -> bool:
    """Check if an IP address belongs to any of the trusted networks."""
    for net in trusted_networks:
        if ip_obj in net:
            return True
    return False


from starlette.types import ASGIApp, Receive, Scope, Send
from starlette.datastructures import Headers as StarletteHeaders
from app.core.config import settings


def _extract_from_forwarded(
    peer_ip: Union[ipaddress.IPv4Address, ipaddress.IPv6Address],
    forwarded_header: Optional[str],
    trusted_nets: List[Union[ipaddress.IPv4Network, ipaddress.IPv6Network]]
) -> str:
    """Extract authoritative client IP traversing X-Forwarded-For right-to-left."""
    if not forwarded_header or not forwarded_header.strip():
        return str(peer_ip)

    if len(forwarded_header) > MAX_FORWARDED_HEADER_LENGTH:
        logger.warning("Rejected oversized X-Forwarded-For header (length=%d)", len(forwarded_header))
        return CLIENT_ID_MALFORMED

    raw_hops = [h.strip() for h in forwarded_header.split(",") if h.strip()]
    if not raw_hops:
        return str(peer_ip)

    if len(raw_hops) > MAX_FORWARDED_HOPS:
        logger.warning("Rejected X-Forwarded-For chain exceeding %d hops (count=%d)", MAX_FORWARDED_HOPS, len(raw_hops))
        return CLIENT_ID_MALFORMED

    # Right-to-left traversal: find first non-trusted hop
    for hop_raw in reversed(raw_hops):
        cleaned_hop = _clean_ip_string(hop_raw)
        try:
            hop_ip = ipaddress.ip_address(cleaned_hop)
        except ValueError:
            return CLIENT_ID_MALFORMED

        if not is_ip_trusted(hop_ip, trusted_nets):
            return str(hop_ip)

    # If all hops in chain are trusted proxies, the leftmost hop represents the client
    try:
        leftmost = ipaddress.ip_address(_clean_ip_string(raw_hops[0]))
        return str(leftmost)
    except ValueError:
        return CLIENT_ID_MALFORMED


class TrustedProxyMiddleware:
    """
    ASGI middleware establishing a coherent reverse-proxy trust boundary.
    Runs on the raw ASGI connection before application handlers.

    1. Inspects immediate socket peer in scope['client'].
    2. If untrusted: completely ignores X-Forwarded-For and X-Forwarded-Proto headers.
       scope['client_ip'] is set directly to the peer IP.
    3. If trusted:
       - Extracts authoritative client IP from X-Forwarded-For right-to-left.
       - Sets scope['scheme'] from X-Forwarded-Proto if 'https' or 'http'.
    4. Sets scope['client_ip'] for downstream rate limiters and audit handlers.
    """
    def __init__(self, app: ASGIApp, trusted_proxies: Optional[List[str]] = None):
        self.app = app
        self.trusted_proxies = trusted_proxies

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] == "http":
            headers = StarletteHeaders(scope=scope)
            peer = scope.get("client")
            peer_raw = peer[0] if peer and len(peer) > 0 else None

            proxies = self.trusted_proxies if self.trusted_proxies is not None else settings.TRUSTED_PROXIES
            trusted_nets = parse_trusted_networks(proxies)

            if not peer_raw or not str(peer_raw).strip():
                scope["client_ip"] = CLIENT_ID_MISSING
            else:
                cleaned_peer = _clean_ip_string(str(peer_raw))
                if cleaned_peer.lower() in ("testclient", "localhost"):
                    cleaned_peer = "127.0.0.1"
                try:
                    peer_ip = ipaddress.ip_address(cleaned_peer)
                    if trusted_nets and is_ip_trusted(peer_ip, trusted_nets):
                        # Trusted proxy: update scheme if X-Forwarded-Proto is provided
                        proto = headers.get("X-Forwarded-Proto", "").strip().lower()
                        if proto in ("https", "http"):
                            scope["scheme"] = proto

                        forwarded_header = headers.get("X-Forwarded-For")
                        scope["client_ip"] = _extract_from_forwarded(peer_ip, forwarded_header, trusted_nets)
                    else:
                        # Direct untrusted peer: ignore forwarding headers entirely
                        scope["client_ip"] = str(peer_ip)
                except ValueError:
                    scope["client_ip"] = CLIENT_ID_MALFORMED

        await self.app(scope, receive, send)


def extract_client_ip(
    request: Request,
    trusted_proxies: Optional[List[str]] = None
) -> str:
    """
    Extract and validate the true client IP address enforcing the proxy trust boundary.

    Policy:
    1. If middleware already resolved client_ip and no custom override is passed, use it.
    2. Determine the immediate peer IP from request.client.host.
    3. If request.client is absent, return 'missing_client'.
    4. If peer IP cannot be parsed as a valid IPv4/IPv6, return 'malformed_client'.
    5. If peer IP does NOT belong to configured TRUSTED_PROXIES, the connection is from an
       untrusted peer. The client identity IS the peer IP. Any X-Forwarded-For or Forwarded
       headers sent by the peer are completely ignored.
    6. If peer IP IS in TRUSTED_PROXIES, inspect the X-Forwarded-For header using right-to-left
       traversal (first non-trusted hop is authoritative client).
    """
    if trusted_proxies is None and hasattr(request, "scope") and "client_ip" in request.scope:
        return request.scope["client_ip"]

    peer_raw = request.client.host if request.client else None
    if not peer_raw or not str(peer_raw).strip():
        return CLIENT_ID_MISSING

    peer_cleaned = _clean_ip_string(str(peer_raw))
    if peer_cleaned.lower() in ("testclient", "localhost"):
        peer_cleaned = "127.0.0.1"
    try:
        peer_ip = ipaddress.ip_address(peer_cleaned)
    except ValueError:
        return CLIENT_ID_MALFORMED

    trusted_nets = parse_trusted_networks(trusted_proxies if trusted_proxies is not None else settings.TRUSTED_PROXIES)
    if not trusted_nets or not is_ip_trusted(peer_ip, trusted_nets):
        # Peer is not a trusted proxy. Ignore all forwarding headers!
        return str(peer_ip)

    # Peer is trusted. Inspect X-Forwarded-For header
    forwarded_header = request.headers.get("X-Forwarded-For")
    return _extract_from_forwarded(peer_ip, forwarded_header, trusted_nets)
