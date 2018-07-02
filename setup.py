#!/usr/bin/env python
# -*- coding: utf-8 -*-

import PyFiSync

from setuptools import setup

setup(
    name='PyFiSync',
    packages=['PyFiSync'],
    long_description=open('readme.md').read(),
    entry_points = {
        'console_scripts': ['PyFiSync=PyFiSync.main:cli'],
    },
    version=PyFiSync.__version__,
    description='Python based intelligent file sync with automatic backups and file move/delete tracking.',
    url='https://github.com/Jwink3101/PyFiSync',
    author=PyFiSync.__author__,
    author_email='Jwink3101@@users.noreply.github.com',
    license='MIT',
)

