"""Project-wide configuration loaded from ``~/.mahjong/config.yaml``.

Provides a lazy-loaded singleton via :func:`get_config`.  If the config
file is missing, all properties return safe defaults (``None`` / ``[]``).
"""

from __future__ import annotations

from pathlib import Path
from typing import Dict, List, Optional

_CONFIG_PATH = Path.home() / ".mahjong" / "config.yaml"


class MahjongConfig:
    """Lazy-loaded project configuration."""

    def __init__(self, path: Optional[Path] = None):
        self._path = Path(path) if path else _CONFIG_PATH
        self._data: Optional[Dict] = None

    def _load(self) -> Dict:
        if self._data is None:
            if self._path.exists():
                import yaml

                with open(self._path) as f:
                    self._data = yaml.safe_load(f) or {}
            else:
                self._data = {}
        return self._data

    def reload(self) -> None:
        """Force a reload on next property access."""
        self._data = None

    # -- paipu paths ----------------------------------------------------------

    @property
    def paipu_xml_path(self) -> Optional[str]:
        """Directory containing Tenhou paipu XML files."""
        return self._load().get("paipu_xml_path")

    @property
    def paipu_game_ids(self) -> List[str]:
        """List of paths to ``game_ids.txt`` files."""
        return list(self._load().get("paipu_game_ids", []))

    @property
    def v4_cache_path(self) -> Optional[str]:
        """Directory for V4 autoregressive event-stream encoded cache."""
        return self._load().get("v4_cache_path")


_singleton: Optional[MahjongConfig] = None


def get_config() -> MahjongConfig:
    """Return the global config singleton."""
    global _singleton
    if _singleton is None:
        _singleton = MahjongConfig()
    return _singleton
