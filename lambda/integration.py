import json
import boto3
from botocore.exceptions import ClientError


def handler(event, context):
    if 'httpMethod' in event and event['httpMethod'] == 'POST':
        # Receive order accept result from restaurant
        client = boto3.client('dynamodb')
        data = json.loads(event['body'])
        try:
            result = client.put_item(
                TableName='OrderResult',
                Item={
                    'order_id': {
                        'N': data['order_id']
                    },
                    'processed_by': {
                        'S': data['processed_by']
                    },
                    'result': {
                        'S': data['result']
                    }
                },
                ConditionExpression="attribute_not_exists(order_id)"
            )
        except ClientError as e:
            if e.response['Error']['Code'] == 'ConditionalCheckFailedException':
                return {
                    'statusCode': 200,
                    'body': 'Already processed order'
                }
        finally:
            return {
                'statusCode': result['ResponseMetadata']['HTTPStatusCode'],
                'body': result['ResponseMetadata']['RequestId']
            }
    elif 'Records' in event:
        for record in event['Records']:
            # Send order to restaurant
            payload = json.loads(record["body"])
            print(payload["Message"])
        return {
            'statusCode': 200,
            'body': 'Send result message'
        }
