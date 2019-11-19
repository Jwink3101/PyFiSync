# Changelog

This is for *major* changes only; especially ones that break or change functionality

## 20191119:

Minor bug fix for ssh+rsync backend where the default excludes (e.g. `.git`) were being applied even when they were explicitly *not* intended to be excluded.

## 20191115:

This change is all about using file hashes.

* Added ability to tell PyFiSync to compare hashes instead of or in addition to `mtime`. This is *much* more robust, though more expensive
    * `mtime` is still used to resolve conflicts but if two files have differing `mtime` but the same hash (and name), they are not transfered.
* Added the ability to specify any `hashlib.algorithms_guaranteed` for local and rsync remotes.
    * Also added dbhash
    * Changed adler to return hex value. (and actually made adler an option)
* Improved hashdb test to ensure it is *actually* being used (it was! It just wasn't tested well)

Plus minor bug fixes, typo fixes, and other improvements

## 20190509:

This is a **major** change! Assuming PyFiSync has been updated on both sides, it is a good practice to copy your old config file, make a new one, and then manually update as needed.

Some (but not all) changes are:

* Added an rclone backend. The config file for rclone is very different but the rsync only has a few minor changes
* Removed `git_exclude` completely. It was a nice feature but really could be accomplished by *only* allowing certain files in git and then excluding them from PyFiSync
* Removed push/pull modes. They were not as robust and didn't add to the tool
