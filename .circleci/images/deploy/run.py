# will lint, build, test
import logging

import click

from deploy.commands.integration import ci_group
from deploy.commands.workflow import workflow_group

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


@click.group()
def entry_point():
    pass


if __name__ == '__main__':
    entry_point.add_command(ci_group)
    entry_point.add_command(workflow_group)
    entry_point(auto_envvar_prefix="DEPLOY")
