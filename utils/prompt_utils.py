from typing import Generator

from tools import db, auth, rpc_tools
from pylon.core.tools import log


def set_columns_as_attrs(q_result, extra_columns: list) -> Generator:
    for i in q_result:
        try:
            entity, *extra_data = i
            for k, v in zip(extra_columns, extra_data):
                setattr(entity, k, v)
        except TypeError:
            entity = i
        yield entity


def fire_searched_event(project_id: int, search_data: dict):
    rpc_tools.EventManagerMixin().event_manager.fire_event(
        "prompt_lib_search_conducted", 
        {
            "project_id": project_id,
            "search_data": search_data,
        }
    )
