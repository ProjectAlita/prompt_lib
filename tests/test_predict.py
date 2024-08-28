import pytest
from flask import Flask, json
from api.v1.predict import ProjectAPI, PromptLibAPI

@pytest.fixture
def client():
    app = Flask(__name__)
    app.testing = True
    with app.test_client() as client:
        yield client

def test_project_api_post(client):
    # Mock request data
    request_data = {
        "prompt_id": 1,
        "integration_settings": {},
        "integration_uid": "uid",
        "input_": "Test input",
        "context": "Test context",
        "examples": [],
        "variables": {},
        "chat_history": [],
        "addons": [],
        "format_response": True
    }
    
    # Mock project_id
    project_id = 1
    
    # Call the API
    response = client.post(f'/api/v1/predict/{project_id}', data=json.dumps(request_data), content_type='application/json')
    
    # Assert the response
    assert response.status_code == 200
    assert 'response' in response.json

def test_prompt_lib_api_post(client):
    # Mock request data
    request_data = {
        "project_id": 1,
        "prompt_version_id": 1,
        "user_name": "test_user",
        "integration": {
            "name": "test_integration"
        }
    }
    
    # Mock project_id and prompt_version_id
    project_id = 1
    prompt_version_id = 1
    
    # Call the API
    response = client.post(f'/api/v1/predict/{project_id}/{prompt_version_id}', data=json.dumps(request_data), content_type='application/json')
    
    # Assert the response
    assert response.status_code == 200
    assert 'messages' in response.json
