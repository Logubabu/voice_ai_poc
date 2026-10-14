import unittest
from app.services.webrtc_service import (
    webrtc_service,
    resolve_to_ipv4,
    is_valid_ipv4,
    is_private_or_loopback,
)


class TestWebRTCService(unittest.IsolatedAsyncioTestCase):
    def test_ip_helpers(self):
        self.assertTrue(is_valid_ipv4("1.1.1.1"))
        self.assertTrue(is_valid_ipv4("127.0.0.1"))
        self.assertFalse(is_valid_ipv4("invalid-ip"))
        self.assertFalse(is_valid_ipv4(""))
        self.assertFalse(is_valid_ipv4("0.0.0.0"))

        self.assertTrue(is_private_or_loopback("127.0.0.1"))
        self.assertTrue(is_private_or_loopback("192.168.1.1"))
        self.assertTrue(is_private_or_loopback("10.0.0.1"))
        self.assertTrue(is_private_or_loopback("172.18.0.2"))
        self.assertFalse(is_private_or_loopback("8.8.8.8"))

        self.assertEqual(resolve_to_ipv4("8.8.8.8"), "8.8.8.8")
        self.assertIsNone(resolve_to_ipv4(""))
        self.assertIsNone(resolve_to_ipv4("invalid.invalid-domain-xyz-123456.com"))

    async def test_get_ice_servers(self):
        client_servers, aiortc_servers = await webrtc_service.get_ice_servers()
        self.assertIsInstance(client_servers, list)
        self.assertGreater(len(client_servers), 0)
        # Must have at least one STUN server
        self.assertTrue(any("stun:" in (s.get("urls") or "") for s in client_servers))
        self.assertIsInstance(aiortc_servers, list)
        self.assertEqual(len(aiortc_servers), len(client_servers))

    async def test_sanitize_and_munge_sdp(self):
        sample_sdp = """v=0
o=- 3969502902 3969502902 IN IP4 0.0.0.0
s=-
t=0 0
m=audio 50010 UDP/TLS/RTP/SAVPF 111 0 8
c=IN IP4 172.17.0.2
a=candidate:4f34beefcf2eb9d91192f8f7bd925cc9 1 udp 2130706431 172.17.0.2 50010 typ host
a=candidate:18685080ed7e60cbb79a6f7784559d28 1 udp 16777215 52.66.194.19 20871 typ relay raddr 172.17.0.2 rport 42435
a=candidate:12f2902f1f23eb766395bbdc170d066f 1 udp 1694498815 106.200.17.112 3543 typ srflx raddr 172.17.0.2 rport 50010
a=end-of-candidates
"""
        munged = await webrtc_service.sanitize_and_munge_sdp(
            answer_sdp=sample_sdp,
            client_host="voice-ai-alb.ap-southeast-2.elb.amazonaws.com",
            req_sdp="a=candidate:3487538208 1 udp 2122129151 192.168.1.4 54681 typ host",
        )

        # 1. Connection line must be normalized
        self.assertIn("c=IN IP4 0.0.0.0", munged)
        self.assertNotIn("c=IN IP4 172.17.0.2", munged)

        # 2. Client private WiFi IP must NEVER be added to server answer
        self.assertNotIn("192.168.1.4", munged)

        # 3. Domain names must NOT appear in candidate lines
        for line in munged.splitlines():
            if line.startswith("a=candidate:"):
                parts = line.split(" ")
                self.assertTrue(is_valid_ipv4(parts[4]), f"Candidate IP is not valid IPv4: {parts[4]}")

        # 4. Relay and srflx candidates preserved
        self.assertIn("typ relay", munged)
        self.assertIn("typ srflx", munged)


if __name__ == "__main__":
    unittest.main()
