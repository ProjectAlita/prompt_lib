import pytest
from unittest.mock import patch
from api.v1.prompt import ProjectAPI, PromptLibAPI

# Example test structure

class TestProjectAPI:
    @pytest.fixture
    def setup(self, mocker):
        self.mock_list_projects = mocker.patch('api.v1.prompt.ProjectAPI.list_projects', return_value={'status': 'success', 'data': []})

    def test_list_projects(self, setup):
        response = ProjectAPI.list_projects()
        assert response['status'] == 'success'
        assert isinstance(response['data'], list)
        self.mock_list_projects.assert_called_once()

class TestPromptLibAPI:
    @pytest.fixture
    def setup(self, mocker):
        self.mock_get_prompt = mocker.patch('api.v1.prompt.PromptLibAPI.get_prompt', return_value={'status': 'success', 'data': 'Example prompt'})

    def test_get_prompt(self, setup):
        response = PromptLibAPI.get_prompt()
        assert response['status'] == 'success'
        assert response['data'] == 'Example prompt'
        self.mock_get_prompt.assert_called_once()