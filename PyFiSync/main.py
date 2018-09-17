#!/usr/bin/env python
# -*- coding: utf-8 -*-
from __future__ import division, print_function, unicode_literals
from io import open

__version__ = '20180916.0'
__author__ = 'Justin Winokur'
__license__ = 'MIT'

import os
import sys
import fnmatch
import subprocess
import time
import shutil
import datetime
import argparse
import itertools
import re
import copy
import json

# This will be fixed when it is installed
self_path = os.path.dirname(__file__)
if self_path not in sys.path:
    sys.path.append(self_path)

from . import utils
from . import PFSwalk
from . import ldtable
ldtable = ldtable.ldtable

from . import remote_interfaces

if sys.version_info[0] > 2:
    xrange = range

# walk with scandir vs listdir
if sys.version_info >= (3,5):
    walk = os.walk
    _scandir = True
else:
    try:
        from scandir import walk
        _scandir = True
    except ImportError:
        walk = os.walk
        _scandir = False

def init(path):
    """
    Intiliaze PyFiSync
    """

    path = os.path.join(os.path.abspath(path),'.PyFiSync')
    try:
        os.makedirs(path)
    except OSError:
        pass # created by logger already?

    cpath = os.path.join(path,'config')
    if os.path.exists(cpath):
        print("ERROR: Already a PyFiSync directory. Must remove '.PyFiSync' folder")
        sys.exit(2)

    with open(cpath,'w') as F:
        F.write(utils.configparser.config_example())

    txt  = '-='*30 + '\n'
    txt += '\n'
    txt += ' Initialized new PyFiSync Directory. You must first\n'
    txt += '    * Modify the config file (self-commented)\n'
    txt += '       {cpath:s}\n'.format(cpath=cpath)
    txt += '    * Perform a `reset --force` once configured\n'
    txt += '=-'*30
    log.add(txt)

def reset_tracking(backup=True,empty='reset',set_time=False):
    """ Reset the tracking"""
    global log,config,remote_interface
    remote = True
    if len(config.userhost) == 0:
        log.add('(local)  B: {:s}'.format(config.pathB))
        remote = False
    else:
        log.add('(remote) B: {:s}{:s}'.format(config.userhost,config.pathB))

    log.add('Parsing files for A')
    
    sha1A = 'sha1' in config.prev_attributesA + config.move_attributesA
    sha1B = 'sha1' in config.move_attributesB + config.prev_attributesB


    PFSwalker = PFSwalk.file_list(config.pathA,config,log,
                                  sha1=sha1A,empty=empty,
                                  use_hash_db=config.use_hash_db)
    if remote:
        # Multithread it
        loc_walk_thread = utils.ReturnThread(target=PFSwalker.files)
        loc_walk_thread.daemon = True
        loc_walk_thread.start()
        
        log.add('  Parsing files for B (remote)')
        log.prepend = '   '
        
        rem_walk_thread = utils.ReturnThread(
                            target=remote_interface.file_list,
                            args=(config.move_attributesB + config.prev_attributesB,),
                            kwargs=dict(empty=empty)
                            )
        rem_walk_thread.daemon = True
        rem_walk_thread.start()
        
        filesA = loc_walk_thread.join()
        filesB = rem_walk_thread.join()
        
        if filesB is None:
            sys.stderr.write('Error on remote call. See logged warnings\n')
            sys.exit(2)
        
        log.prepend = ''
    else:
        filesA = PFSwalker.files()
        
        log.add('  Parsing files for B (local)')
        _tmp = PFSwalk.file_list(config.pathB,config,log,sha1=sha1B,empty=empty,
                                 use_hash_db=config.use_hash_db)
        filesB = _tmp.files()
        
    filesA_old = os.path.join(config.pathA,'.PyFiSync','filesA.old')
    filesB_old = os.path.join(config.pathA,'.PyFiSync','filesB.old')

    if backup:
        try:
            now = datetime.datetime.now().strftime('.%Y-%m-%d_%H%M%S')
            shutil.move(filesA_old,filesA_old + now)
            shutil.move(filesB_old,filesB_old + now)

            txt =  'Moved:\n'
            txt += '  {:s} --> {:s}\n'.format(filesA_old,filesA_old + now)
            txt += '  {:s} --> {:s}\n'.format(filesB_old,filesB_old + now)
            log.add(txt)
        except:
            pass # Not already there

    # Dump the json (see http://stackoverflow.com/a/28032808/3633154)
    with open(filesA_old,'w',encoding='utf8') as F:
        data = json.dumps(filesA,ensure_ascii=False)
        F.write(utils.to_unicode(data))
        txt = 'saved ' + filesA_old
    with open(filesB_old,'w',encoding='utf8') as F:
        data = json.dumps(filesB,ensure_ascii=False)
        F.write(utils.to_unicode(data))
        txt = 'saved ' + filesB_old

    if set_time:
        timepath = os.path.join(config.pathA,'.PyFiSync','last_run.time')
        with open(timepath,'w') as F:
            F.write('{:0.8f}'.format(time.time()))

