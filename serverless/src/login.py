import json
import os
import boto3
import base64
import urllib.request
import urllib.parse

def handler(event, context):
    id_token = extract_access_token_from_cookie(event)
    if id_token and is_token_valid(id_token):
        return get_ui_response(id_token)
    code = get_code_from_event(event)
    if not code:
        return get_redirect_to_cognito_response()
    token_data = exchange_code_for_tokens(code)
    if not token_data:
        return get_redirect_to_cognito_response()
    return get_ui_response(token_data.id_token)

def is_token_valid(id_token):
    return get_creds_for_id(id_token)

def get_creds_for_id(id_token):
    # Fetch environment variables
    region = os.environ.get("REGION")
    user_pool_id = os.environ.get("COGNITO_USERPOOL_ID")
    identity_pool_id = os.environ.get("COGNITO_IDENTITYPOOL_ID")

    # To pass the Cognito User Pool JWT Token, you would need to use the Logins Map in the GetId API call.
    # 'cognito-idp.<region>.amazonaws.com/<YOUR_USER_POOL_ID>': '<JWT ID Token>'
    logins_key = 'cognito-idp.%s.amazonaws.com/%s' % (region, user_pool_id)
    logins = {logins_key: id_token}

    # Configure the credentials provider to use your identity pool
    cognito_identity = boto3.client('cognito-identity', region_name=region)

    try:
        # Make the call to id
        response = cognito_identity.get_id(
            IdentityPoolId=identity_pool_id,
            Logins=logins
        )
        # identity_id = response['IdentityId']
        return response
    except cognito_identity.exceptions.NotAuthorizedException as e:
        print(f"NotAuthorizedException: {e}")
        return False
    except Exception as e:
        print(f"Exception occurred: {e}")
        return False

def extract_access_token_from_cookie(event):
    headers = event.get('headers', {})
    cookies = headers.get('Cookie', '')
    if cookies:
        cookie_list = cookies.split(';')
        for cookie in cookie_list:
            if 'id_token' in cookie:
                return cookie.split('id_token=')[1]
    return None

def get_ui_response(id_token):
    try:
        with open('ui.html', 'r') as file:
            html_content = file.read()
    except FileNotFoundError:
        return {
            "statusCode": 404,
            "body": "UI File not found"
        }

    response = {
        "statusCode": 200,
        "headers": {
            "Content-Type": "text/html",
            "Set-Cookie": f"id_token={id_token}; Max-Age=3600; Secure; HttpOnly; SameSite=None"
        },
        "body": html_content
    }

    return response

def get_code_from_event(event):
    code = None
    if event and "queryStringParameters" in event:
        query_parameters = event["queryStringParameters"]
        if query_parameters and "code" in query_parameters:
            code = query_parameters["code"]
    return code

def get_redirect_to_cognito_response():
    response = {
        "statusCode": 302,
        "headers": {
            "Location": os.environ.get("COGNITO_URL")
        }
    }
    return response

def get_parameter(parameter_name):
    try:
        ssm_client = boto3.client('ssm')
        response = ssm_client.get_parameter(Name=parameter_name, WithDecryption=True)
        parameter_value = response['Parameter']['Value']
        return parameter_value

    except Exception as e:
        print(f"Error retrieving parameter {parameter_name}: {str(e)}")
        return None

class TokenData:
    def __init__(self, id_token, access_token, refresh_token):
        self.id_token = id_token
        self.access_token = access_token
        self.refresh_token = refresh_token

def exchange_code_for_tokens(code):
    token_data = None

    # Fetch parameters
    client_secret = get_parameter("/time-to-post/cognito-client-secret")
    user_pool_domain = os.environ.get("COGNITO_DOMAIN")
    client_id = os.environ.get("COGNITO_CLIENT_ID")
    redirect_uri = os.environ.get("LOGIN_URI")

    # Generate auth URL and header
    url = '%s/oauth2/token' % user_pool_domain
    auth_str = f"{client_id}:{client_secret}"
    auth_bytes = auth_str.encode('utf-8')
    auth_hdr = base64.b64encode(auth_bytes).decode('utf-8')

    # Set the headers
    headers = {
        'Content-Type': 'application/x-www-form-urlencoded',
        'Authorization': 'Basic %s' % auth_hdr,
    }

    # Set the form data
    data = {
        'grant_type': 'authorization_code',
        'client_id': client_id,
        'redirect_uri': redirect_uri,
        'code': code,
    }

    # Encode the form data
    data = urllib.parse.urlencode(data).encode('utf-8')

    # Create a request object
    req = urllib.request.Request(url, data=data, headers=headers)

    try:
        # Make the POST request
        response = urllib.request.urlopen(req)
        # Read and parse the JSON response
        response_data = response.read().decode('utf-8')
        parsed_response = json.loads(response_data)
        print("Oauth Tokens:")
        print(parsed_response)

        # Extract the relevant token data
        token_data = TokenData(parsed_response.get('id_token'),
                               parsed_response.get('access_token'),
                               parsed_response.get('refresh_token'))
    except urllib.error.HTTPError as e:
        print("Error! HTTP Status Code:", e.code)
        print("Response Text:")
        print(e.read().decode('utf-8'))
    except urllib.error.URLError as e:
        print("Error! URL Error:", e.reason)

    return token_data