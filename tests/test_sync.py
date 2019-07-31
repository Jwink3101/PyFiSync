#!/usr/bin/env python
# -*- coding: utf-8 -*-
from __future__ import division, print_function, unicode_literals, absolute_import

try:
    from . import testutils
except (ValueError,ImportError):
    import testutils
testutils.add_module() # make sure the test are importing the NON-installed version

import PyFiSync

import os
import sys
import shutil
import itertools
from glob import glob
import re
from pprint import pprint

import pytest

## Specify whether to test remotely or locally...or both
#remotes = [False]   # Just test locally
#remotes = ['python2','python3']
remotes = [False,'python2','python3']
# remotes = ['python2']

rclone = ['rclone'] 


@pytest.mark.parametrize("remote", remotes+rclone)
def test_nothing(remote): # This used to be test 01
    """ Nothing. Add SHA1 to test that code"""
    
    testpath = os.path.join(os.path.abspath(os.path.split(__file__)[0]),
            'test_dirs','nothing')
    try:
        shutil.rmtree(testpath)
    except:
        pass
    os.makedirs(testpath)
    testutil = testutils.Testutils(testpath=testpath)


    # Init
    testutil.write('A/file1',text='test01f1')

    # Randomize Mod times
    testutil.modtime_all()

    # Start it
    config = testutil.get_config(remote=remote)
    config.move_attributesA += ['sha1']
#     config.persistant = True
    testutil.init(config)

    # Apply actions
    #NONE

    # Sync
    testutil.run(config)

    # Finally
    assert len(testutil.compare_tree()) == 0


@pytest.mark.parametrize("remote", remotes+rclone)
def test_mod_files(remote): # old test 02
    """ Different Files are modified both in A and B """
    
    testpath = os.path.join(os.path.abspath(os.path.split(__file__)[0]),
            'test_dirs','mod_files')
    try:
        shutil.rmtree(testpath)
    except:
        pass
    os.makedirs(testpath)
    testutil = testutils.Testutils(testpath=testpath)


    # Init
    testutil.write('A/file1',text='test02.a')
    testutil.write('A/file2',text='test02.b')

    # Randomize Mod times
    testutil.modtime_all()

    # Start it
    config = testutil.get_config(remote=remote)
    testutil.init(config)

    # Apply actions
    testutil.write('A/file1',text='test02.a',mode='a') # append it
    testutil.write('B/file2',text='test02.b',mode='a')

    # Sync
    testutil.run(config)

    # Check it -- Only need to check A
    assert testutil.read('A/file1') == 'test02.a\ntest02.a','file1'
    assert testutil.read('A/file2') == 'test02.b\ntest02.b','file2'

    # Finally
    assert len(testutil.compare_tree()) == 0


mod_conflicts = ['A','B','newer','both','newer_tag']
@pytest.mark.parametrize("remote,mod_conflict", list(itertools.product(remotes + rclone,mod_conflicts)))
def test_simple_conflict(remote,mod_conflict): 
    """ Same Files are modified both in A and B """
    
    if mod_conflict is None:
        for mc in mod_conflicts:
            test_simple_conflict(remote,mc)
        return
    
    testpath = os.path.join(os.path.abspath(os.path.split(__file__)[0]),
            'test_dirs','simple_conflict')
    try:
        shutil.rmtree(testpath)
    except:
        pass
    os.makedirs(testpath)
    testutil = testutils.Testutils(testpath=testpath)


    # Init
    testutil.write('A/file1',text='test')

    # Randomize Mod times
    testutil.modtime_all()

    # Start it
    config = testutil.get_config(remote=remote)
    config.mod_conflict = mod_conflict
    testutil.init(config)

    # Apply actions
    testutil.write('A/file1',text='A',mode='a',time_adj=+100) # append it
    testutil.write('B/file1',text='B',mode='a',time_adj=+500) # append it

    # Sync
    testutil.run(config)
    
    assert testutil.compare_tree() == []
    files = set(os.path.basename(p) for p in testutil.tree(os.path.join(testpath,'A')))
    
    if mod_conflict == 'A':
        assert files == set(['file1'])
        assert testutil.read('A/file1') == 'test\nA'
    if mod_conflict in ['B' or 'newer'] :
        assert files == set(['file1'])
        assert testutil.read('A/file1') == 'test\nB'
    if mod_conflict == 'newer_tag':
        assert files == set(['file1','file1.machineA'])
        assert testutil.read('A/file1') == 'test\nB'
    if mod_conflict == 'both':    
        assert files == set([u'file1.machineA', u'file1.machineB'])

mod_conflicts = ['both','newer_tag']
@pytest.mark.parametrize("remote,mod_conflict", list(itertools.product(remotes + rclone,mod_conflicts)))
def test_multiple_conflict_tags(remote,mod_conflict): 
    """ 
    Test when a conflict is not resolved and there may be
    multiple flags
    """
    
    testpath = os.path.join(os.path.abspath(os.path.split(__file__)[0]),
            'test_dirs','test_multiple_conflict_tags')
    try:
        shutil.rmtree(testpath)
    except:
        pass
    os.makedirs(testpath)
    testutil = testutils.Testutils(testpath=testpath)


    # Init
    testutil.write('A/file1',text='ONE')
    testutil.write('A/file2',text='TWO')

    # Randomize Mod times
    testutil.modtime_all()

    # Start it
    config = testutil.get_config(remote=remote)
    config.mod_conflict = mod_conflict
    testutil.init(config)

    # Apply actions
    testutil.write('A/file1',text='A1',mode='a',time_adj=5)
    testutil.write('B/file1',text='B1',mode='a',time_adj=0) 
    
    testutil.write('A/file2',text='A1',mode='a',time_adj=0)
    testutil.write('B/file2',text='B1',mode='a',time_adj=5) 
    
    # Sync
    testutil.run(config)
    
    # Do the mods again
    testutil.write('A/file1',text='A2',mode='a',time_adj=5)
    testutil.write('B/file1',text='B2',mode='a',time_adj=0) 
    
    testutil.write('A/file2',text='A2',mode='a',time_adj=0)
    testutil.write('B/file2',text='B2',mode='a',time_adj=5) 
    
    testutil.run(config)

    # tests
    assert len(testutil.compare_tree()) == 0 # All the same so I only need to test one side
    
    if mod_conflict == 'newer_tag':
        testdict = {
            'file1': 'ONE\nA1\nA2',        # Updated on A both times
            'file1.machineB': 'ONE\nB1',   # Updated on B once
            'file1.machineB.1': 'ONE\nA1\nB2', # Updated on A then B
    
            'file2': 'TWO\nB1\nB2',        # Updated on B both times
            'file2.machineA': 'TWO\nA1',   # Updated on A once
            'file2.machineA.1': 'TWO\nB1\nA2', # Updated on B then A
        }  
        
    elif mod_conflict == 'both':
        testdict = {
            'file1.machineA': 'ONE\nA1', # The appended 2's make a new file
            'file1.machineA.1': 'A2',
            'file1.machineB': 'ONE\nB1',
            'file1.machineB.1': 'B2',
            'file2.machineA': 'TWO\nA1',
            'file2.machineA.1': 'A2',
            'file2.machineB': 'TWO\nB1',
            'file2.machineB.1': 'B2',
        }
    else: # No need to test 'A','B','newer' since they do not tag anything
        assert False # Shouldn't be testing this
        
    assert len(testutil.tree(os.path.join(testutil.testpath,'A'))) == len(testdict)
    for filename,text in testdict.items():
        assert testutil.read('A/' + filename) == text
        

    

