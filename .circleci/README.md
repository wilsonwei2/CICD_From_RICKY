

This repository contains automation CI/CD scripts for CircleCI.

# How to Set Up CI/CD Pipeline

To set up the CI/CD pipeline please follow this [documentation](https://goodscloud.atlassian.net/wiki/spaces/FS/pages/1484193941/How+to+Set+Up+CI+CD+Pipeline).

# Overview

CircleCI **config.yml** file orchestrates the entire continuous delivery process from build to deploy through a single file.

CircleCI utilizes a custom docker image to run CI/CD jobs whithin that image. 
* Packaging all required tools into a custom docker image removes the need to install them for every job.
* Adding installation scripts to a custom docker image reduces the number of lines in your **.circleci/config.yml** file.
* Having a custom docker image allows us to be in control of an execution environment for the CI/CD pipeline.

The [Serverless Framework](https://www.serverless.com/framework/docs/providers/aws/guide/serverless.yml/) is utilized to build integration services on AWS Lambda and deploy services and their infrastructures to AWS.

Create the **serverless-deploy** IAM user and IAM Managed policy **serverless-deploy-policy** and attach it to the serverless-deploy user in each AWS deployment environment. 
* Serverless Framework uses the serverless-deploy user to deploy integration services. 
* The serverless-deploy user should have the minimum necessary permissions (least privilege principle) to create and manage resources in AWS.
* The serverless-deploy user allows you to push the docker image to your AWS ECR Repository.

Create S3 Deployment Bucket following the naming convention **{tenant_name}-{stage}-0-newstore-dmz-deploy**. Serverless Framework uses this bucket to store deployment packages of integration services.

Create AWS ECR Repository with the name **devops-build-cicd** in the **Sandbox** environment and AWS Region **us-east-1**.
* AWS ECR is used to store, manage, and deploy Docker container images which are used as execution environments for the CI/CD pipeline.
* CircleCI pulls a docker image from your AWS ECR Repository and runs CI/CD jobs and workflows inside the docker image.

Please follow the instructions below to build a custom docker image on localhost and push the docker image to your AWS ECR Repository.

# Build docker image

Build a custom docker image which is used by CircleCI and locally to run CI/CD jobs whithin that docker image. 

```
docker build -t {Your_AWS_ECR_Repository_URL}:python3.7-buster -f ./.circleci/images/python3.7-buster/Dockerfile --no-cache .
```

# Set AWS Credentials as Environment variables

AWS CLI and other tools need access to an AWS account to do their job. The **serverless-deploy** IAM user can be used to push the docker image to your AWS ECR Repository.

Set the AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY of the **serverless-deploy** user in **sandbox** as environment variables so they are accessible to AWS CLI in your shell.

```
export AWS_ACCESS_KEY_ID={Your_AWS_ACCESS_KEY_ID_x}
export AWS_SECRET_ACCESS_KEY={Your_AWS_SECRET_ACCESS_KEY_x}
```

# Authenticate to AWS ECR Repository

To push and pull Docker images with your AWS ECR Repository you need to authenticate the Docker CLI to your AWS ECR Repository. The following command requires the [AWS CLI version 2](https://docs.aws.amazon.com/cli/latest/userguide/install-cliv2.html) to be installed on your localhost machine. The command uses the AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY environment variables in your shell or your local AWS profile.

```
aws ecr get-login-password --region us-east-1 | docker login --username AWS --password-stdin {Your_AWS_ECR_Repository_URL}
```

# Push docker image to AWS ECR Repository

After authenticating to your AWS ECR Repository you can push the docker image you created to AWS ECR Repository. CircleCI pulls the docker image from the ECR Repository and runs CI/CD jobs within that image.

```
docker push {Your_AWS_ECR_Repository_URL}:python3.7-buster
```

# How to Run CI/CD steps On a Docker Container

To run CI/CD steps (install packages, lint, unittests, etc.) within the custom docker image on your localhost machine please use the following commands.

## Help

```
docker run -v ${PWD}:/project {Your_AWS_ECR_Repository_URL}:python3.7-buster python run.py
```

## Run CI on localhost

Make your code testable and write unit tests. Unit tests are required and are must have.

The following command installs `python packages`, runs `lint` and `unit tests` within a docker container on your localhost machine:
```
docker run -v ${PWD}:/project {Your_AWS_ECR_Repository_URL}:python3.7-buster python run.py ci --integration {integration_name} cibuild
```

## Lint

```
docker run -v ${PWD}:/project {Your_AWS_ECR_Repository_URL}:python3.7-buster python run.py ci --integration {integration_name} lint
```

## Tests

To run unit tests:
```
docker run -v ${PWD}:/project {Your_AWS_ECR_Repository_URL}:python3.7-buster python run.py ci --integration {integration_name} unittests
```

To run integration tests:
```
docker run -v ${PWD}:/project {Your_AWS_ECR_Repository_URL}:python3.7-buster python run.py ci --integration {integration_name} integrationtests
```

To run both unit and integration tests:
```
docker run -v ${PWD}:/project {Your_AWS_ECR_Repository_URL}:python3.7-buster python run.py ci --integration {integration_name} tests
```

## Deploy

The deployment from the localhost machine is not recommended.