#!/bin/sh

#########################################
# Shortcut for ci calls
#
# ./ci.sh <integration> lint
# ./ci.sh <integration> unittests
# ./ci.sh <integration> integrationtests
# ./ci.sh <integration> tests
#########################################

docker run -t --rm -v ${PWD}:/project {Your_AWS_ECR_Repository_URL}:python3.7-buster python run.py ci --integration $@
