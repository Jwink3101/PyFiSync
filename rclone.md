# Rclone

(beta)

[rclone](https://rclone.org/) is now a supported backend with PyFiSync but there are some important details.

First and foremost, **this is a beta feature**. Some aspects have been formally and informally tested but there are a lot more edge cases to consider. And, a fair amount options that may or may not be needed based on settings

## Setup

Set up your remote as you want. You can do it into its own config file but be sure to then add the `--config PATH` flag.

See examples

## Password protected config

If you password protect your config, you will need to either store your password in the PyFiSync config (*not* recommended) or you will have to enter it each time. To enter it each time, specify:

    # Specify False if config is not encrypted. True means it will prompt
    # for your password and a string specifies the password (not recommended)
    rclone_config_encrypted = True

The password is stored in memory only and passes as an environment variable to rclone. This *should* be secure enough but, presumably, an offender can do a memory dump. 

## Flags

With this backend, you can (and usually *need*) to set some flags. Some of them are listed in the config file and they are often rclone remote dependent. Some of them have been tested but not all.

Some common ones:

* `--transfers NN`: How many transfers should be done at once
* `--fast-list`: This should be used on all bucket (S3, B2, Swift) backends.
* `--config PATH`: Specify a different path to the config file. This is very useful if you want to keep the config file somewhere else (including with the files synced)

These are to be specified as a list! 

**WARNING**: There is no validation performed on the specified flags. That means that you could specify some options that interfere with the expected behavior of of rclone including links.

## Symlinks

The `copy_symlinks_as_links` setting does not work for some remotes. rclone claims to have a workaround but it is inconsistent. See [this github issue](https://github.com/ncw/rclone/issues/3163). May be fixed in the future

## Attributes

In addition to the default `mtime`, the acceptable attributes are `size` and hashes as described below


### Hashes

Some, but not all, rlcone remotes support hashes. While on the local side, PyFiSync only supports sha1, the rclone backend will support whatever hash it can. This depends on the [remote]. To specify a hash as a `move_attribute` for rlcone specify as `hash.SHA-1` (where it must be `SHA-1` since that is what `lsjson` returns). If the remote does not support the specified hash, expect a key error!

## Mod Time

rlcone remotes *must* support `ModTime` as per the [remote docs][remote]. If it does not, PyFiSync will likely fail and/or cause issues. There is no check to make sure this is case! It is up to the user 

## Backups

Some [remotes][remote] do not natively support moves or even server-side copy. Rclone presents a unified interface to all of these systems so it replicates moves with either download + upload + delete or, if it can, server-side copy + delete. As such, for files that should be backed up (before overwrite or delete) you can instead just download and store the backup locally.

## Tests 

Many of the sync tests are also tested with rclone. Some however are not because they are not expected to pass or because they require some custom change.

See known issues for a discussion of situations (and failed tests) because rclone cannot handle it.

## Other situations

### Missing Hashes

In general, a remote supports a certain type of hash and that can be specified. For example B2 supports SHA-1 (attribute `hash.SHA-1`) and S3 supports MD5 (attribute `hash.MD5`). Some remotes (e.g. crypt) do not support any hashes.

According to the [rclone docs](https://rclone.org/s3/) not all files have a hash even if the system other-wise supports it.

As such, if `imitate_hash = True` then a warning will be printed about the file but the code will imitate a hash by looking at the other metadata (which means it cannot be used for move tracking). Using `imitate_hash = True` with an incorrectly-specified hash (e.g. `hash.SHA1` instead of `hash.SHA-1`) will cause a lot of errors.

## Known Issues

* When using rclone mode, folders are essentially ignored. Empty directories will remain. This is not an issue for remotes that do not explicitly view directories
* If a file is deleted and then another is moved into its place, it will view it as a delete and then a new file (which will likely conflict). This is due to only specifying the path as a previous attribute so there is no way to know a file was moved vs deleted. This is tested with `test_file_deleted_replaced_with_move` (which the rclone-version would fail) but the issues is replicated in `test_file_replaced_deleted_other_prev_attr`
* Since directories are not a concept in rclone nor some remotes, tests dealing with empty directories will fail. See 
    * `test_delete_file_in_folder`,`test_delete_folder`
* Symlinks do not work on some remotes unless when `copy_symlinks_as_links` is True. See [this github issue](https://github.com/ncw/rclone/issues/3163). A workaround may be included in the future



[remote]:https://rclone.org/overview/
