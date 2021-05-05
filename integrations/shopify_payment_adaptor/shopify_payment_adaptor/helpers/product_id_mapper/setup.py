#!/usr/bin/env python

from setuptools import setup

## TODO:: The Email ID could be changed later
setup(
    name='product_id_mapper',
    version='1.0.0',
    description='Keep track of various product identifiers.',
    author='NewStore Inc.',
    author_email='akasturi@newstore.com',
    url='https://github.com/NewStore/newstore-integrations/lambdas/goorin-brothers/helpers/product_id_mapper',
    packages=['product_id_mapper'],
    package_dir={'': 'src'},
    install_requires=[
        'setuptools',
        'requests'
    ],
)
