"""从插件目录发现用户自装的插件。

插件目录里每个插件是一个 `.py` 文件，或一个包含 `plugin.py` 的子目录。
模块需要导出 `PLUGIN`（`PluginDefinition`）；缺少或导入失败都只跳过并记录。
"""

from __future__ import annotations

import importlib.util
import logging
import sys
from pathlib import Path

from ..core.config import settings
from .contract import PluginDefinition

logger = logging.getLogger(__name__)


def discover_external_plugins(directory: Path | None = None) -> list[PluginDefinition]:
    """扫描插件目录，返回其中可用的插件定义。"""
    root = directory or Path(settings.plugins_dir).expanduser()
    if not str(root).strip() or not root.is_dir():
        return []

    definitions: list[PluginDefinition] = []
    seen_ids: set[str] = set()
    for candidate in sorted(root.iterdir()):
        module_file = _module_file(candidate)
        if module_file is None:
            continue
        definition = _load_definition(module_file)
        if definition is None:
            continue
        if definition.manifest.id in seen_ids:
            logger.error(
                "Duplicate external plugin id ignored: %s", definition.manifest.id
            )
            continue
        seen_ids.add(definition.manifest.id)
        definitions.append(
            PluginDefinition(
                manifest=definition.manifest,
                register=definition.register,
                source="external",
                path=str(module_file),
            )
        )
    return definitions


def _module_file(candidate: Path) -> Path | None:
    if candidate.is_file() and candidate.suffix == ".py":
        return candidate
    if candidate.is_dir() and (candidate / "plugin.py").is_file():
        return candidate / "plugin.py"
    return None


def _load_definition(module_file: Path) -> PluginDefinition | None:
    module_name = f"lens_plugin_{module_file.parent.name}_{module_file.stem}"
    try:
        spec = importlib.util.spec_from_file_location(module_name, module_file)
        if spec is None or spec.loader is None:
            logger.warning("Unreadable plugin file: %s", module_file)
            return None
        module = importlib.util.module_from_spec(spec)
        sys.modules[module_name] = module
        spec.loader.exec_module(module)
    except Exception:
        logger.exception("External plugin failed to load: %s", module_file)
        sys.modules.pop(module_name, None)
        return None

    definition = getattr(module, "PLUGIN", None)
    if not isinstance(definition, PluginDefinition):
        logger.warning("Plugin file exports no PLUGIN definition: %s", module_file)
        return None
    return definition
