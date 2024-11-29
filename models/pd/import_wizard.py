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

    @root_validator(pre=True)
    def validate_import_version_uuid(cls, values):
        for version in values['versions']:
            assert 'import_version_uuid' in version, "Missing import_version_uuid"

        return values

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
    storage: str
    storage_settings: Optional[dict] = {}
    meta: Optional[dict] = {}

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
    application_import_uuid: Optional[str] = None
    application_import_version_uuid: Optional[str] = None
    settings: PromptImportToolSettings | SelfImportToolSettings | DatasourceImportToolSettings | DatasourceSelfImportToolSettings | ApplicationImportToolSettings


    @property
    def not_imported_yet_tool(self):
        return hasattr(self.settings, 'import_uuid')

    def get_real_application_ids(self, postponed_id_mapper):
        assert self.application_import_uuid is not None
        assert self.application_import_version_uuid is not None

        try:
            app_id = postponed_id_mapper['application_id'][self.application_import_uuid]
            app_ver_id = postponed_id_mapper['application_version_id'][self.application_import_version_uuid]
        except KeyError:
            tool_type = self.type
            import_uuid = self.application_import_uuid
            import_version_uuid = self.application_import_version_uuid
            raise RuntimeError(
               f"Unable to find parent application {import_uuid=}({import_version_uuid=}) for application tool of type {tool_type}") from None

        return app_id, app_ver_id

    def generate_create_payload(self, postponed_id_mapper):
        tool = self.dict()

        import_uuid = tool['settings'].pop('import_uuid')
        import_version_uuid = tool['settings'].pop('import_version_uuid', None)
        tool_type = tool['type']
        tool_id_key = f'{tool_type}_id'
        tool_version_id_key = f'{tool_type}_version_id'
        try:

            tool['settings'][tool_id_key] = postponed_id_mapper[tool_id_key][import_uuid]
            if import_version_uuid:
                tool['settings'][tool_version_id_key] = postponed_id_mapper[tool_version_id_key][import_version_uuid]
        except KeyError:
            raise RuntimeError(
               f"Unable to link application tool {import_uuid=}({import_version_uuid=}) with {tool_type}") from None

        connected_app_id = None
        if tool_type == 'application':
            connected_app_id = tool['settings'][tool_id_key]
        return tool, connected_app_id


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
    def validate_import_version_uuid(cls, values):
        for version in values['versions']:
            assert 'import_version_uuid' in version, "Missing import_version_uuid"

        return values

    @root_validator(pre=True)
    def validate_compound_tool(cls, values):
        assert 'import_uuid' in values, "Missing import_uuid"

        postponed_tools = []
        for version in values['versions']:
            clean_tools = []
            for tool in version.get('tools', []):
                if tool['type'] in ('application', 'datasource', 'prompt'):
                    t = ApplicationImportCompoundTool.parse_obj(tool)
                    if t.not_imported_yet_tool:
                        t.application_import_uuid = values['import_uuid']
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
