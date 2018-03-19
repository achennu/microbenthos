#!/usr/bin/env python
# -*- coding: utf-8 -*-

from setuptools import setup

def get_description():
    import os
    CURR = os.path.dirname(__file__)

    with open(os.path.join(CURR, 'README.rst')) as readme_file:
        readme = readme_file.read()

    with open(os.path.join(CURR, 'HISTORY.rst')) as history_file:
        history = history_file.read()

    return readme + '\n\n' + history

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
    version='0.7.1',
    description="In silico microbenthic simulations for studies of biogeochemistry and microbial ecology",
    long_description=get_description(),
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