# Include rclone in this since it will track with the sha-1 and none are modified
@pytest.mark.parametrize("remote", remotes + rclone)
def test_move_files(remote): # old test 03
    """ Different Files are modified both in A and B """
    testpath = os.path.join(os.path.abspath(os.path.split(__file__)[0]),
            'test_dirs','move_files')
    try:
        shutil.rmtree(testpath)
    except:
        pass
    os.makedirs(testpath)
    testutil = testutils.Testutils(testpath=testpath)


    # Init
    testutil.write('A/moveA',text='moveA')
    testutil.write('A/the/very/deep/folder/path/file',text='file')
    testutil.write('A/moveB',text='moveB')

    # Randomize Mod times
    testutil.modtime_all()

    # Start it
    config = testutil.get_config(remote=remote)
    testutil.init(config)

    # Apply actions
    testutil.move('A/moveA','A/moveA_moved')
    testutil.move('B/moveB','B/ff/moveB_moved')
    testutil.move('B/the/very/deep/folder/path/file','B/the/very/deep/folder/path/filename')

    # Sync
    testutil.run(config)

    # Check it -- Only need to check A
    assert testutil.exists('A/moveA_moved')
    assert not testutil.exists('A/moveA')
    
    assert testutil.exists('B/ff/moveB_moved')
    assert not testutil.exists('B/moveB')

    assert testutil.exists('B/the/very/deep/folder/path/filename')
    assert not testutil.exists('B/the/very/deep/folder/path/file')

    # Make sure it actually did the move and not just transfer
    log_path = glob(os.path.join(testpath,'A','.PyFiSync','logs','20*.log'))
    log_path.sort()
    log_txt = open(log_path[-1]).read()
    assert "No A >>> B transfers" in log_txt
    assert "No A <<< B transfers" in log_txt
    assert "move: moveB --> ff/moveB_moved" in log_txt
    assert "move: the/very/deep/folder/path/{file --> filename}" in log_txt # new move naming
    assert "move: moveA --> moveA_moved" in log_txt

    # Finally
    assert len(testutil.compare_tree()) == 0

    

@pytest.mark.parametrize("remote", remotes + rclone)
def test_move_same_file(remote): # old test 04
    """ File moved by both A and B to the same location """
    testpath = os.path.join(os.path.abspath(os.path.split(__file__)[0]),
            'test_dirs','move_same_file')
    try:
        shutil.rmtree(testpath)
    except:
        pass
    os.makedirs(testpath)
    testutil = testutils.Testutils(testpath=testpath)


    # Init
    testutil.write('A/file',text='file')

    # Randomize Mod times
    testutil.modtime_all()

    # Start it
    config = testutil.get_config(remote=remote)
    testutil.init(config)

    # Apply actions
    testutil.move('A/file','A/file_new')
    testutil.move('B/file','B/file_new')

    # Sync
    testutil.run(config)

    # Check it -- Only need to check A
    assert testutil.exists('A/file_new')
    assert not testutil.exists('A/file')


    # Finally
    assert len(testutil.compare_tree()) == 0

@pytest.mark.parametrize("remote", remotes + rclone)
def test_moved_new_in_loc(remote): # old test 05
    """ File moved by A. New file placed by B in same location.
    see test_movedmod_new_in_loc"""
    testpath = os.path.join(os.path.abspath(os.path.split(__file__)[0]),
            'test_dirs','moved_new_in_loc')
    try:
        shutil.rmtree(testpath)
    except:
        pass
    os.makedirs(testpath)
    testutil = testutils.Testutils(testpath=testpath)


    # Init
    testutil.write('A/file0',text='file0')

    # Randomize Mod times
    testutil.modtime_all()

    # Start it
    config = testutil.get_config(remote=remote)
    config.compress_file_list = True
    testutil.init(config)

    # Apply actions
    testutil.move('A/file0','A/file1')
    testutil.write('B/file1',text='file_onB')

    # Sync
    testutil.run(config)

    # Check it -- Only need to check A
    assert testutil.read('A/file0') == 'file0'    # Transferred back
    assert testutil.read('A/file1') == 'file_onB' # Overwritten by B

    # Expected outcome file0 on B will not be allowed to move.
    # file1 was ONLY moved and not modified so it will be overwritten by B
    # See test 14 for a similar case


    # Finally
    assert len(testutil.compare_tree()) == 0

# do not test rclone since it only tracks moves when not modified
@pytest.mark.parametrize("remote", remotes)
def test_movedmod_new_in_loc(remote): # old test 14. Extension of test_moved_new_in_loc
    """ File moved AND MODIFIED by A. New file placed by B in same location.
    See test test_moved_new_in_loc"""

    name = 'test_movedmod_new_in_loc'
    if remote:
        name += '_remote'
    testpath = os.path.join(os.path.abspath(os.path.split(__file__)[0]),
            'test_dirs',name)
    try:
        shutil.rmtree(testpath)
    except:
        pass
    os.makedirs(testpath)
    testutil = testutils.Testutils(testpath=testpath)

    # Init
    testutil.write('A/file0',text='file0')

    # Randomize Mod times
    testutil.modtime_all()

    # Start it
    config = testutil.get_config(remote=remote)
    testutil.init(config)

    # Apply actions
    testutil.move('A/file0','A/file1')
    testutil.write('A/file1',text='hello',mode='a')

    testutil.write('B/file1',text='file_onB')

    # Sync
    testutil.run(config)

    # Check it -- Only need to check A
    assert testutil.read('A/file0') == 'file0', 'synced back file failed'
    assert testutil.read('A/file1.machineA') == 'file0\nhello', 'failed dup 1'
    assert testutil.read('A/file1.machineB') == 'file_onB','failed dup 2' # Overwritten by B
    # Expected outcome file0 on B will not be allowed to move.
    # file1 was ONLY moved and not modified so it will be overwritten by B

    # Expected outcome file0 on B will not be allowed to move.
    # file1 was ONLY moved and not modified so it will be overwritten by B
    # See test 14 for a similar case


    # Finally
    assert len(testutil.compare_tree()) == 0

@pytest.mark.parametrize("remote", remotes + rclone)
def test_move_conflict_at_dest(remote): # old test 06
    """ File moved by both A and B to the same location """
    testpath = os.path.join(os.path.abspath(os.path.split(__file__)[0]),
            'test_dirs','move_conflict_at_dest')
    try:
        shutil.rmtree(testpath)
    except:
        pass
    os.makedirs(testpath)
    testutil = testutils.Testutils(testpath=testpath)


    # Init
    testutil.write('A/file0',text='file0')
    testutil.write('A/file1',text='file1')

    # Randomize Mod times
    testutil.modtime_all()

    # Start it
    config = testutil.get_config(remote=remote)
    testutil.init(config)

    # Apply actions
    testutil.move('A/file0','A/file2')
    testutil.move('B/file1','B/file2')

    # Sync
    testutil.run(config)

    # Check it -- Only need to check A
    assert testutil.read('A/file0') == 'file0','f0'
    assert testutil.read('A/file1') == 'file1','f1'
    assert testutil.read('A/file2.machineA') == 'file0','f2a' # The moved on on A
    assert testutil.read('A/file2.machineB') == 'file1','f2b'

    # Expect that neither move will happen on either side. file2 will
    # conflict and file0 and file1 will remain

    # Finally
    assert len(testutil.compare_tree()) == 0

