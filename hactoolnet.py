"""Wrapper around the hactoolnet --listtitles subprocess call.

Consolidates four call sites in the original monolith into a single
function that returns a structured TitleInfo (or None on failure).
"""

import re
import subprocess
from dataclasses import dataclass, field
from subprocess import CalledProcessError
from typing import Literal

from config import Config


TitleKind = Literal["application", "patch", "addon", "unknown"]


@dataclass
class TitleInfo:
    title_id: str            # lowercase, e.g. "0100abcdef012000"
    application_id: str      # title_id with 13th char forced to "0"
    version_code: str        # numeric, e.g. "65536"
    kind: TitleKind
    nca_ids: list[str] = field(default_factory=list)      # non-meta NCAs
    meta_nca_id: str | None = None                         # *.cnmt.nca with .cnmt stripped
    raw_output: str = ""


def _run_listtitles(nsp_file: str, config: Config) -> str | None:
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
        return subprocess.check_output(args).decode("utf-8")
    except CalledProcessError:
        print(f"Error when process {nsp_file}")
        return None


def list_titles(nsp_file: str, config: Config) -> TitleInfo | None:
    """Invoke hactoolnet --listtitles and parse the result.

    Returns None if the subprocess failed or no title_id could be parsed.
    """
    output = _run_listtitles(nsp_file, config)
    if output is None:
        return None

    title_id_match = re.search("0100[a-zA-Z0-9]{12} v", output)
    if title_id_match is None:
        print(f"No title id is found for {nsp_file}")
        return None
    title_id = output[title_id_match.start() : title_id_match.end()]
    title_id = title_id.lower().replace(" v", "")

    version_match = re.search(" v[0-9]+ ", output)
    version_code = ""
    if version_match is not None:
        version_code = output[version_match.start() : version_match.end()].strip().replace("v", "")

    application_id = title_id[:13] + "0" + title_id[14:]

    if "Application" in output:
        kind: TitleKind = "application"
    elif "Patch" in output:
        kind = "patch"
    elif "AddOnContent" in output:
        kind = "addon"
        # AddOnContent uses the "title 0100..." form for the parent application_id
        app_match = re.search(r"title 0100[a-zA-Z0-9]{12}", output)
        if app_match is not None:
            parent = output[app_match.start() : app_match.end()].lower().replace("title ", "")
            application_id = parent
    else:
        kind = "unknown"

    # NCA ids
    nca_ids = re.findall(r"pfs0:/[a-z0-9]{32}\.nca", output)
    # Strip pfs0:/ and .nca
    nca_ids = [n.replace("pfs0:/", "").replace(".nca", "") for n in nca_ids]

    meta_matches = re.findall(r"pfs0:/[a-z0-9]{32}\.cnmt\.nca", output)
    meta_nca_id: str | None = None
    if meta_matches:
        meta_nca_id = meta_matches[0].replace("pfs0:/", "").replace(".cnmt.nca", "")
        # Remove the meta NCA from nca_ids if present (the original .cnmt.nca form
        # won't match the no-cnmt list, so nothing to filter — meta id is separate)

    return TitleInfo(
        title_id=title_id,
        application_id=application_id,
        version_code=version_code,
        kind=kind,
        nca_ids=nca_ids,
        meta_nca_id=meta_nca_id,
        raw_output=output,
    )
