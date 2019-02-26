(added as they come up)

## How does PyFiSync handle interruptions

I know this sounds odd, but I wrote this about 1.5 years ago so it took me a little bit of time job my memory about how it works.

The short answer is: If you run it again, everything should be fine.

The slightly longer answer is that if I was wrong with what I just said, everything is *still* fine since, by default, nothing is ever transferred until a backup is made.

Ok, more detailed answer (and this is me also thinking out loud about it). The code does a few steps when you run it. First, it makes a file list of the current state of each side. Then, from that list and stored list of the last run, it compares all files to see what is a) new (called `prev_attributes` in the config) or b) moved (called `move_attributes`). This is independent of each file system and does *not* determine if files are modified^*. The reason this is useful is purely to propagate moves on each side so rsync is more efficient. The determination of *what* to transfer happens *after* this independent one and is only based on comparing the mod times (if it exists on both sides)

So, to better answer this question, consider the times an interruption can happen:

* **initial listing and comparison**: No problem. No file has been touched
    * This is also when the file-transfers are determined!
* **Propgate moves, perform deletions and/or backups**: If a file is moved, when it is rerun, even without transfer, the system will think the file was moved on both sides regardless of failure. It won't need to do anything. If it is interrupted during "deletion" (which is really just a move to a backup dir), then the file will have been moved and all is good. If it happens during a backup, then you may have extra backup copies. No problem
* **During file transfer**: If a file was successfully transferred, then when it is rerun, they will match mod-time and nothing happens. Otherwise, they will have the same outcome as before. An additional backup may be made, but that doesn't hurt.
* **After transfer, before last file listings**: The last listing is only needed to get up-to-date `inode` numbers, etc. It is stored for the next run for moves and tracking. Therefore, rerunning it will not have any moves or deletions to propagate so nothing bad will happen.

One additional case is if you didn’t realize it failed and run again later. In this case, the following would be the worst outcomes:

* A file delete will not propagate and may be restored from the other side. No real harm here!
* A file that *could* have been a move will actually end up being treated as a delete + new file. Some extra bandwidth but otherwise harmless.

While I think I thought through all of these conditions, I may have missed something. I personally run extensive backups (since, even though this backs up prior to delete or overwrite, it is a *sync* code, not *backup*). I cannot recall a time I had to dig into them because my code failed. And, except in the early days, I do not remember having to manually unwind anything. Even then, it performs safe opperations but I have since figured out the missed edge case, handled it, and wrote a test!

I hope this clears it up a bit!

^* The original plan had it determine transfers from its own previous state but I moved to comparing the two sides since it was robust to a) failure and b) deletion of the stored file lists

## Are files encrypted?

Using the default (and currently only) mode, the files are encrypted **in transit** via SSH. However, since this is not inherently a server-client model, the files are unencrypted at rest.

I suggest [Cryptomator](https://cryptomator.org/) for encrypted files as it is cross-platform and doesn't introduce much overhead and is efficient. It encrypts on a file-by-file basis (with obfuscated names) so changing a file will only require syncing that file (and some ancillary data). Speedups from rsync will not be realized.

If using only macOS, encrypted disk images can also work well. If using encrypted disk images, I recommend using *sparse* disk image. Sparse images create bands (16mb if I recall correctly) so, while not file-by-file, they are more efficient but less than purely file-by-file. Regular encrypted disk images will, of course, work but *any* change will require syncing the entire thing. These are not recommended.


