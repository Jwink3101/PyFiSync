#!/usr/bin/env python
# -*- coding: utf-8 -*-
from __future__ import division, print_function, unicode_literals, absolute_import

import sys
sys.dont_write_bytecode = True

from PyFiSync import cli

if __name__ == '__main__':
    argv = sys.argv[1:] # Argument besides function name
    cli(argv)
