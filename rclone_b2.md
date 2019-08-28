# Rclone with B2 (and S3)

(See the bottom for noted on using S3 instead of B2)

B2 is a very inexpensive storage platform that is great for syncing. It does have a few limitations, notably <strike>the lack of server-side copy. As such, any "moves" are actually download+upload+delete.</strike> (This is no longer the case for newer rclone versions with the latest B2 API. Therefore, some of these steps may not be necessary).

As such, we make two major changes to our configuration:

1. Download backups locally rather than move them to the backup dir
    * Any remote backups aren't strictly needed since the buckets can be set to backup but we will keep this here for consistency 
2. Do not do any file moves! We *could* let rclone handle the moves but it is less transparent. See below when using S3 because that is not the best setting

Finally, another limitation as noted in the readmes relates to deleting a file and then renaming another in its place.

See notes at the end for the differences with S3 setup

## Plan

We will use the *same* bucket to set up two different PyFiSync repositores. The first will be unencrypted and the second will be encrypted. We will have to adjust the settings accordingly.

It is a good idea to use encryption if you do not trust the remote or want extra protection. In this example, we also password protect the config file but that is really *not* needed on your local machine.

## Rclone Setup

### Preliminaries

Assume your local machine directory is `/path/to/PFS/`

    $ cd /path/to/PFS/
    
And that you have a bucket called `MYBUCKET`

### Set up B2 base version

Create a local config file

    $ rclone config --config rclone.cfg

Create a new B2 remote

```rclone
No remotes found - make a new one
n) New remote
s) Set configuration password
q) Quit config
n/s/q> n

name> b2base

Type of storage to configure.
Storage> b2

[...]
```

The final config should look something like

```rclone
[b2base]
type = b2
account = **ACCOUNT**
key = **KEY**
```

### Set up rclone encrypted

We *could* set up the encrypted in the same config file but we will later encrypt it. Since we also want the non-encrypted, it is easier to make a *copy*. Note that you will have to make changes in both if you change a setting

It is **NOT vital** to encrypt the encrypted B2 config since you probably trust your own computer. If you do not want to encrypt that then there is no reason to make a copy and you can skip the relevant sections

Follow the following

    $ cp rclone.cfg rcloneCRYPT.cfg
    $ rclone config --config rcloneCRYPT.cfg

Then

```
n) New remote
d) Delete remote
r) Rename remote
c) Copy remote
s) Set configuration password
q) Quit config
e/n/d/r/c/s/q> n

name> b2crypt

Storage> crypt

remote> b2base:MYBUCKET/crypt

filename_encryption> standard

directory_name_encryption> true

Password or pass phrase for encryption.
y) Yes type in my own password
g) Generate random password
n) No leave this optional password blank
y/g/n> g

Bits> 256

y/n> y

Password or pass phrase for salt. Optional but recommended.
Should be different to the previous password.
y) Yes type in my own password
g) Generate random password
n) No leave this optional password blank
y/g/n> g

Bits> 256

y/n> y
```

Now your config should look something like the following:

```
[b2base]
type = b2
account = **ACCOUNT**
key = **KEY**

[b2crypt]
type = crypt
remote = b2base:MYBUCKET/crypt
filename_encryption = standard
directory_name_encryption = true
password = **PW2**
password2 = **PW**
```

But you will want to encrypt that!

    $ rclone config --config rcloneCRYPT.cfg

```
Name                 Type
====                 ====
b2base               b2
b2crypt              crypt

e) Edit existing remote
n) New remote
d) Delete remote
r) Rename remote
c) Copy remote
s) Set configuration password
q) Quit config
e/n/d/r/c/s/q> s

a/q> a

**enter password**

Your configuration is encrypted.
c) Change Password
u) Unencrypt configuration
q) Quit to main menu
c/u/q> q

e/n/d/r/c/s/q> q
```

Now you have two configuration files for rclone. Again, you could do this as one but it is nicer to not have to enter your password for the unencrypted but you want to keep your config encrypted for the other

