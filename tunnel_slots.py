from __future__ import annotations

import threading
import time
from dataclasses import dataclass
from typing import Any


@dataclass
class TunnelHandle:
    node_id: str
    interface: str
    route_table: int
    process: Any
    config_file: str
    protocol: str = "openvpn"
    started_at: float = 0.0

    def __post_init__(self) -> None:
        if not self.started_at:
            self.started_at = time.time()

    def running(self) -> bool:
        return self.process is not None and self.process.poll() is None


class TunnelSlots:
    """Thread-safe active/candidate bookkeeping for make-before-break switching."""

    def __init__(self, interfaces: tuple[str, str] = ("tun0", "tun1"), route_tables: tuple[int, int] = (100, 101)) -> None:
        if len(interfaces) != 2 or len(route_tables) != 2:
            raise ValueError("TunnelSlots requires exactly two interfaces and route tables")
        if len(set(interfaces)) != 2 or len(set(route_tables)) != 2:
            raise ValueError("Tunnel slot interfaces and route tables must be unique")
        self.interfaces = interfaces
        self.route_tables = route_tables
        self._active: TunnelHandle | None = None
        self._draining: dict[str, TunnelHandle] = {}
        self._lock = threading.RLock()

    def table_for(self, interface: str) -> int:
        try:
            return self.route_tables[self.interfaces.index(interface)]
        except ValueError as exc:
            raise ValueError(f"Unknown tunnel interface: {interface}") from exc

    def active(self) -> TunnelHandle | None:
        with self._lock:
            return self._active

    def candidate_interface(self) -> str:
        with self._lock:
            if self._active is None:
                return self.interfaces[0]
            return self.interfaces[1] if self._active.interface == self.interfaces[0] else self.interfaces[0]

    def activate(self, handle: TunnelHandle) -> TunnelHandle | None:
        if handle.interface not in self.interfaces:
            raise ValueError(f"Unknown tunnel interface: {handle.interface}")
        if handle.route_table != self.table_for(handle.interface):
            raise ValueError("Tunnel route table does not match its interface slot")
        with self._lock:
            previous = self._active
            self._active = handle
            self._draining.pop(handle.interface, None)
            if previous is not None and previous.interface != handle.interface:
                self._draining[previous.interface] = previous
            return previous

    def draining(self, interface: str | None = None) -> list[TunnelHandle]:
        with self._lock:
            if interface is not None:
                handle = self._draining.get(interface)
                return [handle] if handle is not None else []
            return list(self._draining.values())

    def release_draining(self, interface: str) -> TunnelHandle | None:
        with self._lock:
            return self._draining.pop(interface, None)

    def clear(self) -> list[TunnelHandle]:
        with self._lock:
            handles = list(self._draining.values())
            if self._active is not None:
                handles.append(self._active)
            self._active = None
            self._draining.clear()
            unique: dict[int, TunnelHandle] = {}
            for handle in handles:
                unique[id(handle)] = handle
            return list(unique.values())

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            active = self._active
            return {
                "active": None
                if active is None
                else {
                    "node_id": active.node_id,
                    "interface": active.interface,
                    "route_table": active.route_table,
                    "protocol": active.protocol,
                    "started_at": active.started_at,
                    "running": active.running(),
                },
                "draining": [
                    {
                        "node_id": handle.node_id,
                        "interface": handle.interface,
                        "route_table": handle.route_table,
                        "protocol": handle.protocol,
                        "started_at": handle.started_at,
                        "running": handle.running(),
                    }
                    for handle in self._draining.values()
                ],
            }
