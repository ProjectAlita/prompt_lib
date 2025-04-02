from typing import List, Literal, Optional, Union

from pydantic.v1 import BaseModel, root_validator, constr, Extra


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


class ImportVersionModel(BaseModel):
    name: str
    import_version_uuid: str

    class Config:
        fields = {
            'import_version_uuid': {'exclude': True},
        }
        extra = Extra.allow


class PromptImport(ImportData):
    versions: List[ImportVersionModel]

    def map_postponed_ids(self, imported_entity):
        postponed_id_mapper = {
            self.import_uuid: imported_entity['id'],
        }

        for version in self.versions:
            for imported_version in imported_entity['versions']:
                # find by unique version name within one entity id
                if version.name == imported_version['name']:
                    postponed_id_mapper[version.import_version_uuid] = imported_version['id']
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
        return {
            self.import_uuid: imported_entity['id']
        }


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
    selected_tools: list


class DatasourceSelfImportToolSettings(BaseModel):
    import_uuid: str
    selected_tools: list


class ApplicationImportToolSettings(BaseModel):
    application_id: int
    application_version_id: int
    variables: List[dict]


class ToolImportModelBase(ImportData):
    name: Optional[str]
    description: Optional[str]

    @property
    def not_imported_yet_tool(self):
        return hasattr(self.settings, 'import_uuid')

    def dict_import_uuid_resolved(self, postponed_id_mapper):
        tool = self.dict()

        if self.not_imported_yet_tool:
            import_uuid = tool['settings'].pop('import_uuid')
            import_version_uuid = tool['settings'].pop('import_version_uuid', None)
            tool_type = tool['type']
            tool_id_key = f'{tool_type}_id'
            tool_version_id_key = f'{tool_type}_version_id'
            try:

                tool['settings'][tool_id_key] = postponed_id_mapper[import_uuid]
                if import_version_uuid:
                    tool['settings'][tool_version_id_key] = postponed_id_mapper[import_version_uuid]
            except KeyError:
                toolkit_import_uuid = self.import_uuid
                raise RuntimeError(
                   f"Unable to link {toolkit_import_uuid=} to {tool_type} {import_uuid=}({import_version_uuid=})") from None

        return tool

    def map_postponed_ids(self, imported_entity):
        return {
            self.import_uuid: imported_entity['id']
        }


class ApplicationToolImportModel(ToolImportModelBase):
    type: Literal['application']
    settings: SelfImportToolSettings | ApplicationImportToolSettings


class DatasourceToolImportModel(ToolImportModelBase):
    type: Literal['datasource']
    settings: DatasourceSelfImportToolSettings | DatasourceImportToolSettings


class PromptToolImportModel(ToolImportModelBase):
    type: Literal['prompt']
    settings: SelfImportToolSettings | PromptImportToolSettings


class OtherToolImportModel(ToolImportModelBase):
    type: constr(regex=r'^(?!application|datasource|prompt).*')
    settings: dict


class ToolImportModel(BaseModel):
    import_data: ApplicationToolImportModel | DatasourceToolImportModel | PromptToolImportModel | OtherToolImportModel

    @root_validator(pre=True)
    def to_import_data(cls, values):
        return {'import_data': values}


class ApplicationSelfImportTool(BaseModel):
    import_uuid: str


class ApplicationExistingImportTool(BaseModel):
    id: int


class AgentsImportVersion(ImportVersionModel):
    tools: List[Union[ApplicationSelfImportTool, ApplicationExistingImportTool]] = []
    postponed_tools: List[ApplicationSelfImportTool] = []

    class Config:
        fields = {
            'postponed_tools': {'exclude': True},
        }

    @root_validator(pre=False)
    def split_tools_by_refs(cls, values):
        clean_tools = []
        postponed_tools = []
        for tool in values['tools']:
            if isinstance(tool, ApplicationSelfImportTool):
                postponed_tools.append(tool)
            elif isinstance(tool, ApplicationExistingImportTool):
                clean_tools.append(tool)
            else:
                raise ValueError(f"Unsupported tool type: {type(tool)}")

        values['tools'] = clean_tools
        values['postponed_tools'] = postponed_tools

        return values


class AgentsImport(ImportData):
    versions: List[AgentsImportVersion]
    owner_id: Optional[int]
    shared_id: int = None
    shared_owner_id: int = None

    def has_postponed_toolkits(self):
        for version in self.versions:
            if version.postponed_tools:
                return True

    def map_postponed_ids(self, imported_entity: dict):
        ''' Map import_uuid with real id/version_id of app stored in db'''

        postponed_id_mapper = {
            self.import_uuid: imported_entity['id']
        }

        for version in self.versions:
            for imported_version in imported_entity['versions']:
                # find by unique version name within one entity id
                if version.name == imported_version['name']:
                    postponed_id_mapper[version.import_version_uuid] = imported_version['id']
                    break

        return postponed_id_mapper


IMPORT_MODEL_ENTITY_MAPPER = {
    'prompts': PromptImport,
    'datasources': DatasourcesImport,
    'agents': AgentsImport,
    'toolkits': ToolImportModel
}
