"""ryujinx_tool: a tool for better managing Ryujinx.

Configuration (paths) lives in config.ini next to this script.
See config.ini.example.
"""

# pylint: disable=C0116

import argparse
import sys

import config as config_module


VERSION = "v0.5.0"

# Fix powershell cannot print unicode characters
sys.stdout.reconfigure(encoding="utf-8")


YUZU_PRIORITY = "yuzu"
RYUJINX_PRIORITY = "ryujinx"
NEWER_PRIORITY = "newer"
_PRIORITIES = [YUZU_PRIORITY, RYUJINX_PRIORITY, NEWER_PRIORITY]
_FULL_PRIORITIES = _PRIORITIES + ["~" + p for p in _PRIORITIES]


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="ryujinx_tool",
        description="A tool for better manage Ryujinx",
        formatter_class=argparse.RawTextHelpFormatter,
    )

    actions = parser.add_argument_group("actions", "Requires at least one")
    actions.add_argument(
        "-a", "--autoadd", action="store_true",
        help="Automatically add updates & DLCs to Ryujinx. Requires ryujinx_dir, nsp_dir in config.",
    )
    actions.add_argument(
        "-e", "--exportupdates", action="store_true",
        help="Export csv file with update available status. Requires nsp_dir in config.",
    )
    actions.add_argument(
        "-s", "--syncsaves", metavar="<priority>", choices=_FULL_PRIORITIES,
        help=(
            "Sync saves between yuzu and Ryujinx.\n"
            "Priority: yuzu, ryujinx, or newer. Prefix '~' for simulate mode.\n"
            "Requires ryujinx_dir, yuzu_dir, nsp_dir in config."
        ),
    )
    actions.add_argument(
        "-l", "--listyuzuncas", action="store_true",
        help="Print yuzu NCA paths for a game. Requires --nspfile and ryujinx_dir, yuzu_dir in config.",
    )
    actions.add_argument(
        "--listryujnxnsps", action="store_true",
        help="Print Ryujinx NSP paths for a game. Requires --nspfile and ryujinx_dir in config.",
    )

    parser.add_argument("-v", "--version", action="version", version=f"%(prog)s {VERSION}")
    parser.add_argument(
        "--config", metavar="<file>",
        help=f"Path to config TOML file. Default: {config_module.DEFAULT_CONFIG_PATH}",
    )
    parser.add_argument(
        "--nspfile", metavar="<file>",
        help="Path to the game NSP (required by --listyuzuncas and --listryujnxnsps).",
    )
    return parser


def _require_any_action(args: argparse.Namespace) -> None:
    if not (args.autoadd or args.exportupdates or args.syncsaves or args.listyuzuncas or args.listryujnxnsps):
        raise SystemExit("error: at least one action flag is required (see --help)")


def main() -> None:
    parser = _build_parser()
    args = parser.parse_args()
    _require_any_action(args)

    cfg = config_module.load(args.config)

    if args.autoadd:
        import autoadd
        autoadd.run(cfg)

    if args.exportupdates:
        import export_updates
        export_updates.run(cfg)

    if args.syncsaves:
        import sync_saves
        priority = args.syncsaves
        simulate = priority.startswith("~")
        sync_saves.run(cfg, priority, simulate)

    if args.listyuzuncas:
        if not args.nspfile:
            raise SystemExit("error: --listyuzuncas requires --nspfile")
        import listing
        listing.run_list_yuzu_ncas(cfg, args.nspfile)

    if args.listryujnxnsps:
        if not args.nspfile:
            raise SystemExit("error: --listryujnxnsps requires --nspfile")
        import listing
        listing.run_list_ryujinx_nsps(cfg, args.nspfile)


if __name__ == "__main__":
    main()
