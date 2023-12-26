from queue import Empty
from functools import wraps
from typing import List, Literal, Set, Callable, Union
from sqlalchemy import func
from sqlalchemy.sql import literal

from tools import db, VaultClient, auth, rpc_tools
from ..models.all import Prompt, PromptVersion, Collection
from ..models.pd.authors import AuthorDetailModel, TrendingAuthorModel
from ..models.enums.all import PromptVersionStatus


def determine_prompt_status(version_statuses: Set[PromptVersionStatus]) -> PromptVersionStatus:
    status_priority = (
        PromptVersionStatus.rejected,
        PromptVersionStatus.on_moderation,
        PromptVersionStatus.published,
        PromptVersionStatus.draft,
        # PromptVersionStatus.user_approval,
    )

    for status in status_priority:
        if status in version_statuses:
            return status


def add_public_project_id(f: Callable) -> Callable:
    wraps(f)
    def wrapper(*args, **kwargs):
        secrets = VaultClient().get_all_secrets()
        try:
            public_project_id = secrets['ai_project_id']
        except KeyError:
            return {'error': "'ai_project_id' not set"}, 400
        kwargs.update({'project_id': public_project_id})
        return f(*args, **kwargs)
    return wrapper


def get_authors_data(author_ids: List[int]) -> List[dict]:
    try:
        users_data: list = auth.list_users(user_ids=author_ids)
    except RuntimeError:
        return []
    try:
        social_data: list = rpc_tools.RpcMixin().rpc.timeout(2).social_get_users(author_ids)
    except (Empty, KeyError):
        social_data = []

    for user in users_data:
        for social_user in social_data:
            if user['id'] == social_user['user_id']:
                user['avatar'] = social_user.get('avatar')
                break

    return users_data


def get_author_data(author_id: int) -> dict:
    try:
        author_data = auth.get_user(user_id=author_id)
    except RuntimeError:
        return {}
    try:
        user_data = rpc_tools.RpcMixin().rpc.timeout(2).social_get_user(author_data['id'])
    except (Empty, KeyError):
        user_data = {}
    author = author_data | user_data
    return AuthorDetailModel(**author)


def get_trending_authors(project_id: int, limit: int = 5) -> List[dict]:
    try:
        Like = rpc_tools.RpcMixin().rpc.timeout(2).social_get_like_model()
    except Empty:
        return []

    with db.with_project_schema_session(project_id) as session:

        # Likes subquery
        likes_subquery = Like.query.filter(
            Like.project_id == project_id,
            Like.entity == 'prompt'
            ).subquery()

        # Subquery
        prompt_likes_subq = (
            session.query(Prompt.id, func.count(likes_subquery.c.user_id).label('likes'))
            .outerjoin(likes_subquery, likes_subquery.c.entity_id == Prompt.id)
            .group_by(Prompt.id)
            .subquery()
        )

        # Main query
        sq_result = (
            session.query(
                PromptVersion.prompt_id,
                PromptVersion.author_id,
                prompt_likes_subq.c.likes
            )
            .outerjoin(
                prompt_likes_subq, prompt_likes_subq.c.id == PromptVersion.prompt_id
            )
            .group_by(
                PromptVersion.prompt_id,
                PromptVersion.author_id,
                prompt_likes_subq.c.likes
            )
            .subquery()
        )

        result = (
            session.query(sq_result.c.author_id, func.sum(sq_result.c.likes))
            .group_by(sq_result.c.author_id)
            .order_by(func.sum(sq_result.c.likes).desc())
            .limit(limit)
            .all()
        )

        authors = get_authors_data([row[0] for row in result])

        trending_authors = []
        for row in result:
            for author in authors:
                if author['id'] == row[0]:
                    author_data = TrendingAuthorModel(**author)
                    author_data.likes = int(row[1])
                    trending_authors.append(author_data)
                    break

    return trending_authors


def add_likes_to_query(
        query,
        project_id: int,
        entity_name: Literal['prompt', 'collection'],
        entity: Union[Prompt, Collection]):
    '''Add likes count to the query if social plugin is available'''
    try:
        Like = rpc_tools.RpcMixin().rpc.timeout(2).social_get_like_model()
    except Empty:
        Like = None

    if Like:
        likes_subquery = Like.query.filter(
            Like.project_id == project_id,
            Like.entity == entity_name
            ).subquery()

        query = (
            query
            .add_columns(func.count(likes_subquery.c.user_id).label('likes'))
            .outerjoin(likes_subquery, likes_subquery.c.entity_id == entity.id)
            .group_by(entity.id)
        )
    else:
        query = query.add_columns(literal(0).label('likes'))

    return query