@pytest.mark.parametrize("remote", remotes + rclone)
def test_moved_deleted_same(remote): # old test 07
    """ Moved on one side and deleted on the other"""
    testpath = os.path.join(os.path.abspath(os.path.split(__file__)[0]),
            'test_dirs','test_moved_deleted_same')
    try:
        shutil.rmtree(testpath)
    except:
        pass
    os.makedirs(testpath)
    testutil = testutils.Testutils(testpath=testpath)


    # Init
    testutil.write('A/file0',text='file0')
    testutil.write('A/file3',text='file3')

    # Randomize Mod times
    testutil.modtime_all()

    # Start it
    config = testutil.get_config(remote=remote)
    testutil.init(config)

    # Apply actions
    testutil.move('A/file0','A/file1')
    testutil.remove('B/file0')

    testutil.remove('A/file3')
    testutil.move('B/file3','B/file4')

    # Sync
    testutil.run(config)

    # Check it -- Only need to check A
    assert testutil.read('A/file1') == 'file0'
    assert testutil.read('A/file4') == 'file3'

    # Finally
    assert len(testutil.compare_tree()) == 0

@pytest.mark.parametrize("remote,AB", list(itertools.product(remotes + rclone,['A','B'])))
def test_same_file_moved(remote,AB): # old test 08
    """ Same file moved to different locations"""
    if AB == 'A':
        BA = 'B'
    else:
        BA = 'A'

    testpath = os.path.join(os.path.abspath(os.path.split(__file__)[0]),
            'test_dirs','test_moved_deleted_same'+AB)
    try:
        shutil.rmtree(testpath)
    except:
        pass
    os.makedirs(testpath)
    testutil = testutils.Testutils(testpath=testpath)


    # Init
    testutil.write('A/file0',text='file0')

    # Randomize Mod times
    testutil.modtime_all()

    # Start it
    config = testutil.get_config(remote=remote)
    config.move_conflict = AB
    testutil.init(config)

    # Apply actions
    testutil.move('A/file0','A/fileA')
    testutil.move('B/file0','B/fileB')

    # Sync
    testutil.run(config)

    # Check it -- Only need to check A
    assert testutil.read('A/file'+AB) == 'file0'
    assert not testutil.exists('A/file'+BA)

    # Finally
    assert len(testutil.compare_tree()) == 0

@pytest.mark.parametrize("remote", remotes + rclone)
def test_file_deleted_moved_on_other(remote): # Original test 09
    """ file1 is deleted on A but file2 --> file1 on B w/o modification (see test 19) """
    testpath = os.path.join(os.path.abspath(os.path.split(__file__)[0]),
            'test_dirs','test_file_deleted_moved_on_other')
    try:
        shutil.rmtree(testpath)
    except:
        pass
    os.makedirs(testpath)
    testutil = testutils.Testutils(testpath=testpath)


    # Init
    testutil.write('A/file0',text='file0')
    testutil.write('A/file1',text='file1')

    # Randomize Mod times
    testutil.modtime_all()

    # Start it
    config = testutil.get_config(remote=remote)
    testutil.init(config)

    # Apply actions
    testutil.remove('A/file0')
    testutil.move('B/file1','B/file0')

    # Sync
    testutil.run(config)

    # Check it -- Only need to check A
    assert testutil.read('A/file0') == 'file1','content'
    assert not testutil.exists('A/file1'),'deleted'

    # Finally
    assert len(testutil.compare_tree()) == 0

@pytest.mark.parametrize("remote", remotes)
def test_file_deleted_replaced_with_move(remote): # Original test 19
    """ file1 is deleted on B then file2 --> file1 on B w/o modification (see test 09) """
    testpath = os.path.join(os.path.abspath(os.path.split(__file__)[0]),
            'test_dirs','test_file_deleted_replaced_with_move')
    try:
        shutil.rmtree(testpath)
    except:
        pass
    os.makedirs(testpath)
    testutil = testutils.Testutils(testpath=testpath)


    # Init
    testutil.write('A/file0',text='file0')
    testutil.write('A/file1',text='file1')

    # Randomize Mod times
    testutil.modtime_all()

    # Start it
    config = testutil.get_config(remote=remote)
    testutil.init(config)

    # Apply actions
    testutil.remove('B/file1')
    testutil.move('B/file0','B/file1')

    # Sync
    testutil.run(config)

    # Check it -- Only need to check A
    assert testutil.read('A/file1') == 'file0','content'
    assert not testutil.exists('A/file0'),'deleted'

    # Finally
    assert len(testutil.compare_tree()) == 0

@pytest.mark.parametrize("remote", remotes + rclone)
def test_file_replaced_deleted_other_prev_attr(remote):
    """
    file0 is replaced by file1 on A and file1 is deleted on B
    with a prev_attr of just path
    """
    testpath = os.path.join(os.path.abspath(os.path.split(__file__)[0]),
            'test_dirs','test_file_replaced_deleted_other')
    try:
        shutil.rmtree(testpath)
    except:
        pass
    os.makedirs(testpath)
    testutil = testutils.Testutils(testpath=testpath)

    # Init
    testutil.write('A/file0',text='file0')
    testutil.write('A/file1',text='file1')

    # Randomize Mod times
    testutil.modtime_all()

    # Start it
    config = testutil.get_config(remote=remote)
    config.prev_attributesA = ['path']
#     config.move_attributesA = ['path']
    testutil.init(config)

    # Apply actions
    testutil.remove('B/file1')
    testutil.move('A/file1','A/file0')

    # Sync
    testutil.run(config,silent=True)

    # Check it -- Only need to check A
    # Content of file0
    assert not testutil.exists('A/file1'),'deleted'

    # Finally
    assert len(testutil.compare_tree()) == 0

@pytest.mark.parametrize("remote", remotes + rclone)
def test_new_and_deleted_file(remote): # Old test 10
    """File is created (one on both sides)  each different"""
    testpath = os.path.join(os.path.abspath(os.path.split(__file__)[0]),
            'test_dirs','test_new_and_deleted_file')
    try:
        shutil.rmtree(testpath)
    except:
        pass
    os.makedirs(testpath)
    testutil = testutils.Testutils(testpath=testpath)


    # Init
    testutil.write('A/file0',text='file0')
    testutil.write('A/file1',text='file1')

    # Randomize Mod times
    testutil.modtime_all()

    # Start it
    config = testutil.get_config(remote=remote)
    testutil.init(config)

    # Apply actions
    testutil.write('A/fileA',text='fileA')
    testutil.write('B/fileB',text='fileB')
    testutil.remove('A/file0')
    testutil.remove('A/file1')


    # Sync
    testutil.run(config)

    # Check it -- Only need to check A
    assert testutil.read('A/fileA') == 'fileA', 'copy A'
    assert testutil.read('A/fileB') == 'fileB', 'copy B'
    assert not testutil.exists('A/file0')
    assert not testutil.exists('A/file1')

    # Finally
    assert len(testutil.compare_tree()) == 0

