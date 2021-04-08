from setuptools import setup

import sys
if sys.version_info[0] == 3:

    setup(
        name="lambda_utils",
        version='16.12.1',
        description="NewStore Lambda Utils",
        long_description="",
        author="NewStore Inc.",
        author_email='dev@newstore.com',
        url='https://github.com/NewStore/newstore-integrations/python/lambda_utils',
        packages=[
            'lambda_utils', 'lambda_utils.S3', 'lambda_utils.events',
            'lambda_utils.sqs', 'lambda_utils.config', 'lambda_utils.xml',
            'lambda_utils.newstore_api', 'lambda_utils.lambda_tools', 'lambda_utils.sftp',
            'lambda_utils.ingress', 'lambda_utils.emailer', 'lambda_utils.export_ref_helper',
            'lambda_utils.json', 'lambda_utils.sns', 'lambda_utils.slack', 'lambda_utils.rds', 
            'lambda_utils.token','lambda_utils.dynamodb','lambda_utils.ses', 'lambda_utils.reports'
        ],
        package_dir={'': 'src'},
        install_requires=[
            'setuptools'
        ],
        test_suite="lambda_utils.tests",
    )

else:

    setup(
        name="lambda_utils",
        version='16.12.1',
        description="NewStore Lambda Utils",
        long_description="",
        author="NewStore Inc.",
        author_email='dev@newstore.com',
        url='https://github.com/NewStore/newstore-integrations/python/lambda_utils',
        packages=[
            'lambda_utils', 'lambda_utils.S3', 'lambda_utils.events',
            'lambda_utils.sqs', 'lambda_utils.config', 'lambda_utils.xml',
            'lambda_utils.newstore_api', 'lambda_utils.lambda_tools', 'lambda_utils.sftp',
            'lambda_utils.ingress', 'lambda_utils.emailer', 'lambda_utils.export_ref_helper',
            'lambda_utils.json', 'lambda_utils.sns', 'lambda_utils.slack', 'lambda_utils.rds','lambda_utils.ses',
            'lambda_utils.dynamodb', 'lambda_utils.reports'
        ],
        package_dir={'': 'src'},
        install_requires=[
            'setuptools'
        ],
        test_suite="lambda_utils.tests",
    )

