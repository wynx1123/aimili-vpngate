from __future__ import annotations

import unittest

from tunnel_slots import TunnelHandle, TunnelSlots


class DummyProcess:
    def __init__(self, return_code=None) -> None:
        self.return_code = return_code

    def poll(self):
        return self.return_code


class TunnelSlotTests(unittest.TestCase):
    def test_make_before_break_moves_previous_tunnel_to_draining(self) -> None:
        slots = TunnelSlots()
        first = TunnelHandle("one", "tun0", 100, DummyProcess(), "one.ovpn")
        second = TunnelHandle("two", "tun1", 101, DummyProcess(), "two.ovpn")

        self.assertIsNone(slots.activate(first))
        previous = slots.activate(second)

        self.assertIs(previous, first)
        self.assertIs(slots.active(), second)
        self.assertEqual(slots.draining("tun0"), [first])
        self.assertEqual(slots.candidate_interface(), "tun0")

    def test_rejects_wrong_route_table(self) -> None:
        slots = TunnelSlots()
        with self.assertRaises(ValueError):
            slots.activate(TunnelHandle("one", "tun0", 101, DummyProcess(), "one.ovpn"))

    def test_clear_returns_active_and_draining_handles(self) -> None:
        slots = TunnelSlots()
        first = TunnelHandle("one", "tun0", 100, DummyProcess(), "one.ovpn")
        second = TunnelHandle("two", "tun1", 101, DummyProcess(), "two.ovpn")
        slots.activate(first)
        slots.activate(second)
        handles = slots.clear()
        self.assertEqual({handle.node_id for handle in handles}, {"one", "two"})
        self.assertIsNone(slots.active())


if __name__ == "__main__":
    unittest.main()
