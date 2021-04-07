from typing import Dict

from circleci.api import Api


class ApiV1(Api):

    def get_build(self, username, project, build_num, vcs_type='github'):
        endpoint = f'project/{vcs_type}/{username}/{project}/tree/{build_num}?filter=completed&limit=100&shallow=true'
        resp = self._request('GET', endpoint)
        return resp


class ApiV2(Api):

    def __init__(self, token,
                 username, project, vcs_type='github',
                 url='https://circleci.com/api/v2'):
        super().__init__(token, url)
        self.project = project
        self.vcs_type = vcs_type
        self.username = username

    def _get_slug(self):
        return f"{self.vcs_type}/{self.username}/{self.project}"

    def run_pipeline(self, branch: str, parameters: Dict):
        endpoint = f"project/{self._get_slug()}/pipeline"
        resp = self._request("POST", endpoint, {
            "branch": branch,
            "parameters": parameters
        })
        return resp

    def get_pipeline(self, pipeline_id: str):
        endpoint = f"project/{self._get_slug()}/pipeline/{pipeline_id}"
        return self._request("GET", endpoint)

    def get_pipeline_workflows(self, pipeline_id: str):
        endpoint = f"pipeline/{pipeline_id}/workflow"
        return self._request("GET", endpoint)

    def get_workflow(self, workflow_id: str):
        endpoint = f"workflow/{workflow_id}"
        return self._request("GET", endpoint)
