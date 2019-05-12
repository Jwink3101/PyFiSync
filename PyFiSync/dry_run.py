#!/usr/bin/env python
"""
Dry Run equiv
"""
from __future__ import division, print_function, unicode_literals, absolute_import

from . import utils

import sys
if sys.version_info >= (3,):
    unicode = str
    xrange = range

def apply_action_queue(queue,log,name,config):
    log.add('\n(DRY-RUN) Applying queue on {}'.format(name))
    for action_dict in queue:
        action,path = list(action_dict.items())[0]
        if action == 'move':
            log.add('(DRY-RUN) move: ' + utils.move_txt(path[0],path[1]))
        elif action in ['backup','delete']:
            if action == 'backup' and config.backup:
                log.add('(DRY-RUN) backup: ' + path)
            elif action=='delete' and config.backup:
                log.add('(DRY-RUN) delete (w/ backup): ' + path)
            elif action=='delete' and not config.backup:
                log.add('(DRY-RUN) delete (w/o backup): ' + path)
            else:
                pass # Do nothing for now

def transfer(tqA2B,tqB2A,log,filesA,filesB):
    if len(tqA2B) > 0:
        totA = 0.0
        log.space = 1
        log.add('(DRY-RUN) A >>> B')
        log.space = 4
        for item in tqA2B:
            totA += filesA.query_one(path=item)['size']
            log.add('(DRY-RUN) ' + item)
        log.add('(DRY-RUN) Total Size: %0.2f %s' % utils.bytes2human(totA,short=False))
        
    else:
        log.space=1
        log.add('\nNo A >>> B transfers')
        
    if len(tqB2A) > 0:
        totB = 0.0
        log.space = 1
        log.add('(DRY-RUN) A <<< B')
        log.space = 4
        for item in tqB2A:
            totB += filesB.query_one(path=item)['size']
            log.add('(DRY-RUN) ' + item)
        log.add('(DRY-RUN) Total Size: %0.2f %s' % utils.bytes2human(totB,short=False))
    else:
        log.space=1
        log.add('\nNo A <<< B transfers')
