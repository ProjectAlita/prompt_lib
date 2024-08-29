import unittest
from api.v1.predict import ProjectAPI, PromptLibAPI
from flask import json
from unittest.mock import patch, MagicMock

class TestProjectAPI(unittest.TestCase):
    @patch('api.v1.predict.db.with_project_schema_session')
    @patch('api.v1.predict.log')
    def test_post_success(self, mock_log, mock_with_project_schema_session):
        # Setup mock data
        mock_with_project_schema_session.return_value.__enter__.return_value.query.return_value.get.return_value = MagicMock(model_settings={})
        mock_with_project_schema_session.return_value.__enter__.return_value.commit = MagicMock()
        api = ProjectAPI()
        with patch('api.v1.predict.request') as mock_request:
            mock_request.json = {'prompt_id': 1, 'input_': 'test input', 'project_id': 1}
            response = api.post(1)
            self.assertEqual(response[1], 200)

    @patch('api.v1.predict.log')
    def test_post_validation_error(self, mock_log):
        api = ProjectAPI()
        with patch('api.v1.predict.request') as mock_request:
            mock_request.json = {'input_': 'test input'}  # Missing prompt_id
            response = api.post(1)
            self.assertEqual(response[1], 400)

class TestPromptLibAPI(unittest.TestCase):
    @patch('api.v1.predict.log')
    def test_post_success(self, mock_log):
        api = PromptLibAPI()
        with patch('api.v1.predict.request') as mock_request:
            mock_request.json = {'project_id': 1, 'prompt_version_id': 1}
            response = api.post(1, 1)
            self.assertEqual(response[1], 200)

    @patch('api.v1.predict.log')
    def test_post_validation_error(self, mock_log):
        api = PromptLibAPI()
        with patch('api.v1.predict.request') as mock_request:
            mock_request.json = {'project_id': 1}  # Missing prompt_version_id
            response = api.post(1)
            self.assertEqual(response[1], 400)

if __name__ == '__main__':
    unittest.main()