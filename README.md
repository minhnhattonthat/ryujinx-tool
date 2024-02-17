# ryujinx tool

Script to auto-add updates & dlc files for Ryujinx

## Prerequisites
1. Clone this repo
2. Download [hactoolnet.exe](https://github.com/Thealexbarney/LibHac/releases/latest) and put it in the same folder of the repo
3. Put prod.keys file extracted from Nintendo Switch Console in the same folder of the repo

## Usage

```
usage: ryujinx_tool.py [-h] -r <dir> -n <dir> [-p <file>] [--hactoolnet <file>] [--titlekeys <file>] [-e]

A tool for auto adding updates & dlc

options:
  -h, --help            show this help message and exit
  -p <file>, --versionspath <file>
                        File path of versions.json from titledb. Default to current folder.
  --hactoolnet <file>   File path of hactoolnet.exe. Default to curreent folder.
  --titlekeys <file>    File path of prod.keys. Default to curreent folder.
  -e, --exportupdates   Export csv file with update available status for update files. Required --versionspath

required:
  -r <dir>, --ryujinxdir <dir>
                        Directory path of Ryujinx filesystem folder.
  -n <dir>, --nspdir <dir>
                        Directory path of where nsp update & dlc files are stored.
```

## Examples
Automatically add all updates & dlc files in a folder recursively

`python .\ryujinx_tool.py -r "D:\ryujinx\portable" -n "D:\Switch NSPs"`

## External Keys

For more detailed information on keyset files, see [KEYS.md](https://github.com/Thealexbarney/LibHac/blob/master/KEYS.md).
