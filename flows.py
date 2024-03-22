from pylon.core.tools import web, log
from tools import flow_tools, rpc_tools

from .models.pd.legacy.prompts_pd import PredictPostModel
from .utils.ai_providers import AIProvider


@flow_tools.flow(
    uid='prompt',
    display_name='Prompt',
    tooltip='AI Predict prompt',
    icon_url='/flows/static/icons/prompt.svg',
)
def prompt(flow_context: dict, clean_data: PredictPostModel, **kwargs):
    project_id = flow_context.get('project_id')

    try:
        integration = AIProvider.get_integration(
            project_id=project_id,
            integration_uid=clean_data.integration_uid,
        )
        prompt_struct = rpc_tools.RpcMixin().rpc.call.prompts_prepare_prompt_struct(
            project_id, clean_data.prompt_id, clean_data.input_,
            clean_data.context, clean_data.examples, clean_data.variables
            # todo: handle ignore_template_error - maybe this need to be take from clean_data
        )
    except Exception as e:
        log.error(str(e))
        return {"ok": False, "error": str(e)}

    output = AIProvider.predict(project_id, integration, clean_data.integration_settings, prompt_struct)
    if not output['ok']:
        return output
    return {"ok": True, "result": output['response']}


@flow_tools.validator(flow_uid='prompt')
def prompt_validate(**kwargs) -> PredictPostModel:
    kwargs['input'] = kwargs.pop('prompt_input')
    kwargs['integration_settings'] = kwargs.pop('model_settings')
    variables = kwargs.pop('variables')
    kwargs['variables'] = {}
    for var in variables:
        kwargs['variables'][var['name']] = var['value']
    result = PredictPostModel.parse_obj(kwargs)
    result.integration_settings.pop('service_account_info', None)
    result.integration_settings.pop('api_token', None)
    return result
