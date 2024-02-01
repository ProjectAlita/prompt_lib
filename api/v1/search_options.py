from flask import request
from tools import api_tools, auth, config as c

from ...models.all import Prompt, PromptTag, Collection, PromptVersion
from ...models.pd.list import MultiplePromptSearchModel, MultiplePromptTagListModel
from ...models.pd.collections import MultipleCollectionSearchModel
from ...utils.constants import PROMPT_LIB_MODE

from ...utils.searches import (
    get_search_options, 
    get_prompt_ids_by_tags,
    get_filter_collection_by_tags_condition
)
from ...utils.collections import NotFound


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
        result = {}
        entities = request.args.getlist('entities[]')
        tags = tuple(set(int(tag) for tag in request.args.getlist('tags[]')))
        statuses = request.args.getlist('statuses[]')

        meta_data = {
            "prompt": {
                "Model": Prompt,
                "PDModel": MultiplePromptSearchModel,
                "joinedload_": [Prompt.versions],
                "args_prefix": "prompt",
                "filters": [],
            },
            "collection": {
                "Model": Collection,
                "PDModel": MultipleCollectionSearchModel,
                "joinedload_": None,
                "args_prefix": "col",
                "filters": [],
            },
            "tag": {
                "Model": PromptTag,
                "PDModel": MultiplePromptTagListModel,
                "joinedload_": None,
                "args_prefix": "tag",
                "filters": []
            } 
        }

        if tags:
            try:
                data = get_filter_collection_by_tags_condition(project_id, tags)
                meta_data['collection']['filters'].append(data) 
            except NotFound:
                entities = [entity for entity in entities if entity != "collection"]
                result['collection'] = {
                    "total": 0,
                    "rows": []
                }

            prompt_ids = get_prompt_ids_by_tags(project_id, tags)
            meta_data['prompt']['filters'].append(
                Prompt.id.in_(prompt_ids)
            )
            
            if len(tags) > 1:
                entities = [entity for entity in entities if entity != "tag"]
                result['tag'] = {
                    "total": 0,
                    "rows": []
                }
            else:
                meta_data['tag']['filters'].append(
                    PromptTag.id.in_(tags)
                )
        
        if statuses:
            meta_data['prompt']['filters'].append(
                (Prompt.versions.any(PromptVersion.status.in_(statuses)))
            )
            meta_data['collection']['filters'].append(
                Collection.status.in_(statuses)
            )

        for section, data in meta_data.items():
            if section in entities:
                result[section] = get_search_options(project_id, **data)
        return result, 200




class API(api_tools.APIBase):
    url_params = api_tools.with_modes([
        '<int:project_id>',
    ])

    mode_handlers = {
        PROMPT_LIB_MODE: PromptLibAPI,
    }
