from typing import List, Literal, Optional

from pydantic import BaseModel, root_validator


class ImportData(BaseModel):
    import_uuid: str
    entity: str
    name: str
    description: str
    is_selected: bool = False

    def map_postponed_ids(self, imported_entity):
        return {}

    class Config:
        fields = {
            'import_uuid': {'exclude': True},
        }


class PromptImport(ImportData):
    versions: List[dict]

    def dict(self, **kwargs):
        res = super().dict(**kwargs)
        for v in res['versions']:
            v.pop('import_version_uuid', None)

        return res

    def map_postponed_ids(self, imported_entity):
        postponed_id_mapper = {
            'prompt_id': {
                self.import_uuid: imported_entity['id']},
            'prompt_version_id': {},
        }

        for version in self.versions:
            for imported_version in imported_entity['versions']:
                # find by unique version name within one entity id
                if version['name'] == imported_version['name']:
                    postponed_id_mapper['prompt_version_id'][version['import_version_uuid']] = imported_version['id']
                    break

        return postponed_id_mapper


class DatasourcesImport(ImportData):
    versions: List[dict]
    embedding_model: str
    embedding_model_settings: dict
    storage: Optional[str]
    storage_settings: Optional[dict] = {}

    def map_postponed_ids(self, imported_entity):
        postponed_id_mapper = {
            'datasource_id': {
                self.import_uuid: imported_entity['id']
            },
        }

        return postponed_id_mapper


class PromptImportToolSettings(BaseModel):
    prompt_id: int
    prompt_version_id: int
    variables: List[dict]


class SelfImportToolSettings(BaseModel):
    import_uuid: str
    import_version_uuid: str
    variables: List[dict]


class DatasourceImportToolSettings(BaseModel):
    datasource_id: int
    selected_tools: dict


class DatasourceSelfImportToolSettings(BaseModel):
    import_uuid: str
    selected_tools: list


class ApplicationImportToolSettings(BaseModel):
    application_id: int
    application_version_id: int
    variables: List[dict]


class ApplicationImportCompoundTool(BaseModel):
    name: str
    description: Optional[str]
    type: Literal['application', 'datasource', 'prompt']
    application_import_version_uuid: Optional[str] = None
    settings: PromptImportToolSettings | SelfImportToolSettings | DatasourceImportToolSettings | DatasourceSelfImportToolSettings | ApplicationImportToolSettings

    @property
    def not_imported_yet_tool(self):
        return hasattr(self.settings, 'import_uuid')

    def generate_create_payload(self, postponed_id_mapper):
        assert self.application_import_version_uuid is not None

        tool = self.dict()

        app_ver_id = postponed_id_mapper['application_version_id'].get(
            self.application_import_version_uuid
        )

        tool_type = tool['type']
        tool_id_key = f'{tool_type}_id'
        tool_version_id_key = f'{tool_type}_version_id'
        tool['settings'][tool_id_key] = postponed_id_mapper[tool_id_key].get(
            tool['settings'].pop('import_uuid')
        )
        if tool['settings'].get('import_version_uuid'):
            tool['settings'][tool_version_id_key] = postponed_id_mapper[tool_version_id_key].get(
            tool['settings'].pop('import_version_uuid')
        )

        return app_ver_id, tool


class AgentsImport(ImportData):
    versions: List[dict]
    owner_id: Optional[int]
    shared_id: int = None
    shared_owner_id: int = None

    postponed_tools: List[ApplicationImportCompoundTool] = []

    class Config:
        fields = {
            'import_uuid': {'exclude': True},
            'postponed_tools': {'exclude': True},
        }

    @root_validator(pre=True)
    def validate_compound_tool(cls, values):
        postponed_tools = []
        for version in values['versions']:
            clean_tools = []
            for tool in version.get('tools', []):
                if tool['type'] in ('application', 'datasource', 'prompt'):
                    t = ApplicationImportCompoundTool.parse_obj(tool)
                    if t.not_imported_yet_tool:
                        t.application_import_version_uuid = version['import_version_uuid']
                        postponed_tools.append(t)
                    else:
                        clean_tools.append(tool)
                else:
                    clean_tools.append(tool)

            version['tools'] = clean_tools
        values['postponed_tools'] = postponed_tools

        return values

    def map_postponed_ids(self, imported_entity: dict):
        ''' Map import_uuid with real id/version_id of app stored in db'''

        postponed_id_mapper = {
            'application_id': {
                self.import_uuid: imported_entity['id']
            },
            'application_version_id': {},
        }

        for version in self.versions:
            for imported_version in imported_entity['versions']:
                # find by unique version name within one entity id
                if version['name'] == imported_version['name']:
                    postponed_id_mapper['application_version_id'][version['import_version_uuid']] = imported_version['id']
                    break

        return postponed_id_mapper




IMPORT_MODEL_ENTITY_MAPPER = {
    'prompts': PromptImport,
    'datasources': DatasourcesImport,
    'agents': AgentsImport,
}