def main(mode):
    """
    Main sync function

    * Setup
    * Get file lists
    * Compare to old to determine moved and deleted
        * (the only one figured out modified, but this new one doesn't)
    * Determine deletions on both sides (with conflict resolution)
    * Determine moves on both sides (with conflict resolution)
        * Apply them theoretically so as to save a transfer. Everything will
          be done in order later
    * Determine transfers based on mtime on both sides ~~modified or new~~
    * Apply moves/deletions/backups for real
    * Apply transfers with rsync as the mechanism
    * Get updated lists

    """
    global log,config,remote_interface

    txt = ("""   _____       ______ _  _____                   \n"""
           """  |  __ \     |  ____(_)/ ____|                  \n"""
           """  | |__) |   _| |__   _| (___  _   _ _ __   ___  \n"""
           """  |  ___/ | | |  __| | |\___ \| | | | '_ \ / __| \n"""
           """  | |   | |_| | |    | |____) | |_| | | | | (__  \n"""
           """  |_|    \__, |_|    |_|_____/ \__, |_| |_|\___| \n"""
           """          __/ |                 __/ |            \n"""
           """         |___/                 |___/             \n""")
    
    log.line()
    log.add(txt,end='\n')
    log.line()

    
    ## Setup
    T0 = time.time()
    log.add('Start Time: ' +_unix_time(T0))
    log.add('Mode: {:s}'.format(mode))
    log.add('Version: ' + __version__)
    

    timepath = os.path.join(config.pathA,'.PyFiSync','last_run.time')
    config.last_run = float(open(timepath).read())
    log.add('Last Run: ' + _unix_time(config.last_run))

    log.add('\nPaths:')
    log.add(' (local)  A: {:s}'.format(config.pathA))

    remote = True
    if len(config.userhost) == 0:
        log.add(' (local)  B: {:s}'.format(config.pathB))
        remote = False
    else:
        log.add(' (remote) B: {:s}{:s}'.format(config.userhost,config.pathB))

    run_bash(pre=True)

    log.line()
    log.add('Paring current file lists')
    log.add('  Parsing files for A (local)')
    
    sha1A = 'sha1' in config.prev_attributesA + config.move_attributesA
    sha1B = 'sha1' in config.move_attributesB + config.prev_attributesB


    PFSwalker = PFSwalk.file_list(config.pathA,config,log,
                                  sha1=sha1A,empty='store',
                                  use_hash_db=config.use_hash_db)
    if remote:
        # Multithread it
        loc_walk_thread = utils.ReturnThread(target=PFSwalker.files)
        loc_walk_thread.daemon = True
        loc_walk_thread.start()
        
        log.add('  Parsing files for B (remote)')
        log.prepend = '   '
        
        rem_walk_thread = utils.ReturnThread(
                            target=remote_interface.file_list,
                            args=(config.move_attributesB + config.prev_attributesB,),
                            kwargs=dict(empty='store')
                            )
        rem_walk_thread.daemon = True
        rem_walk_thread.start()
        
        filesA = loc_walk_thread.join()
        filesB = rem_walk_thread.join()        
    
        if filesB is None:
            sys.stderr.write('Error on remote call. See logged warnings\n')
            sys.exit(2)
        
        log.prepend = ''
    else:
        filesA = PFSwalker.files()
        
        log.add('  Parsing files for B (local)')
        _tmp = PFSwalk.file_list(config.pathB,config,log,sha1=sha1B,empty='store',
                                 use_hash_db=config.use_hash_db)
        filesB = _tmp.files()

    ## Get file lists
    log.line()
    log.add('Loading older file list (and applying exclusions if they have changed)')

    filesA_old = os.path.join(config.pathA,'.PyFiSync','filesA.old')
    filesB_old = os.path.join(config.pathA,'.PyFiSync','filesB.old')

    with open(filesA_old,encoding='utf8') as F:
        filesA_old = json.loads(F.read())

    with open(filesB_old,encoding='utf8') as F:
        filesB_old = json.loads(F.read())

    filesA_old = PFSwalker.filter_old_list(filesA_old)
    filesB_old = PFSwalker.filter_old_list(filesB_old)


    ## Handle push and pull modes
    
    txt = None
    if mode in ['push','push_all']:
        config._pushpull=True
        txt = 'push mode: setting as no changes in B.'
        if mode == 'push_all':
             txt += ' --all mode. Set all A files as new/modified'
        # Just make the new files same as the old ones so it looks like nothing
        # has changed and the mtimes are still correct
        filesB = copy.copy(filesB_old)
       
        if mode == 'push_all':  # Make all A files modified
            config.mod_conflict = 'newer'
            now = time.time()
            for fileA in filesA:
                fileA['mtime'] = now

    if mode in ['pull','pull_all']:
        config._pushpull=True
        txt = 'pull mode: setting as no changes in A.'
        if mode == 'pull_all':
             txt += ' --all mode. Set all B files as new/modified'
        
        # Just make the new files same as the old ones so it looks like nothing
        # has changed and the mtimes are still correct
        filesA = copy.copy(filesA_old)

        if mode == 'pull_all': # Make all B files modified
            config.mod_conflict = 'newer'
            
            now = time.time()
            for fileB in filesB:
                fileB['mtime'] = now

    force_mv = mode != 'sync' 
    
    if txt is not None:
        log.line()
        log.add('Appying modifications to lists for push/pull modes')
        log.add('   ' + txt + '\n')
    
    log.line()
    log.add('Creating DB objects')
    filesA     = ldtable(filesA    )
    filesB     = ldtable(filesB    )
    filesA_old = ldtable(filesA_old)
    filesB_old = ldtable(filesB_old)

    ## Compare to old to determine new, modified, deleted
    log.line()
    log.add('Using old file lists to determine moves and deletions\n')
    log.prepend = '  '
    
    file_track(filesA_old,filesA,config.prev_attributesA,config.move_attributesA)
    file_track(filesB_old,filesB,config.prev_attributesB,config.move_attributesB)
    
    ## Determine deletions on both sides (with conflict resolution)
    ## Determine moves on both sides (with conflict resolution)
    # Resolve Conflicts
    move_queueA,move_queueB = compare_queue_moves(filesA,filesB,filesA_old,filesB_old)
    
    log.prepend = ''
    log.space = 0
    log.line()
    log.add('Apply file moves theoretically. Actual moves to be processed later')


    ## Apply them theoretically so as to save a transfer. Everything will
    #  be done in order later
    apply_move_queues_theoretical(filesA,move_queueA,AB='A',force=force_mv)
    apply_move_queues_theoretical(filesB,move_queueB,AB='B',force=force_mv)


    ## Determine transfers based on modified or new
    log.line()
    log.space = 0
    log.add('Determining, resolving conflicts, and queueing file transfers\nbased on modification times\n')
    log.space = 2
    
    action_queueA,action_queueB,tqA2B,tqB2A = determine_file_transfers(
        filesA,filesB)
    
    ## Apply moves/deletions/backups for real
    log.space = 0
    log.line()
    log.add('Applying queues')
    log.space = 2
    
    apply_action_queue(config.pathA,move_queueA + action_queueA,force=force_mv)

    if remote:
        remote_interface.apply_queue(move_queueB + action_queueB,force=force_mv)
    else:
        apply_action_queue(config.pathB,move_queueB + action_queueB,force=force_mv)

    # Clear anything that came up for push/pull modes
    if mode in ['push','push_all']:
        tqB2A = []
    if mode in ['pull','pull_all']:
        tqA2B = []
        
    # We will use the rsync (via the ssh_rsync) interface. 
    if not remote:
        config.persistant = False # Make sure this is off
        remote_interface = remote_interfaces.ssh_rsync(config,log)
    
    log.space = 0;log.prepend = ''
    log.line()
    log.add('Final Transfer')
    log.space=2
    remote_interface.transfer(tqA2B,tqB2A)
    
    ## Get updated lists
    log.space = 0
    log.line()
    log.add('Retrieving and saving updated file lists')
    log.space = 2
    reset_tracking(backup=False,empty='remove',set_time=True)

    run_bash(pre=False)

    log.space = 0
    log.add_close()

