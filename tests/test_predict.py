import unittest
from unittest.mock import patch, MagicMock
from api.v1.predict import ProjectAPI, PromptLibAPI

class TestProjectAPI(unittest.TestCase):

    @patch('api.v1.predict.request')
    @patch('api.v1.predict.db.with_project_schema_session')
    def test_post_valid_payload(self, mock_db, mock_request):
        mock_request.json = {'prompt_id': 1, 'input_': 'Test input', 'project_id': 1}
        mock_db.return_value.__enter__.return_value.query.return_value.get.return_value = MagicMock()
        api = ProjectAPI()
        response = api.post(1)
        self.assertEqual(response[1], 200)

    @patch('api.v1.predict.request')
    def test_post_invalid_payload(self, mock_request):
        mock_request.json = {'invalid_key': 'value'}
        api = ProjectAPI()
        response = api.post(1)
        self.assertEqual(response[1], 400)

class TestPromptLibAPI(unittest.TestCase):

    @patch('api.v1.predict.request')
    def test_post_valid_prompt(self, mock_request):
        mock_request.json = {'prompt_version_id': 1, 'project_id': 1}
        api = PromptLibAPI()
        response = api.post(1)
        self.assertEqual(response[1], 200)

    @patch('api.v1.predict.request')
    def test_post_invalid_prompt(self, mock_request):
        mock_request.json = {'invalid_key': 'value'}
        api = PromptLibAPI()
        response = api.post(1)
        self.assertEqual(response[1], 400)

import unittest
from unittest.mock import patch, MagicMock
from api.v1.predict import ProjectAPI, PromptLibAPI

class TestProjectAPI(unittest.TestCase):

    @patch('api.v1.predict.request')
    @patch('api.v1.predict.db.with_project_schema_session')
    def test_post_valid_payload(self, mock_db, mock_request):
        mock_request.json = {'prompt_id': 1, 'input_': 'Test input', 'project_id': 1}
        mock_db.return_value.__enter__.return_value.query.return_value.get.return_value = MagicMock()
        api = ProjectAPI()
        response = api.post(1)
        self.assertEqual(response[1], 200)

    @patch('api.v1.predict.request')
    def test_post_invalid_payload(self, mock_request):
        mock_request.json = {'invalid_key': 'value'}
        api = ProjectAPI()
        response = api.post(1)
        self.assertEqual(response[1], 400)

class TestPromptLibAPI(unittest.TestCase):

    @patch('api.v1.predict.request')
    def test_post_valid_prompt(self, mock_request):
        mock_request.json = {'prompt_version_id': 1, 'project_id': 1}
        api = PromptLibAPI()
        response = api.post(1)
        self.assertEqual(response[1], 200)

    @patch('api.v1.predict.request')
    def test_post_invalid_prompt(self, mock_request):
        mock_request.json = {'invalid_key': 'value'}
        api = PromptLibAPI()
        response = api.post(1)
        self.assertEqual(response[1], 400)

if __name__ == '__main__':
    unittest.main()