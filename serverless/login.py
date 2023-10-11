import json
import os
import boto3
import base64
import urllib.request
import urllib.parse


def handler(event, context):
    code = get_code_from_event(event)
    if not code:
        return get_redirect_to_cognito_response()

    token_data = exchange_code_for_tokens(code)
    if not token_data:
        return get_redirect_to_cognito_response()

    user_id = get_sub_from_jwt(token_data.id_token)
    if not user_id:
        return get_redirect_to_cognito_response()

    response = get_success_response(token_data.id_token)

    # TODO: Consider doing the below part async
    # Below code is written to ignore failures on purpose
    credentials = get_creds_for_id(token_data.id_token)
    put_tokens_in_dynamodb(user_id, token_data, credentials)
    initialize_s3(user_id, credentials)
    return response


def get_success_response(id_token):
    body = {
        "message": "Go Serverless v3.0! Your function executed successfully!",
        "id_token": id_token
    }
    headers = {
        "Set-Cookie": f"id_token={id_token}; HttpOnly; Secure; SameSite=None; Path=/;",
        "Content-Type": "application/json"
    }
    response = {"statusCode": 200, "body": json.dumps(body), "headers": headers}
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


def get_sub_from_jwt(jwt):
    user_id = None
    # Decode the JWT token to access the 'sub' claim (user ID)
    parts = jwt.split('.')

    if len(parts) != 3:
        print("Error! Invalid JWT format")
    else:
        payload = json.loads(base64.b64decode(parts[1] + '==').decode('utf-8'))
        # Extract the 'sub' claim (user ID)
        user_id = payload.get('sub')

    return user_id


class Credentials:
    def __init__(self, access_key_id, secret_access_key, session_token):
        self.access_key_id = access_key_id
        self.secret_access_key = secret_access_key
        self.session_token = session_token


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

    # Make the call to id
    response = cognito_identity.get_id(
        IdentityPoolId=identity_pool_id,
        Logins=logins
    )
    identity_id = response['IdentityId']

    # Get the credentials
    credentials = cognito_identity.get_credentials_for_identity(
        IdentityId=identity_id,
        Logins=logins
    )

    return Credentials(credentials['Credentials']['AccessKeyId'],
                       credentials['Credentials']['SecretKey'],
                       credentials['Credentials']['SessionToken'])


def put_tokens_in_dynamodb(user_id, token_data, credentials):
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
            'username': user_id,
            'channel': "linkedin",
            'access_token': token_data.access_token,
            'refresh_token': token_data.refresh_token
        }

        # Use the put_item method to add the item to the table
        table.put_item(Item=item)

    except Exception as e:
        # Handle exceptions, e.g., table not found, permissions issues, etc.
        print(f"Error adding item to DynamoDB: {str(e)}")
        return False


def initialize_s3(user_id, credentials):
    s3_client = boto3.client('s3',
                             aws_access_key_id=credentials.access_key_id,
                             aws_secret_access_key=credentials.secret_access_key,
                             aws_session_token=credentials.session_token,
                             region_name=os.environ.get("REGION"))

    object_key = '%s/%s' % (user_id, os.environ.get("POSTS_OBJECT_NAME"))

    try:
        bucket_name = os.environ.get("POSTS_BUCKET_NAME")
        # Use the S3 client to download the object
        s3_client.get_object(Bucket=bucket_name, Key=object_key)
        # You can process the object_content as needed
    except Exception as e:
        print("Error reading object from S3:", str(e))
        # attempt to create new file
        try:
            # Create an empty posts.txt file
            empty_content = ''
            s3_client.put_object(
                Bucket=bucket_name,
                Key=object_key,
                Body=empty_content.encode('utf-8')
            )
        except Exception as e:
            print("Error putting object in S3:", str(e))