def file_track(files_old,files_new,prev_attributes,move_attributes):

    # Add certain fields to the DBs
    files_new.add_attribute('newmod',False)
    files_new.add_attribute('new',False)
    files_new.add_attribute('untouched',False)
    files_new.add_attribute('moved',False)
    files_new.add_attribute('prev_path',None)

    files_old.add_attribute('deleted',True)

    # Main loop
    for file in files_new.items():

        # is it untouched
        query_dict = {a:file[a] for a in prev_attributes + ['mtime']}
        if query_dict in files_old:
            file['prev_path'] = file['path']
            file['untouched'] = True

            files_old.query_one(query_dict)['deleted'] = False
            continue

        # is it the same exact file but modified?
        # We do this as a separate check from the mtime of a moved file to
        # account for cases when the file is marked as new via some attribute
        # but was just modified (e.g. size,sha1)
        query_dict = {a:file[a] for a in prev_attributes}
        if query_dict in files_old:
            # The mtime MUST have changed since it didn't match the past check
            file['prev_path'] = file['path']
            file['newmod'] = True
            files_old.query_one(query_dict)['deleted'] = False
            continue

        # has it been moved?
        query_dict = {a:file[a] for a in move_attributes}
        if query_dict in files_old:
            # file was moved
            file_old = files_old.query_one(query_dict)

            file['prev_path'] = file_old['path']
            file['moved'] = True
            file_old['deleted'] = False

            # Was it also modified?
            if not file_old['mtime'] == file['mtime']:
                file['newmod'] = True
            continue

        # It must be new
        # Note that the paths may remain the same, but a file could have been
        # moved/deleted and a new one created there
        file['newmod'] = True
        file['new'] = True

    # Reindex the DBs
    files_old.reindex()
    files_new.reindex()


