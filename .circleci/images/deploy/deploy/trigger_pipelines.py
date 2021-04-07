import logging
import os
import time

from git import Repo

from deploy.circleci import ApiV1, ApiV2
from deploy.diff_service import DiffService
from deploy.trigger_service import ProjectInfo, TriggerService
from deploy.updater import update_pipelines
from deploy.utils import get_integration_path, get_base_dir
from deploy.workflow import run_workflow

logger = logging.getLogger(__name__)

integration_path = get_integration_path()
base_dir = get_base_dir()
logger.info(f"integration path {integration_path}")


def trigger_pipelines():
    # todo: move into custom

    token = os.environ["CIRCLE_TOKEN"]

    info = ProjectInfo(
        user_name=os.environ["CIRCLE_PROJECT_USERNAME"],
        project_name=os.environ["CIRCLE_PROJECT_REPONAME"],
    )

    api = ApiV1(token)

    apiv2 = ApiV2(username=info.user_name, project=info.project_name, token=token)

    logger.info(f"info: {info}")
    repo = Repo(base_dir)
    current_commit = os.environ["CIRCLE_SHA1"]
    current_branch = os.environ["CIRCLE_BRANCH"]
    trigger_service = TriggerService(current_branch=current_branch, project=info, apiV1=api, repo=repo, apiV2=apiv2)
    diff_service = DiffService(current_commit, repo, base_dir, integration_path)

    last_commit, is_parent = trigger_service.get_last_commit()

    logger.info(f"comparing diffs from current {current_commit} to last {last_commit}")

    if last_commit == "master" and current_branch == "master":
        logger.info(f"First commit. And no previous builds were found.")
        changed_integrations = diff_service.get_integrations()
    else:
        changed_integrations = diff_service.get_changed_integrations(last_commit, is_parent)

    logger.info(f"got changed integrations {changed_integrations}")

    running_pipelines = []

    for changed_integration in changed_integrations:
        response = run_workflow(changed_integration, current_branch, apiv2)
        running_pipelines.append({
            "id": response["id"],
            "integration": changed_integration
        })

    while len(running_pipelines) > 0:
        logger.info("Waiting for pipelines to finish...")
        time.sleep(30)
        logger.info("Updating status.")
        pipelines = update_pipelines(running_pipelines, apiv2)
        if len(pipelines) < 1:
            logger.info(f"All pipelines have been finished. Finishing CI")
            break
        logger.info(f"There are still running pipelines: {pipelines}. Continue to wait.")
        running_pipelines = pipelines

    logger.info(f"Finished all running integrations.")
