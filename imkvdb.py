"""Read, add to, and sort Ryujinx imkvdb.arc save-index entries.

imkvdb.arc is the binary index Ryujinx uses to map title_id -> save
directory name. Missing entries cause Ryujinx not to see yuzu saves
copied onto its filesystem; sorting avoids a Ryujinx crash on load.
"""

import glob
import io
import os
import shutil
from dataclasses import dataclass, field
from datetime import datetime
from functools import cmp_to_key

from util import reverse_hex


IMKVDB_SUBPATH = os.path.join("bis", "system", "save", "8000000000000000", "0")


@dataclass
class ImkvdbState:
    save_map: dict[str, str] = field(default_factory=dict)          # title_id -> save_dirname
    bcat_save_map: dict[str, str] = field(default_factory=dict)
    key_value_list: list[dict] = field(default_factory=list)        # [{"key": hex64, "value": hex64}]
    last_index: int = 1


def _imkvdb_root(ryujinx_dir: str) -> str:
    return os.path.join(ryujinx_dir, IMKVDB_SUBPATH)


def _imkvdb_path(ryujinx_dir: str) -> str:
    return os.path.join(_imkvdb_root(ryujinx_dir), "imkvdb.arc")


def read(ryujinx_dir: str) -> ImkvdbState:
    state = ImkvdbState()
    path = _imkvdb_path(ryujinx_dir)
    with io.open(path, "rb") as f:
        f.seek(0x8)
        total_entries = int(reverse_hex(f.read(0x4).hex()), 16)
        f.seek(0xC)
        for _ in range(total_entries):
            f.seek(0xC, 1)
            key = f.read(0x40).hex()
            title_id = reverse_hex(key[:16])
            value = f.read(0x40).hex()
            save_dirname = reverse_hex(value[:16])

            # System save has save_dirname 8000000000000030; only track game indices
            if save_dirname[0] == "0":
                index = int(save_dirname, 16)
                if index > state.last_index:
                    state.last_index = index

            state.key_value_list.append({"key": key, "value": value})

            if title_id == "0000000000000000":
                continue
            # If a title id has 2 values, the later is the BCAT save entry
            if state.save_map.get(title_id) is None:
                state.save_map[title_id] = save_dirname
            else:
                state.bcat_save_map[title_id] = save_dirname

    return state


def add_entries(ryujinx_dir: str, title_id_list: list[str]) -> None:
    """Append imkvdb entries for title_ids not already present.

    Creates a timestamped .bk backup first and prunes backups to the last 5.
    Also updates lastPublishedId to the highest new index.
    """
    state = read(ryujinx_dir)
    new_last_index = state.last_index
    existing = state.save_map.keys()
    new_title_ids = [tid for tid in title_id_list if tid.lower() not in existing]
    new_total_entries = len(state.key_value_list) + len(new_title_ids)

    root = _imkvdb_root(ryujinx_dir)
    path = _imkvdb_path(ryujinx_dir)

    if not os.path.isfile(path):
        raise FileNotFoundError("imkvdb.arc not existed")

    current_timestamp = int(datetime.now().timestamp() * 1000)
    backup_path = os.path.join(root, f"imkvdb-{current_timestamp}.arc.bk")
    shutil.copy2(path, backup_path)

    # Keep total backups in limit
    backup_list = glob.glob(os.path.join(root, "imkvdb-*.arc.bk"))
    limit = 5
    if len(backup_list) > limit:
        for bk in backup_list[: len(backup_list) - limit]:
            os.remove(bk)

    with io.open(path, "r+b") as f:
        f.seek(0x8)
        total_entries_b = bytes.fromhex(
            reverse_hex(new_total_entries.to_bytes(4, "big").hex())
        )
        f.write(total_entries_b)
        f.seek(0, 2)  # seek to end
        for i, title_id in enumerate(new_title_ids, start=1):
            f.write(bytes.fromhex("494D454E4000000040000000"))
            f.write(bytes.fromhex(reverse_hex(title_id)))
            f.write(bytes.fromhex("0100000000000000"))
            f.write(bytes.fromhex("0" * 32))
            f.write(bytes.fromhex("01000000000000000000000000000000"))
            f.write(bytes.fromhex("0" * 32))
            new_last_index = state.last_index + i
            index_b = reverse_hex(new_last_index.to_bytes(4, "big").hex())
            f.write(bytes.fromhex(index_b))
            f.write(bytes.fromhex("0" * 24))
            f.write(bytes.fromhex("00000000000000000100000000000000"))
            f.write(bytes.fromhex("0" * 64))

    last_publish_id_path = os.path.join(root, "lastPublishedId")
    with io.open(last_publish_id_path, "r+b") as f:
        last_index_b = reverse_hex(new_last_index.to_bytes(4, "big").hex())
        f.write(bytes.fromhex(last_index_b))


def sort_entries(ryujinx_dir: str) -> None:
    """Sort imkvdb entries in-place by the title_id portion of the key.

    Ryujinx crashes on unsorted entries.
    """
    state = read(ryujinx_dir)
    path = _imkvdb_path(ryujinx_dir)

    if not os.path.isfile(path):
        raise FileNotFoundError("imkvdb.arc not existed")

    def compare_key(item1: dict, item2: dict) -> int:
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

    sorted_list = sorted(state.key_value_list, key=cmp_to_key(compare_key))

    with io.open(path, "r+b") as f:
        f.seek(0xC)
        for pair in sorted_list:
            f.write(bytes.fromhex("494D454E4000000040000000"))
            f.write(bytes.fromhex(pair["key"]))
            f.write(bytes.fromhex(pair["value"]))
