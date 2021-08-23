import json


def handler(event, context):
    for record in event['Records']:
        if record['eventName'] == "INSERT":
            # Send notification to backend : Order is accepted or not
            print("DynamoDB Record: " + json.dumps(record['dynamodb'], indent=2))
    return 'Successfully processed {} records.'.format(len(event['Records']))
