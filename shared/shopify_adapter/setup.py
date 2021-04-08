from setuptools import setup

setup(
    name="shopify_adapter",
    version='1.0.0',
    description="Shopify adapter",
    long_description="",
    author="NewStore Inc.",
    author_email='dev@newstore.com',
    url='https://github.com/NewStore/newstore-integrations/lambdas/adapters/shopify_adapter',
    packages=[
        'shopify_adapter'
    ],
    package_dir={'': 'src'},
    install_requires=[
        'setuptools',
        'requests>=2.11.1'
    ],
    test_suite="shopify_adapter.tests",
    tests_require=[
        'requests-mock'
    ],
)
