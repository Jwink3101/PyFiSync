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
from io import open
import itertools
import argparse
import copy
from threading import Thread
import getpass

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

class configparser(object):
    """This will eventually be the configuration"""
    default_path = os.path.join(os.path.dirname(__file__),'config_template.py')
    def __init__(self,sync_dir=None,remote=None):

        self.sync_dir = sync_dir
        
        # These must be a lists!
        self._listattr =  ['move_attributesA','move_attributesB',
                           'prev_attributesA','prev_attributesB',
                           'excludes']

        # These must be changed from the defaults (They are not parsed in 
        # defaults and must be set later)
        self._reqattr = ['pathB']
        if sync_dir is not None:
            # We parse the input twice since we want to know the remote before
            # parsing defaults. But, we do not want to prompt for a password
            # twice so we tell it to ignore it here
            _tmp = self.parse(getdict=True,pw=False)
            self.pathA = os.path.abspath(sync_dir)
            if 'remote' not in _tmp:
                print('ERROR: Must specify a remote. Must update config file for PyFiSync',file=sys.stderr)
                sys.exit(2)
            self.parse_defaults(remote=_tmp['remote'])
            self.parse()
        else:
            self.parse_defaults(remote=remote)
        
        # Some special things
        self.excludes = list(set(self.excludes + ['.PBrsync/','.PyFiSync/']))

    def parse_defaults(self,remote=None):
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
        
        if remote is None:
            remote = 'rsync'
        txt = self._filterconfig(txt,remote=remote)
        
        exec_(txt,config)       
        
        for key,val in config.items():
            # Unike `parse`, there is no need to check for lists since 
            # this isn't user code
            if key in self._reqattr:
                continue
            setattr(self,key,val)

    @property
    def configpath(self):
        for ext in ['','.py']:
            config_path = os.path.join(self.sync_dir,'.PyFiSync','config'+ext)
            if os.path.exists(config_path):
                break
        else:
            sys.stderr.write('ERROR Could not find config file. Did you run `init`?\n')
            sys.exit(2)    
        return config_path

    def parse(self,getdict=False,pw=True):
        none = lambda *a,**k:None
        config = dict(pwprompt=getpass.getpass if pw else none)
        with open(self.configpath,'rt') as F:
            txt = F.read()
            exec_(txt,config)    
        if getdict:
            return config
        
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
    def config_example(cls,remote='rsync'):
        """ Return an example configuration"""
        with open(cls.default_path,'rt') as F:
            config = F.read()
        return configparser._filterconfig(config,remote=remote)
   
    @staticmethod
    def _filterconfig(config,remote='rsync'):   
        # remove anything that is not part of this remote
        from .remote_interfaces import REMOTES
        if remote not in REMOTES:
            raise ValueError('Not a valid remote')
        for rem in REMOTES:
            if rem == remote:
                repr = r'\1'
            else:
                repr = ''
            regex = r'^#[\ \t]*?\<FLAG\>(.*?)#[\ \t]*?\<[\/\\]FLAG\>'.replace('FLAG',rem)
            config = re.sub(regex,repr,config,flags=re.MULTILINE|re.DOTALL)
        return config

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
            csum = zlib.adler32(buf,csum)
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
    if isinstance(txt,unicode):
        return txt
    if hasattr(txt,'decode'):
        return txt.decode('utf8')

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


def move_txt(src,dst):
    """Apply some pretty printing to moves"""
    _fjoin = lambda s: '' if len(s) == 0 else (os.sep if s[0] == '' else '') + os.sep.join(s)

    # Split as sep and add it in
    srcs = src.split(os.sep)
    dsts = dst.split(os.sep)
    
    comb = []
    
    for s,d in zip(srcs,dsts):
        if s != d:
            break
        comb.append(s)
    sremain = _fjoin(srcs[len(comb):])
    dremain = _fjoin(dsts[len(comb):])
    comb = _fjoin(comb)

    if len(comb)>2 and len(sremain)>0 and len(dremain)>0: 
        # Just so that we aren't doing this for nothing
        mtxt = comb + os.sep + '{' + sremain + ' --> ' + dremain + '}'
    else:
        mtxt = '{src:s} --> {dst:s}'.format(src=src,dst=dst)
    
    while os.sep*2 in mtxt:
        mtxt = mtxt.replace(os.sep*2,os.sep)
    
    return mtxt
    


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
            
def RFC3339_to_unix(timestr):
    """
    Parses RFC3339 into a unix time
    """
    d,t = timestr.split('T')
    year,month,day = d.split('-')
    
    t = t.replace('Z','-00:00') # zulu time
    t = t.replace('-',':-').replace('+',':+') # Add a new set
    hh,mm,ss,tzhh,tzmm = t.split(':')
    
    offset = -1 if tzhh.startswith('-') else +1
    tzhh = tzhh[1:]
    
    try:
        ss,micro = ss.split('.')
    except ValueError:
        ss = ss
        micro = '00'
    micro = micro[:6] # Python doesn't support beyond 999999
    
    dt = datetime.datetime(int(year),int(month),int(day),
                           hour=int(hh),minute=int(mm),second=int(ss),
                           microsecond=int(micro))
    unix = (dt - datetime.datetime(1970,1,1)).total_seconds()
    
    # Account for timezone which counts backwards so -=
    unix -= int(tzhh)*3600*offset
    unix -= int(tzmm)*60*offset
    return unix    
    
def imitate_hash(mydict):
    """
    Imitate the hash. This is crude and imperfect but fine for replacing
    a missing hash
    """
    hasher = hashlib.sha1()
    hasher.update(repr(mydict).encode('utf8'))
    return  hasher.hexdigest()
    

def bytes2human(byte_count,base=1024,short=True):
    """
    Return a value,label tuple
    """
    if base not in (1024,1000):
        raise ValueError('base must be 1000 or 1024')
    
    labels = ['kilo','mega','giga','tera','peta','exa','zetta','yotta']
    name = 'bytes'
    if short:
        labels = [l[0] for l in labels]
        name = name[0]
    labels.insert(0,'') 
    
    best = 0
    for ii in range(len(labels)): 
        if (byte_count / (base**ii*1.0)) < 1:
            break
        best = ii
    
    return byte_count / (base**best*1.0),labels[best] + name  

########################### six extracted codes ###########################
# This is pulled from the python six module (see links below) to work 
# around some python 2.7.4 issues
# Links:
#   https://github.com/benjaminp/six
#   https://pypi.python.org/pypi/six
#   http://pythonhosted.org/six/
##############################################################################
# Copyright (c) 2010-2018 Benjamin Peterson
# 
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
# 
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
# 
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
# THE SOFTWARE.
#############################################################################
if sys.version_info[0]>2:
    exec('exec_ = exec')
else:
    def exec_(_code_, _globs_=None, _locs_=None):
        """Execute code in a namespace."""
        if _globs_ is None:
            frame = sys._getframe(1)
            _globs_ = frame.f_globals
            if _locs_ is None:
                _locs_ = frame.f_locals
            del frame
        elif _locs_ is None:
            _locs_ = _globs_
        exec("""exec _code_ in _globs_, _locs_""")



    
    
