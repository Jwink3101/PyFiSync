#!/usr/bin/env python
from __future__ import unicode_literals,print_function

import pytest #with pytest.raises(ValueError):...

try:
    from . import testutils
except (ValueError,ImportError):
    import testutils
testutils.add_module()

from PyFiSync import utils,PFSwalk
from PyFiSync import main as PyFiSync # Need to fix
DictTable = main.DictTable

import os
import sys
import shutil


def _file_list(path,config=None):
    if config is None:
        config = utils.configparser()
    log = utils.logger(silent=True,path=None)
    _tmp = PFSwalk.file_list(path,config,log)
    return _tmp.files()



def test_untouched():
    """ File is not touched """
    name = 'test_untouched'
    testpath = os.path.join(os.path.abspath(os.path.split(__file__)[0]),
            'test_dirs','move_tests',name)
    try:
        shutil.rmtree(testpath)
    except:
        pass
    os.makedirs(testpath)
    testutil = testutils.Testutils(testpath=testpath)


    # Init
    testutil.write('file1.txt',text='test1')

    prev_attr = ['ino','path']
    move_attr = ['ino','birthtime']
    
    # Get and inject configs
    config = testutil.get_config()
    PyFiSync.config = config

    # old list
    files_old = DictTable(_file_list(testpath,config))
    
    # Apply actions
    
    
    # new list and track
    files_new = DictTable(_file_list(testpath,config))
    PyFiSync.file_track(files_old,files_new,prev_attr,move_attr)
    
    # Check
    assert {'path':'file1.txt','untouched':True,'prev_path':'file1.txt'} in files_new

def test_move(): # This used to be test 01
    """ File Moved. inode and birthtime tracking """
    name = 'test_move'
    testpath = os.path.join(os.path.abspath(os.path.split(__file__)[0]),
            'test_dirs','move_tests',name)
    try:
        shutil.rmtree(testpath)
    except:
        pass
    os.makedirs(testpath)
    testutil = testutils.Testutils(testpath=testpath)


    # Init
    testutil.write('file1.txt',text='test1')

    prev_attr = ['ino','path']
    move_attr = ['ino','birthtime']
    
    # Get and inject configs
    config = testutil.get_config()
    PyFiSync.config = config

    # old list
    files_old = DictTable(_file_list(testpath,config))
    
    # Apply actions
    testutil.move('file1.txt','file2.txt')
    
    # new list and track
    files_new = DictTable(_file_list(testpath,config))
    PyFiSync.file_track(files_old,files_new,prev_attr,move_attr)
    
    # Check
    assert {'path':'file2.txt','moved':True,'prev_path':'file1.txt'} in files_new

@pytest.mark.parametrize("mode", ['birthtime','size'])
def test_move_mod(mode):
    """ test modification after move with different modes"""
    name = 'test_move_mod_' + mode
    testpath = os.path.join(os.path.abspath(os.path.split(__file__)[0]),
            'test_dirs','move_tests',name)
    try:
        shutil.rmtree(testpath)
    except:
        pass
    os.makedirs(testpath)
    testutil = testutils.Testutils(testpath=testpath)


    # Init
    testutil.write('file1.txt',text='test1')

    prev_attr = ['ino','path']
    move_attr = ['ino'] + [mode]
    
    # Get and inject configs
    config = testutil.get_config()
    PyFiSync.config = config

    # old list
    files_old = DictTable(_file_list(testpath,config))
    
    # Apply actions
    testutil.move('file1.txt','file2.txt')
    testutil.write('file2.txt',text='mod',mode='a')
    
    # new list and track
    files_new = DictTable(_file_list(testpath,config))
    PyFiSync.file_track(files_old,files_new,prev_attr,move_attr)
    
    # Check
    if mode == 'birthtime':
        assert {'path':'file2.txt','moved':True,'prev_path':'file1.txt'} in files_new
    elif mode == 'size':
        assert not {'path':'file2.txt','moved':True,'prev_path':'file1.txt'} in files_new
        assert {'path':'file2.txt','new':True,'prev_path':None} in files_new
    else:
        assert False
    

def test_no_moves():
    """ tests using name as the only attribute"""
    name = 'pathonly'
    testpath = os.path.join(os.path.abspath(os.path.split(__file__)[0]),
            'test_dirs','move_tests',name)
    try:
        shutil.rmtree(testpath)
    except:
        pass
    os.makedirs(testpath)
    testutil = testutils.Testutils(testpath=testpath)


    # Init
    testutil.write('file1.txt',text='test1')
    testutil.write('file2.txt',text='test2')
    testutil.write('file3.txt',text='test3')
    testutil.write('file4.txt',text='test4')

    prev_attr = ['path']
    move_attr = ['path']
    
    # Get and inject configs
    config = testutil.get_config()
    PyFiSync.config = config

    # old list
    files_old = DictTable(_file_list(testpath,config))
    
    # Apply actions
    testutil.move('file2.txt','file22.txt')
    testutil.move('file3.txt','file33.txt')
    testutil.write('file3.txt',text='testnew',mode='w')
    testutil.remove('file4.txt')
    testutil.write('file5.txt',text='test5',mode='w')
    
    
    # new list and track
    files_new = DictTable(_file_list(testpath,config))
    PyFiSync.file_track(files_old,files_new,prev_attr,move_attr)
    
    files_old.alwaysReturnList = True
    files_new.alwaysReturnList = True
    
    ## Check
    
    # Even though 22 and 33 were moves they should show as new
    # File5 should also be new (since it really is)
    t1db = DictTable( files_new(new=True))
    assert len(t1db) == 3
    assert {'path':'file22.txt'} in t1db
    assert {'path':'file33.txt'} in t1db
    assert {'path':'file5.txt'} in t1db
    assert len(list(t1db(new=True))) == 3
    
    # file 3 should show as being modified and not new
    f3 = files_new.query_one(path='file3.txt')
    assert not f3['new'] 
    assert testutil.read('file3.txt') == 'testnew'
    
    # file2 should be deleted even though moved
    assert files_old.query_one(path='file2.txt')['deleted'] 
    
if __name__=='__main__':
    test_no_moves()# 
#     test_move()
#     test_move_mod()
    
    
    
    
    
    
    
    
    
    
    
    
