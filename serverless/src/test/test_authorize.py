import authorize
import pytest
from unittest.mock import patch, Mock
import urllib.parse

@patch('os.environ.get')
def test_redirect_to_linked_in_when_no_code(mock_env_get):
    # given
    def side_effect(env_var_name):
        if env_var_name == "LINKEDIN_AUTH_URL":
            return "https://linkedin_auth_url"
        elif env_var_name == "LINKEDIN_CLIENT_ID":
            return "linkedin_client_id"
        elif env_var_name == "LINKEDIN_AUTH_REDIRECT_URI":
            return "https://linkedin_redirect_url"
        elif env_var_name == "LINKEDIN_AUTH_SCOPE":
            return "scope1 scope2"
        else:
            return None

    mock_env_get.side_effect = side_effect
    event = {"queryStringParameters": {"not_code": "no_code_present"}}
    # when
    result = authorize.handler(event, None)

    # then
    assert result == {
        "statusCode": 302,
        "headers": {
            "Location": "https://linkedin_auth_url?response_type=code&client_id=linkedin_client_id&redirect_uri=https%3A%2F%2Flinkedin_redirect_url&state=state&scope=scope1%20scope2"

        }
    }

@patch('os.environ.get')
@patch('authorize.get_parameter')
@patch('authorize.urllib.request.Request')
@patch('authorize.urllib.request.urlopen')
def test_exchange_code_for_access_token(mock_urlopen,mock_request,mock_get_parameter,mock_env_get):
    # given
    def side_effect(env_var_name):
        if env_var_name == "LINKEDIN_ACCESS_TOKEN_URL":
            return "https://linkedin_access_token_url"
        elif env_var_name == "LINKEDIN_CLIENT_ID":
            return "linkedin_client_id"
        elif env_var_name == "LINKEDIN_AUTH_REDIRECT_URI":
            return "https://linkedin_redirect_url"
        elif env_var_name == "LINKEDIN_AUTH_SCOPE":
            return "scope1 scope2"
        else:
            return None

    mock_env_get.side_effect = side_effect
    mock_get_parameter.return_value = "test_client_secret"
    mock_request.return_value = "test_req"
    mock_response = Mock()
    mock_response.read.return_value = b'{"access_token": "test_access_token"}'
    mock_urlopen.return_value.__enter__.return_value = mock_response
    code = "test_code"

    # when
    result = authorize.exchange_code_for_access_token(code)

    # then
    assert result == "test_access_token"
    expected_data = "grant_type=authorization_code&code=test_code&client_id=linkedin_client_id&client_secret=test_client_secret&redirect_uri=https://linkedin_redirect_url"
    expected_headers = {'Content-Type': 'application/x-www-form-urlencoded'}
    mock_request.assert_called_once_with(
        "https://linkedin_access_token_url",
        data=urllib.parse.quote(expected_data, safe='=&').encode('ascii') ,
        headers=expected_headers
    )
    mock_urlopen.assert_called_once_with(mock_request.return_value)
