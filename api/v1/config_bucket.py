from io import BytesIO
from typing import Optional

from flask import send_file
from pylon.core.tools import log

from tools import api_tools, VaultClient, MinioClient, auth, config as c

from hurry.filesize import size


class ProjectAPI(api_tools.APIModeHandler):
    @auth.decorators.check_api({
        "permissions": ["models.config"],
        "recommended_roles": {
            c.ADMINISTRATION_MODE: {"admin": True, "editor": True, "viewer": False},
            c.DEFAULT_MODE: {"admin": True, "editor": True, "viewer": False},
        }})
    def get(self, project_id: int, file_name: Optional[str] = None, **kwargs):
        project = self.module.context.rpc_manager.call.project_get_or_404(project_id=project_id)
        # s3_settings = test_data['test_config'].get(
        #     'integrations', {}).get('system', {}).get('s3_integration', {})
        vc = VaultClient(project)
        secrets = vc.get_all_secrets()
        try:
            bucket = secrets['ai_project_bucket_name']
        except KeyError:
            log.critical('ai_project_bucket_name secret not set!')
            return {'error': 'ai_project_bucket_name secret not set'}, 404
        minio_client = MinioClient(project)
        if file_name:
            try:
                file = minio_client.download_file(bucket, file_name)
                return send_file(BytesIO(file), download_name=file_name, as_attachment=True)
            except:
                return None, 404

        def compute_sizes(file_meta: dict) -> dict:
            file_meta['size'] = size(file_meta["size"])
            return file_meta

        return list(map(compute_sizes, minio_client.list_files(bucket))), 200


class API(api_tools.APIBase):
    url_params = [
        '<string:mode>/<int:project_id>',
        '<int:project_id>',
        '<string:mode>/<int:project_id>/<string:file_name>',
        '<int:project_id>/<string:file_name>',
    ]

    mode_handlers = {
        c.DEFAULT_MODE: ProjectAPI,
    }
