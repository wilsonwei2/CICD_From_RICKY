# int-template
Template Repository for integrations.

# How to use this repository

Create a new repository for a tenant by clicking **Use this template** button above. Your new repository will contain the same files and folders as the **NewStore/int-template** repository.

**For details on how to set up CI/CD pipeline and run CI/CD steps locally please see .circleci/README.md in this repository.**

# Serverless Framework

The [Serverless Framework](https://www.serverless.com/framework/docs/providers/aws/guide/serverless.yml/) is utilized to build integration services on AWS Lambda and deploy services and their infrastructures to AWS.

If you don’t already have [Node](https://nodejs.org/en/download/package-manager/) on your machine, you need to install it first.

Install the serverless CLI globally `sudo npm install -g serverless` or locally in the project folder `npm install --save-dev serverless`. When installing locally reference `serverless` like `./node_modules/.bin/serverless package` or with `npx serverless package`.

- [Welcome to the Serverless CLI Reference for AWS.](https://www.serverless.com/framework/docs/providers/aws/cli-reference/)
- [Hello World Python Example](https://www.serverless.com/framework/docs/providers/aws/examples/hello-world/python/)
- For information on Serverless AWS Lambda Events please refer to this [documentation](https://www.serverless.com/framework/docs/providers/aws/events/).

# Serverless Framework Plugins

- Here's the link to [Serverless Framework Plugins Directory](https://www.serverless.com/plugins/).
- For details on how to create a custom plugin for the Serverless Framework please consult this [documentation](https://www.serverless.com/framework/docs/providers/aws/guide/plugins/).

You will need the following two plugins for your every serverless application.

- [serverless-python-requirements](https://www.serverless.com/plugins/serverless-python-requirements). The plugin handles your Python packaging in Lambda. The plugin will bundle the python dependencies specified in your Pipfile when `sls deploy` is run.

- [serverless-pseudo-parameters](https://www.serverless.com/plugins/serverless-pseudo-parameters). The plugin allows you to use the CloudFormation Pseudo Parameters in your `serverless.yml`.

Depending on your serverless application the following plugins are useful and more.

- [serverless-domain-manager](https://github.com/amplify-education/serverless-domain-manager). The plugin creates a custom domain name for Lambda and API Gateway with Serverless.

- [serverless-wsgi](https://www.serverless.com/plugins/serverless-wsgi). The plugin allows you to deploy a Serverless REST API using the Python web framework Flask, Django, etc.

# Conventions

* place integration services in the `integrations/` folder (e.g. integrations/avalara)
* create global pylintrc at the root level
* pylintrc can be overridden if another pylintrc is placed at the project level

# Code structure

When developing integration services please follow the following code structure.

Make your code testable and write unit tests. Unit tests are required and are must have.

```
.circleci/
awsresources/ (To provision non-application related AWS resources)
integrations/
|  integration_name/ (Python/Serverless project)
|  |-- integration_name/ (Application/Root namespace)
|  |   |-- __init__.py
|  |   |-- aws/
|  |   |-- app/
|  |   |-- infrastructure/
|  |   |-- resources/
|  |-- tests/
|  |   |-- unit/ (Unit tests)
|  |   |   |-- __init__.py
|  |   |   |-- test_unit.py
|  |   |-- integration/ (Integration tests)
|  |   |   |-- __init__.py
|  |   |   |-- test_integration.py
|  |-- package-lock.json (Used to manage the serverless framework dependencies)
|  |-- package.json (Used to manage the serverless framework dependencies)
|  |-- pylintrc (If present, it overrides the pylintrc at the root level)
|  |-- Pipfile (Used to manage python dependencies)
|  |-- Pipfile.lock (Used to manage python dependencies)
|  |-- README.md (Integration readme)
|  |-- serverless.yml (Define your AWS Lambda Functions, events, AWS infrastructure resources)
config/
shared/ (Optional)
pylintrc
.gitignore
README.md (Tenant readme)
```

The `shared/` folder in the root directory is supposed to contain common adapters from the newstore-integrations repository. Move to this folder as less as possible and only necessary common packages and code from the newstore-integrations repository until we have a mechanism to distribute common packages.

# Package Management

## Pipenv

**Pipenv** is used for packaging and managing python dependencies. In addition it automatically creates and manages a virtualenv for your Python applications. For details on how to use **Pipenv** please consult [Pipenv](https://pipenv-fork.readthedocs.io/en/latest/) documentation.

`Pipfile` and `Pipfile.lock` are a replacement for the existing `requirements.txt` file.

Navigate to your `integration_name/` root directory and generate a Pipfile and Pipfile.lock by running the command `pipenv install`. For example, to install the latest version of the `requests` package use `pipenv install requests` and to install a specific version and any minor update use `pipenv install "requests~=1.2"`.

The concrete requirements for a Python application come from **Pipfile**. This includes where the packages should be fetched from and their loose version constraints. 

The details of the environment (all installed packages with pinned versions and other details) are stored in **Pipfile.lock**. This file is automatically generated and should not be modified by the developer.

## Node Package Manager (NPM)

Node Package Manager (npm) is used to install and manage the Serverless Framework plugins, especially external plugins.

For information on plugins you will need please see the **Serverless Framework Plugins** section above. You will need the [serverless-python-requirements](https://www.serverless.com/plugins/serverless-python-requirements) plugin for the Serverless Framework to handle your Python packaging in Lambda. The plugin will bundle the python dependencies specified in your Pipfile when `sls deploy` is run.

Make sure you are in your `integration_name/` root directory, then install the plugin.

### Using the Serverless Framework

```
sls plugin install -n serverless-python-requirements
```

This automatically generates **package.json** and **package-lock.json** files, and adds the plugin to your project's package.json and the plugins section of your **serverless.yml**.

The `sls plugin install` is just a wrapper for `npm install --save-dev`.

### Or using NPM

Create your project's **package.json** with the following content replacing {integration_name} with your actual integration_name.
```
{
  "name": "{integration_name}",
  "description": "",
  "version": "1.0.0",
  "dependencies": {},
  "devDependencies": {}
}
```
and run the command
```
npm install --save-dev serverless-python-requirements
```
This automatically generates **package-lock.json** and adds the plugin to your project's **package.json**. Add the plugin to the plugins section of your **serverless.yml**.
```
plugins:
  - serverless-python-requirements
```

To install a specific version of a certain plugin use
```
npm install --save-dev <pluginname>@<version>
```
