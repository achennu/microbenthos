#!/usr/bin/env python
# -*- coding: utf-8 -*-

from setuptools import setup

with open('README.rst') as readme_file:
    readme = readme_file.read()

with open('HISTORY.rst') as history_file:
    history = history_file.read()

requirements = [
    'click>=6.0',
    'fipy>=3',
    'scipy',
    'logutils',
    'sympy',
    'cerberus',
    'PyYaml',
]

test_requirements = [
    # TODO: put package test requirements here
    'pytest',
    'mock',
]

setup(
    name='microbenthos',
    version='0.2.0',
    description="In silico microbenthic simulations for studies of biogeochemistry and microbial ecology",
    long_description=readme + '\n\n' + history,
    author="Arjun Chennu",
    author_email='achennu@mpi-bremen.de',
    url='https://github.com/achennu/microbenthos',
    packages=[
        'microbenthos',
    ],
    package_dir={'microbenthos':
                 'microbenthos'},
    entry_points={
        'console_scripts': [
            'microbenthos=microbenthos.cli:main'
        ]
    },
    include_package_data=True,
    install_requires=requirements,
    license="MIT license",
    zip_safe=False,
    keywords=['microbenthos', 'biogeochemistry', 'marine biology', 'microbial ecology',
              'simulation'],
    classifiers=[
        'Development Status :: 2 - Pre-Alpha',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: MIT License',
        'Natural Language :: English',
        'Programming Language :: Python :: 2.7',
        'Programming Language :: Python :: 3.6',
    ],
    test_suite='tests',
    tests_require=test_requirements
)
