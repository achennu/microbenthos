#!/usr/bin/env python
# -*- coding: utf-8 -*-

from setuptools import setup

with open('README.rst') as readme_file:
    readme = readme_file.read()

with open('HISTORY.rst') as history_file:
    history = history_file.read()

requirements = [
    'click>=6.0',
    'scipy>=1.0.0',
    'fipy',
    'logutils',
    'sympy',
    'cerberus',
    'PyYaml',
    'h5py',
    'tqdm',
    'matplotlib>=2.1'
]

test_requirements = [
    # TODO: put package test requirements here
    'pytest',
    'mock',
]

setup(
    name='microbenthos',
    version='0.6',
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
            'microbenthos=microbenthos.cli:cli'
        ]
    },
    include_package_data=True,
    install_requires=requirements,
    extras_require=dict(
        test=test_requirements,
        ),
    license="MIT license",
    zip_safe=False,
    keywords=['microbenthos', 'biogeochemistry', 'marine biology', 'microbial ecology',
              'simulation', 'modeling', 'microbial mats', 'sediments'],
    classifiers=[
        'Development Status :: 2 - Pre-Alpha',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: MIT License',
        'Natural Language :: English',
        'Programming Language :: Python :: 2.7',
    ],
    test_suite='pytest',
    # tests_require=test_requirements
)
