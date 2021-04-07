from typing import List
import logging
import json

from deploy.circleci import ApiV2

logger = logging.getLogger(__name__)


def update_pipelines(pipelines: List, api: ApiV2):
    logger.info(f"Got running flows: {pipelines}")
    running_pipelines = []
    success_status = ["not_run", "success", "on_hold"]  # skip
    failed_status = ["cancelled", "failing", "failed", "needs_setup"]  # raise error
    progress_status = ["running"]  # add to running pipelines
    for pipeline in pipelines:
        response = api.get_pipeline_workflows(pipeline["id"])
        logger.info(f"Got response {json.dumps(response, indent=4)}")
        workflow = response["items"][0]
        status = workflow["status"]
        logger.info(f"Got status {status}")
        if status in progress_status:
            logger.info("Status is in progress. Adding to running")
            running_pipelines.append(pipeline)
            continue
        if status in success_status:
            logger.info(f"Status finished. Skipping...")
            continue
        raise Exception(f"Status not found in either progress {progress_status} or success {success_status}")

    return running_pipelines