def compare_queue_moves(filesA,filesB,filesA_old,filesB_old):
    """
    Compare the moves and generate a move queue

    action queues look like a list of dictionaries:
        {'backup':[file_path]}  # Make a copy to the backup
        {'move': [src,dest]}    # Move the file
        {'delete': [file_path]} # Move the file into the backup. Essentially a backup

        queues are always performed in the following order:
            * move
            * backup -- if a path is moved it can later be backed up
            * delete

    transfer queue
    """

    global log,tqA2B,tqB2A
    tqA2B = []
    tqB2A = []

    queueA = []
    queueB = []

    log.space = 0
    log.add('Comparing, resolving, and queuing file DELETIONS.\n')
    log.space = 2

    txt  = 'WARNING: File deleted on {AB:s} but moved there, new, or \n'
    txt += '         or modified on {BA:s}. Ignore delete and add to\n'
    txt += '         transfers\n'
    txt += '           File: {path:s}'

    # Process deletions on A.
    for fileA_old in filesA_old.query(deleted=True):
        path = fileA_old['path']

        fileB = filesB.query_one(path=path) # new
        if fileB is None:
            continue # Already deleted or moved

        if fileB['newmod'] or fileB['moved'] or fileB['new']:
            log.add(txt.format(path=path,AB='A',BA='B'))
            tqB2A.append(fileB['path'])
            continue

        # Some programs write a new file on save
        if config.check_new_on_delete and ({'path':path,'new':True} in filesA):
            continue

        # Delete file B and apply it before comparing moves later
        queueB.append({'delete':path} )
        filesB.remove(path=path)

    # Process deletions on B
    for fileB_old in filesB_old.query(deleted=True):
        path = fileB_old['path']

        fileA = filesA.query_one(path=path) # new
        if fileA is None:
            continue # Already deleted or moved

        if fileA['newmod'] or fileA['moved'] or fileA['new']:
            log.add(txt.format(path=path,AB='B',BA='A'))
            tqB2A.append(fileA['path'])
            continue

        # Some programs write a new file on save
        if config.check_new_on_delete and ({'path':path,'new':True} in filesB):
            continue

        # Delete file B and apply it before comparing moves later
        queueA.append({'delete':path} )
        filesA.remove(path=path)

    # We loop through all possible prev_paths and handle it that way
    # Every file that is marked as moved also has a prev path
    prev_paths =  set(fileA['prev_path'] for fileA in filesA.query(moved=True))
    prev_paths.update(fileB['prev_path'] for fileB in filesB.query(moved=True))

    log.space = 0
    log.add('\nComparing, resolving, and queueuing file MOVES')
    log.space = 2

    for prev_path in prev_paths:
        fileA = filesA.query_one(prev_path=prev_path)
        fileB = filesB.query_one(prev_path=prev_path)

        # Check if one was deleted. Both can't be.
        # If deleted, make sure to set it as mod
        # set it as new to make sure it gets transfered
        txt =  'WARNING: file moved on {AB:s} not found on {BA:s}\n'
        txt += '           {AB:s}: {prev_path:s} --> {path:s}\n'
        txt += "         It may have been deleted or {AB:s}'s is new"
        if fileA is None:
            log.add(txt.format(AB='B',BA='A',**fileB))
            filesB.update({'new':True},prev_path=prev_path)
            continue
        if fileB is None:
            log.add(txt.format(AB='A',BA='B',**fileA))
            filesA.update({'new':True},prev_path=prev_path)
            continue

        if fileA['path'] == fileB['path']: # Both moved to the same path
            continue

        if fileA['moved'] and fileB['moved']:
            txt  = 'CONFLICT: Same file moved on A and B\n'
            txt += '           original: {prev_path:s}\n'
            txt += '               on A: {A:s}\n'
            txt += '               on B: {B:s}\n'
            txt += '          Resolve to {AB:s} as per config'
            txt = txt.format(AB=config.move_conflict,A=fileA['path'],B=fileB['path'],**fileA)
            # Reset one to False and change prev_path to the other
            if config.move_conflict == 'A':
                queueB.append( {'move':[fileB['path'],fileA['path'] ]})
                log.add(txt)
            else: # config.move_conflict == 'B':
                queueA.append( {'move':[fileA['path'],fileB['path'] ]})
                log.add(txt)
            continue

        # Apply moves. Only one can be true after the above
        if fileA['moved']:
            queueB.append( {'move':[prev_path,fileA['path'] ]})
        if fileB['moved']:
            queueA.append( {'move':[prev_path,fileB['path'] ]})

    # Note: we do not reindex since the only changes are the moved status
    # and we don't care about them anymore
    return queueA,queueB

