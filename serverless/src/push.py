import boto3
import os
import json
import urllib.request


def handler(event, context):
    # fetch username from input event
    username = event.get('username')
    # use username as partition key and "linked" as sort key to get item from dynamo db
    dynamodb = boto3.resource('dynamodb')
    table = dynamodb.Table(os.environ.get("DYNAMO_TABLE_NAME"))
    key = {
        'username': username,
        'channel': 'linkedin'
    }
    response = table.get_item(Key=key)
    if 'Item' in response:
        item = response['Item']

        s3_client = boto3.client('s3', region_name=os.environ.get("REGION"))

        bucket_name = os.environ.get("POSTS_BUCKET_NAME")
        object_key = '%s/%s' % (username, os.environ.get("POSTS_OBJECT_NAME"))
        posts = s3_client.get_object(Bucket=bucket_name, Key=object_key)
        # Get posts.txt from the S3 bucket
        file_content = posts['Body'].read().decode('utf-8')

        # Parse text to get lines until "---" delimiter or EOF
        lines = file_content.split('\n')
        parsed_lines = []
        for line in lines:
            if line.strip() == '---':
                break
            parsed_lines.append(line)

        # Remove these lines from the file content
        updated_content = '\n'.join(lines[len(parsed_lines) + 1:])

        # Put the updated content back in S3
        s3_client.put_object(
            Bucket=bucket_name,
            Key=object_key,
            Body=updated_content
        )

        # Make a POST request to the LinkedIn REST API
        url = 'https://api.linkedin.com/rest/posts'
        headers = {
            'Authorization': 'Bearer %s' % item['access_token'],
            'X-Restli-Protocol-Version': '2.0.0',
            'LinkedIn-Version': '{version number in the format YYYYMM}',
            'Content-Type': 'application/json'
        }
        print(headers)
        data = {
            "author": "urn:li:organization:5515715",
            "commentary": " ".join(parsed_lines),  # Assuming parsed_lines is a list of strings
            "visibility": "PUBLIC",
            "distribution": {
                "feedDistribution": "MAIN_FEED",
                "targetEntities": [],
                "thirdPartyDistributionChannels": []
            },
            "lifecycleState": "PUBLISHED",
            "isReshareDisabledByAuthor": False
        }
        # Make the POST request
        req = urllib.request.Request(url, data=json.dumps(data).encode('utf-8'), headers=headers, method='POST')
        response = urllib.request.urlopen(req)
        response_code = response.getcode()

        # Print the status code of the POST request

        # Print the extracted lines
        return {
            'statusCode': 200,
            'body': response
        }

    else:
        return {
            'statusCode': 404,
            'body': 'Token not found in the database'
        }
