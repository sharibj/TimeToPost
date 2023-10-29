import json
import os
import boto3
import urllib.request
import urllib.parse

class Credentials:
    def __init__(self, access_key_id, secret_access_key, session_token):
        self.access_key_id = access_key_id
        self.secret_access_key = secret_access_key
        self.session_token = session_token

def handler(event, context):
    username = event['requestContext']['authorizer']['principalId']  
    credentials = Credentials(
        access_key_id=event['requestContext']['authorizer']['AccessKeyId'],
        secret_access_key=event['requestContext']['authorizer']['SecretKey'],
        session_token=event['requestContext']['authorizer']['SessionToken']
    )
    code = get_code_from_event(event)
    if not code:
        return get_auth_code_redirection()

    access_token = exchange_code_for_access_token(code)
    linkedin_sub = get_sub_from_linkedin(access_token)
    put_tokens_in_dynamodb(username, linkedin_sub, access_token, credentials)
    return {
        "statusCode": 302,
        "headers": {
            "Location": os.environ.get("LOGIN_URI")
        }
    }

def get_code_from_event(event):
    code = None
    if event and "queryStringParameters" in event:
        query_parameters = event["queryStringParameters"]
        if query_parameters and "code" in query_parameters:
            code = query_parameters["code"]
    return code

def get_auth_code_redirection():
    linkedin_auth_url = os.environ.get("LINKEDIN_AUTH_URL")
    response_type = "code"
    linkedin_client_id = os.environ.get("LINKEDIN_CLIENT_ID")
    linkedin_auth_redirect_uri = os.environ.get("LINKEDIN_AUTH_REDIRECT_URI")
    state = "state"
    scope = os.environ.get("LINKEDIN_AUTH_SCOPE")

    auth_params = f'response_type={response_type}&client_id={linkedin_client_id}&redirect_uri={linkedin_auth_redirect_uri}&state={state}&scope={scope}'
    encoded_auth_params = urllib.parse.quote(auth_params, safe='=&')
    auth_location = f'{linkedin_auth_url}?{encoded_auth_params}'
    redirection_response = {
            "statusCode": 302,
            "headers": {
                "Location": auth_location
            }
        }
    
    return redirection_response

def exchange_code_for_access_token(code):
    linkedin_access_token_url = os.environ.get("LINKEDIN_ACCESS_TOKEN_URL")
    content_type = 'application/x-www-form-urlencoded'
    grant_type = "authorization_code"
    linkedin_client_id = os.environ.get("LINKEDIN_CLIENT_ID")
    linkedin_client_secret = get_parameter("/time-to-post/linkedin-client-secret")
    linkedin_auth_redirect_uri = os.environ.get("LINKEDIN_AUTH_REDIRECT_URI")
    # LinkedIn supports programmatic refresh tokens for all approved Marketing Developer Platform (MDP) partners.
    data = urllib.parse.urlencode({
    'grant_type': grant_type,
    'code': code,
    'client_id': linkedin_client_id,
    'client_secret': linkedin_client_secret,
    'redirect_uri': linkedin_auth_redirect_uri
    })
    data = data.encode('ascii') 
    try:
        req = urllib.request.Request(linkedin_access_token_url, data=data, headers={'Content-Type': content_type})
        with urllib.request.urlopen(req) as response:
            response_data = response.read()
            linkedin_tokens = json.loads(response_data.decode('utf-8'))
            return linkedin_tokens.get("access_token")
    except urllib.error.URLError as e:
        # Handle network errors
        print(f"URLError: {e}")
    except json.JSONDecodeError as e:
        # Handle JSON decoding errors
        print(f"JSONDecodeError: {e}")
    return None

def get_parameter(parameter_name):
    try:
        ssm_client = boto3.client('ssm')
        response = ssm_client.get_parameter(Name=parameter_name, WithDecryption=True)
        parameter_value = response['Parameter']['Value']
        return parameter_value

    except Exception as e:
        print(f"Error retrieving parameter {parameter_name}: {str(e)}")
        return None

def get_sub_from_linkedin(access_token):
    headers = {
        "Authorization": f"Bearer {access_token}"
    }
    url = "https://api.linkedin.com/v2/userinfo"

    req = urllib.request.Request(url, headers=headers)

    try:
        with urllib.request.urlopen(req) as response:
            data = response.read()
            response_data = json.loads(data)
            return response_data["sub"] if "sub" in response_data else None
    except urllib.error.HTTPError as e:
        print('HTTPError: ', e.code)
    except urllib.error.URLError as e:
        print('URLError: ', e.reason)

def put_tokens_in_dynamodb(username, linkedin_sub, access_token, credentials):
    # Initialize a DynamoDB resource
    dynamodb = boto3.resource('dynamodb',
                              aws_access_key_id=credentials.access_key_id,
                              aws_secret_access_key=credentials.secret_access_key,
                              aws_session_token=credentials.session_token,
                              region_name=os.environ.get("REGION"))

    try:
        # Specify the table name
        # TODO Add CDK code to create this table and set the name in param store
        table = dynamodb.Table(os.environ.get("DYNAMO_TABLE_NAME"))

        # Define the item to be added
        item = {
            'username': username,
            'channel': "linkedin",
            'linkedin_sub': linkedin_sub,
            'access_token': access_token
        }

        # Use the put_item method to add the item to the table
        table.put_item(Item=item)

    except Exception as e:
        # Handle exceptions, e.g., table not found, permissions issues, etc.
        print(f"Error adding item to DynamoDB: {str(e)}")
        return False