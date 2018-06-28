#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Remote interfaces

For now, it is *just* SSH + rsync to work within the subprocess on Unix/Linux
(macOS is Unix). It is separated to more easily make other backends

An interface must have the following methods and behaviors from 
'remote_interface_base'. Note that optional methods have a pass but the 
required ones will raise a NotImplementedError
"""
from __future__ import division, print_function, unicode_literals

import getopt
import subprocess
import re
import sys
import os
import random
import string
import json
import zlib
import shlex
import tempfile

from io import open

if sys.version_info[0] > 2:
    xrange = range
    unicode = str

from . import utils

class remote_interface_base(object):
    def __init__(self,config,log=None):
        """
        * Just pass it the configuration file
        * Optionally, pass it the log object to modify
        """
        raise NotImplementedError()
    def file_list(self,attributes,empty):
        """
        * Attributes are a list of requested attributes but generally, more
          should be returned in case attributes change.
        * follow the `empty` settings of PFSwalk -- if applicable
            'store':    stores a list of empty directories
            'remove':   Deletes all empty directories if (and only if) they 
                        were *not* empty before. Also removes stored list
            'reset':    Removes stored list
        """
        raise NotImplementedError()
        
    def apply_queue(self,queue,force):
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
        raise NotImplementedError()
    
    def transfer(self,tqA2B,tqB2A):
        """
        * Apply the trasnfer from B to A and from A to B
        * MUST maintain modification times upon transfer
        """
        raise NotImplementedError()

    def close(self):
        """
        * If it has this function, it will try to call it at the very end
        """
        pass

    @staticmethod
    def cli(argv): 
        """
        should be decorated with @staticmethod
        All of the commands will be passed. Can use this to communicate remotely
        if needed

        For example
            ./PyFiSync.py _api file_list --flag1 val1 --flag2

            will pass argv = ['file_list', '--flag1', 'val1', '--flag2']
        """
        pass

class ssh_rsync(remote_interface_base):
    def __init__(self,config,log=None):
        self.config = config
        if log is None:
            log = utils.logger(silent=False,path=None)
        self.log = log
        if config.persistant:
            # Set up master connection for 600 seconds 
            self.sm = '-S /tmp/' + _randstr(5)
            cmd = 'ssh -N -M {sm:s} -p {ssh_port:d} -q {userhost:s}'.\
                   format(sm=self.sm,**config.__dict__)            
            
            self.persistant_proc = subprocess.Popen(shlex.split(cmd))
            
        else:
            self.sm = '' # Do nothings
        
    def file_list(self,attributes,empty=None):
        """
        Get the file list in B (remote)
        """        
        attributes = list(set(attributes))
        config = self.config
        log = self.log


        # Construct the command
        cmd = 'ssh {sm} -p {ssh_port:d} -q {userhost:s} "'.format(sm=self.sm,**config.__dict__)

        # construct the call cmd
        if len(config.PyFiSync_path) == 0:
            cmd += 'PyFiSync.py _api file_list'
        else:
            cmd += config.remote_program + ' '
            if config.PyFiSync_path.endswith('PyFiSync.py'):
                cmd += config.PyFiSync_path + ' _api file_list"'
            else:
                cmd += os.path.join(config.PyFiSync_path,'PyFiSync.py _api file_list"')
    
        
        remote_config = dict()
        
        remote_config['path'] = config.pathB
        remote_config['excludes'] = list(set(config.excludes))
        remote_config['empty'] = empty
        remote_config['attributes'] = list(set(attributes))
        remote_config['copy_symlinks_as_links'] = config.copy_symlinks_as_links
        remote_config['git_exclude'] = config.git_exclude
        remote_config['use_hash_db'] = config.use_hash_db
        
        log.add('Calling for remote file list')
        
        # Encode the config. Just in case there is any additional cruft, add
        # a starting sentinel
        sentinel = _randstr(N=10).encode('ascii')
        cmd = shlex.split(cmd)
        cmd[-1] += ' ' + sentinel.decode('ascii') # Add the sentinel to the final command
        
        json_config = sentinel+json.dumps(remote_config,ensure_ascii=False).encode('utf8')
        
        # Use a tempfile to prevent a buffering issue
        outfile =  tempfile.NamedTemporaryFile(mode='wb',delete=False)
        
        proc = subprocess.Popen(cmd,stdin=subprocess.PIPE, 
                                    stdout=outfile,
                                    stderr=subprocess.PIPE, 
                                    bufsize=1,shell=False)        
        _,err = proc.communicate(json_config)
        
        if len(err)>0:
            err = utils.to_unicode(err)
            log.add('Remote Call returned warnings:')
            log.space = 4
            log.add(err)
            log.space = 0

        # Read back the output, find the sentinel, decompress and return the output
        with open(outfile.name,'rb') as F:
            out = F.read()
        out = out[out.find(sentinel) + len(sentinel):]
        out = zlib.decompress(out)
    
        return json.loads(out)

    def apply_queue(self,queue,force=False):
        """
        Remote call to apply queue assumeing B is remote
        """
        log = self.log
        config = self.config

        if len(queue) == 0:
            log.add('  >> No remote actions <<')
            return

        sentinel = _randstr(N=10).encode('ascii')
        
        queue_bytes = json.dumps(queue,ensure_ascii=False).encode('utf8')
        
        # Construct the command
        cmd = 'ssh {sm} -p {ssh_port:d} -q {userhost:s} "'.format(
            sm=self.sm,**config.__dict__)

        # construct the call cmd
        if len(config.PyFiSync_path) == 0:
            cmd += 'PyFiSync.py _api apply_queue'
        else:
            cmd += config.remote_program + ' '
            if config.PyFiSync_path.endswith('PyFiSync.py'):
                cmd += config.PyFiSync_path + ' _api apply_queue '
            else:
                cmd += os.path.join(config.PyFiSync_path,'PyFiSync.py _api apply_queue ')

        if force:
            cmd += ' --force '

        if not config.backup:
            cmd += ' --no-backup '

        cmd += config.pathB + ' {}"'.format(sentinel.decode('ascii'))

        out = ''
        err = ''

        log.space=0
        log.add('\nApplying queue on remote')
        log.prepend = '>  '

        started = False
        cmd = shlex.split(cmd)
        proc = subprocess.Popen(cmd,stdin=subprocess.PIPE,
                                    stdout=subprocess.PIPE,
                                    stderr=subprocess.PIPE, 
                                    bufsize=1,shell=False)
        
        proc.stdin.write(sentinel + queue_bytes)
        proc.stdin.close()
        
        with proc.stdout as stdout:
            for line in iter(stdout.readline, b''):
                line = utils.to_unicode(line)
                if not started and line.find('START>>>>>>>')>=0:
                    started = True
                    continue

                if line.find('<<<<<<<END')>=0:
                    started = False

                if started:
                    log.add(line.rstrip())


        with proc.stderr as stderr:
            for line in iter(stderr.readline, b''):
                err += utils.to_unicode(line)
        proc.wait()
        log.prepend = ''
        if len(err)>0:
            log.add('Remote Call returned warnings:')
            log.space = 4
            log.add(err)

    def transfer(self,tqA2B,tqB2A):
        config = self.config
        log = self.log

        pwd0 = os.getcwd()
        os.chdir(config.pathA)

        # Build the command
        cmd = 'rsync -azvi -hh ' \
            + '--keep-dirlinks --copy-dirlinks ' # make directory links behave like they were folders
            
        if config.rsync_checksum:
            cmd += '--checksum '
        
        if not config.copy_symlinks_as_links:
            cmd += '--copy-links '    
        
        if len(config.userhost) >0:
            cmd += '-e "ssh -q -p {p:d} {sm}" '.format(p=config.ssh_port,sm=self.sm)
            B = '{userhost:s}:{pathB:s}'.format(**config.__dict__)
        else:
            B = '{pathB:s}'.format(**config.__dict__)

        cmd += ' --files-from={files:s} {src:s}/ {dest:s}/'

        log.add('(using rsync)')

        if len(tqA2B) > 0:

            # A2B
            tmp_file = '/tmp/tqA2B' + _randstr()

            for ix,item in enumerate(tqA2B): # Opperate on the list IN PLACE
                item = item.encode('utf-8')
                tqA2B[ix] = item

            with open(tmp_file,'wb') as F:
                F.write('\n'.encode('utf-8').join(tqA2B))

            cmdA2B = cmd.format(files=tmp_file,src=config.pathA,dest=B)

            log.space=1
            log.add('Running rsync A >>> B')
            log.add('  cmd = ' + cmdA2B)
            log.space=4


            proc = subprocess.Popen(cmdA2B, stdout=subprocess.PIPE, bufsize=1,shell=True)
            with proc.stdout:
                for line in iter(proc.stdout.readline, b''):
                    line = self._proc_final_log(line)
                    log.add(line)

            proc.wait()
        else:
            log.space=1
            log.add('\nNo A >>> B transfers')

        #########

        if len(tqB2A) > 0:
            # B2A
            tmp_file = '/tmp/tqB2A' + _randstr()
            for ix,item in enumerate(tqB2A): # Opperate on the list IN PLACE
                item = item.encode('utf-8')
                tqB2A[ix] = item

            with open(tmp_file,'wb') as F:
                F.write('\n'.encode('utf-8').join(tqB2A))

            cmdB2A = cmd.format(files=tmp_file,dest=config.pathA,src=B)

            log.space=1
            log.add('\nRunning rsync A <<< B')
            log.add('  cmd = ' + cmdB2A)
            log.space=4

            proc = subprocess.Popen(cmdB2A, stdout=subprocess.PIPE, bufsize=1,shell=True)
            with proc.stdout:
                for line in iter(proc.stdout.readline, b''):
                    line = self._proc_final_log(line)
                    log.add(line)

            proc.wait()
        else:
            log.space=1
            log.add('\nNo A <<< B transfers')

        os.chdir(pwd0)


    def _proc_final_log(self,line):
        line = line.strip()
        if len(line) == 0: return None
        try:
            line = utils.to_unicode(line)
        except:
            return None
        try:
            action_path = [i.strip() for i in line.split(' ',1)]
        except UnicodeDecodeError: # A bit of a hack but this works to make py2 happy
            action_path = [utils.to_unicode(a) for a in line.decode('utf8').split(' ')]
            
        if len(action_path) != 2:
            return 'could not parse action: {:s}'.format(line)

        action = action_path[0]
        path = action_path[1]

        action = action.replace('<','>')

        if action.startswith('sent'):
            return '\n' + line
        if action.startswith('total'):
            return line

        if any([action.startswith(d) for d in ['receiving','building']]):
            return None

        if action.startswith('>'):  return 'Transfer  ' + path
        if action.startswith('cd'): return 'mkdir     ' + path
        if action.startswith('cL'): return 'link      ' + path
        if action.startswith('.'):  return None

        return line

    @staticmethod
    def cli(argv):
        from . import PFSwalk
        from . import main
            
        mode = argv[0]
        argv = argv[1:]
        if mode == 'file_list':
            # Get the sentinel
            sentinel = argv[0].encode('ascii')
            
            # For python3 to read bytes
            stdin = sys.stdin
            if hasattr(stdin,'buffer'):
                stdin = stdin .buffer
            stdout = sys.stdout
            if hasattr(stdout,'buffer'):
                stdout = stdout.buffer
            
            # Read the config, find and cut up to the sentinel, convert to 
            # unicode and json load
            
            
            remote_config_bytes = stdin.read()  
            remote_config_bytes = remote_config_bytes[remote_config_bytes.find(sentinel)+len(sentinel):]
            remote_config_bytes = remote_config_bytes.decode('utf8')
            remote_config = json.loads(remote_config_bytes)
            
            # Process the input
            path = remote_config['path']
            config = utils.configparser()
            config.pathA = path

            sha1 = 'sha1' in remote_config['attributes']
            empty = remote_config['empty']
            config.copy_symlinks_as_links = remote_config['copy_symlinks_as_links']
            config.git_exclude = remote_config['git_exclude']
            config.excludes = list(set(config.excludes + remote_config['excludes']))
            config.use_hash_db = remote_config['use_hash_db']
            
            # Generate the list. This may raise errors so do not start
            # capture until later
            log = utils.logger(silent=True,path=None)
            _tmp = PFSwalk.file_list(path,config,log,sha1=sha1,empty=empty,
                                    use_hash_db=config.use_hash_db)
            flist = _tmp.files()

            out = json.dumps(flist,ensure_ascii=False)
            out = zlib.compress(out.encode('utf8'),9) # Compress it
            
            stdout.write(sentinel + out) # write the bytes
            
        elif mode == 'apply_queue':
            # For python3 to read bytes
            stdin = sys.stdin
            if hasattr(stdin,'buffer'):
                stdin = stdin.buffer
            stdout = sys.stdout
            if hasattr(stdout,'buffer'):
                stdout = stdout.buffer
            
            try:
                opts, args = getopt.getopt(argv, "",['force','no-backup'])
            except getopt.GetoptError as err:
                print(str(err)) #print error
                sys.exit(2)

            path,sentinel = args

            config = utils.configparser()
            config.pathA = path

            # Place the config into PyFiSync
            main.config = config

            force = False
            for opt,val in opts:
                if opt == '--force':
                    force = True
                if opt == '--no-backup':
                    config.backup = False

            log = utils.logger(path=path,silent=False)

            sys.stdout.write('START>>>>>>>\n')

            # Get the queue from stdin
            sentinel = sentinel.encode('ascii')
            queue = stdin.read()
            queue = queue[queue.find(sentinel)+len(sentinel):]
            queue = queue.decode('utf8')

            try:
                queue = json.loads(queue)
            except Exception as E:
                sys.stderr.write('could not parse input. Error: "{}"'.format(E))
                sys.exit(2)

            print('Successfully loading action queue of {:d} items'.format(len(queue)))

            main.apply_action_queue(path,queue,force=force)

            sys.stdout.write('\n<<<<<<<END')
    def close(self):
        if self.config.persistant:
            self.persistant_proc.terminate()
            # Remove the socket. The other connection will die soon
            try:
                os.remove(self.sm.replace('-S','').strip())
            except Exception as E:
                pass#print('---{}'.format(E))
            
def _randstr(N=10):
    random.seed()
    return ''.join(random.choice('abcdefghijklmnopqrstuvwxyz') for _ in xrange(N))

