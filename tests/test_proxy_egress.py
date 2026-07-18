from __future__ import annotations

import unittest

import proxy_server


class ProxyEgressTests(unittest.TestCase):
    def setUp(self) -> None:
        self.previous = proxy_server.get_active_interface()

    def tearDown(self) -> None:
        proxy_server.set_active_interface(self.previous)

    def test_active_interface_can_switch_atomically(self) -> None:
        old = proxy_server.set_active_interface("tun1")
        self.assertEqual(old, self.previous)
        self.assertEqual(proxy_server.get_active_interface(), "tun1")
        self.assertEqual(proxy_server.get_egress_snapshot()["active_interface"], "tun1")

    def test_invalid_interface_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            proxy_server.set_active_interface("tun0; rm")


if __name__ == "__main__":
    unittest.main()
