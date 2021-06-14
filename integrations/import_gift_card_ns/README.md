# Gift Card import to NewStore

## Data

The data is stored in the data folders invetory, pricebooks and products. You can add or update JSON
files and run `build-zips.sh` after any change to generate the archives.

## Import

1. Upload the zip files from the data folder to S3 `frankandoak-x-0-newstore-dmz/import_files`
2. Run the `frankandoak-import-gift-card-ns` lambda
