# Lambda Utils folder

This folder contains the python libraries created to support lambdas.


## Initialization
To install this on your pip env use:
    `pip install -r .`

## Context Explorer

### S3
S3 utils class, used as interface to access AWS S3 buckets.

### Config
Utils regarding the lambda configurations. Update, get and create methods are available.

### Ingress

### Lambda Tools
Added with the validator of the lambda to detect if a lambda already run or if it is running.

### Newstore API
Contains the job manager used to connect with newstore import api.
Requires the newstore adapter library.

### Sftp
Small simple sftp interface

### xml
XML related tools

### emailer
Simple report sender used to send reports until we have a proper email sender in place (soon).

### json
Simple JSON Encoder. Currently knows how to encode Decimal types
