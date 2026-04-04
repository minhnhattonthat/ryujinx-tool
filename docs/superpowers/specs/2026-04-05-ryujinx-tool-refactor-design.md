# ryujinx_tool.py Refactor — Design

**Date:** 2026-04-05
**Status:** Approved for planning

## Goal

Split the 893-line monolithic `ryujinx_tool.py` into focused modules and move all path/settings configuration out of CLI arguments into a TOML config file. No new dependencies — stdlib only (`tomllib` is available on Python 3.11+; the project runs on 3.12).

## Motivation

- The single file has grown to 893 lines with 5 actions sharing tangled module-level state (`ryujinx_dir`, `yuzu_dir`, etc. read from argparse at import time).
- The `hactoolnet --listtitles` + output-parsing logic is open-coded in four separate places with subtly different parsing.
- Users invoke the tool via batch files that pass six path arguments on every call. A config file is easier to maintain.
- Module-level state and import-time validation make the code hard to reason about.

## Non-Goals

- No new features.
- No test suite (none exists today; adding one is out of scope).
- No packaging changes (still a script run as `python ryujinx_tool.py`).
- Not touching the existing `.bat` files beyond flagging that they need updating.

## Module Layout

Nine files, all in `e:/ryujinx/scripts/`:

```
ryujinx_tool.py       # entry point: CLI parse, load config, dispatch action
config.py             # load config.toml, Config dataclass, require() helper
hactoolnet.py         # subprocess wrapper + listtitles output parsing
imkvdb.py             # read/add/sort imkvdb entries + backup rotation
util.py               # progress_bar + reverse_hex
autoadd.py            # generate_ryujinx_json action
export_updates.py     # export_updates_csv action
sync_saves.py         # sync_saves + _sync_dir + _back_up_save + _newest_file + yuzu uuid
listing.py            # get_yuzu_nca_path + get_ryujinx_nsp_path + _get_nca_full_path
```

Each action module exposes a single public `run(config, ...)` function. The entry point imports action modules lazily (only the one being invoked) so an unused module with a syntax error doesn't break other actions.

## Config File

**Location:** `config.toml` next to `ryujinx_tool.py` by default. Override with `--config <path>`.

**Schema:**

```toml
[paths]
ryujinx_dir   = "..."                 # Ryujinx filesystem folder
yuzu_dir      = "..."                 # yuzu user folder
nsp_dir       = "..."                 # folder containing NSP update/DLC files
hactoolnet    = "./hactoolnet.exe"    # optional, default: next to script
title_keys    = "./prod.keys"         # optional, default: next to script
versions_json = ""                    # optional, empty = auto-download
```

All fields are optional in the file. Relative paths are resolved relative to the config file's directory. A `config.toml.example` will ship with the commented schema.

**`Config` dataclass** (frozen):

```python
@dataclass(frozen=True)
class Config:
    ryujinx_dir: str | None
    yuzu_dir: str | None
    nsp_dir: str | None
    hactoolnet: str          # always has a value (default if not set)
    title_keys: str           # always has a value (default if not set)
    versions_json: str | None

    def require(self, field: str) -> str:
        """Return field value or raise SystemExit with a clear message."""
```

`load(path: str | None) -> Config` reads the TOML file (or returns all-defaults if the file is absent and no `--config` was given), resolves paths, and constructs the dataclass. No field-level validation at load time — each action calls `config.require("nsp_dir")` for the fields it needs.

## CLI Surface

**Kept:**
- `-a/--autoadd`
- `-e/--exportupdates`
- `-s/--syncsaves <priority>` (`yuzu|ryujinx|newer`, `~` prefix for simulate)
- `-l/--listyuzuncas`
- `--listryujnxnsps`
- `--nspfile <file>` (required by the two list actions)
- `-v/--version`
- `-h/--help`

**Added:**
- `--config <path>` — defaults to `config.toml` next to the script.

**Removed (moved to config):**
- `-r/--ryujinxdir`
- `-y/--yuzudir`
- `-n/--nspdir`
- `-p/--versionspath`
- `--hactoolnet`
- `--titlekeys`

At least one action is still required. Argparse-level validation stays argparse's job; path validation moves to the actions themselves.

## Shared Modules

### `hactoolnet.py`

Consolidates the four places that currently call `hactoolnet --listtitles` and parse its output.