**BACKUP** the config file since if you lose these machine-generated passwords, you will lose access to your files.

## Set up PyFiSync

### Unencrypted

These aren't *all* settings, but should give the general idea

    $ cd /path/to/PFS/
    $ mkdir reg
    $ cd reg
    $ PyFiSync init --remote rclone

Now edit the config. This is again, not *all* of it. The comments are **not** the default comments in the documentation. They are my notes

```python
pathB = 'b2base:MYBUCKET/reg'

rclone_pw = False

# B2 should use fast-list to reduce API calls. The rclone docs
# (https://rclone.org/b2/) suggest 32 transfers. The config flag is needed to 
# specify where the configuration file is that we created above. Note that 
# rclone is always executed in the sync directory
 
rclone_flags = ['--transfers', '32',
                '--fast-list',
                '--checkers','10',
                '--config','../rclone.cfg']

# Do backups to the local machine since we can't move files with B2
rclone_backup_local = True         
                
# We never want to do a move with B2. Note that for S3 this is NOT the case
move_attributesB = ['ino','path']
prev_attributesB = ['ino','path']

# B2 supports SHA-1. 
move_attributesB = ['hash.SHA-1']
prev_attributesB = ['path']
        
# Rclone does not like symlinks with B2 and their workaround appears broken
# as of writing. See https://github.com/ncw/rclone/issues/3163
copy_symlinks_as_links = False
                
```

Notes:

* We didn't specify it but you may want to add the flag `--b2-hard-delete` since we are doing backups.

Set up then add some files

    $ pfs reset --force

...add some files and test

### Encrypted

Most of this is the same but we will reproduce it all just to be sure

    $ cd /path/to/PFS/
    $ mkdir crypt
    $ cd crypt
    $ PyFiSync init --remote rclone

Now edit the config. This is again, not *all* of it. The comments are **not** the default comments in the documentation. They are my notes

```python
pathB = 'b2crypt'

# Make it ask each time. You can also either enter the password
# here or choose to not encrypt the rclone config.
rclone_pw = pwprompt() 

# B2 should use fast-list to reduce API calls. The rclone docs
# (https://rclone.org/b2/) suggest 32 transfers. The config flag is needed to 
# specify where the configuration file is that we created above. Note that 
# rclone is always executed in the sync directory
 
rclone_flags = ['--transfers', '32',
                '--fast-list',
                '--checkers','10',
                '--config','../rcloneCRYPT.cfg']

# Do backups to the local machine since we can't move files with B2
rclone_backup_local = True         
                
# As noted above, we only want to do a "move" when the file is unmodified
# since, unlike rsync, rclone cannot make use of existing data
move_attributesA = ['ino','mtime']
prev_attributesA = ['ino','path']

# Crypt does not support any hashes. No remote move tracking!
# (which means you may redownload when not needed)
move_attributesB = ['path']
prev_attributesB = ['path']
        
# Rclone does not like symlinks with B2 and their workaround appears broken
# as of writing. See https://github.com/ncw/rclone/issues/3163
copy_symlinks_as_links = False
                
```

Notes:

* We didn't specify it but you may want to add the flag `--b2-hard-delete` since we are doing backups.

Set up then add some files

    $ pfs reset --force

Now you should be good to go! You will get some "untracked file" warnings on the first sync for files that are not on the same side.


## S3 Notes

The same process can be used for S3-based backends with a few changes.

* S3 supports server-side copy so you *can* worry less about doing backups on the remote side but rclone still cannot use existing data so there is no need to move a modified file
* Since S3 support server-side copy, it also behooves us to track moves. Change the *local* settings to
      
        # As noted above, we only want to do a "move" when the file is unmodified
        # since, unlike rsync, rclone cannot make use of existing data
        # move_attributesA = ['ino','mtime']
        # prev_attributesA = ['ino','path']

* S3 supports MD5 hashes, not SHA-1



