def apply_move_queues_theoretical(files,queue,AB='AB',force=False,):
    """
    Apply the move queues to the file lists as if they were performed
    """
    global log

    txt  = 'CONFLICT: Move scheduled in {AB:s}\n'
    txt += '           {src:s} --> {dest:s}\n'
    txt += '          but destination file already exists. Will not apply\n'
    # Ignore ^^^. It will be printed later when the moves actually take place

    for action_dict in queue:
        action,path = list(action_dict.items())[0]
        if action == 'move':
            src,dest = path

            if ( {'path':dest} not in files ) or force:
                files.update({'path':dest},{'path':src})
                continue # Moved
            # If you can't do the move, you need to update BOTH files that there is a conflict of sorts
            files.update({'newmod':True},{'path':src})
            files.update({'newmod':True},{'path':dest})
        if action == 'delete':
            pass # These were done above
        # Ignore backups


def determine_file_transfers(filesA,filesB):
    """
    Determine transfers

    Note: we only look at new or modified files as per tracking

    Use the push or pull (and/or reset) modes to reset these lists
    """
    global log

    txt1  = ('CONFLICT: File modified on both sides\n'
             '            {path:s}\n'
             '              A: {mtimeA:s}\n'
             '              B: {mtimeB:s}\n'
             "          resolving with '{res:s}' as per config\n")

    txt2  = ('WARNING: File deleted on {AB} but modified on {BA}. Transfer\n'
             '          File: {path:s}\n')


    action_queueA = [] # Actions to be performed ON A
    action_queueB = [] # "  " ON B

    global tqA2B,tqB2A

    paths =  set(fileA['path'] for fileA in filesA.items())
    paths.update(fileB['path'] for fileB in filesB.items())
    for path in paths:

        fileA = filesA.query_one(path=path)
        fileB = filesB.query_one(path=path)

        # Recall that deleted files are already handled

        # Check if the other path doesn't exist. Means file was new or
        # deleted on one and modified on the other. Transfer to missing side
        if fileA is None:
            if not fileB['new']: # A was deleted
                log.add(txt2.format(AB='A',BA='B',path=path))
            tqB2A.append(path)
            continue
        if fileB is None:
            if not fileA['new']: # B was deleted
                log.add(txt2.format(AB='B',BA='A',path=path))
            tqA2B.append(path)
            continue
            
        mtimeA = _unix_time(fileA['mtime'])
        mtimeB = _unix_time(fileB['mtime'])

        #########################
        
        if abs(fileA['mtime'] - fileB['mtime']) <= config.mod_resolution:
            continue # No change on either or within modify resolution
        if fileA['mtime'] <= config.last_run and fileB['mtime'] >= config.last_run:
            # Modified on B
            tqB2A.append(path)
            action_queueA.append( {'backup':path} )
            continue
        if fileA['mtime'] >= config.last_run and fileB['mtime'] <= config.last_run:
            # Modified on A
            tqA2B.append(path)
            action_queueB.append( {'backup':path} )
            continue

        # If they are both modified before the last run, then something strange
        # happened and we want to proceed as a conflict


        ###################
        
        res = config.mod_conflict
        log.add(txt1.format(path=path,mtimeA=mtimeA,mtimeB=mtimeB,res=res))

        if res == 'A':
            tqA2B.append(path)
            action_queueB.append( {'backup':path} )
        if res == 'B':
            tqB2A.append(path)
            action_queueA.append( {'backup':path} )
        if res == 'newer':
            if fileA['mtime']>=fileB['mtime']:
                tqA2B.append(path)
                action_queueB.append( {'backup':path} )
            else:
                tqB2A.append(path)
                action_queueA.append( {'backup':path} )
        else:
            action_queueA.append({'move':[path,path + '.' + config.nameA]})
            tqA2B.append(path + '.' + config.nameA)

            action_queueB.append({'move':[path,path + '.' + config.nameB]})
            tqB2A.append(path + '.' + config.nameB)

    # Unset all backup options
    if not config.backup:
        action_queueA = [a for a in action_queueA if 'backup' not in a]
        action_queueB = [b for b in action_queueB if 'backup' not in b]

    return action_queueA,action_queueB,tqA2B,tqB2A

