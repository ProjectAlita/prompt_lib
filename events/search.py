from pylon.core.tools import log, web

from tools import db
from ..models.all import SearchRequest


class Event:
    @web.event("prompt_lib_search_conducted")
    def handler(self, context, event, payload: dict):
        project_id = payload.get("project_id")
        search_data = payload.get('search_data')
        tag_ids = search_data.get("tag_ids", [])
        keywords: list = search_data.get("keywords", [])
        keywords.extend(keywords)

        with db.with_project_schema_session(project_id) as session:
            tags = session.query(Tag).filter(
                Tag.id.in_(tag_ids)
            ).all()
            for tag in tags:
                keywords.append(tag.name)

            searches = session.query(SearchRequest).filter(
                SearchRequest.search_keyword.in_(keywords)
            )
            # incrementing search counts
            for search in searches:
                search.count += 1
            
            # creating new searches
            existing_searches = set(search.search_keyword for search in searches)
            new_searches = set(keywords) - existing_searches
            for keyword in new_searches:
                new_search = SearchRequest(search_keyword=keyword)
                session.add(new_search)
            session.commit()


            


