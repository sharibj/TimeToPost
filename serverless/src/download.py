import json
import os
import boto3

class Credentials:
    def __init__(self, access_key_id, secret_access_key, session_token):
        self.access_key_id = access_key_id
        self.secret_access_key = secret_access_key
        self.session_token = session_token

def handler(event, context):
    print(event)
    try:
        username = event['requestContext']['authorizer']['principalId']  
        credentials = Credentials(
            access_key_id=event['requestContext']['authorizer']['AccessKeyId'],
            secret_access_key=event['requestContext']['authorizer']['SecretKey'],
            session_token=event['requestContext']['authorizer']['SessionToken']
        )
        s3_client = boto3.client('s3',
                                aws_access_key_id=credentials.access_key_id,
                                aws_secret_access_key=credentials.secret_access_key,
                                aws_session_token=credentials.session_token,
                                region_name=os.environ.get("REGION"))

        bucket_name = os.environ.get("POSTS_BUCKET_NAME")
        object_key = '%s/%s' % (username, os.environ.get("POSTS_OBJECT_NAME"))
        expiration = 60  # 1 minute
        url = s3_client.generate_presigned_url('get_object',
                                            Params={'Bucket': bucket_name,
                                                    'Key': object_key},
                                            ExpiresIn=expiration)
        return {
            'statusCode': 200,
            'body': json.dumps({'downloadURL': url})
        }
    except Exception as e:
        print(f"An error occurred: {e}")
        return {
            'statusCode': 500,
            'body': json.dumps({'error': str(e)})
        }