def apply_action_queue(dirpath,queue,force=False):
    """
    * queue is the action queue that takes the following form
        * {'backup':[file_path]}  # Make a copy to the backup
        * {'move': [src,dest]}    # Move the file
        * {'delete': [file_path]} # Move the file into the backup. Essentially a backup
    * Force tells it to allow a file to be moved into another
    
    Notes:
        * If a file is to be moved into another, it should not work unless 
          force is set. If force it set, it should backup the file as per
          config.backup
        * Delete should backup first if set config.backup == True
        * Backup should NOT happen if config.backup == False
        * If a backup of the file already exists, it should append an integer
          starting at 0
    """

    log.space=2
    log.add('Applying queues on: {:s}'.format(dirpath))
    log.space = 4
    
    txt  = 'CONFLICT: Move scheduled over another\n'
    txt += '           {src:s} --> {dest:s}\n'
    txt += '          {result:s}'


    backup_path = os.path.join(dirpath,'.PyFiSync','backups',
        datetime.datetime.now().strftime('%Y-%m-%d_%H%M%S'))

    if config.backup:
        try:
            os.makedirs(backup_path)
        except OSError:
            pass

    for action_dict in queue:
        action,path = list(action_dict.items())[0]
        if action == 'move':
            src = os.path.join(dirpath,path[0])
            dest = os.path.join(dirpath,path[1])
            dest_dir = os.path.split(dest)[0]
            
            if os.path.exists(dest):
                if force:
                    if config.backup:
                        log.add(txt.format(path=dirpath,src=path[0],dest=path[1],
                            result='Backing up and applying'))

                        dest_old = os.path.join(backup_path,path[1])
                        dest_dir_old = os.path.split(dest_old)[0]
                        try:
                            os.makedirs(dest_dir_old)
                        except OSError:
                            pass
                        shutil.move(dest,dest_old)
                    else:
                        log.add(txt.format(path=dirpath,src=path[0],dest=path[1],
                            result='Applying (w/o backup)'))

                else:
                    log.add(txt.format(path=dirpath,src=path[0],dest=path[1],result='Skipping'))
                    continue
            try:
                os.makedirs(dest_dir)
            except OSError:
                pass

            shutil.move(src,dest)
            log.add('move: ' + utils.move_txt(path[0],path[1]))

        if action in ['backup','delete']:
            src = os.path.join(dirpath,path)
            
            dest = os.path.join(backup_path,path)
            dest_dir = os.path.split(dest)[0]

            try:
                os.makedirs(dest_dir)
            except OSError:
                pass

            # Make sure the backup doesn't already exist from a prev action
            i = 0
            while os.path.exists(dest):
                dest = os.path.join(backup_path,path) + '.' + str(i)
                i += 1

            if not os.path.exists(src) and getattr(config,'_pushpull',True):
                # This is an edge case in push/pull modes where a file may have
                # been moved but is not tracked. Do not do anything
                log.add("WARNING: couldn't find {src} for action in push/pull mode".format(src=src))
            elif action == 'backup' and config.backup:
                shutil.copy2(src,dest)
                log.add('backup: ' + path)
            elif action=='delete' and config.backup:
                shutil.move(src,dest)
                log.add('delete (w/ backup): ' + path)
            elif action=='delete' and not config.backup:
                os.remove(src)
                log.add('delete (w/o backup): ' + path)
            else:
                pass # Do nothing for now
    
    # Remove the backup directory if it was never used
    try:
        os.rmdir(backup_path)
    except OSError: # Will error out if not empty or does not exists
        if config.backup:
            log.add('\nBackups saved in: {}'.format(backup_path))

