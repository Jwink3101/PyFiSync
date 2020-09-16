# PyFiSync Configuration
# This will be evaluated as Python code so indentation matters
#
# Note: 'A' always refers to the local machine and 'B' is the remote;
#       even if the "remote" a local path
#
# Specify strings with ' ' and lists with [ ... ]

# Local Machine
nameA = 'machineA'

# <rsync>
# These settings are the the ssh+rsync remote
remote = 'rsync'

# Remote Machine
nameB = 'machineB'
pathB = '/full/path/to/sync/dir'

# SSH settings
# Specify the user@host for a remote machine. Leave empty for a local
userhost = '' 
ssh_port = 22

# Create a persistant master SSH tunnel and multiplex over the connection.
# This works in practice but has not been as thouroughly tested.
persistant = True

# Specify the remote executable. If it is installed, it is just 'PyFiSync'. 
# Otherwise it may be something like '/path/to/python /path/to/PyFiSync.py'.
# Make sure the paths work via SSH. See the FAQs for details
remote_exe = 'PyFiSync'
# </rsync>

# <rclone>

# These settings are specific to rclone. 
remote = 'rclone'

# Remote Machine name
nameB = 'machineB'

# Specify the path as you would a remote in rclone.
pathB = 'myremote:bucket'

# Set the executable. If rclone is installed, should just be the default
rclone_executable = 'rclone'

# Specify an rclone config password if one is set. Or specify `pwprompt()` to
# have you promoted to enter one on each run. Specify False to ignore.
#
# Alternatively, you can do something like the following: Write the password in
# something like ".PyFiSync/PW.txt" where, by putting it in the .PyFiSync 
# directory, it will not be synchronized. Then:
#
#     with open(".PyFiSync/PW.txt",'rt') as file:
#         rclone_pw = file.read().strip() 
#
# WARNINGS:
#   - Specifying the password in plain text may not be secure if this config file
#     is compromised
#   - The password is passed to rclone via environment variables. Alternatively,
#     use --password-command manually with flags. An improved method may be
#     implemented in the future.
rclone_pw = False

# Specify some flags to include in all rclone calls. Must be specified as a 
# list/tuple/set. These can be used to tune transfers and improve performance. 
# Some of them have been tested but not all.
#
# WARNING: There is no validation performed on the specified flags. That means 
#          that you could specify some options tha
#
# Other Examples:
#   `--transfers NN`: How many transfers should be done at once
#   `--fast-list`: This should be used on all bucket (S3, B2, Swift) backends.
#   `--config PATH`: Specify a different path to the config file. This is very 
#   useful if you want to keep the config file somewhere else (including with 
#   the files synced). Rclone is always evaluated in the root sync directory
#   so the path can be relative to that.
rclone_flags = ['--transfers', '15',
                '--fast-list',
                '--checkers', '10']

# Some remotes (e.g. Backblaze B2) do not support any server-side move/copy
# opperations. As such, moving files is very inefficient as they must
# be downloaded and then re-uploaded. For backups, this is a waste of effort
# so instead, we can *just* backup via a local copy
rclone_backup_local = False

# Some remotes (e.g. S3) do not provide hashes for all files (such as those
# uploaded with multi-part). As such PyFiSync can imitate a hash when missing
# based on the other metadata (so it cannot track remote moves). Warning: if
# this is set with an incorrectly specified hash, (a) the screen will fill with
# warnings and (b) no moves will be tracked
imitate_missing_hash = False

# </rclone>

# File Settings:
# move_attributes specify which attributes to determine a move or previous file.
# Options for local and rsync remote 
#   'path','ino','size','birthtime','mtime' 'adler','dbhash', PLUS any 
#   `hashlib.algorithms_guaranteed`
# 
# Options for rclone remotes: 'path','size','mtime', and hashes as noted in the 
# readme
#

