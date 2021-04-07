from deploy.circleci import ApiV2
from deploy.utils import INTEGRATION_ROOT, has_make_file
import logging

logger = logging.getLogger(__name__)


def run_workflow(integration_path: str, branch: str, api: ApiV2):
    integration_name = integration_path.replace(f"{INTEGRATION_ROOT}/", "")
    logger.info(f"got integration name {integration_name}")

    run_make = has_make_file(integration_name)

    if run_make:
        logger.info("make file found. Running make workflow")

    params = {
        "run_default": not run_make,
        "trigger": False,  # always False
        "integration": integration_name,
        "run_make": run_make
    }
    return api.run_pipeline(branch, params)
