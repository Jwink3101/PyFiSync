# Rsync Setup

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

Then sync. This will essentially create a union of the two sides

    $ PyFiSync sync path/to/syncdir

Essentially this will be a union of the two sides
    
(The `--all` is optional but suggested for the first sync. If using `--all`, it is *highly* suggested to add `--no-backup` since everything would be copied)

Or, (`PyFiSync` assumes a `sync .` if not given other options)

    $ cd path/to/syncdir
    $ PyFiSync
