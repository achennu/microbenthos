#!/usr/bin/env python
# -*- coding: utf-8 -*-

from setuptools import setup, find_packages

def get_description():
    import os
    CURR = os.path.dirname(__file__)

    with open(os.path.join(CURR, 'README.rst')) as readme_file:
        readme = readme_file.read()

    return readme

requirements = [
    'click>=6.0',
    'logutils',
    'sympy',
    'cerberus',
    'PyYaml',
    'h5py',
    'tqdm',
    'matplotlib>=2.1',
    'scipy>=1.0.0',
    'numpy',
    'fipy',
]

test_requirements = [
    # TODO: put package test requirements here
    'pytest',
    'mock',
]

docs_requirements = [
    'sphinx',
    'sphinx_rtd_theme',
    'sphinxcontrib-programoutput',
    'sphinx-autodoc-typehints',
    ]

setup(
    name='microbenthos',
    version='0.8.2',
    description="Modeling framework for microbenthic habitats useful for studies in "
                "biogeochemistry and marine microbial ecology.",
    long_description=get_description(),
    author="Arjun Chennu",
    author_email='arjun.chennu@gmail.com',
    url='https://microbenthos.readthedocs.io',
    packages=find_packages(exclude=['tests']),
    include_package_data=True,
    package_data={
        'microbenthos.utils': ['schema.yml',]
        },
    package_dir={'microbenthos':
                 'microbenthos'},
    entry_points={
        'console_scripts': [
            'microbenthos=microbenthos.cli:cli'
        ]
    },
    install_requires=requirements,
    extras_require=dict(
        test=test_requirements,
        docs=docs_requirements,
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
