from tools import db
# from pylon.core.tools import log
from ..models.all import SearchRequest
from sqlalchemy import desc, asc



def list_search_requests(project_id, args):
    limit = args.get('limit', default=5, type=int)
    offset = args.get('offset', default=0, type=int)
    sort_order = args.get('sort_order', "desc")
    sort_by = args.get('sort_by', "count")

    with db.with_project_schema_session(project_id) as session:
        query = session.query(SearchRequest)
        total = query.count()
        sort_fun = desc if sort_order == "desc" else asc
        query = query.order_by(sort_fun(getattr(SearchRequest, sort_by)))
        query = query.limit(limit).offset(offset)
        return total, query.all()