"""exportupdates action: emit updates.csv with update-available status.

Downloads versions.json from titledb if not provided and not cached next
to the script.
"""

import glob
import io
import json
import os
import re
import subprocess
import urllib.request
from subprocess import CalledProcessError

from config import Config, SCRIPT_DIR
from util import progress_bar


LOCAL_VERSIONS_PATH = os.path.join(SCRIPT_DIR, "versions.json")
VERSIONS_URL = "https://github.com/blawar/titledb/raw/master/versions.json"


def _resolve_versions_path(config: Config) -> str:
    if config.versions_json is not None:
        if not os.path.isfile(config.versions_json):
            raise SystemExit(f"error: versions_json file not found: {config.versions_json}")
        return config.versions_json
    if os.path.isfile(LOCAL_VERSIONS_PATH):
        return LOCAL_VERSIONS_PATH
    print("Downloading versions.json")
    result = urllib.request.urlretrieve(VERSIONS_URL, LOCAL_VERSIONS_PATH)
    print(f"Downloaded to {result[0]}")
    return result[0]


def run(config: Config) -> None:
    nsp_dirs: list[str] = config.require("nsp_dir")
    for d in nsp_dirs:
        if not os.path.isdir(d):
            raise SystemExit(f"error: nsp_dir does not exist: {d}")

    path = _resolve_versions_path(config)
    print("Exporting updates.csv")

    with open(path, encoding="utf-8") as f:
        versions_map = json.load(f)

    output_csv = "Filename, Title ID, Version Code, Latest Version Code, Latest Updated Date, Update Available\n"

    nsp_files: list[str] = []
    for d in nsp_dirs:
        nsp_files.extend(glob.glob(os.path.join(d, "**", "*.nsp"), recursive=True))
    total_files = len(nsp_files)
    for index, nsp_file in enumerate(nsp_files):
        progress_bar(index + 1, total_files)

        args = [
            config.hactoolnet,
            "-k",
            config.title_keys,
            "-t",
            "pfs0",
            nsp_file,
            "--listtitles",
        ]

        try:
            output = subprocess.check_output(args).decode("utf-8")
        except CalledProcessError:
            print(f"Error when process {nsp_file}")
            continue

        if "Patch" not in output:
            continue

        title_id_match = re.search("0100[a-zA-Z0-9]{12} v", output)
        if title_id_match is None:
            print(f"No title id is found for {nsp_file}")
            continue  # BUG FIX: was `break` in the original, which aborted all remaining files
        title_id = output[title_id_match.start() : title_id_match.end()]
        title_id = title_id.lower().replace(" v", "")

        version_code_match = re.search(" v[0-9]+ ", output)
        version_code = output[version_code_match.start() : version_code_match.end()]
        version_code = version_code.strip().replace("v", "")

        application_id = title_id[:13] + "0" + title_id[14:]

        filename = os.path.basename(nsp_file)
        latest_version_code = ""
        latest_version_date = ""
        is_update_available: bool | None = None
        try:
            latest_version = list(versions_map[application_id].items())[-1]
            latest_version_code = latest_version[0]
            latest_version_date = latest_version[1]
            is_update_available = latest_version_code != version_code
        except (KeyError, AttributeError):
            print(f"{filename} data not found")
        output_csv += f'"{filename}", {title_id}, {version_code}, {latest_version_code}, {latest_version_date}, {is_update_available}\n'

    out_path = os.path.join(SCRIPT_DIR, "updates.csv")
    with io.open(out_path, "w", encoding="utf-8") as f:
        f.write(output_csv)
        print(f"Exported to {out_path}")
