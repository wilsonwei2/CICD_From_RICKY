#!/bin/sh
SCRIPTPATH="$( cd -- "$(dirname "$0")" >/dev/null 2>&1 ; pwd -P )"

export TENANT=frankandoak

cd $SCRIPTPATH/data/

NS_TEMPLATE_SCRIPT=../cli/newstore_templates.sh
$NS_TEMPLATE_SCRIPT update-all en_US fr_CA