@pytest.mark.parametrize("remote", remotes + rclone)
def test_same_file_created(remote): # Old test 11
    """ Same file is created with the same content """
    testpath = os.path.join(os.path.abspath(os.path.split(__file__)[0]),
            'test_dirs','test_same_file_created')
    try:
        shutil.rmtree(testpath)
    except:
        pass
    os.makedirs(testpath)
    testutil = testutils.Testutils(testpath=testpath)


    # Init
    testutil.write('A/other',text='other')

    # Randomize Mod times
    testutil.modtime_all()

    # Start it
    config = testutil.get_config(remote=remote)
    testutil.init(config)

    # Apply actions
    testutil.write('A/file',text='file',time_adj=1)
    testutil.write('B/file',text='file',time_adj=5)

    # Sync
    testutil.run(config)

    # Check it -- Only need to check A
    assert testutil.exists('A/file.machineA')
    assert testutil.exists('A/file.machineB')

    # Finally
    assert len(testutil.compare_tree()) == 0

@pytest.mark.parametrize("remote", remotes + rclone)
def test_check_new_on_delete(remote):
    """
    Check when a new file is created as some programs do on save
    
    When true, the the file should be backed up but *not* marked for delete
    unless using rclone which doesn't care about inodes so will always look
    like the same file. (i.e. check_new_on_delete is always True on the remote)
    
    """
    for check_new_on_delete in [True,False]:
        testpath = os.path.join(os.path.abspath(os.path.split(__file__)[0]),
                'test_dirs','test_check_new_on_delete')
        try:
            shutil.rmtree(testpath)
        except:
            pass
        os.makedirs(testpath)
        testutil = testutils.Testutils(testpath=testpath)
    
        testutil.write('A/myfileA',text='fileA')
        testutil.write('A/myfileB',text='fileB')
    
        # Randomize Mod times
        testutil.modtime_all()
    
        # Start it
        config = testutil.get_config(remote=remote)
        config.check_new_on_delete = check_new_on_delete
        testutil.init(config) 
    
        # Apply actions
        # Delete the file and make a new one with the same name. However, to
        # prevent inode reuse from breaking, make as different file before delete
        # and rename
        testutil.write('A/myfileAt',text='fileA2')
        testutil.write('B/myfileBt',text='fileB2')
    
        testutil.remove('A/myfileA')
        testutil.remove('B/myfileB')
    
        testutil.move('A/myfileAt','A/myfileA')
        testutil.move('B/myfileBt','B/myfileB')

        # Sync
        testutil.run(config)
    
        # Test
        assert len(testutil.compare_tree()) == 0
        assert testutil.read('A/myfileA') == 'fileA2'
        assert testutil.read('A/myfileB') == 'fileB2'
    
        # Read the log
            # Make sure it actually did the move and not just transfer
        log_path = glob(os.path.join(testpath,'A','.PyFiSync','logs','20*.log'))
        log_path.sort()
        log_txt = open(log_path[-1]).read()
        
        if check_new_on_delete:
            assert 'backup: myfileA' in log_txt
            assert 'backup: myfileB' in log_txt
        elif remote  != 'rclone':
            assert 'delete (w/ backup): myfileA' in log_txt
            assert 'delete (w/ backup): myfileB' in log_txt    
        else:
            assert 'backup: myfileB' in log_txt # Since still looks like check_new_on_delete for remote 
            assert 'delete (w/ backup): myfileA' in log_txt
    
@pytest.mark.parametrize("remote", remotes)
def test_delete_file_in_folder(remote): # Old test 12
    """ file is deleted. Folder should remain """
    testpath = os.path.join(os.path.abspath(os.path.split(__file__)[0]),
            'test_dirs','test_delete_file_in_folder')
    try:
        shutil.rmtree(testpath)
    except:
        pass
    os.makedirs(testpath)
    testutil = testutils.Testutils(testpath=testpath)

    # Init
    testutil.write('A/dir/file',text='file')
    testutil.write('A/dir2/file2',text='file')

    # Randomize Mod times
    testutil.modtime_all()

    # Start it
    config = testutil.get_config(remote=remote)
    testutil.init(config)

    # Apply actions
    testutil.remove('A/dir/file')
    testutil.remove('B/dir2/file2')

    # Sync
    testutil.run(config)

    # Check it -- should be there
    assert testutil.exists('A/dir/')
    assert testutil.exists('B/dir2/')
    
    # Should not be there
    assert not testutil.exists('A/dir2/')
    assert not testutil.exists('B/dir/')


@pytest.mark.parametrize("remote", remotes)
def test_delete_folder(remote): # Old test 13
    """ Folder is deleted. Should propgate """
    testpath = os.path.join(os.path.abspath(os.path.split(__file__)[0]),
            'test_dirs','test_delete_folder')
    try:
        shutil.rmtree(testpath)
    except:
        pass
    os.makedirs(testpath)
    testutil = testutils.Testutils(testpath=testpath)

    # Init
    testutil.write('A/dir/file',text='file')

    # Randomize Mod times
    testutil.modtime_all()

    # Start it
    config = testutil.get_config(remote=remote)
    testutil.init(config)

    # Apply actions
    testutil.remove('A/dir/') # Remove whole dir

    # Sync
    testutil.run(config)


    # Finally
    diff = testutil.compare_tree()
    assert diff == [('missing_inA', '>>EMPTY<<')]
    assert not testutil.exists('A/dir')
    assert not testutil.exists('B/dir')


@pytest.mark.parametrize("remote", remotes)
def test_empty_dirs(remote): # NEW
    """ Tests for various empty directory actions at different levels """
    testpath = os.path.join(os.path.abspath(os.path.split(__file__)[0]),
            'test_dirs','test_delete_empty_folder')
    try:
        shutil.rmtree(testpath)
    except:
        pass
    os.makedirs(testpath)
    testutil = testutils.Testutils(testpath=testpath)
    
    # The tests will:
    #   - An empty dir should *not* sync
    #   - A deep directory that made empty should be deleted
    #   - Another deeper directory deleted at the base should be removed
    
# 
    # Init -- make with a file we will delete to make an empty folder
    testutil.write('A/will_remove/deeper/file',text='file')
    testutil.write('A/will_remove2/deeper/even_deeper/file',text='file')

    # Randomize Mod times and delete file before starting
    testutil.modtime_all()

    # Remove the emtpydir's file on A and the entire
    testutil.write('A/emptydir/deeper/tmp',text='file')
    testutil.remove('A/emptydir/deeper/tmp')
    
    # Start it
    config = testutil.get_config(remote=remote)
    testutil.init(config)
    
    testutil.remove('A/will_remove/deeper/file') # Just remove the file
    testutil.remove('A/will_remove2/deeper/')
        
    testutil.run(config)
    
    # At this point, B should be empty and A should have the following tree:
    #     .
    #     ├── emptydir/
    #     │   └── deeper/
    #     ├── will_remove/
    #     │   └── deeper/
    #     └── will_remove2/
    gold = set([('missing_inA', '>>EMPTY<<'), 
                ('missing_inA', 'emptydir/deeper/>>EMPTY<<'), 
                ('missing_inA', 'will_remove/deeper/>>EMPTY<<'), 
                ('missing_inA', 'will_remove2/>>EMPTY<<')
               ]) # These say "missing_inA" even though it is B because the file
                  # couldn't be found
    assert gold == set(testutil.compare_tree()) 
    assert os.listdir(os.path.join(testpath,'B')) == ['.PyFiSync'] # Otherwise empty
    

