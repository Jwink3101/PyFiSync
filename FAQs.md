(work in progress)

## Why is this better than Unison

Well, it may not be! I have only dabbled in Unison. Unison seems like a great tool but I wanted my own that I could develop, test, and design (within my abilities). I wanted backups-before-overwrite/delete to be a baseline feature and I also wanted to be able to track file moves.

Plus, this was a great learning tool for python. Developing this was a lot of fun. And I am also really happy with [ldtable](https://github.com/Jwink3101/ldtable) which I developed in concert with this.

## Are files encrypted?

Using the rsync mode, the files are encrypted **in transit** via SSH. However, since this is not inherently a server-client model, the files are unencrypted at rest.

I suggest [Cryptomator](https://cryptomator.org/) for encrypted files as it is cross-platform, doesn't introduce much overhead, and is efficient. It encrypts on a file-by-file basis (with obfuscated names) so changing a file will only require syncing that file (and some ancillary data). Speedups from rsync will not be realized.

If using only macOS, encrypted disk images can also work well. If using encrypted disk images, I recommend using *sparse* disk image. Sparse images create bands (16mb if I recall correctly) so, while not file-by-file, they are more efficient but less than purely file-by-file. Regular encrypted disk images will, of course, work but *any* change will require syncing the entire thing. These are not recommended.

Also, if using the rclone remote, you can use a crypt remote. Details are in the [rclone_b2][rclone_b2.md] guide.

## I set up SSH keys. Why is it asking me for my key password each time?

If you set up SSH keys with a password, you still need to unlock the key. If you're in an interactive session (e.g. directly in macOS terminal or the same for Linux), it does this for you (usually). If you're also SSHed in, you may need to start the `ssh-agent`:

    $ ssh-agent
    $ ssh-add
    
Or, you can put the following in your `.bashrc` and call:

    $ start-ssh-agent
    
code:

```bash
start-ssh-agent () {
    if [ -z "$SSH_AUTH_SOCK" ]; then
        eval $(ssh-agent);
        ssh-add;
    else
        echo "SSH agent already running";
    fi
}
```

## Why am I getting Unicode errors? Did you mess up?

PyFiSync can handle unicode filenames without a problem. It is likely your terminal encoding.

On some `openssh` installations on macOS (anecdotally, from `brew`), there seems to be a problem with sending the wrong encoding to the remote terminal which makes it *seem* like there is a unicode error in PyFiSync. This is actually related to sending terminal encoding. See [this](https://askubuntu.com/a/874765) where they had the *opposite* problem.

The fix is to add the following to `/etc/ssh/ssh_config` or `~/.ssh/config`:

    Host *
        SendEnv LANG LC_* # Send locale to remote

## How does PyFiSync handle interruptions

The short answer is: If you run it again, everything *should* be fine.

The slightly longer answer is that all actions are (more-or-less) safe since backups are made before anything is overwritten and moves are logged.

The more detailed answer: The code does a few steps when you run it. First, it makes a file list of the current state of each side. Then, from that list and stored list of the last run, it compares all files to see what is a) new (called `prev_attributes` in the config); b) moved (called `move_attributes`); or c) deleted. This is independent of each side and does *not* determine if files are modified\*. The reason this is useful is purely to propagate moves on each side so rsync is more efficient. The determination of *what* to transfer happens *after* this independent one and is only based on comparing the mod times (if it exists on both sides)

So, to better answer this question, consider the times an interruption can happen:

* **initial listing and comparison**: No problem. No file has been touched
    * This is also when the file-transfers are determined!
* **Propgate moves, perform deletions and/or backups**: If a file is moved, when PyFiSync is rerun, even without transfer, the system will think the file was moved on both sides regardless of failure. It won't need to do anything. If it is interrupted during "deletion" (which is really just a move to a backup dir), then the file will have been moved and all is good. If it happens during a backup, then you may have extra backup copies. No problem
* **During file transfer**: If a file was successfully transferred, then when it is rerun, they will match mod-time and nothing happens. Otherwise, they will have the same outcome as before. An additional backup may be made, but that doesn't hurt.
* **After transfer, before last file listings**: The last listing is only needed to get up-to-date `inode` numbers, etc. It is stored for the next run for moves and tracking. Therefore, rerunning it will not have any moves or deletions to propagate so nothing bad will happen.

One additional case is if you didn’t realize it failed and run again later. In this case, the following would be the worst outcomes:

* A file delete will not propagate and may be restored from the other side. No real harm here!
* A file that *could* have been a move will actually end up being treated as a delete + new file. Some extra bandwidth but otherwise harmless.

While I think I thought through all of these conditions, I may have missed something. I personally run extensive backups (since, even though this backs up prior to delete or overwrite, it is a *sync* code, not *backup*). I cannot recall a time I had to dig into them because my code failed. And, except in the early days, I do not remember having to manually unwind anything. Even then, it performs safe opperations but I have since figured out the missed edge case, handled it, and wrote a test!

I hope this clears it up a bit!

\* The original plan had it determine transfers from its own previous state but I moved to comparing the two sides since it was robust to a) failure and b) deletion of the stored file lists

## Does this support Windows

No. The remote file listing is handled via an SSH call and the transfers are via rsync. It *may* work in Windows Subshell but it has not been tested.

Also, I suspect that file tracking will be less robust since there are no inode numbers. SHA1 should would to track but that adds a lot of overhead

## Why can't I sync two rclone remotes

This tool was built with rsync in mind and, in particular, syncing your local file system to a remote remote. The infrastructure was designed to be flexible for the remote only. With that said, I suspect I *could* make it work to handle two rclone remotes but I don't have the need. If there is interest, I may re-evaluate.

## Why use `ldtable` instead of something like SQLite

The simple answer is, at the time, I didn't know much SQL. And building out `ldtable` was a lot of fun. It is very useful for in-memory data queries. The more complex answer is that `ldtable` is much easier. Since I do not know all attributes until PyFiSync is instantiated, I would need a variable schema. And since I may or may not query on different combinations of attributes, I would need many table indicies.

Also, `ldtable` has proven to be sufficiently performant. Even on my 60,000 item (~200gb) photo collection. The database is well within memory constraints. I may consider SQLite in the future though.
