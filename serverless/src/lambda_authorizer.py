from http.cookies import SimpleCookie
import os
import json
import boto3
import base64

def get_auth_token_from_cookie(event):
    try:
        cookie = SimpleCookie()
        cookie.load(event["headers"]["Cookie"])
        token = cookie["id_token"].value
        return token
    except:
        print("Problem retrieving Token Cookie from request")
        print(event)
        raise Exception("Problem retrieving Token Cookie from request")

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

def get_credentials_for_id(id_token):
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
    cognito_credentials = cognito_identity.get_credentials_for_identity(
        IdentityId=identity_id,
        Logins=logins
    )

    # Convert the credentials to a dictionary
    credentials = {
        'AccessKeyId': cognito_credentials['Credentials']['AccessKeyId'],
        'SecretKey': cognito_credentials['Credentials']['SecretKey'],
        'SessionToken': cognito_credentials['Credentials']['SessionToken']
    }

    # # Convert the dictionary to a JSON string
    # credentials = json.dumps(credentials_dict)

    
    print(credentials)
    return credentials


def generatePolicy(principalId, effect, methodArn, context):
    authResponse = {}
    authResponse["principalId"] = principalId
    authResponse["context"] = context
    base = methodArn.split("/")[0]
    stage = methodArn.split("/")[1]
    arn = base + "/" + stage + "/*/*"

    if effect and methodArn:
        policyDocument = {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Sid": "FirstStatement",
                    "Action": "execute-api:Invoke",
                    "Effect": effect,
                    "Resource": arn,
                }
            ],
        }
        authResponse["policyDocument"] = policyDocument
    return authResponse

def handler(event, context):
    print(event)
    print(context)
    try:
        token = get_auth_token_from_cookie(event)
        credentials = get_credentials_for_id(token)
        username_from_token = get_sub_from_jwt(token)
        policy =  generatePolicy(username_from_token, "Allow", event["methodArn"],credentials)
        print(policy)
        return policy
    except Exception as e:
        print(e)
        return generatePolicy(None, "Deny", event["methodArn"])