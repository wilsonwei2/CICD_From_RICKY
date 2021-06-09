#!/bin/bash

rm -f ./products-gc.json.zip
rm -f ./prices-gc.json.zip
rm -f ./availabilities-gc.json.zip

cd products
zip ../products-gc.json.zip *

cd ../pricebooks
zip ../prices-gc.json.zip *

cd ../inventory
zip ../availabilities-gc.json.zip *

cd ..
