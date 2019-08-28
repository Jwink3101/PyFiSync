# PyFiSync

Python (+ rsync or rclone) based intelligent file sync with automatic backups and file move/delete tracking.

## Features

* Robust tracking of file moves
    * Especially powerful on MacOS, but works well enough on linux.
* rsync Mode:
    * Works out of the box with Python (tested on 2.7 and 3.5+) for rsync
    * Works over SSH for secure and easy connections with rsync mode
    * Uses rsync for actual file transfers to save bandwidth and make use of existing file data
* [rclone][rclone] mode: (beta!)
    * Can connect to a wide variety of cloud-services and offers encryption
* Extensively tested for a **huge** variety of edge-cases

## Details

PyFiSync uses a small database of files from the last sync to track moves and deletions (based on changeable attributes such as inode numbers, sha1 hashes, and/or create time). It then compares `mtime` from both sides on all files to decide on transfers.

### Backups

By default, any time a file is to be overwritten or modified, it is backed up on the machine first. No distinction is made in the backup for overwrite vs delete.

### Attributes

Moves and deletions are tracked via attributes described below.

Move attributed are used to track if a file has moved while the `prev_attributes` are used to determine if a file is the same as before

Note: On HFS+ (and maybe APFS?), macOS's file system, inodes are not reused quickly. On ext3 (Linux) they are recycled rapidly leading to issues when files are deleted and new ones are made. Do not use inodes alone on these systems

Available attributes:

#### Common attributes

* `path` -- This essentially means that moves are not tracked. If a file has the same name, it is considered the same file
* `size` -- File size. Do not use alone. Also, this attribute means that the file may not change between moves. See examples below
* `mtime` -- When the file was modified. Use with `ino` to track files

#### rsync attributes

* `ino` (inode number)-- Track the filesystem inode number. May be safely used alone on HFS+ but not on ext3 since it reuses inodes. In that case, use with another attribute
* `sha1` -- Very robust to track file moves but like `size`, requires the file not change. Also, slow to calculate (though, by default, they are not recalculated on every sync)
* `birthtime` -- Use the `stat()` (via `os.stat()`) file create time. This does not exist on some linux machines, some python implementations (PyPy), and/or is unreliable

#### rclone attributes

* `hash.HASH` -- Use a hash from rclone. Depends on which hashes are available.

#### Suggested move Attribute Combinations

For rsync

* On macOS, the following is suggested: `[ino,birthtime]`
* On linux, the following is suggested: `[inode,mtime]`
    * This means that **moved files should not be modified** on that side of the sync.

### Empty Directories

PyFiSync syncs files and therefore will *not* sync empty directories from one machine to the other. However, if, and only if, a directory is *made* empty by the sync, it will be deleted. That includes nested directories. In rclone mode, empty directories are not handled at all by PyFiSync

## Install

This are *no dependancies!* (for rsync). Everything is included in the package (though `ldtable` is also separately developed [here](https://github.com/Jwink3101/ldtable))

To install:

    $ pip install git+https://github.com/Jwink3101/PyFiSync
    
Or download the zip file and run

    $ python setup.py install

Note: On the remote machine, the path to PyFiSync must be found via SSH. For example, if your python is from (Ana/Mini)conda, then it places the paths into the `.bash_profile`. Move the paths to `.bashrc` so that PyFiSync can be found. Alternatively, specify `PyFiSync_path` and `remote_program` in the config. Or, you can explicitly set the path to the files

## Setup

See [rsync](rsync.md) for setup of the default mode.

Setting up rclone is a bit more involved since you must set up an appropriate rclone remote. See [rclone readme](rclone.md) for general details and [rclone\_b2](rclone_b2.md) for a detailed walk through of setting up with B2 (and S3 with small noted changes). 

To initiate an rclone-based repo, do

    $ PyFiSync init --remote rclone

## Settings

There are many settings, all documented in the config file written after an `init`. Here are a few:

### Exclusions

Exclusion naming is done is such a way that it replicated a *subset* of `rsync` exclusions. That is, the following pattern is what **this** code follows. `rsync` has its own exclusion engine which is more advanced but should be have similarly.

* If an item ends in `/` it is a folder exclusion
* If an item starts with `/` it is a full path relative to the root
* Wildcards and other patterns are accepted

| Pattern  | Meaning                            |
|----------|------------------------------------|
| `*`      | matches everything                 |
| `?`      | matches any single character       |
| `[seq]`  | matches any character in `seq`     |
| `[!seq]` | matches any character not in `seq` |

Examples:

* Exclude **all** git directories: `.git/`
* Exclude a specific folder: `/path/to/folder/` (where `/` is the start of the sync directory
* Exclude all files that start with `file`: `file*`
* Exclude all files that start with `file` in a specific directory: `/path/to/file*`

### Symlinks

First note that **all directory links are followed** regardless of setting. Use exclusions to avoid syncing a linked directory.

If `copy_symlinks_as_links=False` symlinked files sync their referent (and rsync uses `-L`) If `True` (default), symlinks copy the link itself (a la how git works)

WARNINGS:

* If `copy_symlinks_as_links = False` and there are symlinked files to another IN sync root, there will be issues with the file tracking. Do not do this!
* As also noted in Python's documentation, there is no **safeguard against recursively symlinked directories**.
* rsync may throw warnings for broken links
* rclone's support of symlinks is unreliable at the moment.


### Pre and Post Bash

There is the option to also add some bash scripts pre and post sync. These may be useful if you wish to do a git push, pull, etc either remote or local.

They are ALWAYS executed from the sync root (a `cd /path/to/syncroot` is inserted above).

## Running Tests

To run the test, in bash, do:

    $ source run_test.sh

In addition to testing a whole slew of edge cases, it also  will test all actions on a local sync, and remote to both python2 and python3 (via `ssh localhost`). The run script will try to call `py.test` for both versions of python locally.

## Known Issues and Limitations

The test suite is **extremely** extensive as to cover tons of different and difficult scenarios. See the tests for further exploration of how the code handles these cases. Please note that unless specified explicitly in the config or the command-line flag, all deletions and (future) overwrites first perform a backup. Moves are not backed up but make likely be unwound from the logs.

A few notable limitations are as follows:

* Symlinks are followed (optionally) but if the file they are linking to is also in the sync folder, it may confuse the move tracking
* File move tracking
    * A file moved with a new name that is excluded will propagate as deleted. This is expected since the code no longer has a way to "see" the file on the one side.
    * A file that is moved on one side and deleted on the other will NOT have the deletion propagated regardless of modification
* Sync is based on modification time metadata. This is fairly robust but could still have issues. In rsync mode, even if PyFiSync decides to sync the files, it may just update the metadata. In that case, you may just want to disable backups. With rclone, it depends on the remote and care should be taken.    

There is also a potential issue with the test suite. In order to ensure that the files are noted as changed (since they are all modified so quickly), the times are often adjusted via some random amounts. There is a *small* chance some tests could fail due to a small number not changing. Running the tests again should pass.

See [rclone readme](rclone.md) for some rclone-related known issues

## Other Questions

See the (growing) [FAQ](FAQs.md) for some more details and/or troubleshooting

[rclone]:https://rclone.org/


