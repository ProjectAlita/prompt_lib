from dataclasses import make_dataclass
from functools import wraps
from operator import attrgetter

from pylon.core.tools import log
from tools import rpc_tools
from ...promptlib_shared.utils.exceptions import (
    EntityNotAvailableCollectionError,
)


_RPC_CALL = rpc_tools.RpcMixin().rpc.call

#
# Extend the following global only with supported collection entities
_ENTITIES_INFO_IN = (
    (
        "prompt",
        "prompts",
        _RPC_CALL.prompt_lib_get_prompt_model,
        _RPC_CALL.prompt_lib_get_version_model
    ),
    (
        "datasource",
        "datasources",
        _RPC_CALL.datasources_get_datasource_model,
        _RPC_CALL.datasources_get_version_model
    ),
    (
        "application",
        "applications",
        _RPC_CALL.applications_get_application_model,
        _RPC_CALL.applications_get_version_model
    ),
)
#####################################################################


def _make_entity_registry():
    """ Construct entity registry with obj attrs, just for usage convenience """

    def _rpc_wrapper(rpc_fun, entity_name):
        """ Indicate that collection entity type is not available if rpc call was unsuccessful """

        @wraps(rpc_fun)
        def wrapper(*args, **kwargs):
            try:
                return rpc_fun(*args, **kwargs)
            except Exception as ex:
                log.error(ex)
                raise EntityNotAvailableCollectionError(
                        f"collection {entity_name=} is not available"
                ) from None
        return wrapper

    ret = []
    for entity_name, entities_name, model_rpc, version_rpc in _ENTITIES_INFO_IN:
        reg_dict = {
            "entity_name":  entity_name,
            "entities_name": entities_name,
            "get_entity_type": _rpc_wrapper(model_rpc, entity_name),
            "get_entity_version_type": _rpc_wrapper(version_rpc, entity_name),
            "get_entity_field": attrgetter(entity_name),
            "get_entities_field": attrgetter(entities_name),
        }
        ret.append(make_dataclass("EntityReg_"+entity_name, reg_dict)(**reg_dict))

    return ret


ENTITY_REG = _make_entity_registry()


def get_entity_info_by_name(name):
    for ent in ENTITY_REG:
        if name == ent.entity_name or name == ent.entities_name:
            return ent
    else:
        raise EntityNotAvailableCollectionError(
                f"collection entity name {name} is not available"
        )


def get_entity_type_by_name(name):
    entity_info = get_entity_info_by_name(name)
    return entity_info.get_entity_type()
