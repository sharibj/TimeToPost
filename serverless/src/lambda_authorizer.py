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
    print(">>cognito_identity.get_id response")
    print(response)
    identity_id = response['IdentityId']
    print(">>identity_id")
    print(identity_id)
    return response

def generatePolicy(principalId, effect, methodArn):
    authResponse = {}
    authResponse["principalId"] = principalId
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
        get_creds_for_id(token)
        username_from_token = get_sub_from_jwt(token)
        return generatePolicy(username_from_token, "Allow", event["methodArn"])
    except Exception as e:
        print(e)
        return generatePolicy(None, "Deny", event["methodArn"])