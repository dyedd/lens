"""从插件目录发现用户自装的插件。

插件目录里每个插件是一个 `.py` 文件，或一个包含 `plugin.py` 的子目录。
子目录按包加载，插件内可以用相对导入引用同目录的模块。
模块需要导出 `PLUGIN`（`PluginDefinition`）；缺少或导入失败时返回带原因的
`PluginLoadFailure`，插件列表里显示为 failed。
"""

from __future__ import annotations

import importlib
import importlib.util
import logging
import os
import re
import sys
import threading
from dataclasses import dataclass
from pathlib import Path

from ..core.config import settings
from .contract import PluginDefinition, PluginManifest

logger = logging.getLogger(__name__)

DirectoryStamp = tuple[tuple[str, int, int], ...]


@dataclass(frozen=True, slots=True)
class PluginLoadFailure:
    """插件目录里加载失败的一项；id 取目录名或文件名。"""

    plugin_id: str
    path: str
    error: str


class _PluginLoadError(Exception):
    pass


_MODULE_NAME_UNSAFE = re.compile(r"[^0-9A-Za-z_]")
_BYTECODE_DIR = "__pycache__"

# 模块文件 -> (所在目录的戳, 定义)。文件没变就复用同一个定义对象，
# 注册表据此判断无需重新注册该插件。
_loaded: dict[Path, tuple[DirectoryStamp, PluginDefinition]] = {}
_import_lock = threading.Lock()


def resolve_plugins_dir() -> Path | None:
    raw = settings.plugins_dir.strip()
    return Path(raw).expanduser() if raw else None


def build_directory_stamp(root: Path) -> DirectoryStamp:
    """目录下每个文件的（相对路径, mtime_ns, 大小），排序后作为变化判据。"""
    if root.is_file():
        stat = root.stat()
        return ((root.name, stat.st_mtime_ns, stat.st_size),)
    entries: list[tuple[str, int, int]] = []
    for current, dirs, files in os.walk(root):
        # 导入插件时 Python 会写字节码缓存，不算插件的变化。
        dirs[:] = [name for name in dirs if name != _BYTECODE_DIR]
        for name in files:
            path = Path(current, name)
            try:
                stat = path.stat()
            except OSError:
                continue
            entries.append(
                (path.relative_to(root).as_posix(), stat.st_mtime_ns, stat.st_size)
            )
    return tuple(sorted(entries))


def discover_external_plugins(
    directory: Path | None = None,
) -> list[PluginDefinition | PluginLoadFailure]:
    """扫描插件目录，返回其中的插件定义；加载失败的插件以 `PluginLoadFailure` 返回。"""
    root = directory or resolve_plugins_dir()
    if root is None or not root.is_dir():
        return []

    discovered: list[PluginDefinition | PluginLoadFailure] = []
    seen_ids: set[str] = set()
    with _import_lock:
        for candidate in sorted(root.iterdir()):
            module_file = _module_file(candidate)
            if module_file is None:
                continue
            found: PluginDefinition | PluginLoadFailure
            try:
                found = _load_cached(candidate, module_file)
                plugin_id = found.manifest.id
            except _PluginLoadError as exc:
                plugin_id = candidate.name if candidate.is_dir() else candidate.stem
                found = PluginLoadFailure(
                    plugin_id=plugin_id, path=str(module_file), error=str(exc)
                )
            if plugin_id in seen_ids:
                logger.error("Duplicate external plugin id ignored: %s", plugin_id)
                continue
            seen_ids.add(plugin_id)
            discovered.append(found)
    return discovered


def _module_file(candidate: Path) -> Path | None:
    if candidate.is_file() and candidate.suffix == ".py":
        return candidate
    if (
        candidate.is_dir()
        and candidate.name != _BYTECODE_DIR
        and (candidate / "plugin.py").is_file()
    ):
        return candidate / "plugin.py"
    return None


def _load_cached(candidate: Path, module_file: Path) -> PluginDefinition:
    key = module_file.resolve()
    stamp = build_directory_stamp(candidate)
    cached = _loaded.get(key)
    if cached is not None and cached[0] == stamp:
        return cached[1]
    _loaded.pop(key, None)
    loaded = _load_definition(candidate, module_file)
    definition = PluginDefinition(
        manifest=loaded.manifest,
        register=loaded.register,
        source="external",
        path=str(module_file),
    )
    _loaded[key] = (stamp, definition)
    return definition


def _load_definition(candidate: Path, module_file: Path) -> PluginDefinition:
    is_package = candidate.is_dir()
    # 目录插件与同名单文件插件分开命名，互不覆盖。
    kind = "pkg" if is_package else "file"
    stem = candidate.name if is_package else candidate.stem
    module_name = f"lens_plugin_{kind}_{_MODULE_NAME_UNSAFE.sub('_', stem)}"
    _purge_modules(module_name)
    importlib.invalidate_caches()
    try:
        spec = importlib.util.spec_from_file_location(
            module_name,
            module_file,
            submodule_search_locations=[str(candidate)] if is_package else None,
        )
        if spec is None or spec.loader is None:
            logger.warning("Unreadable plugin file: %s", module_file)
            raise _PluginLoadError("插件文件无法读取")
        module = importlib.util.module_from_spec(spec)
        sys.modules[module_name] = module
        spec.loader.exec_module(module)
    except _PluginLoadError:
        raise
    except Exception as exc:
        logger.exception("External plugin failed to load: %s", module_file)
        _purge_modules(module_name)
        message = str(exc)
        detail = f"{type(exc).__name__}: {message}" if message else type(exc).__name__
        raise _PluginLoadError(f"插件导入失败：{detail}") from exc

    definition = getattr(module, "PLUGIN", None)
    if not isinstance(definition, PluginDefinition) or not isinstance(
        definition.manifest, PluginManifest
    ):
        logger.warning("Plugin file exports no PLUGIN definition: %s", module_file)
        raise _PluginLoadError("插件没有导出有效的 PLUGIN（PluginDefinition）")
    return definition


def _purge_modules(module_name: str) -> None:
    """移除该插件上次导入留下的模块，含它的子模块。"""
    prefix = f"{module_name}."
    for name in [n for n in sys.modules if n == module_name or n.startswith(prefix)]:
        del sys.modules[name]