@pytest.mark.parametrize("remote", remotes + rclone)
def test_backups(remote): # Old test 15
    """ Backups before overwrite and delete. Both sides """
    testpath = os.path.join(os.path.abspath(os.path.split(__file__)[0]),
            'test_dirs','test_backups')
    try:
        shutil.rmtree(testpath)
    except:
        pass
    os.makedirs(testpath)
    testutil = testutils.Testutils(testpath=testpath)

    # Init
    testutil.write('A/fileAd',text='fileAd')
    testutil.write('A/fileBd',text='fileBd')
    testutil.write('A/fileAm',text='fileAm')
    testutil.write('A/fileBm',text='fileBm')

    # Randomize Mod times
    testutil.modtime_all()

    # Start it
    config = testutil.get_config(remote=remote)
    testutil.init(config)

    # Apply actions
    testutil.remove('A/fileAd')
    testutil.remove('B/fileBd')
    testutil.write('A/fileAm',text='am2',mode='a',time_adj=30)
    testutil.write('B/fileBm',text='bm2',mode='a',time_adj=30)

    # Sync
    testutil.run(config)

    # Check it -- Only need to check A
    bpA = glob(os.path.join(testpath,'A/.PyFiSync/backups/20*/'))[0]
    assert testutil.read(os.path.join(bpA,'fileBd')) =='fileBd'
    assert testutil.read(os.path.join(bpA,'fileBm')) =='fileBm'
    assert testutil.read('A/fileAm') =='fileAm\nam2'

    bpB = glob(os.path.join(testpath,'B/.PyFiSync/backups/20*/'))[0]
    assert testutil.read(os.path.join(bpB,'fileAd')) =='fileAd'
    assert testutil.read(os.path.join(bpB,'fileAm')) =='fileAm'
    assert testutil.read('B/fileBm') =='fileBm\nbm2'

    # Finally
    assert len(testutil.compare_tree()) == 0

@pytest.mark.parametrize("remote", remotes + rclone)
def test_exclusions(remote): # Old test 16
    """ test exclusion """
    testpath = os.path.join(os.path.abspath(os.path.split(__file__)[0]),
            'test_dirs','test_exclusions')
    try:
        shutil.rmtree(testpath)
    except:
        pass
    os.makedirs(testpath)
    testutil = testutils.Testutils(testpath=testpath)

    # Init
    testutil.write('A/transfer_me',text='trans')
    testutil.write('A/skip_me',text='onA')
    testutil.write('A/skip_folder/file2',text='onA')

    # Randomize Mod times
    testutil.modtime_all()

    # Start it
    config = testutil.get_config(remote=remote)
    testutil.init(config) # Run then add exclude
    config.excludes += ['skip_me','skip_folder/']

    # Apply actions
    testutil.write('B/skip_me',text='onB',mode='a')
    testutil.write('B/skip_folder/file2',text='onB',mode='a')

    # Sync
    testutil.run(config)

    # Check it -- Only need to check A
    assert testutil.exists('A/transfer_me'),'a'
    assert testutil.read('A/skip_me')=='onA','b'
    assert testutil.read('B/skip_me')=='onA\nonB','c'
    # 'test16/skip_me' is skipped in the final check

    assert testutil.read('A/skip_folder/file2')=='onA','d'
    assert testutil.read('B/skip_folder/file2')=='onA\nonB','e'
    # test16/skip_folder/file2 is skipped in final check

    # Finally
    comp = testutil.compare_tree()
    assert len(comp) == 2
    assert ('disagree', 'skip_folder/file2') in comp
    assert ('disagree', 'skip_me') in comp

# Rclone doesn't do inodes
@pytest.mark.parametrize("remote", remotes)
def test_moved_file_size_track(remote): # Old test 17
    """ test moved files with size tracking rather than birthtime on one side  with modifications"""
    testpath = os.path.join(os.path.abspath(os.path.split(__file__)[0]),
            'test_dirs','test_moved_file_size_track')
    try:
        shutil.rmtree(testpath)
    except:
        pass
    os.makedirs(testpath)
    testutil = testutils.Testutils(testpath=testpath)

    # Init
    testutil.write('A/file0',text='F0')
    testutil.write('A/file1',text='F1')
    testutil.write('A/file2',text='F2')

    # Randomize Mod times
    testutil.modtime_all()

    # Start it
    config = testutil.get_config(remote=remote)

    # Set A to be birthtime and B to be size
    config.move_attributesA = ['ino','birthtime']
    config.move_attributesB = ['ino','size']

    testutil.init(config)

    # Apply actions
    testutil.write('A/file0',text='F0',mode='a')
    testutil.move('A/file0','A/file00') # Should move with ino tracking


    testutil.write('B/file1',text='F1',mode='a')
    testutil.move('B/file1','B/file11') # Should register as delete and new
    testutil.move('B/file2','B/file22') # Should move since it didn't change size

    # Sync
    testutil.run(config)

    # Check it -- Only need to check A
    log_path = glob(os.path.join(testpath,'A','.PyFiSync','logs','20*.log'))
    log_path.sort()
    log_txt = open(log_path[-1]).read()

    # Should move
    assert len(re.findall('move: *file2 *--> *file22',log_txt)) == 1
    assert len(re.findall('move: *file0 *--> *file00',log_txt)) == 1

    # Not found
    assert len(re.findall('move: *file1 *--> *file11',log_txt)) == 0

    # Make sure it was deleted. (and that this regex didn't capture too much
    assert len(re.findall('delete.*?: file1',log_txt)) == 1
    assert len(re.findall('delete.*?: file1',log_txt)[0]) <= 50

    # Should transfer
    assert len(re.findall('Transfer *file11',log_txt)) == 1
    assert len(re.findall('Transfer *file00',log_txt)) == 1

    # Should NOT transfer
    assert len(re.findall('Transfer *file22',log_txt)) == 0

    # Finally
    assert len(testutil.compare_tree()) == 0



@pytest.mark.parametrize("remote", remotes + rclone)
def test_unicode_spaces(remote): # Old test 18
    """ test unicode and spaces in file names """
    testpath = os.path.join(os.path.abspath(os.path.split(__file__)[0]),
            'test_dirs','test_unicode_spaces')
    try:
        shutil.rmtree(testpath)
    except:
        pass
    os.makedirs(testpath)
    testutil = testutils.Testutils(testpath=testpath)

    # Init
    testutil.write('A/spa ces0.txt',text='A0')
    testutil.write('A/unic°de.txt',text='u0')
    testutil.write('A/unic°deB.txt',text='uu2')

    # Randomize Mod times
    testutil.modtime_all()

    # Start it
    config = testutil.get_config(remote=remote)
    testutil.init(config)

    # Apply actions
    testutil.move('A/spa ces0.txt','A/spa ces1.txt')
    testutil.write('A/spa ces1.txt',text='A1',mode='a')

    testutil.move('A/unic°de.txt','A/unic°de1.txt')
    testutil.write('A/unic°de1.txt',text='u1',mode='a')

    testutil.move('B/unic°deB.txt','B/unic°deBB.txt')
    testutil.write('B/unic°deBB.txt',text='uu2',mode='a')

    # Sync
    testutil.run(config)

    # Check it -- Only need to check A
    assert testutil.read('A/spa ces1.txt') == 'A0\nA1'
    assert testutil.read('A/unic°de1.txt') == 'u0\nu1'
    assert testutil.read('A/unic°deBB.txt') == 'uu2\nuu2'

    # Finally
    assert len(testutil.compare_tree()) == 0

