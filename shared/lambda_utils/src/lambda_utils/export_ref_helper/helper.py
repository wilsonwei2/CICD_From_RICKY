from lambda_utils.S3.S3Handler import S3Handler

def get_exp_ref_ids(s3_handler):
    """
    Gathers all the export_reference_ids that have not yet been 'used' and
    adds them to the header of the import endpoint.
    There is a contract that the inventory push should NOT happen before
    push_to_tibco has a chance to complete its run for the day.
    """
    unused_ids = []
    try:
        items = s3_handler.getS3().list_objects(
            Bucket=s3_handler.getS3BucketName(),
            Prefix='export_references/'
        ).get('Contents', {})

        # If our file matches exp_ref_id pattern, we're going to add it to our
        # header list.
        for i in items:
            # Break apart the key
            try:
                key = i['Key'].split('/')[1]
            except Exception:
                continue

            # export_reference_id regex
            if not key.endswith('.reference'):
                continue

            key_id = key.split('.')[0]
            unused_ids.append(key_id)
    except Exception as ex:
        logger.exception(ex)
    return unused_ids


def use_exp_ref_ids(s3_handler, exp_ref_ids=[]):
    """
    Set s3 exp_ref_id files being passed to 'used' so they're not used again.
    """
    nr_of_exported_ref_ids = 0
    s3_resource = s3_handler.getS3Resource()
    for exp_ref_id in exp_ref_ids:
        old_file = 'export_references/%s.reference' % exp_ref_id
        new_file = 'used/%s.used' % old_file
        s3_resource.Object(s3_handler.getS3BucketName(), new_file).copy_from(
            CopySource='%s/%s' % (s3_handler.getS3BucketName(), old_file))
        s3_resource.Object(s3_handler.getS3BucketName(), old_file).delete()
        nr_of_exported_ref_ids += 1

    return nr_of_exported_ref_ids


def set_exp_ref_id(s3_bucket, exp_ref_id, profile_name=None):
    """
    Save exported to tibco reference id in a s3 bucket to be processed later
    :param exp_ref_id: the reference id to save (filename)
    :param s3_bucket: the bucket where to save
    :return:
    """
    s3Handler = S3Handler(
        bucket_name=s3_bucket,
        key_name=('%s/%s.reference') % ('export_references', exp_ref_id),
        profile_name=profile_name
    )
    s3Handler.put_object()
