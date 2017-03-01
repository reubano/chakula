#!/usr/bin/env python
# -*- coding: utf-8 -*-
# vim: sw=4:ts=4:expandtab

import sys

from os import path as p

import pkutils

try:
    from setuptools import setup, find_packages
except ImportError:
    from distutils.core import setup, find_packages

PARENT_DIR = p.abspath(p.dirname(__file__))

sys.dont_write_bytecode = True
requirements = set(pkutils.parse_requirements('requirements.txt'))
dev_requirements = set(pkutils.parse_requirements('dev-requirements.txt'))
readme = pkutils.read('README.rst')
module = pkutils.parse_module(p.join(PARENT_DIR, 'chakula', '__init__.py'))
license = module.__license__
version = module.__version__
project = module.__package_name__
description = module.__description__
user = 'reubano'

setup_require = [r for r in dev_requirements if 'pkutils' in r]

classifiers = [
    pkutils.LICENSES[license],
    pkutils.get_status(version),
    'Natural Language :: English',
    'Programming Language :: Python :: 3',
    'Programming Language :: Python :: 3.5',
    'Programming Language :: Python :: 3.6',
    'Programming Language :: Python :: Implementation :: PyPy',
    'Environment :: Console',
    'Topic :: Software Development :: Libraries :: Python Modules',
    'Topic :: Utilities',
    'Framework :: Flask',
    'Operating System :: OS Independent',
    'Operating System :: POSIX :: Linux',
    'Operating System :: MacOS :: MacOS X',
    'Operating System :: Microsoft :: Windows',
]

kw = {
    'name': project,
    'version': version,
    'description': description,
    'long_description': readme,
    'author': module.__author__,
    'author_email': module.__email__,
    'license': license,
    'keywords': [project] + description.split(' '),
    'url': pkutils.get_url(project, user),
    'download_url': pkutils.get_dl_url(project, user, version),
    'classifiers': classifiers,
    'packages': find_packages(exclude=['tests', 'docs']),
    'include_package_data': True,
    'install_requires': requirements,
    'extras_require': {
        'develop': dev_requirements,
        'redis': ['redisworks>=0.2.7,<0.3.0'],
    },
    'setup_requires': setup_require,
    'tests_require': dev_requirements,
    'package_data': {
        'helpers': ['helpers/*'],
        'tests': ['tests/*'],
    },
    'data_files': [],
    'platforms': ['MacOS X', 'Windows', 'Linux'],
    'zip_safe': False,
    'scripts': [p.join('bin', 'chakula')],
}


if __name__ == '__main__':
    setup(**kw)