def search_up_PyFiSync(path):
    path = os.path.abspath(path) # nothing relative
    
    # Don't allow above the user directory
    if path == '/':
        print('ERROR: Not in a PyFiSync directory. Did you run `init`?')
        sys.exit(2) 
    
    if path.endswith('/'):       # Strip trailing "/". Shouldn't be there though
        path = path[:-1] 
    
    # Make sure the path is a folder
    if not os.path.isdir(path):
        print("ERROR: Must specify a *directory* path or none for '.'")
        sys.exit(2)
    
    # Check it
    if any(os.path.exists(os.path.join(path,'.PyFiSync','config'+ext)) for ext in ['','.py']):
        return path
    else:
        path = os.path.split(path)[0]
        return search_up_PyFiSync(path)

def run_bash(pre):
    """ Run the pre and post bash scripts """
    cmd = 'cd {} # Automatically set by PyFiSync\n\n'.format(config.pathA)
    if pre:
        if len(config.pre_sync_bash.strip()) == 0:
            return 
        cmd += config.pre_sync_bash.strip()
    else:
        if len(config.post_sync_bash.strip()) == 0:
            return 
        cmd += config.post_sync_bash.strip()        
    
    
    log.add('Calling pre/post_sync_bash scripts ')
    log.add('\n'.join('   $ {}'.format(c) for c in cmd.split('\n')))
    
    proc = subprocess.Popen(cmd,shell=True,stderr=subprocess.PIPE,stdout=subprocess.PIPE)
    out,err = proc.communicate()
    
    out = utils.to_unicode(out)
    err = utils.to_unicode(err)
    
    log.add('STDOUT:')
    log.add('\n'.join('   > {}'.format(c.rstrip()) for c in out.split('\n')))
    log.add('STDERR:')
    log.add('\n'.join('   > {}'.format(c.rstrip()) for c in err.split('\n')))
    


def _unix_time(val):
    return datetime.datetime.fromtimestamp(float(val)).strftime('%Y-%m-%d %H:%M:%S')



usage="""
PyFiSync -- Python based file synchronizer with inteligent move tracking and
              conflict resolution

Usage:

    PyFiSync MODE <options> PATH

Or, if *just* called as: PyFiSync , it will assume `PyFiSync sync .`


Modes and Options
    sync -- Perform sync on the path

        -h,--help   : Print this help
        --no-backup : Override config and do not back up files
        -s,--silent : Do not print the log to the screen

    push/pull -- push or pull all changes with no conflict resolution

        --all       : Push every file even if unmodified. Note, will cause
                      backups of every file. Consider --no-backup
                      This is useful if reset files.
        -h,--help   : Print this help
        --no-backup : Override config and do not back up files
        -s,--silent : Do not print the log to the screen

    init -- Initialize PyFiSync in the specified directory

    reset -- Completely reset file tracking. No changes pre-reset will be
             propgrated until you do a `push/pull --all`

        -h,--help   : Print this help
        --force     : Do not prompt for confirmation

        Note that if the files already exist, they will be backed up

    help -- Print this help
"""

desc = """\
Python (+ rsync) based intelligent file sync with automatic backups and file move/delete tracking.
"""
epi = ""

