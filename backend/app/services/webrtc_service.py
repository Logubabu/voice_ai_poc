import re
import socket
import ipaddress
import time
import json
import asyncio
from typing import List, Dict, Any, Tuple, Optional
import httpx

from app.config import config
from app.utils.logging import logger
from pipecat.transports.smallwebrtc.connection import IceServer


def is_valid_ipv4(addr: str) -> bool:
    """Checks whether the address is a valid, routable IPv4 address."""
    if not addr or not isinstance(addr, str):
        return False
    try:
        ip = ipaddress.ip_address(addr.strip())
        return ip.version == 4 and not ip.is_unspecified
    except Exception:
        return False


def is_private_or_loopback(addr: str) -> bool:
    """Checks whether the IPv4 address is loopback (127.0.0.1) or private (10.x, 172.16-31.x, 192.168.x)."""
    try:
        ip = ipaddress.ip_address(addr.strip())
        return ip.is_private or ip.is_loopback
    except Exception:
        return False


def resolve_to_ipv4(host: str | None) -> str | None:
    """Resolves a hostname or IP string to a valid IPv4 address."""
    if not host or not isinstance(host, str):
        return None
    cleaned = host.strip()
    if is_valid_ipv4(cleaned):
        return cleaned
    try:
        # Strip port or scheme if accidentally present
        if ":" in cleaned:
            cleaned = cleaned.split(":")[0]
        ip = socket.gethostbyname(cleaned)
        if is_valid_ipv4(ip):
            return ip
    except Exception:
        pass
    return None


