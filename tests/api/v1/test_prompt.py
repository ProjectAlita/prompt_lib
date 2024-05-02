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

@pytest.mark.asyncio
async def test_update_prompt(client, prompt_data):
    # Assuming a prompt has been created
    update_data = {'name': 'Updated Test Prompt', 'description': 'An updated test prompt'}
    post_response = await client.post(url_for('prompt.create'), json=prompt_data)
    prompt_id = post_response.json['id']
    update_response = await client.put(url_for('prompt.update', prompt_id=prompt_id), json=update_data)
    assert update_response.status_code == 200
    assert update_response.json == update_data

@pytest.mark.asyncio
async def test_delete_prompt(client, prompt_data):
    # Assuming a prompt has been created
    post_response = await client.post(url_for('prompt.create'), json=prompt_data)
    prompt_id = post_response.json['id']
    delete_response = await client.delete(url_for('prompt.delete', prompt_id=prompt_id))
    assert delete_response.status_code == 204

# Additional tests for update and delete operations