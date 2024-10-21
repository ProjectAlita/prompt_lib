from tools import api_tools, db, auth, serialize, config as c

from ...models.pd.pr import PullRequestResponse

from ...utils.constants import PROMPT_LIB_MODE
from ...utils.prompt_utils import get_prompt_with_versions_dict, get_entity_diff


class PromptLibAPI(api_tools.APIModeHandler):
    @auth.decorators.check_api({
        "permissions": ["models.config"],
        "recommended_roles": {
            c.ADMINISTRATION_MODE: {"admin": True, "editor": True, "viewer": False},
            c.DEFAULT_MODE: {"admin": True, "editor": True, "viewer": False},
        }})
    def get(
            self, project_id: int, prompt_id: int,
            target_project_id: int, target_prompt_id: int, **kwargs
    ):
        source_prompt, source_prompt_versions = get_prompt_with_versions_dict(
            project_id, prompt_id, exclude={'created_at'}
        )
        target_prompt, target_prompt_versions = get_prompt_with_versions_dict(
            target_project_id, target_prompt_id, exclude={'created_at'}
        )

        if not source_prompt:
            return {'error': f'No such prompt with id {prompt_id} in project {project_id}'}, 400

        if not target_prompt:
            return {'error': f'No such prompt with id {target_prompt} in project {target_project_id}'}, 400

        source_versions_dict = {version['id']: version for version in source_prompt_versions}
        target_versions_dict = {version['id']: version for version in target_prompt_versions}

        source_prompt.pop('id')
        target_prompt.pop('id')
        prompt_diff = get_entity_diff(source_prompt, target_prompt)

        versions_diff = []

        for version_id, target_version in target_versions_dict.items():
            source_version = source_versions_dict.get(version_id)
            if source_version:
                source_version.pop('id')
                target_version.pop('id')
                version_diff = get_entity_diff(source_version, target_version)
                versions_diff.append(version_diff)

        return serialize(PullRequestResponse(prompt_diff=prompt_diff, versions_diff=versions_diff))


class API(api_tools.APIBase):
    url_params = api_tools.with_modes([
        '<int:project_id>/<int:prompt_id>',
        '<int:project_id>/<int:prompt_id>/<int:target_project_id>/<int:target_prompt_id>',
    ])

    mode_handlers = {
        PROMPT_LIB_MODE: PromptLibAPI,
    }
