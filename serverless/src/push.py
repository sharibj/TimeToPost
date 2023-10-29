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
        
        # TODO Consider doing something to stop running this for empty pool
        ## One Idea -
        ### Create scheduler from authorize when access token is placed in Dynamo (also, maybe create s3 if it doesn't exist)
        ### Disable scheduler from push when file becomes empty
        ### Enable scheduler from upload if (scheduler exists and disabled)

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
        url = 'https://api.linkedin.com/v2/ugcPosts'
        headers = {
            'Authorization': 'Bearer %s' % item['access_token'],
            'X-Restli-Protocol-Version': '2.0.0',
            'Content-Type': 'application/json'
        }
        print(headers)
        data = {
            "author": "urn:li:person:%s" % item['linkedin_sub'],
            "lifecycleState": "PUBLISHED",
            "specificContent": {
                "com.linkedin.ugc.ShareContent": {
                    "shareCommentary": {
                        "text": " ".join(parsed_lines)
                    },
                    "shareMediaCategory": "NONE"
                }
            },
            "visibility": {
                "com.linkedin.ugc.MemberNetworkVisibility": "PUBLIC"
            }
        }
        # Make the POST request
        req = urllib.request.Request(url, data=json.dumps(data).encode('utf-8'), headers=headers, method='POST')
        response = urllib.request.urlopen(req)
        response_code = response.getcode()

        # Print the status code of the POST request
        print(f"Status Code: {response_code}")

        # Print the extracted lines
        content = response.read().decode('utf-8')

        return {
            'statusCode': 200,
            'body': content
        }

    else:
        return {
            'statusCode': 404,
            'body': 'Token not found in the database'
        }
