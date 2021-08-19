import json
import logging
from botocore.exceptions import ClientError
LOG = logging.getLogger()
LOG.setLevel(logging.INFO)
import requests
import boto3

# Map instance architectures to an AMI name pattern
archToAMINamePattern = {
    "PV64": "amzn-ami-pv*x86_64-ebs",
    "HVM64": "amzn-ami-hvm*x86_64-gp2",
    "HVMG2": "amzn-ami-graphics-hvm*x86_64-ebs*"
}


# // Check if the image is a beta or rc image. The Lambda function won't return any of those images.
def is_beta(image_name: str):
    return 'beta' in image_name.lower() or (".rc") in image_name.lower()


def send_response(event, context, response_status, response_data):
    response_body = {'Status': response_status,
                     'Reason': 'See the details in CloudWatch Log Stream: ' + context.log_stream_name,
                     'PhysicalResourceId': context.log_stream_name,
                     'StackId': event['StackId'],
                     'RequestId': event['RequestId'],
                     'LogicalResourceId': event['LogicalResourceId'],
                     'Data': response_data}

    LOG.info(f'RESPONSE BODY: {json.dumps(response_body)}')

    try:
        req = requests.put(event['ResponseURL'], data=json.dumps(response_body))
        if req.status_code != 200:
            LOG.error(req)
            raise Exception('Recieved non 200 response while sending response to CFN.')
        return
    except requests.exceptions.RequestException as e:
        LOG.error('Exception while sending back the request to CFN', e)


def lambda_handler(event, context):
    LOG.info(f'REQUEST RECEIVED: {event}')
    # For Delete requests, immediately send a SUCCESS response.
    if event['RequestType'] == 'Delete':
        LOG.info('Entering Delete')
        send_response(event, context, "SUCCESS", {})
        return
    response_status = 'FAILED'
    response_data = {}
    describe_response = {}
    try:
        region = event['ResourceProperties']['Region']
        architectures= [archToAMINamePattern[event['ResourceProperties']['Architecture']]]
        ec2_client = boto3.client('ec2', region_name=region)
        # Get AMI IDs with the specified name pattern and owner
        describe_response = ec2_client.describe_images(
            Filters=[{'Name': "name", 'Values': architectures},
                     {'Name': "tag-key", 'Values': ['ami-compliance-check']}],
            Owners=["amazon"]
        )
    except ClientError as e:
        LOG.error(e.response['Error']['Code'])
    except Exception as e:
        LOG.error(f'Exception in the lamda handler, {e}')
    if describe_response['ResponseMetadata']['HTTPStatusCode'] == 200:
        images = describe_response['Images']
        # Sort images by name in decscending order. The names contain the AMI version, formatted as YYYY.MM.Ver.
        if len(images) == 0:
            raise Exception("Images not Found")
        images.sort(key=lambda k: k['Name'])
        LOG.info(f'images: {images}')
        for image in images:
            if is_beta(image['Name']):
                continue
            response_status = "SUCCESS"
            response_data["Id"] = image['ImageId']
            break
        send_response(event, context, response_status, response_data)
