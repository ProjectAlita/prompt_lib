import pytest
from api.v1.predict import ProjectAPI, PromptLibAPI
from flask import json
from unittest.mock import patch, MagicMock


@pytest.fixture
def client():
    from flask import Flask
    app = Flask(__name__)
    app.add_url_rule('/api/v1/predict', view_func=ProjectAPI.as_view('project_api'))
    app.add_url_rule('/api/v1/predict/<int:project_version_id>', view_func=PromptLibAPI.as_view('prompt_lib_api'))
    with app.test_client() as client:
        yield client


def test_project_api_post_success(client):
    payload = {'input_': 'test input', 'prompt_id': 1, 'integration_uid': 'test_uid'}
    response = client.post('/api/v1/predict/1', data=json.dumps(payload), content_type='application/json')
    assert response.status_code == 200


def test_project_api_post_invalid_payload(client):
    payload = {'invalid_field': 'test'}
    response = client.post('/api/v1/predict/1', data=json.dumps(payload), content_type='application/json')
    assert response.status_code == 400


def test_prompt_lib_api_post_success(client):
    payload = {'input_': 'test input', 'prompt_version_id': 1}
    response = client.post('/api/v1/predict/1/1', data=json.dumps(payload), content_type='application/json')
    assert response.status_code == 200


def test_prompt_lib_api_post_invalid_payload(client):
    payload = {'invalid_field': 'test'}
    response = client.post('/api/v1/predict/1/1', data=json.dumps(payload), content_type='application/json')
    assert response.status_code == 400