# <rsync>
# Prev File Suggestions (to determine if a file is new or it's only mod time
#   ['ino','path']
# Move Suggestions: (see readme for discussion)
#     macOS: ['ino','birthtime']
#     Linux: ['ino','size'] --OR-- ['ino'] (birthtime isn't avalible and inodes
#                                           get reused)
# MUST specify as a list
move_attributesA = ['ino','birthtime']
prev_attributesA = ['ino','path']

move_attributesB = ['ino','birthtime'] # ['ino','size'] --OR-- ['ino','sha1']
prev_attributesB = ['ino','path']
# </rsync>
# <rclone>
# Prev File Suggestions: 
#   ['path']
# Move Suggestions: Note with rclone, there is no advantage to moving an
#                   also-modified file
# move_attributesA
#   ['ino','mtime']
# move_attributesB
#   If hashes are supported: ['hash.SHA-1'] or whatever hash
#   If hashes are not supported: ['path'] # This essentially doesn't track moves
#
# MUST specify as a list
move_attributesA = ['ino','mtime']
prev_attributesA = ['ino','path']

move_attributesB = ['path'] # --OR-- ['hash.SHA-1']
prev_attributesB = ['path']
# </rclone>

## Conflict Settings
move_conflict = 'A'     # 'A' or 'B': When moves are conflicting

# Modification date conflicts can be resolved as follows:
# 'A','B' -- Always accept either A or B's copy regardless
# 'both' -- Tag BOTH files to with the extension of the computer name
# 'newer' -- Always keep the newer version
# 'newer_tag' -- Keep the newer version un-named and tag the older
mod_conflict = 'both'
mod_resolution = 2.5    # (s) How much time difference is allowed between files

# Specify attributes to comprare from A and B. Must specify as a list of
# (attribA,attribB) tuple, See the examples. Note that `mtime` will use the
# mod_resolution time
mod_attributes = [('mtime','mtime')]

# examples:
# mod_attributes = [('sha1','sha1')] # for rsync remote
# mod_attributes = [('sha1','hash.SHA-1')] # for rclone
# mod_attributes = [('dbhash','hash.DropboxHash')] # dropbox rclone



# Symlinked directories are ALWAYS follow unless excluded. However, if 
# copy_symlinks_as_links=False, symlinked files sync their referent (and 
# rsync uses `-L`) If True (default), symlinks copy the link itself (a la git)
#
# WARNING1: setting to True with links to files inside the sync root will cause
#           issues with tracking
# WARNING2: Recursive symlinks will NOT be caught.
copy_symlinks_as_links = True

## Other settings
backup = True    # Backup before deletion or overwriting

# If a file is deleted but a new one is in the same place, do not treat it as 
# a delete. Useful when programs overwrite rather than update files. Final 
# sync will look the same but this will optimize using rsync on that file
check_new_on_delete = True  

# Set whether or not to create a database of hash values if (and only if) using
# sha1 or adler32 as an attribute. If True (default), the code will not re-hash
# a file unless the path, size, and mtime has changed. This leaves an edge
# case, though rare
use_hash_db = True

## Exclusions.
# * If an item ends in `/` it is a folder exclusion
# * If an item starts with `/` it is a full path relative to the root
# * Wildcards and other patterns are accepted
#
# | Pattern  | Meaning                            |
# |----------|------------------------------------|
# | `*`      | matches everything                 |
# | `?`      | matches any single character       |
# | `[seq]`  | matches any character in `seq`     |
# | `[!seq]` | matches any character not in `seq` |
#
# Specify as a single list.
# These are suggestions. They can be included if desired

# excludes = ['.DS_Store','.git/','Thumbs.db'] # Suggested
excludes = []

# This sets a specified filename (such as '.PyFiSync_skip') wherein if PyFiSync
# sees this file in a directory, it will exclude it. If the file is found on
# either side, it is applied to *both* sides.
exclude_if_present = ''

# The following can be used to perform certain tasks pre and post sync.
# Called the root of the syn direcotory (i.e. they start with 
#       $ cd $PyFiSync_root
# Example uses include cleanup, git push,pull, sync.
pre_sync_bash = ''
post_sync_bash = ''




