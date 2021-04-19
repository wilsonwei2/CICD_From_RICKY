# Copyright (C) 2016 NewStore Inc, all rights reserved.

# wraps authentication library to perform job creation and import
import logging
import datetime
import time
import sys

logger = logging.getLogger(__file__)
logger.setLevel(logging.INFO)

if sys.version_info >= (3,0):
    import io
else:
    from StringIO import StringIO


from zipfile import ZipFile, ZIP_DEFLATED
import json
from newstore_adapter import impex, Context

# Remove this when explore fixes the NA-10222
# This is a hack to json loader that forces the float number to have teo decimals letters
from json import encoder
encoder.FLOAT_REPR = lambda o: format(o, '.2f')

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


class JobsManager:

    def __init__(self, env_variables=None, import_typology=None, s3_handler=None, source_uri=None, is_full=None):
        self.env_variables = env_variables
        self.import_typology = import_typology
        self.s3_handler = s3_handler
        self.source_uri = source_uri

    def get_env_variables(self):
        return self.env_variables

    def get_import_typology(self):
        return self.import_typology

    def get_s3_handler(self):
        return self.s3_handler

    def get_source_uri(self):
        return self.source_uri

    def create_job(self, is_full):
        try:
            logger.info("Creating import for source_uri %s" % self.get_source_uri())
            ctx = Context(url=self.get_env_variables()["url_api"])
            ctx.set_user(self.get_env_variables()["import_login"], self.get_env_variables()["import_password"])
            import_job = impex.Job(ctx)

            meta = {
                "provider": self.get_env_variables()["meta_provider"],
                "name": self.get_env_variables()["meta_name"],
                "source_uri": self.get_source_uri(),
                "revision": int(round(time.time() * 1000)),
                "entities": [self.get_import_typology()],
                "full": is_full
            }

            # Create import job
            logger.info("Creating import job, meta data: {%s}", meta)
            import_job = import_job.create(meta)
            logger.info("Created import job, import id %s", import_job.import_id)
            return import_job
        except Exception as ex:
            raise(ex)

    def fail_job(self, import_job, reason):
        # Fail import job
        logger.info("Set job for import_id %s to FAILED for the following reason: %s" % (import_job.import_id, reason))
        response = import_job.failed(reason)
        logger.info("Response: %s", response['response'])
        logger.info("Response Code: %s", response['response_code'])
        return response

    def start_job(self, import_job, transformed_uri):
        # Start import job
        logger.info("Starting import job for import id %s", import_job.import_id)
        response = import_job.start(transformed_uri)
        logger.info("import job finished")

        logger.info("Response: %s", response['response'])
        logger.info("Response Code: %s", response['response_code'])
        return response

    def create_collection(self, dictionary):
        """
        Create a ZIP archive from a collection of contents taken from a dictionary.
        """
        basename = "%s-%s" % (
            self.get_import_typology(),
            datetime.datetime.utcnow().strftime("%Y%m%d%H%M%S.%f")
        )

        try:
            if sys.version_info >= (3, 0):
                zip_string_buffer = io.BytesIO()
            else:
                zip_string_buffer = StringIO()

            with ZipFile(zip_string_buffer, mode='w', compression=ZIP_DEFLATED) as zip_archive:
                for item in dictionary:
                    if sys.version_info >= (3, 0):
                        data = io.StringIO()
                    else:
                        data = StringIO()
                    data.write(json.dumps(dictionary[item], indent=4))
                    filename = "%s-%s.json" % (basename, item)
                    zip_archive.writestr(filename, data.getvalue())
                    data.close()
        except Exception as e:
            raise Exception(e)

        object_key = "import_files/%s.zip" % basename
        bucket_name = self.get_env_variables()["s3_bucket"]
        source_uri = "s3://%s/%s" % (bucket_name, object_key)
        self.get_s3_handler().getS3Resource().Bucket(bucket_name).put_object(
            Key=object_key,
            Body=zip_string_buffer.getvalue())
        zip_string_buffer.close()

        return source_uri

    def create_file(self, inventory, append_to_file_name_typology=None):
        # Set filename & paths
        if append_to_file_name_typology is not None:
            filename = "%s-%s-%s.json" % (
                self.get_import_typology(),
                append_to_file_name_typology,
                datetime.datetime.utcnow().strftime("%Y%m%d%H%M%S.%f")
            )
        else:
            filename = "%s-%s.json" % (
                self.get_import_typology(),
                datetime.datetime.utcnow().strftime("%Y%m%d%H%M%S.%f")
            )

        source_uri = "s3://%s/import_files/%s" % (self.get_env_variables()["s3_bucket"], filename + ".zip")

        # Create file on s3
        try:
            if sys.version_info >= (3, 0):
                data = io.StringIO()
                data.write(json.dumps(inventory, indent=None, separators=(',', ':')))
                zip_string_buffer = io.BytesIO()
            else:
                data = StringIO()
                data.write(json.dumps(inventory, indent=None, separators=(',', ':')))
                zip_string_buffer = StringIO()
        except Exception as e:
            raise Exception(e)

        with ZipFile(zip_string_buffer, mode='w', compression=ZIP_DEFLATED) as zip_archive:
            zip_archive.writestr(filename, data.getvalue())
        self.get_s3_handler().getS3Resource().Bucket(self.get_env_variables()["s3_bucket"]).put_object(
            Key='import_files/%s' % filename + ".zip",
            Body=zip_string_buffer.getvalue())
        data.close()

        return source_uri
