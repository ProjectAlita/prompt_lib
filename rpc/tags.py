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
# from ..models.prompts import Prompt
# from ..models.tags import Tag
# from ..models.pd.tag import PromptTagModel


class RPC:  # pylint: disable=E1101,R0903
    """ RPC Resource """
    ...
