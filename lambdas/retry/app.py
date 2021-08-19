
import json
import boto3
import datetime
import logging

LOG = logging.getLogger()
LOG.setLevel(logging.INFO)
SUCCESS='SUCCESS'
FAILED = 'FAILED'


def lambda_handler(event, context):
    LOG.info("Event Info: {}".format(event))

    status_code = 200
    response_data = []


    client = boto3.client('lambda')

    for record in event['Records']:
        body = json.loads(record['body'])
        response = client.invoke(
            FunctionName=body['requestContext']['functionArn'],
            InvocationType='RequestResponse',
            Payload=json.dumps(body['requestPayload']).encode()
        )
        LOG.info("Response Info: {}".format(response))
        if 'FunctionError' in response:
            raise Exception ("Retry function returned error - " + response['FunctionError'])


        response_data.append({ "Status":SUCCESS , "Item": body['requestContext']['functionArn']})

    LOG.info("Status Info {}".format(response_data))
    return {
        'statusCode': status_code,
        'body': json.dumps(response_data)
    }

def default(o):
    if isinstance(o, (datetime.date, datetime.datetime)):
        return o.isoformat()