```python
@dataclass
class TitleInfo:
    title_id: str            # e.g. "0100abc..."
    application_id: str      # title_id with 13th char forced to "0"
    version_code: str        # numeric, e.g. "65536"
    kind: Literal["application", "patch", "addon"]
    nca_ids: list[str]       # non-meta NCAs from pfs0:/*.nca
    meta_nca_id: str | None  # the *.cnmt.nca id, stripped of .cnmt
    raw_output: str          # for any caller that still wants it

def list_titles(nsp_file: str, config: Config) -> TitleInfo | None:
    """Run hactoolnet --listtitles; return None on subprocess error or
    missing title_id (caller logs and skips)."""
```

### `imkvdb.py`

```python
@dataclass
class ImkvdbState:
    save_map: dict[str, str]         # title_id -> save_dirname
    bcat_save_map: dict[str, str]
    key_value_list: list[dict]       # {"key": hex, "value": hex}
    last_index: int

def read(ryujinx_dir: str) -> ImkvdbState
def add_entries(ryujinx_dir: str, title_ids: list[str]) -> None   # includes backup + rotation
def sort_entries(ryujinx_dir: str) -> None
```

### `util.py`

```python
def progress_bar(current: float, total: float, bar_length: int = 20, suffix: str = "") -> None
def reverse_hex(hex_str: str) -> str
```

## Action Modules

Each exposes `def run(config: Config, ...) -> None`. Private helpers stay module-private with `_` prefix.

- **`autoadd.run(config)`** — uses `config.require("nsp_dir")`, `config.require("ryujinx_dir")`. Calls `hactoolnet.list_titles` per NSP.
- **`export_updates.run(config)`** — uses `config.require("nsp_dir")`. Uses `config.versions_json` or auto-downloads.
- **`sync_saves.run(config, priority, simulate)`** — uses `config.require("ryujinx_dir")`, `config.require("yuzu_dir")`, `config.require("nsp_dir")`. Owns the sync_dir/backup/newest-file helpers and the yuzu profile UUID reader.
- **`listing.run_list_yuzu_ncas(config, nsp_file)`** and **`listing.run_list_ryujinx_nsps(config, nsp_file)`** — both use `config.require("ryujinx_dir")`; `run_list_yuzu_ncas` also requires `yuzu_dir`.

## Error Handling

- Missing required config field → `SystemExit(f"error: {action} requires '{field}' in {config_path}")`.
- Missing file/directory referenced in config → `SystemExit` with the path that failed and the config key it came from.
- No action flag → argparse error (unchanged).
- Per-NSP subprocess failures inside a loop → log and continue (unchanged behavior, but see bug fix below).

## Bug Fixes Bundled With the Refactor

1. **`export_updates_csv` — `break` on missing title_id** (ryujinx_tool.py:168 and :308): currently aborts the entire loop when any file lacks a title_id. Should be `continue`. This is a behavior change but an unambiguous bug — the surrounding code logs "No title id is found for X" and then stops processing all remaining files.
2. **Four-way duplication of `hactoolnet --listtitles` + parsing**: consolidated into `hactoolnet.list_titles`. This is a cleanup, not a behavior change, but the consolidation will standardize parsing (the four copies differ in whitespace handling and error paths).
3. **Redundant `f.close()` calls inside `with` blocks**: removed. Harmless today.

If additional clear bugs surface during implementation, they will be flagged to the user rather than silently fixed.

## Migration

- Ship `config.toml.example` with commented fields.
- Update `README.md`:
  - New usage: `python ryujinx_tool.py -a` (paths come from config).
  - Document `--config` flag.
  - Document the config schema.
- **Not updated (flagged for user):** `add-updates-and-dlcs.bat` and `add-updates-and-dlcs - drive h.bat`. These currently pass paths on the command line and will break after the refactor. The user can either update them to rely on config or use per-invocation `--config` files.

## Verification Plan

No test suite exists. Post-refactor verification:

1. `python -m py_compile` on every new module — syntax check.
2. `python ryujinx_tool.py -h` — argparse still parses.
3. `python ryujinx_tool.py --version` — still prints version.
4. If the user can provide valid dirs in a config file: `python ryujinx_tool.py -s ~newer` (simulate mode, no file writes) to exercise sync_saves, imkvdb read path, and most shared modules end-to-end.
5. Manual diff of one action's output (e.g., `-e`) against the pre-refactor script on the same inputs, if feasible.

## Open Items

- Whether to bump `VERSION` to `v0.5.0` for the breaking CLI change (likely yes, decided at implementation time).
- Whether `config.toml` should be `.gitignore`d (it contains user-specific paths — yes, add to `.gitignore`; ship only `.example`).
