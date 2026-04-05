"""autoadd action: scan nsp_dir for update/DLC NSPs and write Ryujinx
updates.json and dlc.json files per application_id."""

import glob
import io
import json
import os

import hactoolnet
from config import Config
from util import progress_bar


def run(config: Config) -> None:
    ryujinx_dir = config.require("ryujinx_dir")

    update_dirs: list[str] = config.update_nsp_dir or []
    dlc_dirs: list[str] = config.dlc_nsp_dir or []
    if not update_dirs and not dlc_dirs:
        raise SystemExit(
            f"error: autoadd requires 'update_nsp_dir' and/or 'dlc_nsp_dir' "
            f"in [paths] of {config.config_path}"
        )

    for d in (*update_dirs, *dlc_dirs):
        if not os.path.isdir(d):
            raise SystemExit(f"error: nsp directory does not exist: {d}")

    ryujinx_update_json_map: dict[str, dict] = {}
    ryujinx_dlc_json_map: dict[str, list] = {}

    nsp_files: list[str] = []
    for d in (*update_dirs, *dlc_dirs):
        nsp_files.extend(glob.glob(os.path.join(d, "**", "*.nsp"), recursive=True))
    total_files = len(nsp_files)
    for index, nsp_file in enumerate(nsp_files):
        progress_bar(index + 1, total_files, suffix=f"\nProcessing {nsp_file}")

        info = hactoolnet.list_titles(nsp_file, config)
        if info is None:
            continue

        if info.kind == "application":
            continue

        if info.kind == "patch":
            app_id = info.application_id
            update_json = ryujinx_update_json_map.get(app_id)
            if update_json is None:
                update_json = {"selected": None, "paths": []}
            update_json["selected"] = nsp_file
            update_json["paths"].append(nsp_file)
            ryujinx_update_json_map[app_id] = update_json

        elif info.kind == "addon":
            # Use the first non-meta NCA as the DLC nca path
            if not info.nca_ids:
                continue
            nca_id = info.nca_ids[0]
            dlc_entry = {
                "path": nsp_file,
                "dlc_nca_list": [
                    {
                        "path": f"/{nca_id}.nca",
                        "title_id": int(info.title_id, 16),
                        "is_enabled": True,
                    }
                ],
            }
            dlc_list = ryujinx_dlc_json_map.get(info.application_id)
            if dlc_list is None:
                dlc_list = []
            dlc_list.append(dlc_entry)
            ryujinx_dlc_json_map[info.application_id] = dlc_list

    print("Exporting updates.json")
    total_updates = len(ryujinx_update_json_map.items())
    for index, (application_id, update_json) in enumerate(ryujinx_update_json_map.items()):
        output_dir = os.path.join(ryujinx_dir, "games", application_id)
        progress_bar(
            index + 1,
            total_updates,
            suffix=f"\nExporting {os.path.join(output_dir, 'updates.json')}",
        )
        os.makedirs(output_dir, exist_ok=True)
        with io.open(os.path.join(output_dir, "updates.json"), "w", encoding="utf-8") as f:
            f.write(json.dumps(update_json, indent=2))
    print("\nFinished exporting updates.json")

    print("Exporting dlc.json")
    total_dlcs = len(ryujinx_dlc_json_map.items())
    for index, (application_id, dlc_json) in enumerate(ryujinx_dlc_json_map.items()):
        output_dir = os.path.join(ryujinx_dir, "games", application_id)
        progress_bar(
            index + 1,
            total_dlcs,
            suffix=f"\nExporting {os.path.join(output_dir, 'dlc.json')}",
        )
        os.makedirs(output_dir, exist_ok=True)
        with io.open(os.path.join(output_dir, "dlc.json"), "w", encoding="utf-8") as f:
            f.write(json.dumps(dlc_json, indent=2))
    print("\nFinished exporting dlc.json")
