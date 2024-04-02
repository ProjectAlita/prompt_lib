import pytest
from unittest.mock import patch
from sio.all import SIO

@pytest.fixture
def mock_sio_instance():
    sio_instance = SIO()
    return sio_instance

@patch('sio.all.prepare_payload')
@patch('sio.all.prepare_conversation')
@patch('sio.all.AzureChatOpenAI')
def test_predict_valid_input(mock_chat, mock_prepare_conversation, mock_prepare_payload, mock_sio_instance):
    mock_prepare_payload.return_value = {'mock': 'payload'}
    mock_prepare_conversation.return_value = ['mock', 'conversation']
    mock_chat.return_value.stream.return_value = iter([{"type": "success", "content": "Test response"}])

    response = mock_sio_instance.predict('mock_sid', {'message_id': 'test_message_id'})
    assert response is None  # Since predict does not return anything

@patch('sio.all.prepare_payload')
def test_predict_invalid_input(mock_prepare_payload, mock_sio_instance):
    mock_prepare_payload.side_effect = ValidationError(['error'])
    with pytest.raises(Exception) as exc_info:
        mock_sio_instance.predict('mock_sid', {'message_id': 'wrong_input'})
    assert 'error' in str(exc_info.value)