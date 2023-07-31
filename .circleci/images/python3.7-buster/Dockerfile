FROM python:3.7-slim-buster

# Update and install curl and git
RUN set -xe && apt-get update && apt-get -y upgrade && apt-get install -y --no-install-recommends curl git

# Install node.js
RUN curl -sL https://deb.nodesource.com/setup_14.x | bash && apt-get install -y nodejs

# Install other dependencies
RUN apt-get install -y --no-install-recommends openssh-client libxml2-dev libxslt-dev

# Install pipenv and Serverless
RUN pip install pipenv==2021.5.29 && npm install serverless@2.68.0 -g --unsafe-perm=true

WORKDIR /deploy

COPY ./.circleci/images/deploy /deploy

RUN pipenv install --deploy --system