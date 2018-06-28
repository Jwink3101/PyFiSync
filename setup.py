#!/usr/bin/env python
# -*- coding: utf-8 -*-
from __future__ import division, print_function, unicode_literals, absolute_import

from setuptools import setup

setup(
    name='PyFiSync',
    packages=['PyFiSync'],
    long_description=open('readme.md').read(),
    entry_points = {
        'console_scripts': ['PyFiSync=PyFiSync.main:cli'],
    },
    version='20180628',
    description='Python based intelligent file sync with automatic backups and file move/delete tracking.',
    url='https://github.com/Jwink3101/PyFiSync',
    author='Justin Winokur',
    author_email='Jwink3101@@users.noreply.github.com',
    license='MIT',
)

