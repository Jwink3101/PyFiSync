# PyFiSync

Python (+ rsync) based intelligent file sync with automatic backups and file move/delete tracking.

## Features

* Robust tracking of file moves
    * Especially powerful on MacOS, but works well enough on linux.
* Works out of the box with Python (tested on 2.7 and 3.6)
* Works over SSH for secure and easy connections
* Uses rsync for actual file transfers to save bandwidth
* Extensively tested for a **huge** variety of edge-cases


## Details

PyFiSync uses a small database of files from the last sync to track moves and deletions (based on changeable attributes such as inode numbers, sha1 hashes, and/or create time). It then compares `mtime` from both sides on all files to decide on transfers.

### Backups

By default, any time a file is to be overwritten or modified, it is backed up on the machine first. No distinction is made in the backup for overwrite vs delete.

### Attributes

Moves and deletions are tracked via attributes described below.

Note: On HFS+ (and maybe APFS?), macOS's file system, inodes are not reused quickly. On ext3 (Linux) they are recycled rapidly leading to issues when files are deleted and new ones are made. Do not use inodes alone on these systems

Available attributes:

* `path` -- This essentially means that moves are not tracked. If a file has the same name, it is considered the same file
* `ino` (inode number)-- Track the filesystem inode number. May be safely used alone on HFS+ but not on ext3
* `size` -- File size. Do not use alone. Also, this attribute means that the file may not change between moves. See examples below
* `sha1` -- Very robust to track file moves but like `size`, requires the file not change. Also, slow to calculate (though, by default, they are not recalculated on every sync)
* `birthtime` -- Use the `stat()` (via `os.stat()`) file create time. This does not exist on some linux machines, some python implementations (PyPy), and/or is unreliable

#### Suggested move Attribute Combinations

* On macOS, the following is suggested: `inode,birthtime`
* On linux, the following is suggested: `inode,size`
    * This means that **moved files should not be modified** on that side of the sync.

### Empty Directories

PyFiSync syncs files and therefore will *not* sync empty directories from one machine to the other. However, if, and only if, a directory is *made* empty by the sync, it will be deleted. That includes nested directories.


## Install