@pytest.mark.parametrize("remote", remotes + rclone)
def test_replace_deleted_with_new(remote): #old test 20
    """file deleted both sides but a new one is placed there (May be hard to
    test well if inodes are reused) """
    testpath = os.path.join(os.path.abspath(os.path.split(__file__)[0]),
            'test_dirs','test_replace_deleted_with_new')
    try:
        shutil.rmtree(testpath)
    except:
        pass
    os.makedirs(testpath)
    testutil = testutils.Testutils(testpath=testpath)

    # Init
    testutil.write('A/file0',text='A0')

    # Randomize Mod times
    testutil.modtime_all()

    # Start it
    config = testutil.get_config(remote=remote)
    testutil.init(config)

    # Apply actions
    testutil.remove('A/file0')
    testutil.remove('B/file0')

    testutil.write('A/file0',text='A1')

    # Sync
    testutil.run(config)

    # Check it -- Only need to check A
    assert testutil.read('A/file0') == 'A1'

    log_path = glob(os.path.join(testpath,'A','.PyFiSync','logs','20*.log'))
    log_path.sort()
    log_txt = open(log_path[-1]).read()
    assert len(re.findall('WARNING: *File deleted on B but move.*\n.*\n.*\n *File: *file0?',log_txt,re.MULTILINE)) == 1

    # Finally
    assert len(testutil.compare_tree()) == 0

@pytest.mark.parametrize("remote,symlinks", list(itertools.product(remotes,[True,False])))
def test_symlinks(remote,symlinks):
    """ test symlinked files and folders """
    testpath = os.path.join(os.path.abspath(os.path.split(__file__)[0]),
            'test_dirs','test_symlinks')
    print('symlinks',symlinks)
    try:
        shutil.rmtree(testpath)
    except:
        pass
    os.makedirs(testpath)
    testutil = testutils.Testutils(testpath=testpath)

    # Init
    testutil.write('A/file0',text='A0') # just to have a file

    # Randomize Mod times
    testutil.modtime_all()

    # Start it
    config = testutil.get_config(remote=remote)
    config.copy_symlinks_as_links = not symlinks
#     config.symlinks = symlinks
    testutil.init(config)


    # Apply actions
    # Create symlinks  OUTSIDE of the sync dir!!!!
    testutil.write('source/file1',text='S1')
    testutil.write('source/dir/file2',text='S2')
    testutil.write('source/dir/file3',text='S3')

    os.symlink(os.path.join(testpath,'source/file1'),
               os.path.join(testpath,'A/file1_link'))

    os.symlink(os.path.join(testpath,'source/dir'),
               os.path.join(testpath,'A/dir_link'))

    # Sync
    testutil.run(config)

    ## Check

    # Make sure the linked files are there in A
    assert testutil.read('A/file1_link') == 'S1','linked file'
    assert testutil.read('A/dir_link/file2') == 'S2','linked file'
    assert testutil.read('A/dir_link/file3') == 'S3','linked file'

    # Missing files will be caught in the dir equivalence test
    diff = testutil.compare_tree()
    assert len(diff) == 0
    if symlinks:
        # Make sure the file got copies
        assert not os.path.islink(os.path.join(testpath,'B','file1_link'))
    else:
        # Make sure the link got copied
        assert os.path.islink(os.path.join(testpath,'B','file1_link'))
        # NOTE: directories are ALWAYS followed. Just make sure:
        assert os.path.islink(os.path.join(testpath,'A','dir_link'))
        assert not os.path.islink(os.path.join(testpath,'B','dir_link'))
    
    # Again, directories are always followed and the files within are treated as new.
    assert not os.path.islink(os.path.join(testpath,'A','dir_link','file2'))
    assert not os.path.islink(os.path.join(testpath,'A','dir_link','file3'))
    assert not os.path.islink(os.path.join(testpath,'B','dir_link','file2'))
    assert not os.path.islink(os.path.join(testpath,'B','dir_link','file3'))
    assert not os.stat(os.path.join(testpath,'A','dir_link','file2')).st_ino == os.stat(os.path.join(testpath,'B','dir_link','file2')).st_ino
    
    

@pytest.mark.parametrize("remote", remotes)
def test_remove_empty_folders(remote):
    """ Totally empty folders are removed """

    testpath = os.path.join(os.path.abspath(os.path.split(__file__)[0]),
            'test_dirs','test_replace_deleted_with_new')
    try:
        shutil.rmtree(testpath)
    except:
        pass
    os.makedirs(testpath)
    testutil = testutils.Testutils(testpath=testpath)

    # Init
    testutil.write('A/file0',text='A0')

    # Randomize Mod times
    testutil.modtime_all()

    # Start it
    config = testutil.get_config(remote=remote)
    testutil.init(config)

    # Apply actions
    testutil.remove('A/file0')
    testutil.remove('B/file0')

    testutil.write('A/file0',text='A1')

    # Sync
    testutil.run(config)

    # Check it -- Only need to check A
    assert testutil.read('A/file0') == 'A1'

    log_path = glob(os.path.join(testpath,'A','.PyFiSync','logs','20*.log'))
    log_path.sort()
    log_txt = open(log_path[-1]).read()

    assert len(re.findall('WARNING: *File deleted on B but move.*\n.*\n.*\n *File: *file0?',log_txt,re.MULTILINE)) == 1

    # Finally
    assert len(testutil.compare_tree()) == 0

# Rclone passes this but I will not test it since we don't expect folders to work
@pytest.mark.parametrize("remote", remotes)
def test_empty_bc_excludes(remote):
    """ 
    Tests when a folder has nothing but excluded files 
    """
    testpath = os.path.join(os.path.abspath(os.path.split(__file__)[0]),
            'test_dirs','test_empty_bc_excludes')
    try:
        shutil.rmtree(testpath)
    except:
        pass
    os.makedirs(testpath)
    testutil = testutils.Testutils(testpath=testpath)

    # Init
    testutil.write('A/a.txt',text='1')

    # Randomize Mod times
    testutil.modtime_all()

    # Start it
    config = testutil.get_config(remote=remote)
    config.excludes += ['*.exc']
    testutil.init(config)

    # Apply actions/create the files
    testutil.write('A/A.kep',text='keep')
    testutil.write('A/Aa.exc',text='exc')
    testutil.write('A/dir1/bla1.exc',text='exc')
    testutil.write('A/dir2/bla2.kep',text='keep')
    
    testutil.write('B/dir3/bla3.exc',text='Other Way')
    
    testutil.write('A/dir4/bla4.exc',text='FOUR')
    testutil.write('A/dir4/bla5.kep',text='FIVE')
    
    os.makedirs(os.path.join(testpath,'A','EMPT')) # Just an empty dir

    # Sync
    testutil.run(config)
    
    diffs = testutil.compare_tree()
    
    # These were excluded
    assert (u'missing_inB', u'Aa.exc') in diffs
    assert (u'missing_inB', u'dir1/bla1.exc') in diffs
    assert (u'missing_inB', u'dir4/bla4.exc') in diffs
    assert  (u'missing_inA', u'dir3/bla3.exc') in diffs
    
    # A/EMPT should NOT be transferred since it is empty
    assert os.path.exists(os.path.join(testpath,'A','EMPT')) # Empty Directory
    assert not os.path.exists(os.path.join(testpath,'B','EMPT')) # Empty Directory
    
    # Making it an exclude looks like a delete
    assert not os.path.exists(os.path.join(testpath,'B','dir1')) 
    assert not os.path.exists(os.path.join(testpath,'A','dir3'))

