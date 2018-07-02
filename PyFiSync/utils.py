#!/usr/bin/env python
"""
Collection of utilities I have written along the way that may be useful

parallel_map -- Improved multiprocessing.map. See references therein
"""
from __future__ import division, print_function, unicode_literals, absolute_import

import hashlib
import os
import sys
import datetime
import re
import zlib
import base64
from io import open
import itertools
import argparse
import copy
from threading import Thread

try:
    from queue import Queue
except ImportError:
    from Queue import Queue
    

if sys.version_info >= (3,):
    unicode = str
    xrange = range

class logger(object):
    def __init__(self,path=None,silent=False):

        self.silent = silent
        self.path = path

        if path is not None:
            filepath = os.path.abspath(os.path.join(path,'.PyFiSync','logs'))
            self.path = filepath
            try:
                os.makedirs(filepath)
            except OSError:
                pass # Already exists
            self.filepath = os.path.join(filepath,
                datetime.datetime.now().strftime('%Y-%m-%d_%H%M%S') + '.log')

            # Write the file with nothing but this will overwrite it
            with open(self.filepath,'w') as F:
                F.write(' ')


        self.space = 0
        self.prepend = ''
    def add(self,text,end=u'\n',return_out=False):

        if text is None:
            return
        text = text.split('\n')
        out = []
        for line in text:
            out.append(self.prepend + ' '*self.space + line)

        out = '\n'.join(out)
        out = to_unicode(out)
        
        if not self.silent:
            try:
                print(out,end=end)
            except UnicodeEncodeError: # This is a bit hacky but I think there are issues with remove queues and printing
                print(out.encode('utf-8'),end=end.encode('utf8'))

        out = out.encode('utf-8')

        if self.path is not None:
            with open(self.filepath,'ba') as F:
                F.write(out + end.encode('utf-8'))
        
        if return_out:
            return out
    
    def add_err(self,*A,**K):
        """
        Same as add except that it will write it to stderr instead of with 'print'
        """
        silent0 = self.silent
        self.silent = True
        
        out = self.add(return_out=True,*A,**K)
        
        self.silent = silent0
        
        # Now print it to stderr (even if silent!)
        end = K.get('end',u'\n')
        out = to_unicode('\n') + to_unicode(out) + to_unicode(end)
        try:
            sys.stderr.write(out)
        except UnicodeEncodeError: # This is a bit hacky but I think there are issues with remove queues and printing      
            sys.stderr.write(out.encode('utf-8'))
            
    def add_close(self):
        if self.path is None:
            return
        self.line()
        self.add('Log saved in {path:s}'.format(path=self.filepath))

    def line(self):
        self.add('='*50,end='\n')

# This is the main configuration parser. It will parse upon creation, though
# in the future, the design will change that this will be an object that gets
# parser later.
class configparser(object):
    """This will eventually be the configuration"""
    default_path = os.path.join(os.path.dirname(__file__),'config_template.py')
    def __init__(self,sync_dir=None):

        self.sync_dir = sync_dir
        
        # These must be a lists!
        self._listattr =  ['move_attributesA','move_attributesB',
                           'prev_attributesA','prev_attributesB',
                           'excludes']

        # These must be changed from the defaults (They are not parsed in 
        # defaults and must be set later)
        self._reqattr = ['pathB']

        self.parse_defaults()
        
        if sync_dir is not None:
            self.pathA = os.path.abspath(sync_dir)
            self.parse()

        # Some special things
        self.excludes = list(set(self.excludes + ['.PBrsync/','.PyFiSync/']))

    def parse_defaults(self):
        """
        Parse all defaults from the template except those in self._reqattr
        """
        
        config = dict()
        try:
            with open(self.default_path,'rt') as F:
                txt = F.read()
        except:
            # This is a hack for when it is in an egg file. I need to figure
            # out a better way
            import zipfile
            _zf = zipfile.ZipFile(self.default_path[:self.default_path.find('/PyFiSync/config_template.py')])
            txt = _zf.read('PyFiSync/config_template.py')
            txt = to_unicode(txt)
        exec(txt,config)       
        
        for key,val in config.items():
            # Unike `parse`, there is no need to check for lists since 
            # this isn't user code
            if key in self._reqattr:
                continue
            setattr(self,key,val)
    
    def parse(self):
        for ext in ['','.py']:
            config_path = os.path.join(self.sync_dir,'.PyFiSync','config'+ext)
            if os.path.exists(config_path):
                break
        else:
            sys.stderr.write('ERROR Could not find config file. Did you run `init`?\n')
            sys.exit(2)

        config = dict()
        with open(config_path,'rt') as F:
            txt = F.read()
            exec(txt,config)    
        
        for key,val in config.items():
            if key in self._listattr and not isinstance(val,list):
                if isinstance(val,(set,tuple)):
                    val = list(val)
                else:
                    val = [val]
            setattr(self,key,val)

        # Some minor adjustments        
        self.mod_resolution = float(self.mod_resolution)
        # Aliases
        if hasattr(self,'symlinks'):
            self.copy_symlinks_as_links = not self.symlinks

    @classmethod
    def config_example(cls):
        """ Return an example configuration"""
        with open(cls.default_path,'rt') as F:
            return F.read()

