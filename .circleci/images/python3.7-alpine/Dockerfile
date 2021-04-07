FROM python:3.7-alpine

#alpine-sdk necessary for some python packages and circleci
#ssh necessary for circleci
RUN apk add --update --no-cache \
        alpine-sdk \
        libc6-compat \                 
        bash \
        openssh \        
        libxml2-dev \
        libxslt-dev \               
        nodejs \
        nodejs-npm \
        && pip install "pipenv==2018.11.26" && npm install -g serverless


WORKDIR /deploy

COPY ./.circleci/images/deploy /deploy

RUN pipenv install --deploy --system