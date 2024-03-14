"""tool for ryujinx"""

# pylint: disable=C0301,C0116

import argparse
from argparse import ArgumentError, _get_action_name
from datetime import datetime
from functools import cmp_to_key
import glob
import io
import json
import os
import re
import shutil
import subprocess
from subprocess import CalledProcessError
import sys
import urllib.request

VERSION = "v0.4"

# Fix powershell cannot print unicode characters
sys.stdout.reconfigure(encoding='utf-8')

dir_path = os.path.dirname(os.path.realpath(__file__))

YUZU_PRIORIY = "yuzu"
RYUJINX_PRIORIY = "ryujinx"
NEWER_PRIORITY = "newer"

priority_choices = [YUZU_PRIORIY, RYUJINX_PRIORIY, NEWER_PRIORITY]
full_priority_choices = priority_choices + list(
    map(lambda x: "~" + x, priority_choices)
)

parser = argparse.ArgumentParser(
    prog="ryujinx_tool",
    description="A tool for better manage Ryujinx",
    formatter_class=argparse.RawTextHelpFormatter,
)
actions_arg_group = parser.add_argument_group("actions", "Requires at least one")
autoadd_arg = actions_arg_group.add_argument(
    "-a",
    "--autoadd",
    action="store_true",
    help="Automatically add updates & DLCs to Ryujinx. Requires --nspdir, --ryujinx",
)
exportupdates_arg = actions_arg_group.add_argument(
    "-e",
    "--exportupdates",
    action="store_true",
    help="Export csv file with update available status for update files. Requires --nspdir",
)
syncsaves_arg = actions_arg_group.add_argument(
    "-s",
    "--syncsaves",
    metavar="<priority>",
    choices=full_priority_choices,
    help="""Export csv file with update available status for update files.\nPriority includes yuzu, ryujinx or newer. Add '~' before priority (e.g. ~yuzu) to use simulation mode.\nRequires --ryujinxdir, --yuzudir""",
)
parser.add_argument("-v", "--version", action="version", version=f"%(prog)s {VERSION}")
ryujinxdir_arg = parser.add_argument(
    "-r",
    "--ryujinxdir",
    metavar="<dir>",
    help="Directory path of Ryujinx filesystem folder.",
)
yuzudir_arg = parser.add_argument(
    "-y",
    "--yuzudir",
    metavar="<dir>",
    help="Directory path of yuzu user folder.",
)
nspdir_arg = parser.add_argument(
    "-n",
    "--nspdir",
    metavar="<dir>",
    help="Directory path of where nsp update & dlc files are stored.",
)
versionspath_arg = parser.add_argument(
    "-p",
    "--versionspath",
    metavar="<file>",
    help="File path of versions.json from titledb. If not provide will search in current folder or download from its source.",
)
hactoolnet_arg = parser.add_argument(
    "--hactoolnet",
    metavar="<file>",
    help=f"File path of {'hactoolnet.exe' if os.name == 'nt' else 'hactoolnet'}. Default to current folder.",
    default=os.path.join(
        dir_path, "hactoolnet.exe" if os.name == "nt" else "hactoolnet"
    ),
)
titlekeys_arg = parser.add_argument(
    "--titlekeys",
    metavar="<file>",
    help="File path of prod.keys. Default to curreent folder.",
    default=os.path.join(dir_path, "prod.keys"),
)
arguments = parser.parse_args()

ryujinx_dir = arguments.ryujinxdir
yuzu_dir = arguments.yuzudir
nsp_dir = arguments.nspdir
hactoolnet_path = arguments.hactoolnet
title_keys_path = arguments.titlekeys
versions_path = arguments.versionspath
should_auto_add = arguments.autoadd
should_export_csv = arguments.exportupdates
should_sync_saves = arguments.syncsaves is not None
sync_priority = arguments.syncsaves
should_simulate_sync = should_sync_saves and arguments.syncsaves[0] == "~"

local_versions_path = os.path.join(dir_path, "versions.json")