@pytest.mark.parametrize("remote", remotes + rclone)
def test_filename_characters_exclude(remote):
    """
    Characters such as $ (and maybe spaces in the future)?
    when excluded
    """

    testpath = os.path.join(os.path.abspath(os.path.split(__file__)[0]),
            'test_dirs','test_filename_characters_exclude')
    try:
        shutil.rmtree(testpath)
    except:
        pass
    os.makedirs(testpath)
    testutil = testutils.Testutils(testpath=testpath)

    # Init
    testutil.write('A/plain_file',text='aa')
    testutil.write('A/dollar$mid',text='$$')

    # Randomize Mod times
    testutil.modtime_all()

    # Start it
    config = testutil.get_config(remote=remote)
    config.excludes += ['$*','*e s*']
    testutil.init(config)

    # Apply actions

    testutil.write('A/$file_moneyA',text='A$')
    testutil.write('B/$file_moneyB',text='B$')

    testutil.write('A/file spaceA',text='A space')
    testutil.write('B/file spaceB',text='B space')

    testutil.write('A/regA',text='a') # Regular file to make sure the sync still
    testutil.write('B/regB',text='b') # happened

    testutil.write('B/dollar$mid',text='$',mode='a')
    testutil.move('B/dollar$mid','B/dollar$midd')


    # Sync
    testutil.run(config)

    # Check it -- Only need to check A
    diffs = testutil.compare_tree()
    # The files created on one side *SHOULD* be missing but nothing else should
    # be missing.

    assert testutil.read('B/dollar$midd') == '$$\n$'

    assert (u'missing_inB', u'$file_moneyA') in diffs
    assert (u'missing_inA', u'$file_moneyB') in diffs

    assert (u'missing_inB', u'file spaceA') in diffs
    assert (u'missing_inA', u'file spaceB') in diffs

    assert len(diffs) == 4,"Unaccounted for missing item(s)"


@pytest.mark.parametrize("remote", remotes + rclone)
def test_move_to_exclude(remote):
    """
    Test that a file may be moved into an excluded name.
    
    This should show as a delete!!! WARNING
    """

    testpath = os.path.join(os.path.abspath(os.path.split(__file__)[0]),
            'test_dirs','test_move_to_exclude')
    try:
        shutil.rmtree(testpath)
    except:
        pass
    os.makedirs(testpath)
    testutil = testutils.Testutils(testpath=testpath)

    # Init
    testutil.write('A/file1',text='a1')
    testutil.write('A/file2',text='a2')
    testutil.write('A/file3',text='a3')
    
    # Randomize Mod times
    testutil.modtime_all()

    # Start it
    config = testutil.get_config(remote=remote)
    config.excludes += ['efile*','edir/']
    testutil.init(config)

    # Apply actions

    testutil.move('A/file2','A/efile2')
    testutil.move('B/file3','B/edir/file3')

    # Sync
    testutil.run(config)

    # Check it -- Only need to check A
    diffs = testutil.compare_tree()
    
    # They should be deleted on the other side
    assert (u'missing_inA', u'edir/file3') in diffs
    assert (u'missing_inB', u'efile2') in diffs
    
    assert len(diffs) == 2,"Unaccounted for missing item(s)"
   
@pytest.mark.parametrize("remote", remotes+rclone)
def test_move_path_track(remote):
    """
    Tests using `path` as a move attribute to disable moves.
    
    For now, will test it on just ONE side to show that other attributes
    work. But in the future, if a backend doesn't support moves, then it
    it will need to be set on both
    
    """

    testpath = os.path.join(os.path.abspath(os.path.split(__file__)[0]),
            'test_dirs','test_move_path_track')
    try:
        shutil.rmtree(testpath)
    except:
        pass
    os.makedirs(testpath)
    testutil = testutils.Testutils(testpath=testpath)

    # Init
    testutil.write('A/fileA',text='AA')
    testutil.write('A/fileB',text='BB')
    testutil.write('A/file',text='nothing')
    
    # Randomize Mod times
    testutil.modtime_all()

    # Start it
    config = testutil.get_config(remote=remote)
    config.move_attributesA = ['ino','size'] 
    config.move_attributesB = ['path']
    testutil.init(config)

    # Apply actions

    testutil.move('A/fileA','A/fileAM')
    testutil.move('B/fileB','B/fileBM')
    
    # Sync
    testutil.run(config)

    # Check it -- Only need to check A
    diffs = testutil.compare_tree()
    
    assert diffs == [],"tree did not sync" # Even w/o move tracking, it should still sync

    log_path = glob(os.path.join(testpath,'A','.PyFiSync','logs','20*.log'))
    log_path.sort()
    log_txt = open(log_path[-1]).read()
    
    assert 'move: fileA --> fileAM' in log_txt # ['ino','size'] tracking shows move
    assert 'delete (w/ backup): fileB' in log_txt # ['path'] tracking do not show move


@pytest.mark.parametrize("remote", remotes)
def test_broken_links(remote): # old test 02
    """ How to handle broken links on the B side """
    testpath = os.path.join(os.path.abspath(os.path.split(__file__)[0]),
            'test_dirs','broken_links')
    try:
        shutil.rmtree(testpath)
    except:
        pass
    os.makedirs(testpath)
    testutil = testutils.Testutils(testpath=testpath)

    # Init
    testutil.write('A/fileA',text='AA')

    # Randomize Mod times
    testutil.modtime_all()

    # Start it
    config = testutil.get_config(remote=remote)
    config.copy_symlinks_as_links = False
    
    testutil.init(config)

    # Apply actions
    
    src = '/path/to/nothing.txt'
    dest = os.path.join(testpath,'B','broken_link')
    os.symlink(src,dest)
    
    # Sync
    testutil.run(config)

    # Check it -- Only need to check A
    diffs = testutil.compare_tree()
    assert (u'missing_inA', u'broken_link') in diffs
    assert len(diffs) == 1
    
    # We also want to confirm that an error was printed to the screen
    log_path = glob(os.path.join(testpath,'A','.PyFiSync','logs','20*.log'))
    log_path.sort()
    log_txt = open(log_path[-1]).read()
    
    if remote: # No warnings if not remote
        N = 2
    else:
        N = 0
    
    assert len(re.findall('Remote Call returned warnings:',log_txt)) == N
    assert len(re.findall('ERROR: Could not find information on broken_link',log_txt)) == 2

@pytest.mark.parametrize("remote", remotes + rclone)
def test_pre_post_bash(remote):
    """ Testing the pre_sync_bash and post_sync_bash"""
    testpath = os.path.join(os.path.abspath(os.path.split(__file__)[0]),
            'test_dirs','pre_post_bash')
    try:
        shutil.rmtree(testpath)
    except:
        pass
    os.makedirs(testpath)
    testutil = testutils.Testutils(testpath=testpath)

    # Init
    testutil.write('A/fileA',text='AA')

    # Randomize Mod times
    testutil.modtime_all()

    # Start it
    config = testutil.get_config(remote=remote)
    config.copy_symlinks_as_links = False
    
    # Test by creating and delete files. They should NOT be done with the init
    
    config.pre_sync_bash="""\
echo "testing2" > from_bash2
echo "testing3" > from_bash3
    """
    config.post_sync_bash="""\
echo "testing4" > from_bash2 # Append to a file
rm from_bash3   # Delete
python -c "import sys;sys.stderr.write('error test\\n')" # Write to error
    """    
    
    testutil.init(config)
    
    # Sync
    testutil.run(config)

    # Check it -- Only need to check A
    diffs = testutil.compare_tree()
    assert (u'disagree', u'from_bash2') in diffs,"post or pre not called"
    assert (u'missing_inA', u'from_bash3') in diffs
    assert len(diffs) == 2

    # Make sure the STDERR is in the log
    log_path = glob(os.path.join(testpath,'A','.PyFiSync','logs','20*.log'))
    log_path.sort()
    log_txt = open(log_path[-1]).read()
    assert len(re.findall(r'STDERR: *?> *? error test',log_txt.replace('\n',''),re.DOTALL)) == 1

