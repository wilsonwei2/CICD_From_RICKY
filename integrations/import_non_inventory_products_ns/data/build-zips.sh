#!/bin/bash

rm -f ./non-inventory-products.json.zip
rm -f ./non-inventory-prices.json.zip
rm -f ./non-inventory-availabilities.json.zip

cd products
zip ../non-inventory-products.json.zip *

cd ../pricebooks
zip ../non-inventory-prices.json.zip *

cd ../inventory
zip ../non-inventory-availabilities.json.zip *

cd ..
