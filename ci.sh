#!/bin/sh

#########################################
# Shortcut for ci calls
#
# ./ci.sh <integration> lint
# ./ci.sh <integration> unittests
# ./ci.sh <integration> integrationtests
# ./ci.sh <integration> tests
#########################################

docker run -t --rm -v ${PWD}:/project 142087941708.dkr.ecr.us-east-1.amazonaws.com/devops-build-cicd:python3.7-buster python run.py ci --integration $@
