#!/usr/bin/python3
# coding=utf-8

#   Copyright 2024 EPAM Systems
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

""" Method """

from pylon.core.tools import log  # pylint: disable=E0611,E0401,W0611
from pylon.core.tools import web  # pylint: disable=E0611,E0401,W0611


class Method:  # pylint: disable=E1101,R0903,W0201
    """
        Method Resource

        self is pointing to current Module instance

        web.method decorator takes zero or one argument: method name
        Note: web.method decorator must be the last decorator (at top)
    """

    @web.method()
    def get_limits_from_payload(  # pylint: disable=R0913
            self,
            payload,
        ):
        """ Get limits """
        #
        max_tokens = None  # Max new (predict) tokens
        #
        if "max_tokens" in payload.merged_settings:
            max_tokens = payload.merged_settings["max_tokens"]
        else:
            try:
                max_tokens = payload.model_settings.max_tokens
            except:  # pylint: disable=W0702
                pass
        #
        token_limit = 0  # Model token limit
        #
        model_name = payload.merged_settings["model_name"]
        model_settings = None
        #
        for model_data in payload.merged_settings["models"]:
            if model_data["name"] == model_name:
                model_settings = model_data
        #
        if model_settings is not None and "token_limit" in model_settings:
            token_limit = model_settings["token_limit"]
        #
        if not token_limit and max_tokens:
            token_limit = max_tokens
        #
        return token_limit, max_tokens
