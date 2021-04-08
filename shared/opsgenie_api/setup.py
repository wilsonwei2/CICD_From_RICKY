#!/usr/bin/env python

""" opsgenie_api setup """

from setuptools import setup

setup(
    name="opsgenie_api",
    version='1.00.00',
    description="NewStore Opsgenie API wrapper",
    long_description="",
    author="NewStore Inc.",
    author_email='dev@newstore.com',
    url='https://github.com/NewStore/newstore-integrations/python/opsgenie_api',
    packages=['opsgenie_api'],
    package_dir={'': 'src'},
    install_requires=[
        'setuptools',
        'requests>=2.11.1'
    ],
    test_suite="",
    tests_require=[],
)
