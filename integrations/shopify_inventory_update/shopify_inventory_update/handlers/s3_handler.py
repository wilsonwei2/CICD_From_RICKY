import logging
import zipfile
import glob
import os
import io
import os.path
import time
import boto3 # pylint: disable=import-error
import botocore
import shutil
import json

logger = logging.getLogger(__name__)


class S3Handler:
    DOWNLOAD_PATH = '/tmp'

    def __init__(self, record=None, bucket_name=None, key_name=None, profile_name=None):
        self.s3 = None
        self.s3_resource = None
        self.object = None
        self.part_list = None
        self.part_object = None
        self.session = boto3.session.Session(profile_name=profile_name)
        if record is not None:
            self.bucket = record['s3']['bucket']
            self.bucket_name = record['s3']['bucket']['name']
            self.bucket_key = record['s3']['object']['key']
        elif bucket_name is not None:
            self.bucket_name = bucket_name
            self.bucket_key = key_name

    def getS3(self):
        if self.s3 is None:
            self.s3 = self.session.client('s3')
        return self.s3

    def getS3BucketName(self):
        return self.bucket_name

    def getS3Bucket(self):
        return self.bucket

    def getS3BucketKey(self):
        return self.bucket_key

    def getS3Resource(self):
        if self.s3_resource is None:
            self.s3_resource = self.session.resource('s3')
        return self.s3_resource

    def getMultiPartObject(self):
        return self.part_object

    def load_s3_Object(self):
        if self.object is None:
            self.object = self.getS3Resource().Object(self.bucket_name, self.bucket_key)

    def getKeySize(self):
        return self.object.content_length

    def start_multipart_upload(self, metadata, content_type):
        self.part_list = []
        if self.part_object is None:
            self.part_object = self.object.initiate_multipart_upload(
                Metadata=metadata, ContentType=content_type)

    def add_multipart_upload(self, part_number, part_data):
        mpart = self.part_object.Part(part_number=part_number)
        part_response = mpart.upload(Body=part_data)
        self.part_list.append({
            'ETag': part_response['ETag'],
            'PartNumber': part_number
        })

    def abort_multipart_upload(self):
        self.part_object.abort()

    def complete_multipart_upload(self):
        self.part_object.complete(MultipartUpload={'Parts': self.part_list})

    def put_object(self, data=b''):
        self.load_s3_Object()
        self.object.put(Body=data)

    def get_objects_list(self):
        response = self.getS3().list_objects_v2(Bucket=self.bucket_name, Prefix=self.bucket_key)
        if response:
            return response
        else:
            return None

    def getFiles(self):
        logger.info('Get File for Key --> %s' % self.getS3BucketKey())

        obj = self.getS3Resource().Object(self.getS3BucketName(), self.getS3BucketKey())

        if self.getS3BucketKey().endswith('.zip'):
            with io.BytesIO(obj.get()["Body"].read()) as tf:
                # rewind the file
                tf.seek(0)
                # Read the file as a zipfile and process the members
                with zipfile.ZipFile(tf, mode='r') as zf:
                    return {name: zf.read(name) for name in zf.namelist()}
        else:
            return {self.getS3BucketKey().split("/")[-1]: obj.get()['Body'].read()}

    def getS3File(self):
        """
        Retrieve a file from a S3 bucket based on a record. This auto unzip a file if the file comes zipped
        :param record: the json of the event containint the information to where retrieve the file
        :return: a double element, one containing the filename and the other the file data as a string
        """
        try:
            logger.info("Reading Bucket and key name")
            # logger.info("Bucket: %s | File: %s" % (self.getS3BucketName(), self.getS3BucketKey()))
            filename = self.getS3BucketKey().split("/")[-1]
            obj = self.getS3Resource().Object(self.getS3BucketName(), self.getS3BucketKey())

            if self.getS3BucketKey().endswith('.zip'):
                with io.BytesIO(obj.get()["Body"].read()) as tf:
                    # rewind the file
                    tf.seek(0)
                    # Read the file as a zipfile and process the members
                    with zipfile.ZipFile(tf, mode='r') as zipf:
                        for subfile in zipf.namelist():
                            if subfile.startswith('__MACOSX'):
                                continue
                            # Assumes only one.
                            return {'file': filename, 'data': zipf.read(subfile)}

            else:
                logger.info("Reading csv file")
                byte_data = obj.get()['Body'].read()
                return {'file': self.getS3BucketKey(), 'data': byte_data}
        except Exception as ex:
            logger.exception(ex)
            raise ex

    def get_json_files_dict(self):
        jsons = {}
        s3 = self.getS3Resource()
        bucket = s3.Bucket(self.getS3BucketName())
        for file in bucket.objects.all():
            if file.key[-4:] == 'json':
                jsons[file.key] = json.loads(file.get()['Body'].read())
        return jsons

    def validate_exists(self):
        if self.object is None:
            self.load_s3_Object()
        try:
            self.object.load()
        except botocore.exceptions.ClientError as e:
            if e.response['Error']['Code'] == "404":
                exists = False
            else:
                raise e
        else:
            exists = True
        return exists
