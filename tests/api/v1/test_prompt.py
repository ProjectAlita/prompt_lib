import pytest

import pytest
from models.pd.prompt import PromptDetailModel, PromptCreateModel

# Example test case

def test_prompt_detail_model():
    # Mock data setup
    prompt_detail = PromptDetailModel(
        id=1,
        name='Test Prompt',
        description='Just a test prompt',
        owner_id=123
    )
    assert prompt_detail.id == 1
    assert prompt_detail.name == 'Test Prompt'
    assert prompt_detail.description == 'Just a test prompt'
    assert prompt_detail.owner_id == 123

# More tests to be added here, following the structure and functionalities outlined in 'models/pd/prompt.py'