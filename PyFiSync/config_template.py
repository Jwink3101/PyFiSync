# PyFiSync Configuration
# This will be evaluated as Python code so indentation matters
#
# Note: 'A' always refers to the local machine and 'B' is the remote;
#       even if the "remote" a local path
#
# Specify strings with ' ' and lists with [ ... ]

# Local Machine
nameA = 'machineA'

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

# Specify the path to the REMOTE PyFiSync file
# If empty, will assume it is installed and not specify a path
PyFiSync_path = ''

# Specify the remote python path 
# WARNING: PyPy does not support birthtimes and will set them to zero. Do not
#          use PyPy if using birthtime but otherwise, it is faster!
remote_program = 'python'
# remote_program = 'python3'
# remote_program='/path/to/python'

# File Settings:
# move_attributes specify which attributes to determine a move or previous file.
# Options 'path','ino','size','sha1','birthtime'
#
# Prev File Suggestions (to determine if a file is new or it's only mod time
#   ['ino','path']
#
# Move Suggestions: (see readme for discussion)
#     macOS: ['ino','birthtime']
#     Linux: ['ino','size'] --OR-- ['ino'] (birthtime isn't avalible and inodes
#                                           get reused)
# MUST specify as a list
move_attributesA = ['ino','birthtime']
prev_attributesA = ['ino','path']

move_attributesB = ['ino','birthtime'] # ['ino','size'] --OR-- ['ino','sha1']
prev_attributesB = ['ino','path']

## Conflict Settings
move_conflict = 'A'     # 'A' or 'B': When moves are conflicting
mod_conflict = 'both'   # 'both','newer','A','B'
mod_resolution = 2.5    # (s) How much time difference is allowed between files

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
rsync_checksum = False # Uses --checksum

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
# Specify as a single list
excludes = ['.DS_Store','.git/','Thumbs.db']

# The following can be used to perform certain tasks pre and post sync.
# They are ONLY called on a sync/push/pull and they will ALWAYS be called
# from the root of the syn direcotory (i.e. they start with 
#       $ cd $PyFiSync_root
# Example uses include cleanup, git push,pull, sync.
pre_sync_bash = ''
post_sync_bash = ''

# Setting this to True will ignore any file that is currently tracked with git.
# It will work regardless of where the git repo is located (e.g. below the root
# of the PyFiSync folder).
# WARNING: It will be based on the current state of any git repos on both
#          sides. Make sure the git repos are in sync (via pre_sync_bash
#          for example) before syncing
git_exclude = False





