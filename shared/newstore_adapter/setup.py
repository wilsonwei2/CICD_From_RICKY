#!/usr/bin/env python

""" newstore_adapter setup """

from setuptools import setup

setup(
    name="newstore_adapter",
    version='17.08.31',
    description="NewStore API Adapter",
    long_description="",
    author="NewStore Inc.",
    author_email='dev@newstore.com',
    url='https://github.com/NewStore/newstore-integrations/python/newstore_adapter',
    packages=['newstore_adapter'],
    package_dir={'': 'src'},
    install_requires=[
        'setuptools',
        'requests>=2.11.1'
    ],
    test_suite="newstore_adapter.tests",
    tests_require=[
        'requests-mock',
    ],
)
