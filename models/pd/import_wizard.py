from typing import List, Optional

from openai import BaseModel


class ImportData(BaseModel):
    entity: str
    name: str
    description: str
    is_selected: bool = False


class PromptImport(ImportData):
    versions: List[dict]
    collection_id: Optional[int]


class DatasourcesImport(ImportData):
    versions: List[dict]
    collection_id: Optional[int]
    embedding_model: str
    embedding_model_settings: dict
    storage: Optional[str]
    storage_settings: Optional[dict] = {}


class AgentsImport(ImportData):
    versions: List[dict]
    owner_id: Optional[int]
    shared_id: int = None
    shared_owner_id: int = None


IMPORT_MODEL_ENTITY_MAPPER = {
    'prompts': PromptImport,
    'datasources': DatasourcesImport,
    'agents': AgentsImport,
}
