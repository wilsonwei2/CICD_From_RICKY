import os
import logging
from git import Repo

from deploy.utils import log_diffs

logger = logging.getLogger(__name__)


class DiffService:

    def __init__(self, current_commit: str, repo: Repo, base_dir: str, integration_root: str):
        self.current_commit = current_commit
        self.repo = repo
        self.base_dir = base_dir
        self.integration_root = integration_root

    def get_integrations(self):
        return [f.path.replace(f"{self.base_dir}/", "") for f in os.scandir(self.integration_root) if f.is_dir()]

    def get_changed_integrations(self, last_commit: str, is_parent: bool):
        changed_integrations = []
        integrations = self.get_integrations()
        logger.info(f"Found integrations {integrations}")
        for integration in integrations:
            logger.info(f"getting integration diff for {integration}")
            if is_parent:
                has_diffs = self.has_diffs_to_parent(last_commit, integration)
            else:
                has_diffs = self.has_diffs_to_previous_commit(last_commit, integration)
            if has_diffs:
                logger.info(f"found diffs in integration {integration}")
                changed_integrations.append(integration)
        return changed_integrations

    def has_diffs_to_parent(self, parent_branch: str, integration_path: str):
        git = self.repo.git
        diff = git.diff("--numstat", f"origin/{parent_branch}...{self.current_commit}", "--", integration_path)
        logger.info(f"got diff string: {diff}")
        return bool(diff)

    def has_diffs_to_previous_commit(self, last_commit: str, integration_path: str):
        circle_commit = self.repo.commit(self.current_commit)
        diffs = circle_commit.diff(last_commit, paths=[integration_path])
        log_diffs(diffs)
        return len(diffs) > 0
