# Changelog

This is for *major* changes only; especially ones that break or change functionality

## 20190509:

This is a **major** change! Assuming PyFiSync has been updated on both sides, it is a good practice to copy your old config file, make a new one, and then manually update as needed.

Some (but not all) changes are:

* Added an rclone backend. The config file for rclone is very different but the rsync only has a few minor changes
* Removed `git_exclude` completely. It was a nice feature but really could be accomplished by *only* allowing certain files in git and then excluding them from PyFiSync
* Removed push/pull modes. They were not as robust and didn't add to the tool
