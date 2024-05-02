import pytest
from flask import url_for

@pytest.fixture
def prompt_data():
    return {'name': 'Test Prompt', 'description': 'A test prompt'}

@pytest.mark.asyncio
async def test_create_prompt(client, prompt_data):
    response = await client.post(url_for('prompt.create'), json=prompt_data)
    assert response.status_code == 201
    assert 'id' in response.json

@pytest.mark.asyncio
async def test_get_prompt(client, prompt_data):
    post_response = await client.post(url_for('prompt.create'), json=prompt_data)
    prompt_id = post_response.json['id']
    get_response = await client.get(url_for('prompt.get', prompt_id=prompt_id))
    assert get_response.status_code == 200
    assert get_response.json == prompt_data

# Additional tests for update and delete operations