import login
from login import TokenData
import pytest
from unittest.mock import patch
import io
# TODO Add test for cookie
def side_effect(env_var_name):
        if env_var_name == "COGNITO_URL":
            return "https://cognito_url"
        elif env_var_name == "REGION":
            return "test_region"
        elif env_var_name == "COGNITO_USERPOOL_ID":
            return "test_user_pool"
        elif env_var_name == "COGNITO_IDENTITYPOOL_ID":
            return "test_identity_pool"
        else:
            return None

    
@patch('os.environ.get')
def test_redirect_to_cognito_when_no_code(mock_env_get):
    # given
    mock_env_get.side_effect = side_effect
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

# TODO: Add test for exchange_code_for_tokens

@patch('os.environ.get')
@patch('login.exchange_code_for_tokens')
def test_redirect_to_cognito_when_code_can_not_be_exchanged(mock_exchange, mock_env_get):
    # given
    mock_env_get.side_effect = side_effect
    mock_exchange.side_effect = lambda code: None if code == "invalid_code" else TokenData("","","")
    event = {"queryStringParameters": {"code": "invalid_code"}}
    # when
    result = login.handler(event, None)

    # then
    assert result == {
        "statusCode": 302,
        "headers": {
            "Location": "https://cognito_url"
        }
    }


@patch('login.open')
@patch('login.exchange_code_for_tokens')
def test_return_error_if_ui_html_not_found(mock_exchange,mock_open):
    # given
    event = {"queryStringParameters": {"code": "valid_code"}}
    mock_exchange.side_effect = lambda code: TokenData("test_id_token", "test_access_token", "test_refresh_token") if code == "valid_code" else None
    ui_file_path = "ui.html"
    open_mode = "r"
    mock_open.side_effect = FileNotFoundError

    # when
    response = login.handler(event, None)

    # then
    assert response == {
            "statusCode": 404,
            "body": "UI File not found"
        }
    
@patch('login.open')
@patch('login.exchange_code_for_tokens')
def test_return_ui_html_for_valid_code(mock_exchange,mock_open):
    # given
    event = {"queryStringParameters": {"code": "valid_code"}}
    mock_exchange.side_effect = lambda code: TokenData("test_id_token", "test_access_token", "test_refresh_token") if code == "valid_code" else None
    ui_file_path = "ui.html"
    open_mode = "r"
    mock_open.side_effect = lambda file, mode: io.StringIO("UI HTML Code") if file == ui_file_path and mode == open_mode else None
    # when
    response = login.handler(event, None)

    # then
    assert response == {
        "statusCode": 200,
        "headers": {
            "Content-Type": "text/html",
            "Set-Cookie": f"id_token=test_id_token; Max-Age=3600; Secure; HttpOnly; SameSite=Strict",
        },
        "body": "UI HTML Code"
    }
