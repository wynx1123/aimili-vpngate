from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path

from config_cleanup import ConfigCleanupPolicy, cleanup_config_cache


class ConfigCleanupTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.config_dir = Path(self.temp_dir.name) / "configs"
        self.config_dir.mkdir()
        self.now = 1_000_000.0

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def write_config(self, name: str, *, age: int, size: int = 32) -> Path:
        path = self.config_dir / name
        path.write_text("x" * size, encoding="utf-8")
        modified_at = self.now - age
        os.utime(path, (modified_at, modified_at))
        return path

    def test_deletes_unavailable_publicvpnlist_config_and_clears_payload(self) -> None:
        path = self.write_config("pvl.ovpn", age=3600)
        nodes = [
            {
                "id": "pvl-node",
                "catalog_source": "publicvpnlist",
                "probe_status": "unavailable",
                "config_file": str(path),
                "config_text": "client\nremote 192.0.2.1 443 tcp\n",
                "config_cached_at": self.now - 3600,
            }
        ]
        result = cleanup_config_cache(
            self.config_dir,
            nodes,
            policy=ConfigCleanupPolicy(invalid_grace_seconds=1800),
            now=self.now,
        )
        self.assertFalse(path.exists())
        self.assertEqual(result.deleted_by_reason, {"unavailable": 1})
        self.assertEqual(result.nodes[0]["config_text"], "")
        self.assertEqual(result.nodes[0]["config_cached_at"], 0)

    def test_protects_active_fixed_or_favorite_node(self) -> None:
        path = self.write_config("protected.ovpn", age=30 * 24 * 3600)
        nodes = [
            {
                "id": "protected-node",
                "catalog_source": "publicvpnlist",
                "probe_status": "unavailable",
                "config_file": str(path),
                "config_text": "profile",
            }
        ]
        result = cleanup_config_cache(
            self.config_dir,
            nodes,
            protected_node_ids={"protected-node"},
            policy=ConfigCleanupPolicy(max_files=0, invalid_grace_seconds=0, max_age_seconds=300),
            now=self.now,
        )
        self.assertTrue(path.exists())
        self.assertEqual(result.deleted_files, 0)

    def test_deletes_old_orphan_temporary_and_expired_files(self) -> None:
        orphan = self.write_config("orphan.ovpn", age=8 * 3600)
        temporary = self.write_config(".test_abandoned.ovpn", age=2 * 3600)
        expired = self.write_config("expired.ovpn", age=4 * 24 * 3600)
        fresh_invalid = self.write_config("fresh-invalid.ovpn", age=60)
        nodes = [
            {"id": "expired", "probe_status": "available", "config_file": str(expired)},
            {"id": "fresh", "probe_status": "unavailable", "config_file": str(fresh_invalid)},
        ]
        result = cleanup_config_cache(
            self.config_dir,
            nodes,
            policy=ConfigCleanupPolicy(
                max_files=100,
                max_age_seconds=3 * 24 * 3600,
                invalid_grace_seconds=1800,
                orphan_grace_seconds=6 * 3600,
                temp_max_age_seconds=3600,
            ),
            now=self.now,
        )
        self.assertFalse(orphan.exists())
        self.assertFalse(temporary.exists())
        self.assertFalse(expired.exists())
        self.assertTrue(fresh_invalid.exists())
        self.assertEqual(
            result.deleted_by_reason,
            {"expired": 1, "orphaned": 1, "temporary": 1},
        )

    def test_capacity_removes_oldest_unprotected_files(self) -> None:
        paths = [self.write_config(f"node-{index}.ovpn", age=500 - index * 100) for index in range(4)]
        nodes = [
            {"id": f"node-{index}", "probe_status": "available", "config_file": str(path)}
            for index, path in enumerate(paths)
        ]
        result = cleanup_config_cache(
            self.config_dir,
            nodes,
            protected_node_ids={"node-0"},
            policy=ConfigCleanupPolicy(
                max_files=2,
                max_age_seconds=100_000,
                invalid_grace_seconds=100_000,
                orphan_grace_seconds=100_000,
                temp_max_age_seconds=100_000,
            ),
            now=self.now,
        )
        self.assertTrue(paths[0].exists())
        self.assertFalse(paths[1].exists())
        self.assertFalse(paths[2].exists())
        self.assertTrue(paths[3].exists())
        self.assertEqual(result.deleted_by_reason, {"capacity": 2})
        self.assertEqual(result.remaining_files, 2)


if __name__ == "__main__":
    unittest.main()
