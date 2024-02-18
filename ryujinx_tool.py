"""tool for ryujinx"""

import glob
import os
import subprocess
import argparse
from argparse import ArgumentError
import io
from subprocess import CalledProcessError
import re
import json

dir_path = os.path.dirname(os.path.realpath(__file__))

parser = argparse.ArgumentParser(
    prog="ryujinx_tool", description="A tool for better manage Ryujinx"
)
actions_group = parser.add_argument_group("actions", "Requires at least one")
autoadd_arg = actions_group.add_argument(
    "-a",
    "--autoadd",
    action="store_true",
    help="Automatically add updates & DLCs to Ryujinx. Requires --nspdir, --ryujinx",
)
exportupdates_arg = actions_group.add_argument(
    "-e",
    "--exportupdates",
    action="store_true",
    help="Export csv file with update available status for update files. Requires --nspdir, --versionspath",
)
parser.add_argument("-v", "--version", action="version", version="%(prog)s v0.2")
ryujinxdir_arg = parser.add_argument(
    "-r",
    "--ryujinxdir",
    metavar="<dir>",
    help="Directory path of Ryujinx filesystem folder.",
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
    help="File path of versions.json from titledb. Default to current folder.",
    default=os.path.join(dir_path, "versions.json"),
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
nsp_dir = arguments.nspdir
hactoolnet_path = arguments.hactoolnet
title_keys_path = arguments.titlekeys
versions_path = arguments.versionspath
should_auto_add = arguments.autoadd
should_export_csv = arguments.exportupdates


def _validate_args():
    if all(flag is None for flag in [should_auto_add, should_export_csv]):
        raise TypeError("At least one argument in actions group is required")

    if os.path.isfile(hactoolnet_path) is False:
        raise ArgumentError(
            hactoolnet_arg,
            f"{'hactoolnet.exe' if os.name == 'nt' else 'hactoolnet'} not found",
        )

    if os.path.isfile(title_keys_path) is False:
        raise ArgumentError(titlekeys_arg, "prod.keys not found")

    if should_auto_add:
        if ryujinx_dir is None:
            raise ArgumentError(ryujinxdir_arg, "required when have --autoadd")
        if nsp_dir is None:
            raise ArgumentError(nspdir_arg, "required when have --autoadd")
        if os.path.isdir(nsp_dir) is False:
            raise ArgumentError(nspdir_arg, "directory not existed")

    if should_export_csv:
        if versions_path is None:
            raise ArgumentError(versionspath_arg, "required when have --exportupdates")
        if nsp_dir is None:
            raise ArgumentError(nspdir_arg, "required when have --exportupdates")
        if os.path.isdir(nsp_dir) is False:
            raise ArgumentError(nspdir_arg, "directory not existed")


def export_updates_csv():
    print("Exporting updates.csv")

    versions_map = {}
    with open(versions_path, encoding="utf-8") as f:
        versions_map = json.load(f)
        f.close()

    output_csv = "Filename, Title ID, Version Code, Latest Version Code, Latest Updated Date, Update Available\n"

    nsp_files = glob.glob(os.path.join(nsp_dir, "**", "*.nsp"), recursive=True)
    total_files = len(nsp_files)
    for index, nsp_file in enumerate(nsp_files):
        __progress_bar(index + 1, total_files)

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


def generate_ryujinx_json():
    ryujinx_update_json_map = {}
    ryujinx_dlc_json_map = {}

    nsp_files = glob.glob(os.path.join(nsp_dir, "**", "*.nsp"), recursive=True)
    total_files = len(nsp_files)
    for index, nsp_file in enumerate(nsp_files):
        suffix = f"\nProcessing {nsp_file}"
        __progress_bar(index + 1, total_files, suffix=suffix)

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

        __progress_bar(
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

        __progress_bar(
            index + 1,
            total_dlcs,
            suffix=f"\nExporting {os.path.join(output_dir, 'dlc.json')}",
        )

        if not os.path.isdir(output_dir):
            os.makedirs(output_dir)

        with io.open(os.path.join(output_dir, "dlc.json"), "w", encoding="utf-8") as f:
            f.write(json.dumps(ryujinx_dlc_jsons, indent=2))

    print("\nFinished exporting dlc.json")


def __progress_bar(current, total, bar_length=20, suffix=""):
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