def cli(argv=None):
    if argv is None:
        argv = sys.argv[1:]
    global log,config,remote_interface
    
    # Set up main parser and subparsers. Then, (hackily) generate a list
    # of modes. If the first argument is not a mode, then insert "sync". The
    # edge case of this is if the directory is named one of the modes. Oh well!
    
    parser_main = argparse.ArgumentParser(\
        description=desc,
        epilog=epi,
        formatter_class=utils.RawSortingHelpFormatter)
        
    parser_main.add_argument('-v', '--version', action='version', 
        version='%(prog)s-' + __version__,help='Display version and exit')
    
    # Parent parser for ALL modes/subparsers
    parser_all_opts = argparse.ArgumentParser(add_help=False) # Notice this is NOT a subparser of parser_main
    parser_all_opts.add_argument('path',default='.',nargs='?',
        help="['%(default)s'] path to the PyFiSync directory")
    
    subparsers = parser_main.add_subparsers(dest='mode',title='modes',help="[sync]. Enter `{mode} -h` for individual help")
    
    ## Sync, Push,Pull
    # Options for all
    parser_syncops = argparse.ArgumentParser(add_help=False) # Notice this is NOT a subparser of parser_main
    
    parser_syncops.add_argument('-s','--silent',
        action='store_true',help='Do not print the log to screen')
    parser_syncops.add_argument('--no-backup',
        action='store_true',
        help='Override config and do not back up files')
    
    # options for push and pull
    parser_pushpull = argparse.ArgumentParser(add_help=False) # Notice this is NOT a subparser of parser_main
    parser_pushpull.add_argument('--all',
        action='store_true',
        help=('Push/Pull every file even if unmodified. Note, will cause '
              'backups of every file. Consider --no-backup. '
              'This is useful if reset files.'))
    
    # Make the parser with the right combination of options
    parser_sync = subparsers.add_parser('sync',
        help='Synchronize to the server',
        parents=[parser_syncops,parser_all_opts],
        formatter_class=utils.RawSortingHelpFormatter)
    
    parser_push = subparsers.add_parser('push',
        help='Push to the server',
        parents=[parser_pushpull,parser_syncops,parser_all_opts],
        formatter_class=utils.RawSortingHelpFormatter)
    
    parser_pull = subparsers.add_parser('pull',
        help='Pull from the server',
        parents=[parser_syncops,parser_pushpull,parser_all_opts],
        formatter_class=utils.RawSortingHelpFormatter)
    
    ## Init
    parser_init = subparsers.add_parser('init',
        help='Initialize in the specified directory',
        parents=[parser_all_opts],
        formatter_class=utils.RawSortingHelpFormatter)
    
    ## Reset
    parser_reset = subparsers.add_parser('reset',
        help=('Completely reset file tracking. No changes pre-reset '
              'will be propgrated until you do a `push/pull --all`. '
              'Existing database files will be backed up'),
        parents=[parser_all_opts],
        formatter_class=utils.RawSortingHelpFormatter)
    
    parser_reset.add_argument('--force',action='store_true',help='Do not prompt for confirmation')
    
    # get a list of the modes. Inspired by https://stackoverflow.com/a/20096044/3633154
    modes = []
    for _s in parser_main._actions:
        if not isinstance(_s, argparse._SubParsersAction):
            continue
        for choice in _s.choices.items():
            modes.append(choice[0])
    
    main_actions = list(itertools.chain.from_iterable(a.option_strings for a in parser_main._actions))
    
    if len(argv) == 0:
        argv = ['sync']
    if argv[0].lower() == 'help': # add help mode
        argv[0] = '--help'
    if argv[0] not in modes + main_actions + ['_api']:
        argv.insert(0,'sync')
    
    if argv[0] == '_api':
        remote_interfaces.ssh_rsync.cli(argv[1:])
        sys.exit()
    
    args = parser_main.parse_args(argv)

    #############

    if args.mode == 'init':
        log = utils.logger(path=args.path,silent=False)
        init(args.path)

    elif args.mode in ['push','pull','sync']:
        path = search_up_PyFiSync(args.path)
        
        config = utils.configparser(sync_dir=path)
        log = utils.logger(path=path,silent=False)
        
        if len(config.userhost) != 0:
            remote_interface = remote_interfaces.ssh_rsync(config,log)
        else:
            remote_interface = None
        
        if args.mode != 'sync' and args.all:
            args.mode += '_all'
        
        if args.no_backup:
            config.backup = False
        
        if args.silent:
            log.silent = True
        
        main(args.mode)
        
        if remote_interface is not None and hasattr(remote_interface,'close')\
                and hasattr(remote_interface.close,'__call__'):
            remote_interface.close()

    elif args.mode == 'reset':
        path = search_up_PyFiSync(args.path)
        
        config = utils.configparser(sync_dir=path)
        log = utils.logger(path=path,silent=False)

        if len(config.userhost) != 0:
            remote_interface = remote_interfaces.ssh_rsync(config,log)
        else:
            remote_interface = None
        
        if not args.force:
            print('Are you sure you want to reset? (Y/[N]): ')
            if not raw_input().lower().startswith('y'):
               sys.exit()
        
        reset_tracking(set_time=True,empty='reset')
        
        if remote_interface is not None and hasattr(remote_interface,'close')\
                and hasattr(remote_interface.close,'__call__'):
            remote_interface.close()
        


if __name__ == '__main__':
    argv = sys.argv[1:] # Argument besides function name
    cli(argv)
else:
    log = utils.logger(path=None,silent=False)












