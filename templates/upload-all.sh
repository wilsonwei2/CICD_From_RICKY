#!/bin/sh
SCRIPTPATH="$( cd -- "$(dirname "$0")" >/dev/null 2>&1 ; pwd -P )"

TENANT=frankandoak
locales=en_US,fr_CA
wait=10s

cd $SCRIPTPATH/data/

NS_TEMPLATE_SCRIPT=../cli/newstore_templates.sh
NS_ACCESS_TOKEN=`$NS_TEMPLATE_SCRIPT accesstoken`

for filename in *.j2; do
  filebase=$(basename "$filename" | cut -d. -f1)
  for locale in ${locales//,/ }; do
    echo Update template $filebase for $locale
    $NS_TEMPLATE_SCRIPT "update-template" $filebase $locale $filename
    sleep $wait
  done
done

for filename in *.css; do
  echo update asset $filename
  $NS_TEMPLATE_SCRIPT "update-style" $filename $filename
  sleep $wait
done