def sha1(filepath,BLOCKSIZE=2**20):
    """
    http://pythoncentral.io/hashing-files-with-python/
    
    2**20: 1 mb
    2**12: 4 kb
    
    """
    hasher = hashlib.sha1()
    with open(filepath, 'rb') as afile:
        buf = afile.read(BLOCKSIZE)
        while len(buf) > 0:
            hasher.update(buf)
            buf = afile.read(BLOCKSIZE)
    return hasher.hexdigest()

def adler(filepath,BLOCKSIZE=2**20):
    """
    Create an additive adler32 checksum. Faster than sha1.

    From the documentation:
     > Changed in version 3.0: Always returns an unsigned value.
     > To generate the same numeric value across all Python versions and
     > platforms, use adler32(data) & 0xffffffff.
    """
    csum = 1
    with open(filepath, 'rb') as afile:
        buf = afile.read(BLOCKSIZE)
        while len(buf) > 0:
            csum = zlib.crc32(buf,csum)
            buf = afile.read(BLOCKSIZE)
    csum = csum & 0xffffffff
    return csum

def to_unicode(txt,verbose=False):
    """
    Convert input to unicode if it can!
    """
    for objtype in [list,tuple,set]:
        if isinstance(txt,objtype):
            return objtype(to_unicode(a) for a in txt)
    
    if isinstance(txt,unicode): # JUST unicode in case py2 and bytes <==> str
        return txt
    
    try:
        return unicode(txt,'utf8','strict')
    except:
        pass
   
    try:
        import chardet
        enc = chardet.detect(txt)['encoding']
        return unicode(txt,encoding,'strict')
    except:
        pass
    
    for err,enc in itertools.product(['replace','ignore'],['utf8']):
        return unicode(txt,enc,err)
    
    return txt

class RawSortingHelpFormatter(argparse.RawDescriptionHelpFormatter):
    """
    argparse help formatter that uses RawDescriptionHelpFormatter but
    alphebatizes by the long-form action and lower case
    
    Based on https://stackoverflow.com/a/12269143/3633154
    WARNING: Uses non-documented behavior but it *should* be fine
    """
    # override parent
    def add_arguments(self, actions):
        actions = sorted(actions, key=self._sortkey)
        super(RawSortingHelpFormatter, self).add_arguments(actions)
    
    # new
    def _sortkey(self,action):
        """
        Sorter for optional strings. Sort by lower case of long 
        argument otherwise short
        """
        options = copy.copy(action.option_strings)
        options.sort(key=self._count_leading_dash)
        return tuple(opt.lower() for opt in options)
   
    def _count_leading_dash(self,item):
        count = 0
        while item.startswith('-'):
            count += -1
            item = item[1:]
        return count


class ReturnThread(Thread):
    """
    Like a regular thread except when you `join`, it returns the function
    result. And it assumes a target is always passed
    """
    
    def __init__(self,**kwargs):
        self.target = kwargs.pop('target',False)
        if self.target is False:
            raise ValueError('Must specify a target')
        self.q = Queue()
        super(ReturnThread, self).__init__(target=self._target,**kwargs)
    
    def _target(self,*args,**kwargs):
        self.q.put( self.target(*args,**kwargs) )
    
    def join(self,**kwargs):
        super(ReturnThread, self).join(**kwargs)
        res = self.q.get()
        self.q.task_done()
        self.q.join()
        return res