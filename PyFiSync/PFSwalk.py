#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Main tool for walking a directory that is tuned to PyFiSync's needs and 
uses scandir if it can!
"""

from __future__ import division, print_function, unicode_literals
from io import open

import sys
import os
import fnmatch
import subprocess
import json

try:
    from os import scandir as _scandir
except ImportError:
    try:
        from scandir import scandir as _scandir
    except ImportError:
        _scandir = None

try:
    from itertools import imap as map
    from itertools import izip as zip 
except ImportError: # python >2
    pass

from itertools import repeat
from functools import partial

from . import utils
from . import ldtable
ldtable = ldtable.ldtable

def fnmatch_mult(name,patterns):
    """
    will return True if name matches any patterns
    """
    return any(fnmatch.fnmatch(name,pat) for pat in patterns)


class file_list:
    def __init__(self,path,config,log,
            attributes=(),
            empty='store',use_hash_db=True):
        """
        Main interface to the walk. the final list will
        be in the attribute file_list.
        
        Empty:
            'store':    stores a list of empty directories
            'remove':   Deletes all empty directories if (and only if) they 
                        were *not* empty before. Also removes stored list
            'reset':    Removes stored list
        """
        self.path = path
        self.config = config
        self.log = log
        self.attributes = attributes
        self.use_hash_db = use_hash_db
        
        self.empty = empty
        self.empties = set()
        
        self._set_exclusions()

    def files(self,parallel=False):
        """
        Process the files. 
        if parallel is False or <= 1 will run hashes serially
        Otherwise specify True to use all cores or specify a number
        """
        
        # The hash_db is essentially the same as the filelist but it does
        # *not* need to be the latest a certain sync-pair has seen. It should
        # just be the latest parse of the files. The general idea is that
        # if the ['mtime','path','size'] are identical, no need to recalculate
        # the sha1 or adler of the file.
        
        self.hashes = any(a in utils.HASHFUNS for a in self.attributes)
        
        if self.hashes:
            self.load_hash_db()
        
        if parallel and self.hashes:
            import multiprocessing as mp
            if not isinstance(parallel,int):
                parallel = mp.cpu_count()
            pool = mp.Pool(parallel)
            _map = partial(pool.imap,chunksize=10)
        else:
            pool = None
            _map = map 
            
        # Set this up as a chain of generators
        items = self._walk(self.path)   # Tuples of DirEnty,rootpath
        items = map(self._file_info,items)   # Dictionaries
        
        ## Here is where we add hashes
        for attribute in self.attributes:
            if attribute in utils.HASHFUNS:
                items = _map(partial(self.add_hash,hashname=attribute),zip(items,repeat(self.path)))
         
         # Run it!
        result = list(items)
     
        if pool is not None:
            pool.close()
        self.process_empty()
     
        if self.hashes:
            self.save_hash_db(result)
     
        return result   
    def process_empty(self):
        """
        Process empties based on self.empty and self.empties
        """
        empty_path = os.path.join(self.path,'.PyFiSync','empty_dirs')
        if self.empty == 'reset':
            try:
                os.remove(empty_path)
            except OSError:
                pass
        elif self.empty == 'store':
            try:
                os.makedirs(os.path.dirname(empty_path))
            except OSError:
                pass
            empties = list(self.empties)    
            with open(empty_path,'wt',encoding='utf8') as fobj:
                fobj.write(utils.to_unicode(json.dumps(empties,ensure_ascii=False)))
        elif self.empty == 'remove':
            with open(empty_path,'rt') as fobj:
                prev = set(json.loads(fobj.read()))
            # Remove the remaining empty dirs
            empties = self.empties - prev # both sets
            
            # Loop through empty dirs and remove. Do it longest to shortest so
            # that nested empty dirs are removed
            empties = sorted(empties,key=lambda a: (-len(a),a.lower()))
            for empty_dir in empties:
                try:
                    os.removedirs(empty_dir)
                except OSError:
                    pass # May just be empty due to exclusion

    def _set_exclusions(self):
        """
        Set up and control exclusion
        
        Note that we separate those with glob patterns from those without
        so that those without can be checked via O(1) set while those with
        will go through fnmatch. If there is a false positive for glob, 
        it won't change the final outcome; it will just be slower on that
        single run.
        """
        GLOBS = '*?[]!'
        self.all_excludes = set(self.config.excludes)
        
        self.exclude_file_full = set()
        self.exclude_file      = set()
        
        # non-glob patters are done separately since the exclude can be checked faster
        # using a set `in`  O(1) instead of fnmatch O(n) (or worse)
        self.exclude_file_full_no_glob   = set()
        self.exclude_file_no_glob        = set()
        
        
        self.exclude_dirs_full = set()
        self.exclude_dirs      = set()
        

        for e in self.all_excludes:
            e = utils.to_unicode(e)
            if e.startswith('/'): # Full
                if e.endswith('/'):
                    self.exclude_dirs_full.add(e)
                elif any(g in e for g in GLOBS):
                    self.exclude_file_full.add(e)
                else:
                    self.exclude_file_full_no_glob.add(e)
            else:
                if e.endswith('/'):
                    self.exclude_dirs.add(e)
                elif any(g in e for g in GLOBS):
                    self.exclude_file.add(e)
                else:
                    self.exclude_file_no_glob.add(e)
    
    def _walk(self,path,_d=0):
        """
        Yields tuples of (DirEntry,relpath) since relpath is already computed
        and avoids recompute
        """
        if path.endswith('/'):
            path = path[:-1] # Remove trailing / so we can avoid os.path.join

        
        # We only care if anything was returned; directory or file
        # Note that based on the nested nature of this, directories are trans-
        # versed deep first so if the end is empty (and nothing from them was
        # returned) to empty will propagate upwards and will be deleted 
        # if applicable.
        no_returns = True 
        for item in scandir(path):
            
            itemname = utils.to_unicode(item.name)
            relpath = _relpath(item.path,self.path)
            if item.is_dir(follow_symlinks=True): # Always follow directory links
                
                if fnmatch_mult(itemname +'/',self.exclude_dirs):
                    continue
                
                if fnmatch_mult('/'+relpath +'/',self.exclude_dirs_full):
                    continue
                
                for subitem in self._walk(item.path,_d=_d+1):
                    no_returns = False
                    yield subitem
            
            elif item.is_file():
                if itemname in self.exclude_file_no_glob:
                    continue
            
                if '/'+relpath in self.exclude_file_full_no_glob:
                    continue
            
                if fnmatch_mult(itemname,self.exclude_file):
                    continue

                if fnmatch_mult('/'+relpath,self.exclude_file_full):
                    continue
                
                no_returns = False
                yield item,relpath
            
            elif item.is_symlink(): # Must be broken!
                self.log.add_err('ERROR: Could not find information on {}\n'.format(relpath) +
                                 '       May be a BROKEN link. Skipping\n')
                

        # Was it empty? Note that if there is nothing returned because
        # of exclusions, it is still considered empty. 
        if no_returns:
            self.empties.add(path)
            
    def _file_info(self,item_relpath):
        item,relpath = item_relpath
    
        stat_attributes = ['ino','size','mtime','birthtime']
        file = {'path':relpath}
        
        
        follow_symlinks = not self.config.copy_symlinks_as_links

        try:
            stat = item.stat(follow_symlinks=follow_symlinks)
        except OSError as E:
            self.log.add_err('\n' + 
                             'ERROR: Could not find information on {}\n'.format(relpath) +
                             '         May be a BROKEN link.\n MSG: {}\nskipping...\n'.format(E))
            return
            
        for attrib in stat_attributes:
            try:
                file[attrib] = getattr(stat,'st_'+attrib)
            except AttributeError:
                file[attrib] = 0.0

        # if it cannot get mtime, set to future:
        if file['mtime'] == 0: file['mtime'] = time.time()+3600

        return file
    
    def filter_old_list(self,old_list):
        """
        Use the exclusions to filter the old lists
        """
        out_list = []
        for ix,file in enumerate(old_list):
            dirname,filename = os.path.split(file['path'])

            # file name only -- w/o glob
            if filename in self.exclude_file_no_glob:
                continue
                
            # file name only -- w/ glob
            if fnmatch_mult(filename,self.exclude_file):
                continue

            # Full file
            fullfile = '/' + file['path']
            
            if fullfile in self.exclude_file_full_no_glob:
                continue
                
            if fnmatch_mult(fullfile,self.exclude_file_full):
                continue
                
            # Dirnames. Need to test the full build up
            
            #dname = []
            
            # dirname only -- test
            dname_list = []
            dflag = False
            for dname in dirname.split('/'):
                dname_list.append(dname)
                if fnmatch_mult(dname + '/',self.exclude_dirs):
                    dflag = True
                    break
                # Full dir
                if fnmatch_mult('/'+'/'.join(dname_list)+'/',self.exclude_dirs_full):
                    dflag = True
                    break
            if dflag:
                continue
                
            out_list.append(file)
        return out_list
    

    def add_hash(self,file_rootpath,hashname=None):
        """
        Add the hash but check the db first. Note that if use_hash_db=False,
        the load_hash_db made it empty so we won't find it in the query.
        """
        file,rootpath = file_rootpath
        
        query = {k:file[k] for k in ['mtime','path','size']}
        dbitem = self.hash_db.query_one(**query)
        
        if dbitem and hashname in dbitem:
            file[hashname] = dbitem[hashname]
        else:
            fullpath = os.path.join(rootpath,file['path'])
            file[hashname] = utils.HASHFUNS[hashname](fullpath)
        
        return file          
                

    def load_hash_db(self):
        hash_db = list()
        
        hash_path = os.path.join(self.path,'.PyFiSync','hash_db.json')
        if self.use_hash_db and os.path.exists(hash_path):
            with open(hash_path,'rt',encoding='utf8') as F:
                hash_db = json.loads(F.read())
        
        self.hash_db = ldtable(hash_db,attributes=['mtime','path','size'])
         
    def save_hash_db(self,files):
        if not self.use_hash_db:
            return
        hash_path = os.path.join(self.path,'.PyFiSync','hash_db.json')
        try:
            os.makedirs(os.path.dirname(hash_path))
        except OSError:
            pass
        with open(hash_path,'wt',encoding='utf8') as F:
            F.write(utils.to_unicode(json.dumps(files)))
                    
def _relpath(*A,**K):
    """
    Return the results of os.relpath but remove leading ./
    """
    res = os.path.relpath(*A,**K)
    res = utils.to_unicode(res)
    if res.startswith('./'):
        return res[2:]
    if res == '.':
        return ''
    return res      



def scandir(path,force_listdir=False):
    if _scandir is not None and not force_listdir:
        for item in _scandir(path):
            yield item
    
    else:
        for item in os.listdir(path):
            fullpath = os.path.join(path,item)
            yield fake_DirEntry(fullpath)


class fake_DirEntry(object):
    """
    Fake DirEntry object.

    Will be used by backup scandir
    """
    # Use __slots__ for better memory
    __slots__ = ('path','name','_lstat','_stat','_is_dir','_is_symlink')        
    
    def __init__(self,path):
        self.path = path
        self.name = os.path.basename(path)
        
        self._stat = None
        self._lstat = None
        self._is_dir = None
        self._is_symlink = None

    def inode(self,follow_symlinks=True):
        """
        The main object doesn't seem to be clear on whether or not
        if follows sym links. I added it but call stat first!!!
        """
        if self._stat is None:
            self.stat(follow_symlinks=follow_symlinks)
        
        return self._stat.st_ino

    def is_dir(self,follow_symlinks=True):
        if self.is_symlink() and not follow_symlinks:
            return False # Symlinks are NEVER dirs when follow_symlinks is False
        
        if self._is_dir is None:
            self._is_dir = os.path.isdir(self.path)
        return self._is_dir

    def is_file(self,follow_symlinks=True):
        # Make sure it is not a broken link b/c DirEntry will 
        # tell you both false for file and dir
        if self.is_symlink():
            try:
                self.stat(follow_symlinks=True)
            except OSError:
                return False # Broken link
        
        return not self.is_dir(follow_symlinks=follow_symlinks)
    
    def stat(self,follow_symlinks=True):
        if follow_symlinks:
            if self._stat is None:
                self._stat = os.stat(self.path)
            return self._stat
        else:
            if self._lstat is None:
                self._lstat = os.lstat(self.path)
            return self._lstat
            
    
    def is_symlink(self):
        if self._is_symlink is None:
            self._is_symlink = os.path.islink(self.path)
        return self._is_symlink
        
    def __str__(self):
        return '<{0}: {1!r}>'.format(self.__class__.__name__, self.name)
    __repr__ = __str__
        
            
        
    
        
