from __future__ import annotations

import time
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable


@dataclass(frozen=True)
class ConfigCleanupPolicy:
    max_files: int = 300
    max_age_seconds: int = 3 * 24 * 60 * 60
    invalid_grace_seconds: int = 30 * 60
    orphan_grace_seconds: int = 6 * 60 * 60
    temp_max_age_seconds: int = 60 * 60


@dataclass
class ConfigCleanupResult:
    nodes: list[dict[str, Any]]
    scanned_files: int
    remaining_files: int
    deleted_files: int
    deleted_bytes: int
    deleted_by_reason: dict[str, int]
    errors: list[str]

    def to_state(self) -> dict[str, Any]:
        return {
            "scanned_files": self.scanned_files,
            "remaining_files": self.remaining_files,
            "deleted_files": self.deleted_files,
            "deleted_bytes": self.deleted_bytes,
            "deleted_by_reason": self.deleted_by_reason,
            "errors": self.errors,
        }


def _contained_path(path: Path, directory: Path) -> Path | None:
    try:
        resolved = path.resolve(strict=False)
        resolved.relative_to(directory)
        return resolved
    except (OSError, ValueError):
        return None


def cleanup_config_cache(
    config_dir: Path,
    nodes: Iterable[dict[str, Any]],
    *,
    protected_node_ids: Iterable[str] = (),
    protected_paths: Iterable[Path] = (),
    policy: ConfigCleanupPolicy | None = None,
    now: float | None = None,
) -> ConfigCleanupResult:
    policy = policy or ConfigCleanupPolicy()
    now = time.time() if now is None else now
    config_dir = config_dir.resolve(strict=False)
    copied_nodes = [dict(node) for node in nodes]
    protected_ids = {str(node_id) for node_id in protected_node_ids if str(node_id)}
    protected = {
        resolved
        for path in protected_paths
        if (resolved := _contained_path(Path(path), config_dir)) is not None
    }

    node_by_path: dict[Path, dict[str, Any]] = {}
    for node in copied_nodes:
        raw_path = node.get("config_file")
        if not raw_path:
            continue
        resolved = _contained_path(Path(str(raw_path)), config_dir)
        if resolved is None:
            continue
        node_by_path[resolved] = node
        if str(node.get("id") or "") in protected_ids:
            protected.add(resolved)

    try:
        files = [path for path in config_dir.glob("*.ovpn") if path.is_file()]
    except OSError as exc:
        return ConfigCleanupResult(
            nodes=copied_nodes,
            scanned_files=0,
            remaining_files=0,
            deleted_files=0,
            deleted_bytes=0,
            deleted_by_reason={},
            errors=[str(exc)],
        )

    file_info: dict[Path, tuple[float, int]] = {}
    errors: list[str] = []
    for path in files:
        try:
            resolved = _contained_path(path, config_dir)
            if resolved is None:
                continue
            stat = path.stat()
            file_info[resolved] = (stat.st_mtime, stat.st_size)
        except OSError as exc:
            errors.append(f"{path.name}: {exc}")

    candidates: dict[Path, str] = {}
    for path, (modified_at, _) in file_info.items():
        if path in protected:
            continue
        age = max(0.0, now - modified_at)
        node = node_by_path.get(path)
        if path.name.startswith(".test_") and age >= policy.temp_max_age_seconds:
            candidates[path] = "temporary"
        elif node is None and age >= policy.orphan_grace_seconds:
            candidates[path] = "orphaned"
        elif node is not None and node.get("probe_status") == "unavailable" and age >= policy.invalid_grace_seconds:
            candidates[path] = "unavailable"
        elif age >= policy.max_age_seconds:
            candidates[path] = "expired"

    remaining_after_policy = [path for path in file_info if path not in candidates]
    overflow = max(0, len(remaining_after_policy) - max(0, policy.max_files))
    if overflow:
        capacity_candidates = sorted(
            (path for path in remaining_after_policy if path not in protected),
            key=lambda path: file_info[path][0],
        )
        for path in capacity_candidates[:overflow]:
            candidates[path] = "capacity"

    deleted_paths: set[Path] = set()
    deleted_bytes = 0
    reasons: Counter[str] = Counter()
    for path, reason in sorted(candidates.items(), key=lambda item: file_info[item[0]][0]):
        try:
            path.unlink()
            deleted_paths.add(path)
            deleted_bytes += file_info[path][1]
            reasons[reason] += 1
        except OSError as exc:
            errors.append(f"{path.name}: {exc}")

    if deleted_paths:
        for node in copied_nodes:
            raw_path = node.get("config_file")
            if not raw_path:
                continue
            resolved = _contained_path(Path(str(raw_path)), config_dir)
            if resolved not in deleted_paths:
                continue
            node["config_cached_at"] = 0
            if node.get("catalog_source") == "publicvpnlist":
                node["config_text"] = ""

    return ConfigCleanupResult(
        nodes=copied_nodes,
        scanned_files=len(file_info),
        remaining_files=len(file_info) - len(deleted_paths),
        deleted_files=len(deleted_paths),
        deleted_bytes=deleted_bytes,
        deleted_by_reason=dict(sorted(reasons.items())),
        errors=errors,
    )
