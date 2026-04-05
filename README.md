# ryujinx tool

A tool for better manage Ryujinx

## Prerequisites

1. Install python
2. Clone this repo
3. Download [hactoolnet](https://github.com/Thealexbarney/LibHac/releases/latest) (Windows & Linux are supported) and put it in the same folder of the repo
4. Put prod.keys file extracted from Nintendo Switch Console in the same folder of the repo

## Configuration

`ryujinx_tool` reads paths from `config.ini` next to the script. Copy `config.ini.example` to `config.ini` and fill in the paths (the file uses TOML syntax):

```toml
[paths]
ryujinx_dir   = "C:/path/to/Ryujinx/filesystem"
yuzu_dir      = "C:/path/to/yuzu/user"
nsp_dir       = "C:/path/to/nsp/updates-and-dlcs"
# hactoolnet  = "./hactoolnet.exe"  # optional, default: next to script
# title_keys  = "./prod.keys"       # optional, default: next to script
# versions_json = "./versions.json" # optional, auto-downloaded if unset
```

Use `--config <file>` to point at a different config file.

## Usage

```text
usage: ryujinx_tool [-h] [-a] [-e] [-s <priority>] [-l] [--listryujnxnsps]
                    [-v] [--config <file>] [--nspfile <file>]

actions (requires at least one):
  -a, --autoadd         Automatically add updates & DLCs to Ryujinx
  -e, --exportupdates   Export csv of update-available status
  -s, --syncsaves <priority>
                        Sync saves between yuzu and Ryujinx.
                        <priority> is one of: yuzu, ryujinx, newer.
                        Prefix with '~' (e.g. ~newer) for simulate mode.
  -l, --listyuzuncas    Print yuzu NCA paths for a game (requires --nspfile)
  --listryujnxnsps      Print Ryujinx NSP paths for a game (requires --nspfile)

options:
  -h, --help            show this help message and exit
  -v, --version         show program's version number and exit
  --config <file>       Path to config file (default: config.ini next to script)
  --nspfile <file>      Game NSP path (required by list actions)
```

## Examples

Automatically add all updates & DLC files in a folder (paths come from config.ini):

```
python ryujinx_tool.py -a
```

Export updates.csv:

```
python ryujinx_tool.py -e
```

Sync saves, preferring the newer side:

```
python ryujinx_tool.py -s newer
```

Simulate the sync without writing any files:

```
python ryujinx_tool.py -s ~newer
```

Print the NCA paths yuzu should have for a game:

```
python ryujinx_tool.py -l --nspfile "path/to/game.nsp"
```

## External Keys

For more detailed information on keyset files, see [KEYS.md](https://github.com/Thealexbarney/LibHac/blob/master/KEYS.md).

## Credits

- [Ryujinx](https://github.com/Ryujinx/Ryujinx/)
- [LibHac](https://github.com/Thealexbarney/LibHac/) provides hactoolnet program.
- [SwitchBrew](https://switchbrew.org) provides details on IMKV data structure.
- [yuzu](https://github.com/yuzu-emu/yuzu)
