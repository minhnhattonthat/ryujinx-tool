"""listing actions: print file paths for a given game's NSPs or NCAs.

- list_ryujinx_nsps: print NSP paths Ryujinx has registered (updates + DLCs)
- list_yuzu_ncas: translate Ryujinx's NSP registrations into yuzu's
  content-registered NCA paths via hactoolnet listing + sha256 hashing
"""

import hashlib
import io
import json
import os
import re

import hactoolnet
from config import Config


def _extract_title_id(nsp_file: str) -> str | None:
    match = re.search(r"0100[a-zA-Z0-9]{12}", nsp_file)
    if match is None:
        print(f"No title id is found for {nsp_file}")
        return None
    return nsp_file[match.start() : match.end()]


def _load_paths_from_json(json_path: str, key: str) -> list[str]:
    if not os.path.isfile(json_path):
        return []
    with io.open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    if key == "updates":
        return list(data.get("paths", []))
    if key == "dlcs":
        return [entry["path"] for entry in data]
    return []


def run_list_ryujinx_nsps(config: Config, nsp_file: str) -> None:
    ryujinx_dir = config.require("ryujinx_dir")
    title_id = _extract_title_id(nsp_file)
    if title_id is None:
        return

    app_dir = os.path.join(ryujinx_dir, "games", title_id.lower())
    if not os.path.isdir(app_dir):
        return

    nsp_list: list[str] = []
    nsp_list.extend(_load_paths_from_json(os.path.join(app_dir, "updates.json"), "updates"))
    nsp_list.extend(_load_paths_from_json(os.path.join(app_dir, "dlc.json"), "dlcs"))

    for nsp_path in nsp_list:
        print(nsp_path)


def _nca_full_path(yuzu_dir: str, nca_id: str) -> str:
    hash_hex = hashlib.sha256(bytes.fromhex(nca_id)).hexdigest().upper()
    hash_first = hash_hex[0:2]
    return os.path.join(
        yuzu_dir,
        "nand",
        "user",
        "Contents",
        "registered",
        "000000" + hash_first,
        nca_id + ".nca",
    )


def _collect_ncas_for_nsp(nsp_file: str, config: Config) -> list[str]:
    info = hactoolnet.list_titles(nsp_file, config)
    if info is None:
        return []
    nca_ids = list(info.nca_ids)
    if info.meta_nca_id is not None:
        nca_ids.append(info.meta_nca_id)
    return nca_ids


def run_list_yuzu_ncas(config: Config, nsp_file: str) -> None:
    ryujinx_dir = config.require("ryujinx_dir")
    yuzu_dir = config.require("yuzu_dir")

    title_id = _extract_title_id(nsp_file)
    if title_id is None:
        return

    app_dir = os.path.join(ryujinx_dir, "games", title_id.lower())
    if not os.path.isdir(app_dir):
        return

    nca_list: list[str] = []

    # Updates: hactoolnet the "selected" update NSP from updates.json
    updates_json_path = os.path.join(app_dir, "updates.json")
    if os.path.isfile(updates_json_path):
        with io.open(updates_json_path, "r", encoding="utf-8") as f:
            update_json = json.load(f)
        selected = update_json.get("selected")
        if selected:
            nca_list.extend(_collect_ncas_for_nsp(selected, config))

    # DLCs: hactoolnet each dlc path from dlc.json
    dlc_json_path = os.path.join(app_dir, "dlc.json")
    if os.path.isfile(dlc_json_path):
        with io.open(dlc_json_path, "r", encoding="utf-8") as f:
            dlc_json = json.load(f)
        for dlc in dlc_json:
            nca_list.extend(_collect_ncas_for_nsp(dlc["path"], config))

    for nca_id in nca_list:
        print(_nca_full_path(yuzu_dir, nca_id))
