from tools import db
from pylon.core.tools import log

from ..models.enums.all import CollectionStatus, PromptVersionStatus
from ..models.all import Collection, Prompt, PromptVersion


def get_stats(project_id: int, author_id: int):
    result = {}
    log.info(f'{project_id=} {author_id=}')
    with db.with_project_schema_session(project_id) as session:
        query = session.query(Prompt).filter(Prompt.versions.any(PromptVersion.author_id == author_id))
        result['total_prompts'] = query.count()
        log.info(f'total_prompts {query.count()=}')
        log.info(f'total_prompts {query.all()=}')
        query = query.filter(Prompt.versions.any(PromptVersion.status == PromptVersionStatus.published))
        result['public_prompts'] = query.count()
        log.info(f'public_prompts {query.count()=}')
        log.info(f'public_prompts {query.all()=}')

        query = session.query(Collection).filter(Collection.author_id == author_id)
        result['total_collections'] = query.count()
        log.info(f'total_collections {query.count()=}')
        log.info(f'total_collections {query.all()=}')
        query = query.filter(Collection.status == CollectionStatus.published)
        result['public_collections'] = query.count()
        log.info(f'public_collections {query.count()=}')
        log.info(f'public_collections {query.all()=}')
    return result
