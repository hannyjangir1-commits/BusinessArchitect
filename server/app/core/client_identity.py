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


def extract_client_ip(
    request: Request,
    trusted_proxies: Optional[List[str]] = None
) -> str:
    """
    Extract and validate the true client IP address enforcing the proxy trust boundary.

    Policy:
    1. Determine the immediate peer IP from request.client.host.
    2. If request.client is absent, return 'missing_client'.
    3. If peer IP cannot be parsed as a valid IPv4/IPv6, return 'malformed_client'.
    4. If peer IP does NOT belong to configured TRUSTED_PROXIES, the connection is from an
       untrusted peer. The client identity IS the peer IP. Any X-Forwarded-For or Forwarded
       headers sent by the peer are completely ignored.
    5. If peer IP IS in TRUSTED_PROXIES, inspect the X-Forwarded-For header:
       - Header length must not exceed MAX_FORWARDED_HEADER_LENGTH (512 chars).
       - Header chain must not exceed MAX_FORWARDED_HOPS (10 hops).
       - Traverse the chain right-to-left (from proxy nearest to server backwards).
       - The first non-trusted hop encountered is the authoritative client IP.
       - If all hops are trusted, the leftmost hop is the client IP.
       - If any hop in the chain is malformed or invalid, return 'malformed_client'.
    6. All extracted IP addresses are canonicalized (standard IPv4/IPv6 notation).
    7. Attacker-controlled header strings are never logged in full.
    """
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

    trusted_nets = parse_trusted_networks(trusted_proxies)
    if not trusted_nets or not is_ip_trusted(peer_ip, trusted_nets):
        # Peer is not a trusted proxy. Ignore all forwarding headers!
        return str(peer_ip)

    # Peer is trusted. Inspect X-Forwarded-For header
    forwarded_header = request.headers.get("X-Forwarded-For")
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
