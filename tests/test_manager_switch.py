from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

_data_directory = tempfile.TemporaryDirectory()
os.environ["VPNGATE_DATA_DIR"] = _data_directory.name

import proxy_server
import vpngate_manager as manager
from tunnel_slots import TunnelHandle, TunnelSlots


class FakeProcess:
    def __init__(self, name: str, events: list[str]) -> None:
        self.name = name
        self.events = events
        self.return_code = None

    def poll(self):
        return self.return_code

    def terminate(self) -> None:
        self.events.append(f"stop:{self.name}")
        self.return_code = 0

    def wait(self, timeout=None):
        return self.return_code

    def kill(self) -> None:
        self.events.append(f"kill:{self.name}")
        self.return_code = -9


class DeferredThread:
    def __init__(self, *args, **kwargs) -> None:
        self.target = kwargs.get("target") or (args[0] if args else None)

    def start(self) -> None:
        return None


class ManagerSwitchTests(unittest.TestCase):
    def setUp(self) -> None:
        self.events: list[str] = []
        manager.ensure_dirs()
        manager.tunnel_slots = TunnelSlots()
        self.old_process = FakeProcess("old", self.events)
        old = TunnelHandle("old-node", "tun0", 100, self.old_process, "old.ovpn")
        manager.tunnel_slots.activate(old)
        manager.active_openvpn_process = self.old_process
        manager.active_openvpn_node_id = "old-node"
        manager.active_openvpn_interface = "tun0"
        manager.is_connecting = False
        proxy_server.set_active_interface("tun0")

        config_path = Path(_data_directory.name) / "configs" / "new-node.ovpn"
        config_path.write_text("client\nremote 192.0.2.20 443 tcp\n", encoding="utf-8")
        nodes = [
            {
                "id": "old-node",
                "catalog_source": "vpngate",
                "protocol": "openvpn",
                "ip": "192.0.2.10",
                "remote_host": "192.0.2.10",
                "remote_port": 443,
                "proto": "tcp",
                "config_file": str(Path(_data_directory.name) / "configs" / "old.ovpn"),
                "probe_status": "available",
                "active": True,
            },
            {
                "id": "new-node",
                "catalog_source": "vpngate",
                "protocol": "openvpn",
                "ip": "192.0.2.20",
                "remote_host": "192.0.2.20",
                "remote_port": 443,
                "proto": "tcp",
                "config_file": str(config_path),
                "probe_status": "available",
                "active": False,
            },
        ]
        manager.write_json(manager.NODES_FILE, nodes)

    def tearDown(self) -> None:
        manager.is_connecting = False
        manager.tunnel_slots.clear()
        proxy_server.set_active_interface("tun0")

    def test_candidate_is_verified_before_proxy_switch_and_old_is_not_stopped(self) -> None:
        new_process = FakeProcess("new", self.events)

        def health(interface: str):
            self.events.append(f"health:{interface}")
            return {"ok": True, "ip": "198.51.100.20", "latency_ms": 25}

        real_switch = proxy_server.set_active_interface

        def switch(interface: str):
            self.events.append(f"switch:{interface}")
            return real_switch(interface)

        with (
            mock.patch.object(manager, "run_openvpn_until_ready", return_value=(True, "ok", new_process)),
            mock.patch.object(manager, "setup_policy_routing"),
            mock.patch.object(manager, "check_tunnel_health", side_effect=health),
            mock.patch.object(manager.proxy_server, "set_active_interface", side_effect=switch),
            mock.patch.object(manager.threading, "Thread", DeferredThread),
        ):
            manager.connect_node("new-node")

        self.assertLess(self.events.index("health:tun1"), self.events.index("switch:tun1"))
        self.assertNotIn("stop:old", self.events)
        self.assertEqual(proxy_server.get_active_interface(), "tun1")
        self.assertEqual(manager.tunnel_slots.active().node_id, "new-node")
        self.assertEqual(manager.tunnel_slots.draining("tun0")[0].node_id, "old-node")

    def test_failed_candidate_keeps_old_tunnel_active(self) -> None:
        new_process = FakeProcess("new", self.events)
        with (
            mock.patch.object(manager, "run_openvpn_until_ready", return_value=(True, "ok", new_process)),
            mock.patch.object(manager, "setup_policy_routing"),
            mock.patch.object(manager, "cleanup_policy_routing"),
            mock.patch.object(
                manager,
                "check_tunnel_health",
                return_value={"ok": False, "error": "candidate failed"},
            ),
        ):
            with self.assertRaises(RuntimeError):
                manager.connect_node("new-node")

        self.assertEqual(proxy_server.get_active_interface(), "tun0")
        self.assertEqual(manager.tunnel_slots.active().node_id, "old-node")
        self.assertNotIn("stop:old", self.events)
        self.assertIn("stop:new", self.events)


if __name__ == "__main__":
    unittest.main()
