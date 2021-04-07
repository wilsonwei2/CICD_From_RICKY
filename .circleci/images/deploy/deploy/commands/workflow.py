import click

from deploy.trigger_pipelines import trigger_pipelines


@click.group(name="workflow")
def workflow_group():
    pass


@workflow_group.command()
def trigger():
    trigger_pipelines()