This are *no dependancies!*. Everything is included in the package (though `ldtable` is also separately developed [here](https://github.com/Jwink3101/ldtable))

To install:

    $ pip install git+https://github.com/Jwink3101/PyFiSync
    
Or download the zip file and run

    $ python setup.py install

Note: On the remote machine, the path to PyFiSync must be found via SSH. For example, if your python is from (Ana/Mini)conda, then it places the paths into the `.bash_profile`. Move the paths to `.bashrc` so that PyFiSync can be found. Alternatively, specify `PyFiSync_path` and `remote_program` in the config.

## Set Up

First set up ssh keys on your *local* machine:

    $ cd
    $ ssh-keygen -t rsa 
    
    # It is highly suggested you use a password but you can hit enter 
    # twice to skip it

    $ cat ~/.ssh/id_rsa.pub | ssh user@remote-system "mkdir -p ~/.ssh && cat >>  ~/.ssh/authorized_keys" 

I will assume that `PyFiSync` is in the path or an alias has been set up:

    $ PyFiSync init path/to/sync_dir

Then modify the config file. All options are commented.

    $ PyFiSync reset --force path/to/sync_dir

Then sync, push, or pull by choosing one of the following commands:

    $ PyFiSync sync path/to/syncdir
    $ PyFiSync push --all --no-backup path/to/syncdir
    $ PyFiSync pull --all --no-backup path/to/syncdir
    
(The `--all` is optional but suggested for the first sync. If using `--all`, it is *highly* suggested to add `--no-backup` since everything would be copied)

Or, (`PyFiSync` assumes a `sync .` if not given other options)

    $ cd path/to/syncdir
    $ PyFiSync

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

### Ignore git-tracked files

When selected, PyFiSync will exclude any file that is tracked by git and exclude `.git/` directories. This is preferable to syncing the `.git/` folder and everything since that can get corrupted pretty easily. Then, to keep a directory in line, you can use git to sync specific files and PyFiSync for everything else.

Please note that if your typical use case involves larger files and requires better syncing, [`git-annex`][ga] or [`git-lfs`][gl] may be more appropriate

[gl]:https://git-lfs.github.com/
[ga]:https://git-annex.branchable.com/

#### Warnings and Edge Cases

There are a few gotchas to excluding git-tracked files

* The exclusions are based on each machine's local copy of the git repo. Therefore, if a file is tracked via git on one side but not the other, it will transfer and overwrite (thankfully, this should be recoverable via git...)
    * It is *highly* recommended to **make sure the git repos are in sync** first!
* If it is an entire type of file that will be kept in sync, it is faster and preferable to use git and PyFiSync's exclusions to keep them separate

### Pre and Post Bash

There is the option to also add some bash scripts pre and post sync. These may be useful if you wish to do a git push, pull, etc either remote or local.

They are ALWAYS executed from the sync root (a `cd /path/to/syncroot` is inserted above).

## Primary Modes

### Sync

This is the primary mode. It is assumed that if you invoke PyFiSync without any arguments, it is the same as `sync .`.

Synchronizes to the host and updates the file DBs

### Push and Pull mode

A push or a pull follows the same logic as a sync except they do not do any kind of conflict resolution and diminished backups.

File backups *do* occur in a push or pull but a file can move into another and it will *not* backup.

Furthermore, because `--all` mode tells PyFiSync that *everything* has been modified, it is **highly** suggested to use `--no-backup` with `--all`. Since rsync is used for the transfer, the `--all` mode is otherwise still pretty fast.


General Warning: As with `rsync`, push and pull modes do not guarantee parity of both sides. And there is no `--delete` mode. If push/pull are part of your regular workflow, consider using `rsync` directly.


## Running Tests

To run the test, in bash, do:

    $ source run_test.sh

In addition to testing a whole slew of edge cases, it also  will test all actions on a local sync, and remote to both python2 and python3 (via `ssh localhost`). The run script will try to call `py.test` for both versions of python locally.

### Python 3 Note

The code is tested and compatible with both python 2 and 3. Furthermore, if using a later version of python (or have installed the backported scandir), the file listing time will be faster.

## Known Issues and Limitations

The test suite is **extremely** extensive as to cover tons of different and difficult scenarios. See the tests for further exploration of how the code handles these cases. Please note that unless specified explicitly in the config or the command-line flag, all deletions and (future) overwrites first perform a backup. Moves are not backed up but make likely be unwound from the logs.

A few notable limitations are as follows:

* Moves are compared and conflicts are accounted for but the code will *never* move a file into another in *sync* mode. If not in sync mode, it will back up before the move (by default)
* Symlinks are followed (optionally) but if the file they are linking to is also in the sync folder, it may confuse the move tracking
* File move tracking
    * A file moved with a new name that is excluded will propagate as deleted. This is expected since the code no longer has a way to "see" the file on the one side.
    * A file that is moved on one side and deleted on the other will NOT have the deletion propagated regardless of modification
    
There is also a potential issue with the test suite. In order to ensure that the files are noted as changed (since they are all modified so quickly), the times are often adjusted via some random amounts. There is a *small* chance some tests could fail due to a small number not changing. Running the tests again should pass.


## Other Backends

Right now, the only backend that is supported is SSH + rsync. This was coded to be somewhat modular that another backend could be easily supported.

A backend needs to be able to:

* List files and attributes
* Processes moves, backups, deletions
* Upload and download files (but **needs** to maintain the `mtime`)
    * Potentially, this may be done by adding a separate metadata file but this has not yet been considered.

This means that something like S3 or B2 could be incorporated (though B2 does not support moves).

See the `remote_interfaces.py` and the base class `remote_interface_base` for details.

## Potential Issues

On some `openssh` installations on macOS (anecdotally, from `brew`), there seems to be a problem with sending the wrong encoding to the remote terminal which makes it *seem* like there is a unicode error in PyFiSync. This is actually related to sending terminal encoding. See [this](https://askubuntu.com/a/874765) where they had the *opposite* problem.

The fix is to add the following to `/etc/ssh/ssh_config` or `~/.ssh/config`:

    Host *
        SendEnv LANG LC_* # Send locale to remote




