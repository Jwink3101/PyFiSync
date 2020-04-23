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
import datetime

from io import open

if sys.version_info[0] > 2:
    xrange = range
    unicode = str

from . import utils

REMOTES = ['rsync','rclone']

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
            * overwriting moves have already been removed
            * Delete should backup first if set config.backup == True
            * Backup should NOT happen if config.backup == False
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
        self._debug = getattr(config,'_debug',False)
        
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

        if hasattr(config,'PyFiSync_path') and hasattr(config,'remote_program'):
            log.add("DEPRECATION WARNING: 'PyFiSync_path' and 'remote_program' are deprecated. Use 'remote_exe'")
            # construct the call cmd
            if len(config.PyFiSync_path) == 0:
                cmd += 'PyFiSync _api file_list"'
            else:
                cmd += config.remote_program + ' '
                if any(config.PyFiSync_path.endswith('PyFiSync'+ext) for ext in ['','.py']):
                    cmd += config.PyFiSync_path + ' _api file_list"'
                else:
                    cmd += os.path.join(config.PyFiSync_path,'PyFiSync.py _api file_list"')
        else:
            cmd += '{} _api file_list"'.format(config.remote_exe)
        
        remote_config = dict()
        
        remote_config['path'] = config.pathB
        remote_config['excludes'] = list(set(config.excludes))
        remote_config['empty'] = empty
        remote_config['attributes'] = list(set(attributes))
        remote_config['copy_symlinks_as_links'] = config.copy_symlinks_as_links
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

        try:
            out = zlib.decompress(out)    
        except:
            return
        
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
        if hasattr(config,'PyFiSync_path') and hasattr(config,'remote_program'):
            log.add("DEPRECATION WARNING: 'PyFiSync_path' and 'remote_program' are deprecated. Use 'remote_exe'")
            if len(config.PyFiSync_path) == 0:
                cmd += 'PyFiSync _api apply_queue'
            else:
                cmd += config.remote_program + ' '
                if any(config.PyFiSync_path.endswith('PyFiSync'+ext) for ext in ['','.py']):
                    cmd += config.PyFiSync_path + ' _api apply_queue'
                else:
                    cmd += os.path.join(config.PyFiSync_path,'PyFiSync.py _api apply_queue')
        else:
            cmd += '{} _api apply_queue'.format(config.remote_exe)
        
        if force:
            cmd += ' --force '

        if not config.backup:
            cmd += ' --no-backup '

        cmd += ' ' + config.pathB + ' {}"'.format(sentinel.decode('ascii'))

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

            empty = remote_config['empty']
            config.copy_symlinks_as_links = remote_config['copy_symlinks_as_links']
            config.excludes = list(set(remote_config['excludes'])) # do *not* use default excludes
            config.use_hash_db = remote_config['use_hash_db']
            
            # Generate the list. This may raise errors so do not start
            # capture until later
            log = utils.logger(silent=True,path=None)
            _tmp = PFSwalk.file_list(path,config,log,
                                    attributes=remote_config['attributes'],
                                    empty=empty,
                                    use_hash_db=config.use_hash_db)
            flist = _tmp.files()

            out = json.dumps(flist,ensure_ascii=False)
            out = zlib.compress(out.encode('utf8'),9) # Compress it
            
            stdout.write(sentinel + out) # write the bytes
            
        elif mode == 'apply_queue':
            import getopt  # Even though it is "old school" use getopt here 
                           # since it is easier and this interface is never 
                           # exposed to the user
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

            main.apply_action_queue(path,queue)

            sys.stdout.write('\n<<<<<<<END')
    def close(self):
        if self.config.persistant:
            self.persistant_proc.terminate()
            # Remove the socket. The other connection will die soon
            try:
                os.remove(self.sm.replace('-S','').strip())
            except Exception as E:
                pass#print('---{}'.format(E))


