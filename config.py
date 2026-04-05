"""Configuration loading for ryujinx_tool.

Reads a TOML-formatted config file (default: config.ini next to the
script) and exposes a frozen Config dataclass. Paths are resolved
relative to the config file's directory. Field validation happens
per-action via Config.require().
"""

import os
import tomllib
from dataclasses import dataclass
from typing import Any


SCRIPT_DIR = os.path.dirname(os.path.realpath(__file__))
DEFAULT_CONFIG_PATH = os.path.join(SCRIPT_DIR, "config.ini")
DEFAULT_HACTOOLNET = os.path.join(
    SCRIPT_DIR, "hactoolnet.exe" if os.name == "nt" else "hactoolnet"
)
DEFAULT_TITLE_KEYS = os.path.join(SCRIPT_DIR, "prod.keys")


@dataclass(frozen=True)
class Config:
    ryujinx_dir: str | None
    yuzu_dir: str | None
    nsp_dir: list[str] | None
    hactoolnet: str
    title_keys: str
    versions_json: str | None
    config_path: str  # for error messages

    def require(self, field: str) -> Any:
        value = getattr(self, field)
        if value is None:
            raise SystemExit(
                f"error: this action requires '{field}' in [paths] of {self.config_path}"
            )
        return value


def _resolve(base_dir: str, value: str | None) -> str | None:
    if value is None or value == "":
        return None
    if os.path.isabs(value):
        return value
    return os.path.normpath(os.path.join(base_dir, value))


def _resolve_dir_list(base_dir: str, value: Any, config_path: str) -> list[str] | None:
    """Normalize nsp_dir: accept a string or list of strings, return list or None."""
    if value is None or value == "":
        return None
    if isinstance(value, str):
        resolved = _resolve(base_dir, value)
        return [resolved] if resolved else None
    if isinstance(value, list):
        out: list[str] = []
        for entry in value:
            if not isinstance(entry, str):
                raise SystemExit(
                    f"error: nsp_dir entries in {config_path} must be strings"
                )
            resolved = _resolve(base_dir, entry)
            if resolved:
                out.append(resolved)
        return out or None
    raise SystemExit(
        f"error: nsp_dir in {config_path} must be a string or list of strings"
    )


def load(path: str | None) -> Config:
    """Load config from `path` (or DEFAULT_CONFIG_PATH if None).

    If the file does not exist and no explicit path was given, returns a
    Config with all optional fields set to None and defaults for
    hactoolnet/title_keys. If an explicit path was given and is missing,
    raises SystemExit.
    """
    explicit = path is not None
    config_path = path or DEFAULT_CONFIG_PATH

    if not os.path.isfile(config_path):
        if explicit:
            raise SystemExit(f"error: config file not found: {config_path}")
        # No config file and none requested — return defaults-only Config.
        return Config(
            ryujinx_dir=None,
            yuzu_dir=None,
            nsp_dir=None,
            hactoolnet=DEFAULT_HACTOOLNET,
            title_keys=DEFAULT_TITLE_KEYS,
            versions_json=None,
            config_path=config_path,
        )

    with open(config_path, "rb") as f:
        try:
            data = tomllib.load(f)
        except tomllib.TOMLDecodeError as e:
            raise SystemExit(f"error: invalid TOML in {config_path}: {e}")

    paths = data.get("paths", {})
    base_dir = os.path.dirname(os.path.realpath(config_path))

    hactoolnet = _resolve(base_dir, paths.get("hactoolnet")) or DEFAULT_HACTOOLNET
    title_keys = _resolve(base_dir, paths.get("title_keys")) or DEFAULT_TITLE_KEYS

    config = Config(
        ryujinx_dir=_resolve(base_dir, paths.get("ryujinx_dir")),
        yuzu_dir=_resolve(base_dir, paths.get("yuzu_dir")),
        nsp_dir=_resolve_dir_list(base_dir, paths.get("nsp_dir"), config_path),
        hactoolnet=hactoolnet,
        title_keys=title_keys,
        versions_json=_resolve(base_dir, paths.get("versions_json")),
        config_path=config_path,
    )

    # Validate shared prerequisites that every action needs.
    if not os.path.isfile(config.hactoolnet):
        raise SystemExit(
            f"error: hactoolnet not found at {config.hactoolnet} "
            f"(set [paths].hactoolnet in {config_path})"
        )
    if not os.path.isfile(config.title_keys):
        raise SystemExit(
            f"error: prod.keys not found at {config.title_keys} "
            f"(set [paths].title_keys in {config_path})"
        )

    return config
