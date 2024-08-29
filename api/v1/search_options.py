from tools import api_tools, auth, config as c
from pylon.core.tools import log

from ...models.pd.misc import MultiplePromptSearchModel
from ...models.all import Prompt, PromptVersion, PromptVersionTagAssociation
from ...utils.constants import PROMPT_LIB_MODE
from ...utils.searches import get_search_options_one_entity


def _merge_search_options_results(search_results):
    assert len(search_results) != 0

    res = {
        "collection": {
            "total": 0,
            "rows": []
        },
        "tag": {
            "total": 0,
            "rows": []
        }
    }
    for search_result in search_results:
        for entity_name, entity_result in search_result.items():
            if entity_name in ('collection', 'tag'):
                for item in entity_result['rows']:
                    if item not in res[entity_name]['rows']:
                        res[entity_name]['rows'].append(item)
                res[entity_name]['total'] = len(res[entity_name]['rows'])
            elif entity_name not in res:
                res[entity_name] = entity_result
            else:
                continue

    return res


class PromptLibAPI(api_tools.APIModeHandler):
    @auth.decorators.check_api(
        {
            "permissions": ["models.prompt_lib.prompts.search"],
            "recommended_roles": {
                c.ADMINISTRATION_MODE: {"admin": True, "editor": True, "viewer": False},
                c.DEFAULT_MODE: {"admin": True, "editor": True, "viewer": False},
            },
        }
    )
    @api_tools.endpoint_metrics
    def get(self, project_id: int):
        results = []

        res = get_search_options_one_entity(
            project_id,
            'prompt',
            Prompt,
            PromptVersion,
            MultiplePromptSearchModel,
            PromptVersionTagAssociation
        )
        results.append(res)

        try:
            res = self.module.context.rpc_manager.timeout(2).datasources_get_search_options(project_id)
        except Exception as ex:
            log.debug(ex)
            log.warning("Datasource plugun is not available, skipping for search_options")
        else:
            results.append(res)

        try:
            res = self.module.context.rpc_manager.timeout(2).applications_get_search_options(project_id)
        except Exception as ex:
            log.debug(ex)
            log.warning("Application plugun is not available, skipping for search_options")
        else:
            results.append(res)

        result = _merge_search_options_results(results)

        return result, 200


class API(api_tools.APIBase):
    url_params = api_tools.with_modes([
        '<int:project_id>',
    ])

    mode_handlers = {
        PROMPT_LIB_MODE: PromptLibAPI,
    }
