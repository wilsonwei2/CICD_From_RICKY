from setuptools import setup, find_packages

setup(
    name="newstore_loader",
    version='16.11.7',
    description="NewStore Loader",
    long_description="",
    author="NewStore Inc.",
    author_email='dev@newstore.com',
    url='https://github.com/NewStore/newstore-integrations/python/newstore_loader',
    packages= [ 'newstore_loader' ],
    package_dir = { '': 'src' },
    install_requires=[
        'newstore_adapter',
        'setuptools',
    ],
    test_suite="newstore_loader.tests",
)
