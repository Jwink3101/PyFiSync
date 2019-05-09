#!/usr/bin/env python
from __future__ import unicode_literals,print_function
#from io import open

import os
import sys
import random
import string
import shutil
from pprint import pprint

def add_module():
    
    path = os.path.abspath(__file__)
    path = os.path.split(os.path.split(path)[0])[0] # Move up one
    sys.path.insert(0,path)

add_module()
import PyFiSync
import PyFiSync.utils
utils = PyFiSync.utils

MAX_TIME_MOD = 500;

class Testutils(object):
    def __init__(self,testpath=None):
        self.testpath = testpath

    def modtime_all(self):
        """ modified all of the times """
        random.seed(4474)
        pathA = os.path.join(self.testpath,'A')
        pathB = os.path.join(self.testpath,'B')

        for dirpath, dirnames, filenames in os.walk(pathA):
            for f in filenames:
                change_time(os.path.join(dirpath,f),random.randint(-100*MAX_TIME_MOD,-(MAX_TIME_MOD+2)))
        try:
            os.makedirs(pathB)
        except:
            pass


    def write(self,path,time_adj=None,mode='w',text=None):
        """Write or append a file"""
        path = os.path.join(self.testpath,path)
        directory = os.path.split(path)[0]
        try:
            os.makedirs(directory)
        except OSError:
            pass

        if text is None:
            text = randstr()

        text += '\n'

        if mode == 'a' and time_adj == 0:
            time_adj = 1

        with open(path,mode) as F:
            F.write(text)

        if time_adj is None:
            change_time(path,random.randint(5,MAX_TIME_MOD))
        elif time_adj != 0:
            change_time(path,time_adj)
        

    def exists(self,path):
        path = os.path.join(self.testpath,path)
        return os.path.exists(path)
    def move(self,src,dst):
        """Move and makedirs if needed"""
        src = os.path.join(self.testpath,src)
        dst = os.path.join(self.testpath,dst)
        directory = os.path.split(dst)[0]
        try:
            os.makedirs(directory)
        except OSError:
            pass

        shutil.move(src,dst)

    def remove(self,path):
        """remove and makedirs if needed"""
        path = os.path.join(self.testpath,path)
        if os.path.isfile(path):
            os.remove(path)
        if os.path.isdir(path):
            shutil.rmtree(path)

    def read(self,item):
        path = os.path.join(self.testpath,item)

        assert os.path.exists(path), "file doesn't exist '%s'" % item

        with open(path) as F:
            return F.read().strip()
    
    def tree(self,path):
        files = []
        for dirpath, dirnames, filenames in os.walk(path,followlinks=True):
            for d in ['.PyFiSync','.git']:
                try:
                    dirnames.remove(d)
                except ValueError:
                    pass

            files.extend(os.path.join(dirpath,filename) for filename in filenames)
            if len(dirnames) == len(filenames) == 0:
                files.append(os.path.join(dirpath,'>>EMPTY<<'))
        return files
        
    def compare_tree(self):
        """ All file systems are identical"""
        result = []
        
        pathA = os.path.join(self.testpath,'A')
        pathB = os.path.join(self.testpath,'B')

        filesA = [os.path.relpath(f,pathA) for f in self.tree(pathA)]
        filesB = [os.path.relpath(f,pathB) for f in self.tree(pathB)]

        filesAB = set(filesA).union(filesB)
        for fileAB in sorted(list(filesAB)):

            fileA = os.path.join(self.testpath,'A',fileAB)
            fileB = os.path.join(self.testpath,'B',fileAB)
            try:
                fileAtxt = open(fileA).read()
            except IOError:
                result.append( ('missing_inA',fileAB) )
                continue
            
            try:
                fileBtxt = open(fileB).read()
            except IOError:
                result.append( ('missing_inB',fileAB) )
                continue

            if not fileAtxt == fileBtxt:
                result.append( ('disagree',fileAB))
            
        return result

    def get_config(self,remote=False):
        if remote == 'rclone':
            config = utils.configparser(remote='rclone')
            config.move_attributesB = ['hash.SHA-1']
        else:
            config = utils.configparser(remote='rsync')
            if remote:
                config.userhost = os.environ['USER'] + '@localhost'
                if remote == 'python2':
                    config.remote_program = 'python2'
                elif remote == 'python3':
                    config.remote_program = 'python3'
            else:
                config.userhost = ''
            # This will need to change when/if there is no longer the PyFiSync.py
            # file (using, say, entry-points)
            config.PyFiSync_path = os.path.normpath(os.path.join(os.path.dirname(__file__),'..','PyFiSync.py'))        
        
        config.excludes += ['.DS_Store','.git/','Thumbs.db']
        config.pathA = os.path.join(self.testpath,'A')
        config.pathB = os.path.join(self.testpath,'B')

        return config
        
    def write_config(self,config):
        if self.testpath is None:
            return
        config_path = os.path.join(self.testpath,'A','.PyFiSync','config')
        config_file = open(config_path,'w')
        
        for key,val in config.__dict__.items():
            if key.startswith('_') or key == 'pwprompt':
                continue
            config_file.write(key + ' = ' )
            pprint(val,stream=config_file)
        
        config_file.close()    

    def init(self,config):
        pathA = os.path.join(self.testpath,'A')
        pathB = os.path.join(self.testpath,'B')
    
        PyFiSync.cli(['init',pathA])
        self.write_config(config)
        PyFiSync.cli(['reset','--force',pathA])
        PyFiSync.cli(['sync',pathA])
        # At init, every file's mod time was changed to be at least -(MAX_TIME_MOD+2)
        # so we do not need to modify the last_run
        

    def run(self,config,mode='sync',silent=False,flags=tuple()):
        pathA = os.path.join(self.testpath,'A')
        pathB = os.path.join(self.testpath,'B')

        self.write_config(config)
        if mode == 'sync':
            cmd = ['sync'] + list(flags) + [pathA]
            PyFiSync.cli(cmd)
        
    
def randstr(N=10):
    return ''.join(random.choice(string.lowercase+'0123456789') for _ in xrange(10))

def change_time(path,time_adj):
    """ Change the time on a file path"""
    try:
        stat = os.stat(path)
    except OSError as E:
        print('path {:s} does not exist'.format(E))

    os.utime(path,(stat.st_atime+time_adj,stat.st_mtime+time_adj))










