FROM python:3.7-slim-buster

#ssh necessary for circleci
RUN set -xe && apt-get update && apt-get -y upgrade && apt-get install -y --no-install-recommends \
        git \
        openssh-client \
        libxml2-dev \
        libxslt-dev \
        nodejs \
        npm \
        && pip install "pipenv==2018.11.26" && npm install -g serverless@2.34.0 \
        && apt-get clean \
        && rm -rf /var/lib/apt/lists/*


WORKDIR /deploy

COPY ./.circleci/images/deploy /deploy

RUN pipenv install --deploy --system
