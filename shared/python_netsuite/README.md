# Python NetSuite Adapter

Note: README.rst was included in the original package and includes basic usage. This document describes NewStore
Integration-specific usage.

## User-based Authentication
User-based Authentication with NetSuite includes creating a passport object that is logged in and then sent with
requests as a method of verifying the permissions access of our NewStore user. The passport includes several values
including the raw Username and Password values that are also used to manually login to the NetSuite web console. This is
 a legacy method that requires a login and limits the number of requests that can be sent at a time. This can become a
bottleneck when using this package in multiple lambdas.

The credentials required to use this login method are as follows:
1. Role
1. Email
1. Password
1. Account

See below on the Environment Loader to find how these are supplied to the package.


## Token Based Authentication (TBA)
Token Based Authentication with NetSuite includes creating a specific token passport object that is sent with requests
as a method of verifying the permissions access of our NewStore user. The passport includes several values including
API keys specifically generated for use in the NewStore integration layer. This is a newer method that does not require
the login of the token passport, and allows multiple simultaneous connections using the token passport credentials. This
 is the method that should be used for future clients if possible.

The credentials required to use this login method are as follows:
1. Consumer Key
1. Consumer Secret
1. Token ID
1. Token Secret
1. Account


Since this is a newer capability of the `python_netsuite` adapter, it has to be enabled with an additional value
`activate_tba`. In addition, since the login process is not needed, login can be skipped by also supplying
`disable_login`

See below on the Environment Loader to find how these value are supplied to the package.


## NetSuite Environment Loader
This package requires that the credentials used to authenticate with NetSuite are saved in environment variables. This
means that, when working in the cloud, these values must be populated before the client package is imported, otherwise
the login will throw an exception. There are two approaches to supplying the variables to AWS Lambda

### Using the Systems Manager Parameter Store to Store and Load Credentials (Preferred)
An ideal solution involves storing the credentials in a designated Parameter Store Key and configuring each Lambda to
load the values and set them as environment variables during the startup of the Lambda. The
`netsuite_environment_loader` is designed to call the Parameter Store and set a list of values necessary for
authentication with NetSuite. The Parameter Store key is used by the Anine Bing solution and a few others, and looks
something like this:

```
{
    "account_id": "...",
    "role_id": "...",
    "activate_tba": "1",
    "disable_login": "1",
    "consumer_key": "...",
    "consumer_secret": "...",
    "token_key": "...",
    "token_secret": "..."
}
```
Note: This example uses the 4 API keys used in Token-Based Authentication. For User-based Authentication, the last 4
values would be replaced with keys for the `email` and `password`

### Setting the credentials in the Lambda's Environment Variables Manually
For simplicity and testing, it may be easiest to include the credentials in the Lambda's Environment Variables list
right from the AWS console. This should work, but this would have to be done for every Lambda that utilizes the
credentials to authenticate, and could get tricky when having to update the values later on.

