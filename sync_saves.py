"""syncsaves action: two-way sync between yuzu and Ryujinx saves.

Priority selects which side wins on conflict:
    yuzu    -> always copy yuzu -> ryujinx
    ryujinx -> always copy ryujinx -> yuzu
    newer   -> copy whichever side has the most recently modified file

Prefix priority with '~' (e.g. ~newer) for simulation mode: no file
writes, no imkvdb mutations. Backups of destination saves are taken to
yuzu-save-backup/ or ryujinx-save-backup/ next to the script before
overwriting.
"""

import io
import os
import shutil

import imkvdb
from config import Config, SCRIPT_DIR
from util import progress_bar, reverse_hex


def _get_yuzu_profile_uuid(yuzu_dir: str) -> str:
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
    with io.open(profiles_path, "rb") as f:
        f.seek(0x10)
        return f.read(0x10).hex()


def _newest_file_in_folder(root_dir: str) -> str:
    newest_file: str | None = None
    newest_file_date: float | None = None

    for topdir, _, files in os.walk(root_dir):
        if len(files) == 0:
            continue
        dir_newest = sorted(
            files,
            key=lambda f, topdir=topdir: os.stat(os.path.join(topdir, f)).st_mtime,
            reverse=True,
        )[0]
        dir_newest = os.path.join(topdir, dir_newest)
        dir_newest_date = os.stat(dir_newest).st_mtime
        if newest_file_date is None or dir_newest_date > newest_file_date:
            newest_file = dir_newest
            newest_file_date = dir_newest_date

    if newest_file is not None:
        return newest_file

    # Empty folder: fall back to first entry
    first_dir = os.listdir(root_dir)[0]
    return os.path.join(root_dir, first_dir)


def _back_up_save(save_dir: str) -> None:
    src = save_dir
    is_ryujinx = False
    if os.path.basename(save_dir) == "0":
        src = os.path.dirname(save_dir)
        is_ryujinx = True
    bk_folder = os.path.basename(src)
    backup_root = "ryujinx-save-backup" if is_ryujinx else "yuzu-save-backup"
    dst = os.path.join(SCRIPT_DIR, backup_root, bk_folder)
    os.makedirs(dst, exist_ok=True)
    shutil.copytree(src, dst, dirs_exist_ok=True)


def _sync_dir(
    yuzu_game_save_dir: str,
    ryujinx_game_save_dir: str,
    title_id: str,
    priority: str,
    simulate: bool,
    nsp_dir: str,
) -> None:
    log_suffix = "- [Simulate]" if simulate else "-"
    reason = "Unknown error."
    src: str | None = None
    dst: str | None = None
    title = next(
        (t for t in os.listdir(nsp_dir) if title_id.lower() in t.lower()), None
    )

    if "yuzu" in priority:
        src = yuzu_game_save_dir
        dst = ryujinx_game_save_dir
        reason = "yuzu save is priority."
    elif "ryujinx" in priority:
        src = ryujinx_game_save_dir
        dst = yuzu_game_save_dir
        reason = "Ryujinx save is priority."
    elif not os.path.isdir(yuzu_game_save_dir):
        src = ryujinx_game_save_dir
        dst = yuzu_game_save_dir
        reason = "yuzu save not existed."
    elif not os.path.isdir(ryujinx_game_save_dir):
        src = yuzu_game_save_dir
        dst = ryujinx_game_save_dir
        reason = "Ryujinx save not existed."
    else:
        yuzu_listdir = os.listdir(yuzu_game_save_dir)
        ryujinx_listdir = os.listdir(ryujinx_game_save_dir)

        if len(yuzu_listdir) == 0:
            if len(ryujinx_listdir) > 0:
                src = ryujinx_game_save_dir
                dst = yuzu_game_save_dir
                reason = "yuzu save is empty."
            else:
                reason = "yuzu & Ryujinx saves are both empty."
        elif len(ryujinx_listdir) == 0:
            src = yuzu_game_save_dir
            dst = ryujinx_game_save_dir
            reason = "Ryujinx save is empty."
        elif (
            os.stat(_newest_file_in_folder(yuzu_game_save_dir)).st_mtime
            - os.stat(_newest_file_in_folder(ryujinx_game_save_dir)).st_mtime
            > 1
        ):
            src = yuzu_game_save_dir
            dst = ryujinx_game_save_dir
            reason = "yuzu save is newer."
        elif (
            os.stat(_newest_file_in_folder(ryujinx_game_save_dir)).st_mtime
            - os.stat(_newest_file_in_folder(yuzu_game_save_dir)).st_mtime
            > 1
        ):
            src = ryujinx_game_save_dir
            dst = yuzu_game_save_dir
            reason = "Ryujinx save is newer."
        else:
            reason = "yuzu & Ryujinx saves are synced."

    label = title if title is not None else title_id
    if src is not None and dst is not None:
        if not simulate:
            os.makedirs(dst, exist_ok=True)
            _back_up_save(dst)
            shutil.copytree(src, dst, dirs_exist_ok=True)
        print(log_suffix, label, reason, f"Copy from\n\t{src} to\n\t{dst}.")
    else:
        print(log_suffix, label, reason)


def run(config: Config, priority: str, simulate: bool) -> None:
    ryujinx_dir = config.require("ryujinx_dir")
    yuzu_dir = config.require("yuzu_dir")
    nsp_dir = config.require("nsp_dir")

    print("Syncing saves")

    yuzu_save_dirname = reverse_hex(_get_yuzu_profile_uuid(yuzu_dir)).upper()
    yuzu_save_dir = os.path.join(
        yuzu_dir, "nand", "user", "save", "0000000000000000", yuzu_save_dirname
    )
    ryujinx_save_dir = os.path.join(ryujinx_dir, "bis", "user", "save")

    title_id_list = os.listdir(yuzu_save_dir)
    if not simulate:
        imkvdb.add_entries(ryujinx_dir, title_id_list)
        imkvdb.sort_entries(ryujinx_dir)

    save_map = imkvdb.read(ryujinx_dir).save_map
    total_saves = len(save_map.items())

    for index, (title_id, ryujinx_save_dirname) in enumerate(save_map.items()):
        yuzu_game_save_dir = os.path.join(yuzu_save_dir, title_id.upper())
        ryujinx_game_save_dir = os.path.join(ryujinx_save_dir, ryujinx_save_dirname, "0")
        _sync_dir(yuzu_game_save_dir, ryujinx_game_save_dir, title_id, priority, simulate, nsp_dir)
        progress_bar(index + 1, total_saves)

    print("Saves synced")
