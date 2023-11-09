#!/usr/bin/python3
# coding=utf-8

#   Copyright 2022 getcarrier.io
#
#   Licensed under the Apache License, Version 2.0 (the "License");
#   you may not use this file except in compliance with the License.
#   You may obtain a copy of the License at
#
#       http://www.apache.org/licenses/LICENSE-2.0
#
#   Unless required by applicable law or agreed to in writing, software
#   distributed under the License is distributed on an "AS IS" BASIS,
#   WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#   See the License for the specific language governing permissions and
#   limitations under the License.

""" RPC """
import json
from pydantic import parse_obj_as
from typing import List

from pylon.core.tools import web, log  # pylint: disable=E0611,E0401
from tools import rpc_tools, db
from ..models.prompts import Prompt
from ..models.tags import Tag
from ..models.pd.tag import PromptTagModel


def _delete_unused_tags(session):
    tags = session.query(Tag).all()
    for tag in tags:
        if not tag.prompts:
            session.delete(tag)


class RPC:  # pylint: disable=E1101,R0903
    """ RPC Resource """

    @web.rpc("prompts_get_tags", "get_tags")
    @rpc_tools.wrap_exceptions(RuntimeError)
    def _get_tags(self, project_id, prompt_id):
        with db.with_project_schema_session(project_id) as session:
            prompt = session.query(Prompt).filter_by(id=prompt_id).first()
            return [tag.to_json() for tag in prompt.tags]

    @web.rpc("prompts_get_all_tags", "get_all_tags")
    @rpc_tools.wrap_exceptions(RuntimeError)
    def _get_all_tags(self, project_id):
        with db.with_project_schema_session(project_id) as session:
            tags = session.query(Tag).all()
            return [tag.to_json() for tag in tags]

    @web.rpc("prompts_update_tags", "update_tags")
    @rpc_tools.wrap_exceptions(RuntimeError)
    def _update_tags(self, project_id, prompt_id, tags):
        with db.with_project_schema_session(project_id) as session:
            prompt = session.query(Prompt).get(prompt_id)
            prompt.tags.clear()
            tags = parse_obj_as(List[PromptTagModel], tags)
            for new_tag in tags:
                new_tag = new_tag.dict()
                tag = session.query(Tag).filter_by(tag=new_tag['tag']).first()
                if not tag:
                    tag = Tag(**new_tag)
                prompt.tags.append(tag)
            _delete_unused_tags(session)
            session.commit()
            return [tag.to_json() for tag in prompt.tags]
