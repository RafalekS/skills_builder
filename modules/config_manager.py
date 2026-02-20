"""
Config Manager - JSON config with dot-notation get/set
"""

import json
import logging
import os
from pathlib import Path

logger = logging.getLogger(__name__)

DEFAULT_CONFIG = {
    "app": {
        "theme": "dark",
        "window_width": 1200,
        "window_height": 800,
        "window_x": -1,
        "window_y": -1,
        "last_tab": 0
    },
    "skills": {
        "user_skills_dir": "",
        "project_skills_dir": ""
    },
    "github": {
        "token": "",
        "search_timeout": 10,
        "cache_hours": 24
    },
    "editor": {
        "font_family": "Consolas",
        "font_size": 13,
        "tab_width": 2,
        "wrap_lines": True
    },
    "table_state": {}
}


class ConfigManager:
    def __init__(self, config_path: Path = None):
        if config_path is None:
            config_path = Path(__file__).parent.parent / "config" / "config.json"
        self._path = Path(os.path.expanduser(os.path.expandvars(str(config_path))))
        self._config = {}
        self.load()

    def load(self) -> bool:
        if self._path.exists():
            try:
                with open(self._path, "r", encoding="utf-8") as f:
                    loaded = json.load(f)
                # Merge with defaults so new keys are always present
                self._config = self._merge(DEFAULT_CONFIG, loaded)
                return True
            except Exception:
                logger.exception("Failed to load config from %s", self._path)
                self._config = dict(DEFAULT_CONFIG)
                return False
        else:
            self._config = dict(DEFAULT_CONFIG)
            self.save()
            return True

    def save(self) -> bool:
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            with open(self._path, "w", encoding="utf-8") as f:
                json.dump(self._config, f, indent=2)
            return True
        except Exception:
            logger.exception("Failed to save config to %s", self._path)
            return False

    def get(self, key: str, default=None):
        """Dot-notation get: config.get('github.token')"""
        parts = key.split(".")
        current = self._config
        for part in parts:
            if isinstance(current, dict) and part in current:
                current = current[part]
            else:
                return default
        return current

    def set(self, key: str, value) -> None:
        """Dot-notation set: config.set('github.token', 'abc123')"""
        parts = key.split(".")
        current = self._config
        for part in parts[:-1]:
            if part not in current or not isinstance(current[part], dict):
                current[part] = {}
            current = current[part]
        current[parts[-1]] = value

    def get_user_skills_dir(self) -> Path:
        """Returns resolved user skills directory (never empty)."""
        raw = self.get("skills.user_skills_dir", "")
        if raw:
            return Path(os.path.expanduser(os.path.expandvars(raw)))
        return Path.home() / ".claude" / "skills"

    def get_project_skills_dir(self) -> Path | None:
        """Returns resolved project skills directory, or None if not set."""
        raw = self.get("skills.project_skills_dir", "")
        if raw:
            return Path(os.path.expanduser(os.path.expandvars(raw)))
        return None

    @staticmethod
    def _merge(defaults: dict, overrides: dict) -> dict:
        """Deep merge: overrides wins, but missing keys filled from defaults."""
        result = dict(defaults)
        for key, value in overrides.items():
            if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                result[key] = ConfigManager._merge(result[key], value)
            else:
                result[key] = value
        return result
