#!/usr/bin/env python

from setuptools import setup

setup(
    name='param_store',
    version='1.0.0',
    description='NewStore Param Store Client',
    long_description="Simple interface for SSM Param Store.",
    author='NewStore Inc.',
    author_email='dev@newstore.com',
    url='https://github.com/NewStore/newstore-integrations/python/3.6/param_store',
    packages=['param_store'],
    package_dir={'': 'src'},
    install_requires=[
        'setuptools'
    ],
    test_suite='tests',
)
