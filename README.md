# ryujinx tool

A tool for better manage Ryujinx

## Prerequisites

1. Install python
2. Clone this repo
3. Download [hactoolnet](https://github.com/Thealexbarney/LibHac/releases/latest) (Windows & Linux are supported) and put it in the same folder of the repo
4. Put prod.keys file extracted from Nintendo Switch Console in the same folder of the repo

## Usage

```text
usage: ryujinx_tool [-h] [-a] [-e] [-s <priority>] [-v] [-r <dir>] [-y <dir>] [-n <dir>] [-p <file>] [--hactoolnet <file>] [--titlekeys <file>]

A tool for better manage Ryujinx

options:
  -h, --help            show this help message and exit
  -v, --version         show program's version number and exit
  -r <dir>, --ryujinxdir <dir>
                        Directory path of Ryujinx filesystem folder.
  -y <dir>, --yuzudir <dir>
                        Directory path of yuzu user folder.
  -n <dir>, --nspdir <dir>
                        Directory path of where nsp update & dlc files are stored.
  -p <file>, --versionspath <file>
                        File path of versions.json from titledb. If not provide will search in current folder or download from its source.
  --hactoolnet <file>   File path of hactoolnet.exe. Default to current folder.
  --titlekeys <file>    File path of prod.keys. Default to curreent folder.

actions:
  Requires at least one

  -a, --autoadd         Automatically add updates & DLCs to Ryujinx. Requires --nspdir, --ryujinx
  -e, --exportupdates   Export csv file with update available status for update files. Requires --nspdir
  -s <priority>, --syncsaves <priority>
                        Export csv file with update available status for update files.
                        Priority includes yuzu, ryujinx or newer. Add '~' before priority (e.g. ~yuzu) to use simulation mode.
                        Requires --ryujinxdir, --yuzudir
```

## Examples

Automatically add all updates & dlc files in a folder recursively

`python ryujinx_tool.py -a -r <Ryujinx filesystem path> -n <path to folder contains NSP files>`

Export csv file with update available status for update files

`python ryujinx_tool.py -e -n <path to folder contains NSP files>`

Sync save between Ryujinx & yuzu, with priority for newer saves to override

`python ryujinx_tool.py -s newer -r <Ryujinx filesystem path> -y <yuzu user folder path>`

## External Keys

For more detailed information on keyset files, see [KEYS.md](https://github.com/Thealexbarney/LibHac/blob/master/KEYS.md).

## Credits

- [Ryujinx](https://github.com/Ryujinx/Ryujinx/)
- [LibHac](https://github.com/Thealexbarney/LibHac/) provides hactoolnet program.
- [SwitchBrew](https://switchbrew.org) provides details on IMKV data structure.
- [yuzu](https://github.com/yuzu-emu/yuzu)
