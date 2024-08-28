import unittest
from flask import json
from api.v1.predict import ProjectAPI, PromptLibAPI  # Adjust the import based on your structure
from unittest.mock import patch

class TestProjectAPI(unittest.TestCase):
    def setUp(self):
        self.app = ...  # Initialize your Flask app
        self.client = self.app.test_client()

    @patch('api.v1.predict.AIProvider.predict')
    def test_valid_prediction(self, mock_predict):
        mock_predict.return_value = {'ok': True, 'response': 'Test response'}
        response = self.client.post('/api/v1/predict/1', json={
            'prompt_id': 1,
            'input_': 'Test input',
            'integration_uid': 'test_uid',
            'integration_settings': {'model_name': 'gpt-3.5-turbo'}
        })
        self.assertEqual(response.status_code, 200)
        self.assertIn('messages', response.json)

    def test_invalid_prediction_missing_fields(self):
        response = self.client.post('/api/v1/predict/1', json={})
        self.assertEqual(response.status_code, 400)

    @patch('api.v1.predict.AIProvider.predict')
    def test_prediction_error_handling(self, mock_predict):
        mock_predict.return_value = {'ok': False, 'error': 'Prediction failed'}
        response = self.client.post('/api/v1/predict/1', json={
            'prompt_id': 1,
            'input_': 'Test input',
            'integration_uid': 'test_uid',
            'integration_settings': {'model_name': 'gpt-3.5-turbo'}
        })
        self.assertEqual(response.status_code, 400)
        self.assertIn('error', response.json)

    @patch('api.v1.predict.AIProvider.predict')
    def test_update_prompt(self, mock_predict):
        mock_predict.return_value = {'ok': True, 'response': 'Updated response'}
        response = self.client.post('/api/v1/predict/1', json={
            'prompt_id': 1,
            'input_': 'Test input',
            'update_prompt': True,
            'integration_uid': 'test_uid',
            'integration_settings': {'model_name': 'gpt-3.5-turbo'}
        })
        self.assertEqual(response.status_code, 200)

    def tearDown(self):
        pass  # Clean up after tests

if __name__ == '__main__':
    unittest.main()