class WebRTCService:
    """Manages WebRTC ICE servers, NAT traversal (STUN/TURN), public IP discovery, and SDP munging."""

    def __init__(self):
        self._cached_client_servers: List[Dict[str, Any]] = []
        self._cached_aiortc_servers: List[IceServer] = []
        self._tokens_expire_at: float = 0.0
        self._cached_public_ip: Optional[str] = None
        self._public_ip_checked_at: float = 0.0

    async def get_public_ip(self) -> Optional[str]:
        """Discovers the server's public IPv4 address for direct P2P connections."""
        # 1. Explicit configuration takes precedence
        if config.WEBRTC_HOST:
            resolved = resolve_to_ipv4(config.WEBRTC_HOST)
            if resolved:
                return resolved

        # 2. Return cached public IP if checked within the last 1 hour
        now = time.time()
        if self._cached_public_ip and (now - self._public_ip_checked_at < 3600):
            return self._cached_public_ip

        if not getattr(config, "AUTO_DISCOVER_PUBLIC_IP", True):
            return None

        # 3. Try AWS IMDSv2 / IMDSv1 (for EC2 / ECS container deployments)
        try:
            async with httpx.AsyncClient(timeout=1.0) as client:
                resp = await client.get("http://169.254.169.254/latest/meta-data/public-ipv4")
                if resp.status_code == 200:
                    candidate = resp.text.strip()
                    if is_valid_ipv4(candidate):
                        self._cached_public_ip = candidate
                        self._public_ip_checked_at = now
                        logger.info(f"[WEBRTC][IP] Discovered public IP via AWS IMDS: {candidate}")
                        return candidate
        except Exception:
            pass

        # 4. Fallback to public checkip endpoints
        discovery_endpoints = [
            "https://checkip.amazonaws.com",
            "https://api.ipify.org",
        ]
        for url in discovery_endpoints:
            try:
                async with httpx.AsyncClient(timeout=2.0) as client:
                    resp = await client.get(url)
                    if resp.status_code == 200:
                        candidate = resp.text.strip()
                        if is_valid_ipv4(candidate):
                            self._cached_public_ip = candidate
                            self._public_ip_checked_at = now
                            logger.info(f"[WEBRTC][IP] Discovered public IP via {url}: {candidate}")
                            return candidate
            except Exception:
                continue

        return None

    async def get_ice_servers(self) -> Tuple[List[Dict[str, Any]], List[IceServer]]:
        """Retrieves active ICE servers (STUN + TURN) for both client browsers and aiortc backend.

        Automatically integrates Twilio Network Traversal Service (NTS) if Twilio credentials are configured,
        custom TURN servers, or reliable Google STUN fallback.
        """
        now = time.time()
        # Return cached list if still valid (refresh 5 minutes before expiration)
        if self._cached_client_servers and self._cached_aiortc_servers and (now < self._tokens_expire_at - 300):
            return self._cached_client_servers, self._cached_aiortc_servers

        client_servers: List[Dict[str, Any]] = []
        aiortc_servers: List[IceServer] = []
        ttl = 86400  # Default 24 hours

        # 1. Twilio Network Traversal Service (TURN & STUN)
        if config.TWILIO_ACCOUNT_SID and config.TWILIO_AUTH_TOKEN:
            try:
                async with httpx.AsyncClient(timeout=6.0) as client:
                    resp = await client.post(
                        f"https://api.twilio.com/2010-04-01/Accounts/{config.TWILIO_ACCOUNT_SID}/Tokens.json",
                        auth=(config.TWILIO_ACCOUNT_SID, config.TWILIO_AUTH_TOKEN),
                    )
                    if resp.status_code in (200, 201):
                        data = resp.json()
                        raw_servers = data.get("ice_servers", [])
                        ttl = int(data.get("ttl", 86400))
                        logger.info(f"[WEBRTC][NTS] Successfully fetched {len(raw_servers)} Twilio TURN/STUN servers (TTL: {ttl}s)")

                        for s in raw_servers:
                            url = s.get("url") or s.get("urls")
                            username = s.get("username")
                            credential = s.get("credential")

                            if not url:
                                continue

                            client_entry: Dict[str, Any] = {"urls": url}
                            if username and credential:
                                client_entry["username"] = username
                                client_entry["credential"] = credential
                            client_servers.append(client_entry)

                            aiortc_servers.append(
                                IceServer(
                                    urls=url,
                                    username=username,
                                    credential=credential,
                                )
                            )
            except Exception as e:
                logger.warning(f"[WEBRTC][NTS] Notice fetching Twilio ICE tokens: {e}")

        # 2. Custom TURN server from environment variables
        turn_url = getattr(config, "TURN_SERVER_URL", "")
        turn_user = getattr(config, "TURN_USERNAME", "")
        turn_pass = getattr(config, "TURN_PASSWORD", "")
        if turn_url:
            urls = [u.strip() for u in turn_url.split(",") if u.strip()]
            for u in urls:
                c_entry = {"urls": u}
                if turn_user and turn_pass:
                    c_entry["username"] = turn_user
                    c_entry["credential"] = turn_pass
                client_servers.append(c_entry)
                aiortc_servers.append(IceServer(urls=u, username=turn_user or None, credential=turn_pass or None))
            logger.info(f"[WEBRTC] Added custom configured TURN server: {turn_url}")

        # 3. Configured ICE_SERVERS (comma-separated or JSON)
        raw_ice = getattr(config, "ICE_SERVERS", "") or ""
        if raw_ice.startswith("[") or raw_ice.startswith("{"):
            try:
                parsed = json.loads(raw_ice)
                if isinstance(parsed, dict):
                    parsed = [parsed]
                for p in parsed:
                    p_urls = p.get("urls") or p.get("url")
                    p_user = p.get("username")
                    p_cred = p.get("credential")
                    if p_urls:
                        client_servers.append(p)
                        aiortc_servers.append(IceServer(urls=p_urls, username=p_user, credential=p_cred))
            except Exception as e:
                logger.warning(f"[WEBRTC] Notice parsing ICE_SERVERS JSON: {e}")
        elif raw_ice:
            for item in raw_ice.split(","):
                item = item.strip()
                if item and not any(s.get("urls") == item for s in client_servers):
                    client_servers.append({"urls": item})
                    aiortc_servers.append(IceServer(urls=item))

        # 4. Reliable Google STUN servers fallback
        google_stuns = [
            "stun:stun.l.google.com:19302",
            "stun:stun1.l.google.com:19302",
            "stun:stun2.l.google.com:19302",
        ]
        for gstun in google_stuns:
            if not any(s.get("urls") == gstun for s in client_servers):
                client_servers.append({"urls": gstun})
                aiortc_servers.append(IceServer(urls=gstun))

        self._cached_client_servers = client_servers
        self._cached_aiortc_servers = aiortc_servers
        self._tokens_expire_at = now + min(ttl, 86400)

        logger.info(f"[WEBRTC] Configured {len(client_servers)} ICE server(s) for WebRTC connections")
        return client_servers, aiortc_servers

    async def sanitize_and_munge_sdp(
        self,
        answer_sdp: str,
        client_host: Optional[str] = None,
        req_sdp: Optional[str] = None,
    ) -> str:
        """Sanitizes and munges the SDP answer to ensure valid ICE candidate traversal across Docker and cloud networks.

        Rules:
        - Resolves public IP or configured host and adds as candidate.
        - NEVER includes the client's private WiFi IP from the offer as a server candidate.
        - NEVER adds unresolvable hostnames into an `a=candidate:` line (RFC 8839 compliance).
        - Only includes `127.0.0.1` if client is legitimately connecting from localhost.
        - Preserves all aiortc-generated `relay` and `srflx` candidates.
        """
        if not answer_sdp:
            return answer_sdp

        # 1. Determine candidate IP addresses reachable from outside the container
        target_ips: List[str] = []

        is_local_client = client_host in ("localhost", "127.0.0.1", "::1", None)
        if is_local_client:
            target_ips.append("127.0.0.1")

        # Explicit WEBRTC_HOST configuration takes highest precedence for public direct host candidate
        if config.WEBRTC_HOST:
            explicit_host_ip = resolve_to_ipv4(config.WEBRTC_HOST)
            if explicit_host_ip and explicit_host_ip not in target_ips and not is_private_or_loopback(explicit_host_ip):
                target_ips.append(explicit_host_ip)
        elif getattr(config, "AUTO_DISCOVER_PUBLIC_IP", True):
            # Only discover public IP if WEBRTC_HOST is not explicitly configured
            pub_ip = await self.get_public_ip()
            if pub_ip and pub_ip not in target_ips and not is_private_or_loopback(pub_ip):
                target_ips.append(pub_ip)

        # CRITICAL: DO NOT add client_host (the ALB or proxy domain) as a UDP host candidate!
        # An Application Load Balancer (ALB) or reverse proxy only handles TCP HTTP/HTTPS signaling,
        # and DROPS all UDP media packets. Adding the ALB IP as a host candidate causes browsers
        # to send audio packets to the ALB instead of the container or TURN relay, breaking audio.

        # 2. Process SDP answer line by line
        lines = answer_sdp.splitlines()
        new_lines: List[str] = []
        cand_idx = 1
        seen_cand_keys: set[str] = set()

        for line in lines:
            # Normalize private container IP on connection line
            if line.startswith("c=IN IP4 172.") or line.startswith("c=IN IP4 10."):
                new_lines.append("c=IN IP4 0.0.0.0")
                continue

            # Munge host candidates to provide the reachable external/public IP
            if line.startswith("a=candidate:") and " typ host" in line:
                parts = line.split(" ")
                if len(parts) >= 8:
                    orig_ip = parts[4]
                    orig_port = parts[5]

                    # Keep original host candidate if it's already an IP
                    if is_valid_ipv4(orig_ip):
                        key = f"{orig_ip}:{orig_port}"
                        if key not in seen_cand_keys:
                            new_lines.append(f"a=candidate:c{cand_idx} 1 udp 2130706431 {orig_ip} {orig_port} typ host")
                            seen_cand_keys.add(key)
                            cand_idx += 1

                    # Append target IPs (public IP, localhost if local)
                    for tip in target_ips:
                        key = f"{tip}:{orig_port}"
                        if key not in seen_cand_keys and is_valid_ipv4(tip):
                            prio = max(2130706431 - (cand_idx * 256), 1000)
                            new_lines.append(f"a=candidate:c{cand_idx} 1 udp {prio} {tip} {orig_port} typ host")
                            seen_cand_keys.add(key)
                            cand_idx += 1
                    continue

            # Keep relay, srflx, rtcp, and other standard SDP lines
            new_lines.append(line)

        return "\r\n".join(new_lines) + "\r\n"


webrtc_service = WebRTCService()