# - [ ] Need to check this test....
@pytest.mark.parametrize("remote", remotes)
def test_duplicate_sha1(remote): # old test 02    
    """ 
    Test for SHA1 (only) tracking when there are more than one file with the 
    same contents
    
    This is a known issue and an alert will be raised but, the key is to 
    protect data integrity which the current behavior seems to do.
    
    """
    import random
    testpath = os.path.join(os.path.abspath(os.path.split(__file__)[0]),
            'test_dirs','test_sha1_dups')
    try:
        shutil.rmtree(testpath)
    except:
        pass
    os.makedirs(testpath)
    testutil = testutils.Testutils(testpath=testpath)

    content1 = ''.join(random.choice('0123456789') for _ in range(200))
    content2 = ''.join(random.choice('0123456789') for _ in range(201))
    content3 = ''.join(random.choice('0123456789') for _ in range(202))

    # Init
    testutil.write('A/a.txt',text=content1)
    testutil.write('A/b.txt',text=content2)
    testutil.write('A/c0.txt',text=content3)
    testutil.write('A/c1.txt',text=content3)


    # Randomize Mod times
    testutil.modtime_all()

    # Start it
    config = testutil.get_config(remote=remote)
    config.move_attributesA = ['sha1']
    config.move_attributesB = ['sha1']
    config.excludes += ['*.exc']
    
    testutil.init(config)

    # Apply actions/create the files
    testutil.move('A/a.txt','A/amoved.txt') # Just check the move
    
    # Create a new file
    testutil.write('A/adup.txt',text=content1)
    testutil.write('A/bdup.txt',text=content2)

    # Sync
    testutil.run(config)
    diffs = testutil.compare_tree()
    assert len(diffs) == 0 # No differences
    
    files_gold = set(['adup.txt', 'amoved.txt', 'b.txt', 'bdup.txt', 'c0.txt', 'c1.txt'])
    testpathA = os.path.join(testpath,'A')
    files = testutil.tree(testpathA)
    files = set(os.path.relpath(f,testpathA) for f in files)
    assert files == files_gold

@pytest.mark.parametrize("remote", remotes)
def test_use_hashdb(remote): # This used to be test 01
    """ 
    Tests that the hashdb is or isn't used. 
    
    For the time being, this does not actually test to ensure the sha1 doesn't
    get computed again. Only that the hashdb is created
    
    """
    for usedb in [True,False]:
        testpath = os.path.join(os.path.abspath(os.path.split(__file__)[0]),
                'test_dirs','test_use_hashdb')
        try:
            shutil.rmtree(testpath)
        except:
            pass
        os.makedirs(testpath)
        testutil = testutils.Testutils(testpath=testpath)

        # Init
        testutil.write('A/file1',text='test01f1')

        # Randomize Mod times
        testutil.modtime_all()

        # Start it
        config = testutil.get_config(remote=remote)
        config.move_attributesA += ['sha1']
        config.move_attributesB += ['sha1']
        config.use_hash_db = usedb
        testutil.init(config)

        # Apply actions
        #NONE

        # Sync
        testutil.run(config)
        # Finally
        assert len(testutil.compare_tree()) == 0
        if usedb:
            assert testutil.exists(os.path.join(testpath,'A','.PyFiSync','hash_db.json'))
            assert testutil.exists(os.path.join(testpath,'B','.PyFiSync','hash_db.json'))

@pytest.mark.parametrize("remote", remotes)
def test_dry_run(remote):
    """ Test DRY RUN """
    testpath = os.path.join(os.path.abspath(os.path.split(__file__)[0]),
            'test_dirs','dry_run')
    try:
        shutil.rmtree(testpath)
    except:
        pass
    os.makedirs(testpath)
    testutil = testutils.Testutils(testpath=testpath)


    # Init
    testutil.write('A/moveA',text='moveA')
    testutil.write('A/moveB',text='moveB')
    
    testutil.write('A/deleteA',text='deleteA')
    testutil.write('A/deleteB',text='deleteB')
    
    testutil.write('A/modA',text='modA')
    testutil.write('A/modB',text='modB')    
    

    # Randomize Mod times
    testutil.modtime_all()

    # Start it
    config = testutil.get_config(remote=remote)
    testutil.init(config)

    # Apply actions and update config with bash 
    config.pre_sync_bash="""\
echo "PRE" > from_bashPRE
    """    
    config.post_sync_bash="""\
echo "POST" > from_bashPOST
    """    
    
    testutil.move('A/moveA','A/moveAA')
    testutil.move('B/moveB','B/moveBB')
    
    testutil.remove('A/deleteA')
    testutil.remove('B/deleteB')
    
    testutil.write('A/modA',text='mA',mode='a')
    testutil.write('B/modB',text='mB',mode='a')   

    # Sync
    # Make sure nothing is changed -- including bash commands
    pre_tree = set(testutil.tree(testutil.testpath))
    testutil.run(config,flags=('--dry-run',))
    post_tree = set(testutil.tree(testutil.testpath))
    
    assert pre_tree == post_tree
    
##############################
### rclone Only
#############################
@pytest.mark.parametrize("remote",rclone)
def test_imitate_rclone_hash(remote):
    """ Test for incorectly specified or missing hash with rlcone """
    for imitate in [True,False]:
        testpath = os.path.join(os.path.abspath(os.path.split(__file__)[0]),
                'test_dirs','test_imitate_rclone_hash')
        assert remote == 'rclone'
        try:
            shutil.rmtree(testpath)
        except:
            pass
        os.makedirs(testpath)
        testutil = testutils.Testutils(testpath=testpath)


        # Init
        testutil.write('A/moveA',text='moveA')
        testutil.write('A/moveB',text='moveB')

        # Randomize Mod times
        testutil.modtime_all()

        # Start it
        config = testutil.get_config(remote=remote)
        config.move_attributesB = ['hash.NOPE']
        config.imitate_missing_hash = imitate
        
        if imitate:
            testutil.init(config)
        else:
            with pytest.raises(SystemExit):
                testutil.init(config)
            return
            
        # Apply actions
        testutil.move('A/moveA','A/moveA_moved')
        testutil.move('B/moveB','B/moveB_moved')

        # Sync
        testutil.run(config)

        # Check it -- Only need to check A
        # If it failed this wouldn't show but we'll check the logs to make sure
        # it didn't move the file
        assert testutil.exists('A/moveA_moved')
        assert not testutil.exists('A/moveA')
    
        assert testutil.exists('B/moveB_moved')
        assert not testutil.exists('B/moveB')
    
        # Make sure it actually did the move and not just transfer for A
        log_path = glob(os.path.join(testpath,'A','.PyFiSync','logs','20*.log'))
        log_path.sort()
        log_txt = open(log_path[-1]).read()
        assert "No A >>> B transfers" in log_txt
        assert "No A <<< B transfers" not in log_txt # NOT!
        assert "moveB --> moveB_moved" not in log_txt # NOT!

        assert len(testutil.compare_tree()) == 0


if __name__=='__main__':    
    sys.exit()