class Rclone(remote_interface_base):
    """
    rclone based remote
    """
    def __init__(self,config,log=None):
        self.config = config
        if log is None:
            log = utils.logger(silent=False,path=None)
        self.log = log
        self.flags = list(config.rclone_flags)
        
        # Backup paths
        now = datetime.datetime.now().strftime('%Y-%m-%d_%H%M%S')
        if self.config.rclone_backup_local:
            self.backup_path = os.path.join(
                    config.pathA,'.PyFiSync','backups_remote',now)
        else:
            self.backup_path = os.path.join(
                    config.pathB,'.PyFiSync','backups',now)            
        
        self._debug = getattr(config,'_debug',False)
        self.rc_version = self.call(['--version'])
        
        
    def file_list(self,attributes,empty):
        """
        use rclone to produce a file list
        """
        # This is a hack to only show it the first time
        if self.rc_version:
            self.log.add('rclone version:\n')
            self.log.add(self.rc_version)
            self.rc_version = False
        
        from . import PFSwalk
        attributes = set(attributes)
        attributes.add('size')
        attributes.add('mtime')
        args = ['-q']
        
        # The order of some flags matter
        args.append('lsjson')
        args.extend(['--exclude','".PyFiSync/**"']) # other filters will come later
        args.append('-R')
        if any(attribute.startswith('hash.') for attribute in attributes):
            args.append('--hash')
            
        args.append(self.config.pathB)
        list_out = self.call(args)
        
        raw_list = json.loads(list_out)
        
        files = []
        for rawfile in raw_list:
            if rawfile['IsDir']:
                continue
            file = dict()
            file['path'] = rawfile['Path']
            file['size'] = rawfile['Size']
            file['mtime'] = utils.RFC3339_to_unix(rawfile['ModTime'])
            for attr in attributes:
                if not attr.startswith('hash.'):
                    continue
                name = attr.split('.')[-1]
                try:
                    file[attr] = rawfile['Hashes'][name]
                except KeyError:
                    self.log.add_err('Could not get hash "{}". Make sure it is availible in the specified remote'.format(name))
                    if self.config.imitate_missing_hash:    
                        self.log.add_err('Imitateing hash')
                        file[attr] = utils.imitate_hash(rawfile)
                    else:
                        sys.exit(2)
            files.append(file)
        
        # Use the machinery for rsync+ssh and local to filter
        # since we want to be consistent
        pfswalk = PFSwalk.file_list('',self.config,self.log)
        files = pfswalk.filter_old_list(files)
        
        return files
    
    def apply_queue(self,queue,force=None):
        """
        Apply the queue
        """
        config,log = self.config,self.log
        
        log.add('\nApplying queue on remote')
        didback = False
        
        for action_dict in queue:
            action,path = list(action_dict.items())[0]
            if action == 'move':
                src = os.path.join(self.config.pathB,path[0])
                dst = os.path.join(self.config.pathB,path[1])
                self.call(['moveto',src,dst])
                self.log.add('move: ' + utils.move_txt(path[0],path[1]))
            elif action in ['backup','delete']:
                src = os.path.join(self.config.pathB,path)
                dst = os.path.join(self.backup_path,path)
                if action == 'backup' and config.backup:
                    self.call(['copyto',src,dst])
                    log.add('backup: ' + path)
                    didback = True
                elif action=='delete' and config.backup:
                    self.call(['moveto',src,dst])
                    log.add('delete (w/ backup): ' + path)
                    didback = True
                elif action=='delete' and not config.backup:
                    self.call(['delete',src])
                    log.add('delete (w/o backup): ' + path)
                else:
                    pass # Do nothing for now
        
        # Cleanup local backup folder if not used
        if self.config.rclone_backup_local:
            try:
                os.rmdir(self.backup_path)
            except OSError:
                pass
        
        if didback: 
            if self.config.rclone_backup_local:
                log.add('\nBackups saved LOCALLY in {}'.format(self.backup_path))
            else:
                log.add('\nBackups saved in {}'.format(self.backup_path))    
        
    def transfer(self,tqA2B,tqB2A):
        config = self.config
        log = self.log
        
        args = ['--ignore-times'] # We don't need this since we've already compared
        # set up arguments
        if config.copy_symlinks_as_links:
            args.append('--links')
            log.add('WARNING: rclone may or may-not work with `copy_symlinks_as_links`')
        else:
            args.append('--copy-links')
        
        log.add('(using rclone)')
        
        if len(tqA2B) > 0:

            # A2B
            tmp_file = '/tmp/tqA2B' + _randstr()

            with open(tmp_file,'wt') as file:
                file.write('\n'.join('/' + t for t in tqA2B)) # Must start with / to be full path for root
            
            newargs = args[:]
            newargs.extend(['-v','--stats-one-line'])
            newargs.extend(['copy','--files-from','{}'.format(tmp_file)])
            newargs.extend([config.pathA,config.pathB])
            
            log.space=1
            log.add('Running rclone A >>> B')
            log.space = 4
            out = self.call(newargs,echo=True)
           
            
        else:
            log.space=1
            log.add('\nNo A >>> B transfers')
        
        log.add('')
        
        if len(tqB2A) > 0:

            # B2A
            tmp_file = '/tmp/tqB2A' + _randstr()

            with open(tmp_file,'wt') as file:
                file.write('\n'.join('/' + t for t in tqB2A)) # Must start with / to be full path for root
            
            newargs = args[:]
            newargs.extend(['-v','--stats-one-line'])
            newargs.extend(['copy','--files-from','{}'.format(tmp_file)])
            newargs.extend([config.pathB,config.pathA])

            log.space=1
            log.add('Running rclone A <<< B ')
            log.space = 4
            out = self.call(newargs,echo=True)
            #log.add(out)
            
        else:
            log.space=1
            log.add('\nNo A <<< B transfers')       
        
            
    def call(self,args,echo=False):
        """
        Call rclone with the appropriate flags already set
        """
        if isinstance(args,(str,unicode)):
            args = shlex.split(args)
        args = list(args)
        env = dict(os.environ)
        if self.config.rclone_pw:
            args.append('--ask-password=false')
            env['RCLONE_CONFIG_PASS'] = self.config.rclone_pw
        
        cmd = list()
        cmd.append(self.config.rclone_executable)
        cmd.extend(self.flags)
        cmd.extend(args)
        
        # Use two different methods depending on whether we need to stream
        # the result. This is to hopefully prevent issues with large
        # buffered responses
        if self._debug:
            txt = ['DEBUG MODE','']
            txt.append('rclone call')
            txt.append(' '.join(cmd))
            txt.append(' ')
            self.log.add_err('\n'.join(txt))
            
        if echo:
            stdout = subprocess.PIPE
            self.log.add('rclone\n  $ ' + ' '.join(cmd) + '\n')
        else:
            stdout =  tempfile.NamedTemporaryFile(mode='wb',delete=False)
        
        proc = subprocess.Popen(cmd,
                                stdout=stdout,
                                stderr=subprocess.STDOUT if not self._debug else subprocess.PIPE,
                                shell=False,
                                env=env,
                                cwd=self.config.pathA)
        if echo:
            out = []
            with proc.stdout:
                for line in iter(proc.stdout.readline, b''):
                    line = utils.to_unicode(line)
                    self.log.add(line.rstrip())
                    out.append(line)
            if self._debug:
                err = proc.stderr.read()
        else:
            _,err = proc.communicate() # Since we are not streaming the output
            with open(stdout.name,'rb') as F:
                out = utils.to_unicode(F.read())
        proc.wait()
        if proc.returncode >0:
            self.log.add_err('rclone returned a non-zero exit code')
        
        if self._debug:
            txt = []
            txt.append('OUT:')
            txt.append(''.join(out))
            txt.append('ERR:')
            txt.append(utils.to_unicode(err))
            txt = '\n'.join(txt)
            txt = [''] + txt.split('\n')
            txt = '\nDEBUG: '.join(txt)
            self.log.add_err(txt)
        
        
        return ''.join(out)
        
        
def get_remote_interface(config=None,name=None):
    if config is None == name is None:
        raise ValueError('Must specify config OR name')
    
    if config is not None:
        name = config.remote
    
    if name == 'rsync':
        if len(getattr(config,'userhost','')) == 0:
            return None
        return ssh_rsync
    elif name == 'rclone':
        return Rclone
    else:
        raise ValueError()


def _randstr(N=10):
    random.seed()
    return ''.join(random.choice('abcdefghijklmnopqrstuvwxyz') for _ in xrange(N))






