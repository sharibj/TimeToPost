import json
import os
import boto3
import urllib.request
import urllib.parse
import Credentials
    
def handler(event, context):
    print(event)
    user_id = event['requestContext']['authorizer']['principalId']
    access_key_id = event['requestContext']['authorizer']['AccessKeyId']
    secret_key = event['requestContext']['authorizer']['SecretKey']
    session_token = event['requestContext']['authorizer']['SessionToken']    
    print(">>>")                               
    print(user_id)
    print(access_key_id)
    print(secret_key)
    print(session_token)
    code = get_code_from_event(event)
    if not code:
        return get_auth_code_redirection()

    access_token = exchange_code_for_access_token(code)
    # TODO store in dynamo by  assuming IAM role
    # store_in_dynamo(user_id,access_token)
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

def store_in_dynamo(user_id,access_token):   
    dynamodb = boto3.resource('dynamodb')
    table = dynamodb.Table(os.environ.get("DYNAMO_TABLE_NAME"))
    item = {
        'username': user_id,
        'channel': "linkedin",
        'access_token': access_token
    }
    table.put_item(Item=item)