def generate_ryujinx_json():
    ryujinx_update_json_map = {}
    ryujinx_dlc_json_map = {}

    nsp_files = glob.glob(os.path.join(nsp_dir, "**", "*.nsp"), recursive=True)
    total_files = len(nsp_files)
    for index, nsp_file in enumerate(nsp_files):
        suffix = f"\nProcessing {nsp_file}"
        _progress_bar(index + 1, total_files, suffix=suffix)

        args = [
            hactoolnet_path,
            "-k",
            title_keys_path,
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

        if "Application" in output:
            continue

        title_id_match = re.search("0100[a-zA-Z0-9]{12} v", output)
        if title_id_match is None:
            print(f"No title id is found for {nsp_file}")
            break
        title_id = output[title_id_match.start() : title_id_match.end()]
        title_id = title_id.lower().replace(" v", "")

        version_code_match = re.search(" v[0-9]+ ", output)
        version_code = output[version_code_match.start() : version_code_match.end()]
        version_code = version_code.strip().replace("v", "")

        if "Patch" in output:
            application_id = title_id[:13] + "0" + title_id[14:]

            ryujinx_update_json = ryujinx_update_json_map.get(application_id)
            if ryujinx_update_json is None:
                ryujinx_update_json = {"selected": None, "paths": []}
            ryujinx_update_json["selected"] = nsp_file
            ryujinx_update_json["paths"].append(nsp_file)
            ryujinx_update_json_map[application_id] = ryujinx_update_json

        if "AddOnContent" in output:
            nca_id_match = re.search(r"pfs0:/[a-z0-9]{32}.nca", output)
            nca_id = output[nca_id_match.start() : nca_id_match.end()][6:38]

            application_id_match = re.search(r"title 0100[a-zA-Z0-9]{12}", output)
            application_id = output[
                application_id_match.start() : application_id_match.end()
            ]
            application_id = application_id.lower().replace("title ", "")

            ryujinx_dlc_json = {
                "path": nsp_file,
                "dlc_nca_list": [
                    {
                        "path": f"/{nca_id}.nca",
                        "title_id": int(title_id, 16),
                        "is_enabled": True,
                    }
                ],
            }

            dlc_list = ryujinx_dlc_json_map.get(application_id)
            if dlc_list is None:
                dlc_list = []
            dlc_list.append(ryujinx_dlc_json)
            ryujinx_dlc_json_map[application_id] = dlc_list

    print("Exporting updates.json")
    total_updates = len(ryujinx_update_json_map.items())
    for index, (application_id, ryujinx_update_jsons) in enumerate(
        ryujinx_update_json_map.items()
    ):
        output_dir = os.path.join(ryujinx_dir, "games", application_id)

        _progress_bar(
            index + 1,
            total_updates,
            suffix=f"\nExporting {os.path.join(output_dir, 'updates.json')}",
        )

        if not os.path.isdir(output_dir):
            os.makedirs(output_dir)

        with io.open(
            os.path.join(output_dir, "updates.json"), "w", encoding="utf-8"
        ) as f:
            f.write(json.dumps(ryujinx_update_jsons, indent=2))
    print("\nFinished exporting updates.json")

    print("Exporting dlc.json")
    total_dlcs = len(ryujinx_dlc_json_map.items())
    for index, (application_id, ryujinx_dlc_jsons) in enumerate(
        ryujinx_dlc_json_map.items()
    ):
        output_dir = os.path.join(ryujinx_dir, "games", application_id)

        _progress_bar(
            index + 1,
            total_dlcs,
            suffix=f"\nExporting {os.path.join(output_dir, 'dlc.json')}",
        )

        if not os.path.isdir(output_dir):
            os.makedirs(output_dir)

        with io.open(os.path.join(output_dir, "dlc.json"), "w", encoding="utf-8") as f:
            f.write(json.dumps(ryujinx_dlc_jsons, indent=2))

    print("\nFinished exporting dlc.json")


def export_updates_csv():
    versions_map = {}

    path = local_versions_path

    if versions_path is not None:
        path = versions_path
    elif os.path.isfile(local_versions_path) is False:
        print("Downloading versions.json")
        target_path = os.path.join(dir_path, "versions.json")
        versions_url = "https://github.com/blawar/titledb/raw/master/versions.json"
        result = urllib.request.urlretrieve(versions_url, target_path)
        path = result[0]
        print(f"Downloaded to {path}")

    print("Exporting updates.csv")

    with open(path, encoding="utf-8") as f:
        versions_map = json.load(f)
        f.close()

    output_csv = "Filename, Title ID, Version Code, Latest Version Code, Latest Updated Date, Update Available\n"

    nsp_files = glob.glob(os.path.join(nsp_dir, "**", "*.nsp"), recursive=True)
    total_files = len(nsp_files)
    for index, nsp_file in enumerate(nsp_files):
        _progress_bar(index + 1, total_files)

        args = [
            hactoolnet_path,
            "-k",
            title_keys_path,
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
            # print(f"{nsp_file} is not Patch")
            continue

        title_id_match = re.search("0100[a-zA-Z0-9]{12} v", output)
        if title_id_match is None:
            print(f"No title id is found for {nsp_file}")
            break
        title_id = output[title_id_match.start() : title_id_match.end()]
        title_id = title_id.lower().replace(" v", "")

        version_code_match = re.search(" v[0-9]+ ", output)
        version_code = output[version_code_match.start() : version_code_match.end()]
        version_code = version_code.strip().replace("v", "")

        application_id = title_id[:13] + "0" + title_id[14:]

        filename = os.path.basename(nsp_file)
        latest_version_code = ""
        latest_version_date = ""
        is_update_available = None
        try:
            latest_version = list(versions_map[application_id].items())[-1]
            latest_version_code = latest_version[0]
            latest_version_date = latest_version[1]
            is_update_available = latest_version_code != version_code
        except KeyError:
            print(f"{filename} data not found")
        output_csv += f'"{filename}", {title_id}, {version_code}, {latest_version_code}, {latest_version_date}, {is_update_available}\n'

    with io.open(os.path.join(dir_path, "updates.csv"), "w", encoding="utf-8") as f:
        f.write(output_csv)
        print(f"Exported to {f.name}")


def sync_saves():
    print("Syncing saves")

    yuzu_save_dirname = _reverse_hex_str(_get_yuzu_profile_uuid()).upper()
    yuzu_save_dir = os.path.join(
        yuzu_dir, "nand", "user", "save", "0000000000000000", yuzu_save_dirname
    )
    ryujinx_save_dir = os.path.join(ryujinx_dir, "bis", "user", "save")

    title_id_list = os.listdir(yuzu_save_dir)
    if should_simulate_sync is True:
        _add_imkvdb_entries(title_id_list)
        _sort_imkvdb_entries()

    save_map = _get_save_map_from_imkvdb()[0]

    total_saves = len(save_map.items())

    for index, (title_id, ryujinx_save_dirname) in enumerate(save_map.items()):
        yuzu_game_save_dir = os.path.join(yuzu_save_dir, title_id.upper())
        ryujinx_game_save_dir = os.path.join(
            ryujinx_save_dir, ryujinx_save_dirname, "0"
        )

        _sync_dir(yuzu_game_save_dir, ryujinx_game_save_dir, title_id)
        _progress_bar(index + 1, total_saves)

    print("Saves synced")


def _get_save_map_from_imkvdb():
    save_map = {}
    bcat_save_map = {}
    key_value_list = []
    imkvdb_path = os.path.join(
        ryujinx_dir, "bis", "system", "save", "8000000000000000", "0", "imkvdb.arc"
    )
    last_index = 1
    with io.open(imkvdb_path, "rb") as f:
        f.seek(0x8)
        total_entries = int(_reverse_hex_str(f.read(0x4).hex()), 16)
        f.seek(0xC)
        for _ in range(total_entries):
            f.seek(0xC, 1)
            key = f.read(0x40).hex()
            k = key[:16]
            title_id = _reverse_hex_str(k)
            value = f.read(0x40).hex()
            v = value[:16]
            save_dirname = _reverse_hex_str(v)

            # The system save has save_dirname as 8000000000000030 and should be skipped
            if save_dirname[0] == "0":
                index = int(save_dirname, 16)
                if index > last_index:
                    last_index = index

            key_value_list.append({"key": key, "value": value})

            if title_id == "0000000000000000":
                # system title
                continue
            # If a title id has 2 values, the later is the BCAT save entry
            if save_map.get(title_id) is None:
                save_map[title_id] = save_dirname
            else:
                bcat_save_map[title_id] = save_dirname

    return save_map, key_value_list, last_index


def _add_imkvdb_entries(title_id_list):

    save_map, key_value_list, last_index = _get_save_map_from_imkvdb()
    existed_title_id_list = save_map.keys()
    new_title_id_list = list(filter(lambda id: id.lower() not in existed_title_id_list, title_id_list))
    new_total_entries = len(key_value_list) + len(new_title_id_list)

    imkvdb_root = os.path.join(
        ryujinx_dir, "bis", "system", "save", "8000000000000000", "0"
    )
    imkvdb_path = os.path.join(imkvdb_root, "imkvdb.arc")

    current_timestamp = int(datetime.now().timestamp() * 1000)
    imkvdb_bk_path = os.path.join(imkvdb_root, f"imkvdb-{current_timestamp}.arc.bk")

    if os.path.isfile(imkvdb_path) is False:
        raise FileNotFoundError("imkvdb.arc not existed")

    shutil.copy2(imkvdb_path, imkvdb_bk_path)

    # Keep total backups in limit
    backup_list = glob.glob(os.path.join(imkvdb_root, "imkvdb-*.arc.bk"))
    length = len(backup_list)
    limit = 5
    if length > limit:
        for bk in backup_list[:length - limit]:
            os.remove(bk)

    with io.open(imkvdb_path, "r+b") as f:
        f.seek(0x8)
        total_entries_b = bytes.fromhex(_reverse_hex_str(new_total_entries.to_bytes(4, 'big').hex()))
        f.write(total_entries_b)
        # seek to end of file
        f.seek(0, 2)
        for i, title_id in enumerate(new_title_id_list, start=1):
            print(title_id)
            f.write(bytes.fromhex("494D454E4000000040000000"))
            f.write(bytes.fromhex(_reverse_hex_str(title_id)))
            f.write(bytes.fromhex("0100000000000000"))
            f.write(bytes.fromhex("00000000000000000000000000000000"))
            f.write(bytes.fromhex("01000000000000000000000000000000"))
            f.write(bytes.fromhex("00000000000000000000000000000000"))
            index_b = _reverse_hex_str((last_index + i).to_bytes(4, "big").hex())
            f.write(bytes.fromhex(index_b))
            f.write(bytes.fromhex("000000000000000000000000"))
            f.write(bytes.fromhex("00000000000000000100000000000000"))
            f.write(bytes.fromhex("00000000000000000000000000000000"))
            f.write(bytes.fromhex("00000000000000000000000000000000"))


def _sort_imkvdb_entries():
    _, key_value_list, _ = _get_save_map_from_imkvdb()

    imkvdb_path = os.path.join(
        ryujinx_dir, "bis", "system", "save", "8000000000000000", "0", "imkvdb.arc"
    )

    if os.path.isfile(imkvdb_path) is False:
        raise FileNotFoundError("imkvdb.arc not existed")

    def compare_key(item1, item2):
        k1 = item1["key"][:16]
        k2 = item2["key"][:16]
        for i in range(8):
            start = 16 - i * 2 - 2
            stop = start + 2
            h1 = int(k1[start:stop], 16)
            h2 = int(k2[start:stop], 16)
            if h1 == h2:
                continue
            return h1 - h2
        return int(item1["key"][64:66]) - int(item2["key"][64:66])

    sorted_key_value_list = sorted(key_value_list, key=cmp_to_key(compare_key))

    with io.open(imkvdb_path, "r+b") as f:
        f.seek(0xC)
        for pair in sorted_key_value_list:
            f.write(bytes.fromhex("494D454E4000000040000000"))
            f.write(bytes.fromhex(pair["key"]))
            f.write(bytes.fromhex(pair["value"]))


def _get_yuzu_profile_uuid():
    profiles_path = os.path.join(
        yuzu_dir,
        "nand",
        "system",
        "save",
        "8000000000000010",
        "su",
        "avators",
        "profiles.dat",
    )
    profile_uuid = None
    with io.open(profiles_path, "rb") as f:
        f.seek(0x10)
        profile_uuid = f.read(0x10).hex()
    return profile_uuid


def _reverse_hex_str(hex_str: str):
    output = None
    l = [hex_str[i : i + 2] for i in range(0, len(hex_str), 2)]
    l.reverse()
    output = "".join(l)
    return output


def _sync_dir(_yuzu_dir, _ryujinx_dir, title_id):
    log_suffix = "- [Simulate]" if should_simulate_sync else "-"
    reason = "Unknown error."
    src = None
    dst = None
    title = next(
        (t for t in os.listdir(nsp_dir) if title_id.lower() in t.lower()), None
    )
    if YUZU_PRIORIY in sync_priority:
        src = _yuzu_dir
        dst = _ryujinx_dir
        reason = "yuzu save is priority."

    elif RYUJINX_PRIORIY in sync_priority:
        src = _ryujinx_dir
        dst = _yuzu_dir
        reason = "Ryujinx save is priority."

    elif os.path.isdir(_yuzu_dir) is False:
        src = _ryujinx_dir
        dst = _yuzu_dir
        reason = "yuzu save not existed."

    elif os.path.isdir(_ryujinx_dir) is False:
        src = _yuzu_dir
        dst = _ryujinx_dir
        reason = "Ryujinx save not existed."

    else:
        yuzu_listdir = os.listdir(_yuzu_dir)
        ryujinx_listdir = os.listdir(_ryujinx_dir)

        if len(yuzu_listdir) == 0:
            if len(ryujinx_listdir) > 0:
                src = _ryujinx_dir
                dst = _yuzu_dir
                reason = "yuzu save is empty."
            else:
                reason = "yuzu & Ryujinx saves are both empty."

        elif len(ryujinx_listdir) == 0:
            if len(yuzu_listdir) > 0:
                src = _yuzu_dir
                dst = _ryujinx_dir
                reason = "Ryujinx save is empty."
            else:
                reason = "yuzu & Ryujinx saves are both empty."

        elif (
            os.stat(_newest_file_in_folder(_yuzu_dir)).st_mtime
            - os.stat(_newest_file_in_folder(_ryujinx_dir)).st_mtime
            > 1
        ):
            src = _yuzu_dir
            dst = _ryujinx_dir
            reason = "yuzu save is newer."

        elif (
            os.stat(_newest_file_in_folder(_ryujinx_dir)).st_mtime
            - os.stat(_newest_file_in_folder(_yuzu_dir)).st_mtime
            > 1
        ):
            src = _ryujinx_dir
            dst = _yuzu_dir
            reason = "Ryujinx save is newer."

        else:
            reason = "yuzu & Ryujinx saves are synced."

    if src is not None and dst is not None:
        if should_simulate_sync is False:
            if os.path.isdir(dst) is False:
                os.makedirs(dst)
            _back_up_save(dst)
            shutil.copytree(src, dst, dirs_exist_ok=True)
        print(
            log_suffix,
            title if title is not None else title_id,
            reason,
            f"Copy from\n\t{src} to\n\t{dst}.",
        )
    else:
        print(log_suffix, title if title is not None else title_id, reason)


def _back_up_save(save_dir):
    src = save_dir
    is_ryujinx = False
    if os.path.basename(save_dir) == "0":
        src = os.path.dirname(save_dir)
        is_ryujinx = True
    bk_folder = os.path.basename(src)
    if is_ryujinx:
        dst = os.path.join(dir_path, "ryujinx-save-backup", bk_folder)
    else:
        dst = os.path.join(dir_path, "yuzu-save-backup", bk_folder)
    if os.path.isdir(dst) is False:
        os.makedirs(dst)
    shutil.copytree(src, dst, dirs_exist_ok=True)


def _newest_file_in_folder(root_dir):
    newest_file = None
    newest_file_date = None

    for topdir, _, files in os.walk(root_dir):
        if len(files) == 0:
            continue
        dir_newest_file = sorted(
            files,
            key=lambda f, topdir=topdir: os.stat(os.path.join(topdir, f)).st_mtime,
            reverse=True,
        )[0]
        dir_newest_file = os.path.join(topdir, dir_newest_file)
        dir_newest_file_date = os.stat(dir_newest_file).st_mtime
        if newest_file_date is None or dir_newest_file_date > newest_file_date:
            newest_file = dir_newest_file
            newest_file_date = dir_newest_file_date

    if newest_file is not None:
        return newest_file

    # if folder doesn't have any file, then it doesn't matter which dir to compare
    first_dir = os.listdir(root_dir)[0]
    return os.path.join(root_dir, first_dir)


# pylint: disable=W0212
def _validate_args():
    if all(
        getattr(arguments, action.dest) is None
        for action in actions_arg_group._group_actions
    ):
        raise TypeError("At least one argument in actions group is required")

    if os.path.isfile(hactoolnet_path) is False:
        raise ArgumentError(
            hactoolnet_arg,
            f"{'hactoolnet.exe' if os.name == 'nt' else 'hactoolnet'} not found",
        )

    if os.path.isfile(title_keys_path) is False:
        raise ArgumentError(titlekeys_arg, "file not found")

    if should_auto_add:
        if ryujinx_dir is None:
            raise ArgumentError(
                ryujinxdir_arg, f"required when having {_get_action_name(autoadd_arg)}"
            )
        if nsp_dir is None:
            raise ArgumentError(
                nspdir_arg, f"required when having {_get_action_name(autoadd_arg)}"
            )
        if os.path.isdir(nsp_dir) is False:
            raise ArgumentError(nspdir_arg, "directory not existed")

    if should_export_csv:
        if versions_path is not None and os.path.isfile(versions_path) is False:
            raise ArgumentError(versionspath_arg, "file not found")
        if nsp_dir is None:
            raise ArgumentError(
                nspdir_arg,
                f"required when having {_get_action_name(exportupdates_arg)}",
            )
        if os.path.isdir(nsp_dir) is False:
            raise ArgumentError(nspdir_arg, "directory not existed")

    if should_sync_saves:
        if ryujinx_dir is None:
            raise ArgumentError(
                ryujinxdir_arg,
                f"required when having {_get_action_name(syncsaves_arg)}",
            )
        if yuzu_dir is None:
            raise ArgumentError(
                yuzudir_arg, f"required when having {_get_action_name(syncsaves_arg)}"
            )


def _progress_bar(current, total, bar_length=20, suffix=""):
    fraction = current / total

    arrow = int(fraction * bar_length - 1) * "-" + ">"
    padding = int(bar_length - len(arrow)) * " "

    ending = (
        "\n"
        if current == total
        else "\r" if suffix == "" else f'{suffix[:117].ljust(120, " ")}\033[F'
    )

    print(f"Progress: [{arrow}{padding}] {int(fraction*100)}%", end=ending)


_validate_args()

if should_auto_add:
    generate_ryujinx_json()

if should_export_csv:
    export_updates_csv()

if should_sync_saves:
    sync_saves()
