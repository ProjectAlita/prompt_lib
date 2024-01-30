import json
from typing import List
from flask import request
from pylon.core.tools import log
from sqlalchemy import or_

from tools import api_tools, auth, config as c

from ...models.all import Prompt, PromptTag, Collection, PromptVersion
from ...models.pd.list import MultiplePromptSearchModel, MultiplePromptTagListModel
from ...models.pd.collections import MultipleCollectionSearchModel
from ...utils.constants import PROMPT_LIB_MODE

from ...utils.searches import get_search_options
from ...utils.collections import get_filter_collection_by_tags_condition


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
        entities = request.args.getlist('entities')
        tags = [int(tag) for tag in request.args.getlist('tags')]

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
            data = get_filter_collection_by_tags_condition(project_id, tags)
            meta_data['collection']['filters'].append(
                # get_filter_collection_by_tags_condition(project_id, tags)
                data
            ) 
            meta_data['prompt']['filters'].append(
                Prompt.versions.any(PromptVersion.tags.any(PromptTag.id.in_(tags)))
            )
            meta_data['tag']['filters'].append(
                PromptTag.id.in_(tags)
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
