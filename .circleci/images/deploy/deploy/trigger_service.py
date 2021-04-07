import logging
from dataclasses import dataclass
from typing import Dict, Optional

from git import Repo
from gitdb.exc import BadName

from deploy.circleci import ApiV1, ApiV2

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ProjectInfo:
    user_name: str
    project_name: str


class TriggerService:

    def __init__(self, current_branch: str, project: ProjectInfo, apiV1: ApiV1, apiV2: ApiV2, repo: Repo):
        self.apiV2 = apiV2
        self.repo = repo
        self.apiV1 = apiV1
        self.project = project
        self.current_branch = current_branch

    def get_parent_branch(self) -> str:
        return "master"  # from gitflow to single branch

        # if self.current_branch.startswith("feature"):
        #     return "develop"
        # elif self.current_branch.startswith("hotfix"):
        #     return "master"
        # elif self.current_branch in ["master", "develop"]:
        #     return "master"
        # else:
        #     raise Exception(f"branch not supported {self.current_branch}")

    def _get_latest_build(self) -> Optional[Dict]:
        if self.current_branch not in ["master", "develop"]:
            logger.info(f"current branch is not master or develop. Not returning last build.")
            return None
        builds = self.apiV1.get_build(username=self.project.user_name, project=self.project.project_name,
                                      build_num=self.current_branch)
        last_build = next((b for b in builds if b["status"] == "success" and b["workflows"]["workflow_name"] != "ci"),
                          None)
        logger.info(f"got last build from API: {last_build}")
        if last_build:
            workflow_id = last_build["workflows"]["workflow_id"]
            workflow = self.apiV2.get_workflow(workflow_id)
            logger.info(f"got workflow {workflow}")

            success_status = ["success", "on_hold", "not_run"]
            if not workflow["status"] in success_status:
                logger.info(f"last workflow failed.")
                return None
        return last_build

    def _get_build_commit(self, build: Optional[Dict]) -> Optional[str]:
        last_hash = None
        if build:
            workflow_name = build["workflows"]["workflow_name"]
            logger.info(f"Found last build from workflow: {workflow_name}")
            last_hash = build["vcs_revision"]
        return last_hash

    def get_last_commit(self) -> (str, bool):
        is_parent = False
        last_build = self._get_latest_build()
        logger.info(f"Last build {last_build}")
        last_commit = self._get_build_commit(last_build)
        logger.info(f"Last hash {last_commit}")
        try:
            self.repo.commit(last_commit)
        except BadName:
            logger.info(f"commit does not exist: {last_commit}. reason could be rebase. setting to none.")
            last_commit = None
        except ValueError as ex:
            msg = str(ex)
            if f"{last_commit} missing" not in msg:
                raise ex
            last_commit = None

        if not last_commit:
            last_commit = self.get_parent_branch()
            logger.info(f"last commit not found. setting to parent branch {last_commit}")
            is_parent = True
        return last_commit, is_parent
