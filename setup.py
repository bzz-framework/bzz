#!/usr/bin/python
# -*- coding: utf-8 -*-

# This file is part of bzz.
# https://github.com/heynemann/bzz

# Licensed under the MIT license:
# http://www.opensource.org/licenses/MIT-license
# Copyright (c) 2014 Bernardo Heynemann heynemann@gmail.com


from setuptools import setup, find_packages
from bzz import __version__

tests_require = [
    'mock',
    'nose',
    'coverage',
    'yanc',
    'preggy',
    'tox',
    'factory-boy',
    'ipdb',
    'coveralls',
    'markupsafe',
    'sphinx',
    'mongoengine',
    'nose-focus',
    'sphinx_rtd_theme',
]

setup(
    name='bzz',
    version=__version__,
    description='bzz is a Rest API framework for working bees.',
    long_description='''
bzz is a Rest API framework for working bees.
''',
    keywords='api rest tornado hal',
    author='Bernardo Heynemann',
    author_email='heynemann@gmail.com',
    url='https://github.com/heynemann/bzz',
    license='MIT',
    classifiers=[
        'Development Status :: 4 - Beta',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: MIT License',
        'Natural Language :: English',
        'Operating System :: Unix',
        "Programming Language :: Python :: 2.7",
        "Programming Language :: Python :: 3.4",
        "Programming Language :: Python :: Implementation :: PyPy",
        'Operating System :: OS Independent',
    ],
    packages=find_packages(),
    include_package_data=True,
    install_requires=[
        'awesome-slugify',
        'cow-framework>=1.0.0',
        'blinker',
        'pyjwt',
        'six',
    ],
    extras_require={
        'tests': tests_require,
    },
    entry_points={
        'console_scripts': [
            # add cli scripts here in this form:
            # 'bzz=bzz.cli:main',
        ],
    },
)
