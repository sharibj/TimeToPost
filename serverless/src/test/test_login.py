import login
import pytest
from unittest.mock import patch

# TODO Remove the test below as it's testing a small utility function
# Cover this under other test
def test_get_code_from_event():
    # given
    event = {"queryStringParameters": {"code": "test_code"}}
    # when
    result = login.get_code_from_event(event)
    # then
    assert result == "test_code"

@patch('os.environ.get')
def test_redirect_to_cognito_when_no_code(mock_env_get):
    # given
    mock_env_get.side_effect = lambda env_var_name: "https://cognito_url" if env_var_name == "COGNITO_URL" else None
    event = {"queryStringParameters": {"not_code": "no_code_present"}}
    # when
    result = login.handler(event, None)

    # then
    assert result == {
        "statusCode": 302,
        "headers": {
            "Location": "https://cognito_url"
        }
    }


# TODO add more tests
@patch('login.exchange_code_for_tokens')
def test_handler(mock_exchange_code_for_tokens):
    event = {"queryStringParameters": {"code": "test_code"}}
    context = None
    mock_exchange_code_for_tokens.return_value = login.TokenData("test_id_token", "test_access_token", "test_refresh_token")
    response = login.handler(event, context)
    assert response['statusCode'] == 200
