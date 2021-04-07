import os
import subprocess

import click
import pytest
import sys
from click import Context
from pylint.lint import Run

from deploy.utils import get_base_dir, has_make_file, get_integration_dir


@click.group(name="ci")
@click.option('-i', '--integration', type=str, required=True)
@click.pass_context
def ci_group(ctx: Context, integration: str):
    if has_make_file(integration):
        raise Exception("make file not supported currently")
    click.echo(f"handling integration: {integration}")
    ctx.obj = {
        "integration": integration
    }

@ci_group.command()
@click.pass_context
def cibuild(ctx: Context):
    integration = ctx.obj["integration"]
    _install_python_dependencies(integration)
    _run_linting(integration)
    _run_tests(integration, "unit")
    sys.exit(0)

@ci_group.command()
@click.pass_context
def lint(ctx: Context):
    integration = ctx.obj["integration"]
    _install_python_dependencies(integration)
    _run_linting(integration)
    sys.exit(0)

@ci_group.command()
@click.pass_context
def unittests(ctx: Context):
    integration = ctx.obj["integration"]
    _install_python_dependencies(integration)
    _run_tests(integration, "unit")
    sys.exit(0)

@ci_group.command()
@click.pass_context
def integrationtests(ctx: Context):
    integration = ctx.obj["integration"]
    _install_python_dependencies(integration)
    _run_tests(integration, "integration")
    sys.exit(0)

@ci_group.command()
@click.pass_context
def tests(ctx: Context):
    integration = ctx.obj["integration"]
    _install_python_dependencies(integration)
    _run_tests(integration, "unit")
    _run_tests(integration, "integration")
    sys.exit(0)

@ci_group.command()
@click.option('-t', '--tenant', required=True)
@click.option('-s', '--stage', required=True)
@click.pass_context
def deploy(ctx: Context, tenant: str, stage: str):
    integration = ctx.obj["integration"]
    _deploy(integration, tenant, stage)
    sys.exit(0)


def _install_python_dependencies(integration: str):
    integration_root_dir = get_integration_dir(integration)
    click.echo(f'Install python dependencies {integration_root_dir}')
    return_code = subprocess.call(["pipenv", "install", "--system"], cwd=integration_root_dir)
    click.echo(f"Pipenv exited with status {return_code}")

def _run_linting(integration: str):
    integration_root_dir = get_integration_dir(integration)
    code_dir = os.path.join(integration_root_dir, integration)
    click.echo(f'Linting {code_dir}')
    project_pylint = os.path.join(integration_root_dir, "pylintrc")
    global_pylint = os.path.join(get_base_dir(), "pylintrc")
    if os.path.exists(project_pylint):
        pylint_config = project_pylint
    else:
        pylint_config = global_pylint
    click.echo(f"Using pylintrc: {pylint_config}")
    runner = Run(['-v', f"--rcfile={pylint_config}", code_dir], do_exit=False)
    click.echo(f"Pylint exited with status {runner.linter.msg_status}")
    _exit_on_error_code(runner.linter.msg_status)

def _run_tests(integration: str, tests_folder: str):
    integration_root_dir = get_integration_dir(integration)
    tests_dir = os.path.join(integration_root_dir, f"tests/{tests_folder}")
    click.echo(f"Run tests: {tests_dir}")
    return_code = subprocess.call(["pytest", "-v"], cwd=tests_dir)
    click.echo(f"Pytest exited with status {return_code}")
    _exit_on_error_code(return_code)

def _deploy(integration: str, tenant: str, stage: str):
    integration_root_dir = get_integration_dir(integration)
    click.echo(f"Deploying integration: {integration_root_dir}, stage: {stage}, tenant: {tenant}")
    subprocess.call(["npm", "install"], cwd=integration_root_dir)
    subprocess.call(["serverless", "print", "--stage", stage, "--tenant", tenant], cwd=integration_root_dir)
    # right now it only supports serverless, later we could introduce SAM depending on which file is found
    return_code = subprocess.call(["serverless", "deploy", "--stage", stage, "--tenant", tenant], cwd=integration_root_dir)
    click.echo(f"Serverless exited with status {return_code}")
    _exit_on_error_code(return_code)

def _exit_on_error_code(return_code):
    if return_code != 0:
        sys.exit(return_code)
