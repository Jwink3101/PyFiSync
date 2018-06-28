#!/usr/bin/env python
# -*- coding: utf-8 -*-
from __future__ import unicode_literals,print_function

try:
    from . import testutils
except (ValueError,ImportError):
    import testutils
testutils.add_module()

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
# remotes = [False]   # Just test locally
# remotes = [False,True]
remotes = [False,'python2','python3']


@pytest.mark.parametrize("remote,AB,all_", list(itertools.product(remotes,['A','B'],[True,False])))
def test_mod_new_different(remote,AB,all_):
    """ Different file modified on each side. Only one changes. Then add 'all'
    to make sure both have uploaded everything, even what is not modified """
    testpath = os.path.join(os.path.abspath(os.path.split(__file__)[0]),
            'test_dirs','pp','test_mod_new_different')
    try:
        shutil.rmtree(testpath)
    except:
        pass
    os.makedirs(testpath)
    testutil = testutils.Testutils(testpath=testpath)



    # Init
    testutil.write('A/fileA',text='fileA')
    testutil.write('A/fileB',text='fileB')

    # copy over
    testutil.copy_tree()

    # Start it
    config = testutil.get_config(remote=remote)
    testutil.init(config)

    # Apply actions
    testutil.write('A/fileA',text='Aaa',mode='a') # append it
    testutil.write('B/fileB',text='B',mode='a')

    testutil.write('A/fileA_new',text='fileA_new')
    testutil.write('B/fileB_new',text='fileB_new')

    # Sync
    if AB == 'A':
        mode = 'push'
    else:
        mode='pull'

    if all_:
        mode += '_all'

    testutil.run(config,mode=mode)
    # Check it -- Only need to check A
    diff = testutil.compare_tree()

    if all_:
        assert len(diff) == 1
    else:
        assert len(diff) == 2

    if AB == 'A':
        assert (u'missing_inA', u'fileB_new') in diff
        if not all_: # This change should be overwritten
            assert ('disagree', 'fileB') in diff
    else:
        assert (u'missing_inB', u'fileA_new') in diff
        if not all_:# This change should be overwritten
            assert ('disagree', 'fileA') in diff


@pytest.mark.parametrize("remote,AB,all_", list(itertools.product(remotes,['A','B'],[True,False])))
def test_move_overwrite(remote,AB,all_):
    """ A file move that will overwrite on recieveing end. Check backups """
    testpath = os.path.join(os.path.abspath(os.path.split(__file__)[0]),
            'test_dirs','pp','test_move_overwrite')
    try:
        shutil.rmtree(testpath)
    except:
        pass
    os.makedirs(testpath)
    testutil = testutils.Testutils(testpath=testpath)



    # Init
    testutil.write('A/fileA0',text='fileA0')
    testutil.write('A/fileB0',text='fileB0')

    # copy over
    testutil.copy_tree()

    # Start it
    config = testutil.get_config(remote=remote)
    testutil.init(config)

    # Apply actions
    testutil.write('A/fileA1',text='fileA1')
    testutil.move('A/fileA0','A/fileB1')

    testutil.write('B/fileB1',text='fileB1')
    testutil.move('B/fileB0','B/fileA1')

    # Sync
    if AB == 'A':
        mode = 'push'
    else:
        mode='pull'

    if all_:
        mode += '_all'

    testutil.run(config,mode=mode)

    # Check it -- Only need to check A
    diff = testutil.compare_tree()

    if AB == 'A': # Check backups in B
        backB = glob(os.path.join(testpath,'B','.PyFiSync','backups','20*'))[0]
        if all_:
            # This file gets backed up before move but then the later upload
            # tries to overwrite. fileB1 is not changed so it doesn't happen
            # when not using --all
            assert open(os.path.join(backB,'fileB1.0')).read().strip() == 'fileA0'

        # Overwritten file should be backed up
        assert open(os.path.join(backB,'fileB1')).read().strip() == 'fileB1'

        # Backed up file on transfer
        assert open(os.path.join(backB,'fileA1')).read().strip() == 'fileB0'
    else:
        backA = glob(os.path.join(testpath,'A','.PyFiSync','backups','20*'))[0]
        if all_:
            # This file gets backed up before move but then the later upload
            # tries to overwrite. fileA1 is not changed so it doesn't happen
            # when not using --all
            assert open(os.path.join(backA,'fileA1.0')).read().strip() == 'fileB0'

        # Overwritten file should be backed up
        assert open(os.path.join(backA,'fileA1')).read().strip() == 'fileA1'

        # Backed up file on transfer
        assert open(os.path.join(backA,'fileB1')).read().strip() == 'fileA0'






if __name__=='__main__':
    for remote,AB,all_ in itertools.product(remotes,['A','B'],[True,False]):
        print(remote,AB,all_)
        test_mod_new_different(remote,AB,all_)
        test_move_overwrite(remote,AB,all_)
# 

