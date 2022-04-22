import logging
import boto3
import botocore
import datetime
from cfn_tools import load_yaml
from ignition.utils.propvaluemap import PropValueMap
from ignition.locations.exceptions import InvalidDeploymentLocationError
from ignition.locations.utils import get_property_or_default


PUBLIC_KEY_SUFFIX = '_public'
PRIVATE_KEY_SUFFIX = '_private'

AWS_STACK_STATUS_CREATE_IN_PROGRESS = 'CREATE_IN_PROGRESS'
AWS_STACK_STATUS_CREATE_FAILED = 'CREATE_FAILED'
AWS_STACK_STATUS_ROLLBACK_COMPLETE = ['ROLLBACK_COMPLETE', 'ROLLBACK_IN_PROGRESS']
AWS_STACK_STATUS_CREATE_COMPLETE = 'CREATE_COMPLETE'

AWS_STACK_STATUS_DELETE_IN_PROGRESS = 'DELETE_IN_PROGRESS'
AWS_STACK_STATUS_DELETE_FAILED = 'DELETE_FAILED'
AWS_STACK_STATUS_DELETE_COMPLETE = 'DELETE_COMPLETE'

logger = logging.getLogger(__name__)

class AWSDeploymentLocation:
    """
    AWS based deployment location

    Attributes:
      name (str): name of the location
    """

    NAME = 'name'
    PROPERTIES = 'properties'
    AWS_ACCESS_KEY_ID = 'accessKeyId'
    AWS_SECRET_ACCESS_KEY = 'secretAccessKey'
    AWS_DEFAULT_REGION = 'aws_default_region'

    @staticmethod
    def from_dict(dl_data, resource_properties=None):
        """
        Creates an AWS deployment location from dictionary format

        Args:
            dl_data (dict): the deployment location data. Should have a 'name' field and 'properties' for the location configuration
            resource_properties (dict): resource properties

        Returns:
            an AWSDeploymentLocation instance
        """

        name = dl_data.get(AWSDeploymentLocation.NAME)
        if name is None:
            raise InvalidDeploymentLocationError(f'Deployment location missing \'{AWSDeploymentLocation.NAME}\' value')
        properties = dl_data.get(AWSDeploymentLocation.PROPERTIES)
        if properties is None:
            raise InvalidDeploymentLocationError(
                f'Deployment location missing \'{AWSDeploymentLocation.PROPERTIES}\' value')
        aws_access_key_id = get_property_or_default(
            properties, AWSDeploymentLocation.AWS_ACCESS_KEY_ID, error_if_not_found=False)
        aws_secret_access_key = get_property_or_default(
            properties, AWSDeploymentLocation.AWS_SECRET_ACCESS_KEY, error_if_not_found=False)
        aws_default_region = get_property_or_default(
            properties, AWSDeploymentLocation.AWS_DEFAULT_REGION, error_if_not_found=False)
        kwargs = {}
        if aws_default_region is not None:
            kwargs = {'aws_default_region': aws_default_region}

        if aws_access_key_id is None or aws_secret_access_key is None:
            raise InvalidDeploymentLocationError(f'AWS credentials are missing')

        return AWSDeploymentLocation(name, aws_access_key_id, aws_secret_access_key, **kwargs)

    def __init__(self, name, aws_access_key_id, aws_secret_access_key, aws_default_region='eu-west-1'):
        self.name = name
        self.aws_access_key_id = aws_access_key_id
        self.aws_secret_access_key = aws_secret_access_key
        self.aws_default_region = aws_default_region
        self.__cf_driver = None
        self.ec2 = self.__ec2()
        #sts client required to get peer account id in case of peer connection
        self.sts = self.__sts()

    def to_dict(self):
        """
        Produces a dictionary copy of the deployment location

        Returns:
            the deployment location configuration as a dictionary. For example:

            {
                'name': 'Test',
                'properties': {
                    ...
                }
            }
        """
        return {
            AWSDeploymentLocation.NAME: self.name,
            AWSDeploymentLocation.PROPERTIES: {
                AWSDeploymentLocation.AWS_ACCESS_KEY_ID: self.aws_access_key_id,
                AWSDeploymentLocation.AWS_SECRET_ACCESS_KEY: self.aws_secret_access_key
            }
        }

    @property
    def cloudformation_driver(self):
        if self.__cf_driver is None:
            self.__cf_driver = CloudFormationDriver(self,self.aws_default_region)
            if self.aws_default_region:
                self.__cf_driver.default_region = self.aws_default_region
        return self.__cf_driver

    def __ec2(self):
        return boto3.client(
            'ec2',
            aws_access_key_id=self.aws_access_key_id,
            aws_secret_access_key=self.aws_secret_access_key,
            region_name=self.aws_default_region
        )

    def __sts(self):
        return boto3.client(
            'sts',
            aws_access_key_id=self.aws_access_key_id,
            aws_secret_access_key=self.aws_secret_access_key,
            region_name=self.aws_default_region
        )

    def get_cf_input_util(self):
        return CFInputUtil()

    def close(self):
        pass


class RateLimitException(Exception):
    def __init__(self, message):
        self.message = message


class CloudFormationDriver():
    def __init__(self, aws_deployment_location, default_region='eu-west-1'):
        self.aws_deployment_location = aws_deployment_location
        self.default_region = default_region
        self.client = self.__create_cloudformation_client()
        self.paused_at = None

    def __create_cloudformation_client(self):
        return boto3.client(
            'cloudformation',
            aws_access_key_id=self.aws_deployment_location.aws_access_key_id,
            aws_secret_access_key=self.aws_deployment_location.aws_secret_access_key,
            region_name=self.default_region
        )
    
    def __to_parameter(self, param_name, param_value):
        return {
            'ParameterKey': param_name,
            'ParameterValue': param_value
        }

    def pause_api_calls(self):
        self.paused_at = datetime.datetime.now()

    def api_calls_paused(self):
        return self.paused_at is not None
    
    def resume_api_calls(self):
        self.paused_at = None

    def get_stack(self, stack_id_or_name):
        try:
            if self.api_calls_paused():
                delta = datetime.datetime.now() - self.paused_at
                # TODO add property for this
                if delta.total_seconds() > 10:
                    self.resume_api_calls()
                else:
                    return None

            response = self.client.describe_stacks(StackName=stack_id_or_name)
            stacks = response.get('Stacks', [])
            for stack in stacks:
                stack_id = stack.get('StackId', None)
                if stack_id is not None and stack_id == stack_id_or_name:
                    return stack
                stack_name = stack.get('StackName', None)
                if stack_name is not None and stack_name == stack_id_or_name:
                    return stack
        except botocore.exceptions.ClientError as ex:
            error_message = ex.response['Error']['Message']
            if 'Rate exceeded' in error_message:
                self.pause_api_calls()
                raise RateLimitException('')
            else:
                raise

        return None

    def get_stack_matching_name(self, matcher):
        try:
            # if self.api_calls_paused():
            #     delta = datetime.now() - self.paused_at
            #     if delta.total_seconds() > 20:
            #         self.resume_api_calls()
            #     else:
            #         return LifecycleExecution(request_id, STATUS_IN_PROGRESS)                    

            response = self.client.describe_stacks()
            for stack in response.get('Stacks', []):
                stack_name = stack.get('StackName', None)
                if stack_name is not None and matcher(stack_name):
                    return stack
        except botocore.exceptions.ClientError as ex:
            error_message = ex.response['Error']['Message']
            logging.debug(f'Failed to get AWS stack, {error_message}')
            raise 

        return None

    def get_stack_failure(self, want_stack_id):
        try:
            # if self.api_calls_paused():
            #     delta = datetime.now() - self.paused_at
            #     if delta.total_seconds() > 20:
            #         self.resume_api_calls()
            #     else:
            #         return LifecycleExecution(request_id, STATUS_IN_PROGRESS)                    

            response = self.client.describe_stack_events(StackName=want_stack_id)
            stack_failed_event = [f for f in response.get('StackEvents') if f.get('ResourceStatus', None)== 'CREATE_FAILED']
            if len(stack_failed_event) > 0:
                return stack_failed_event[0]["ResourceStatusReason"]
            else:
                return ''
        except botocore.exceptions.ClientError as ex:
            error_message = ex.response['Error']['Message']
            logging.debug(f'Failed to get AWS stack, {error_message}')
            return error_message

        return None

    def get_stack_resources(self, want_stack_id):
        stack_name = None
        stack = self.get_stack(want_stack_id)
        if stack is not None:
            #stack_name = stack.name
            stack_name = stack.get('StackName', None)
        if stack_name is not None:
            response = self.client.describe_stack_resources(StackName=stack_name)
            return response.get('StackResources', [])

        return []

    def create_stack(self, stack_name, template, parameters_dict):
        parameters = [self.__to_parameter(param_name, param_value) for (param_name, param_value) in parameters_dict.items()]
        params = {
            'StackName': stack_name,
            'TemplateBody': template,
            'Parameters': parameters,
        }

        stack_id = None
        try:
            if self._stack_exists(stack_name):
                # TODO hard-coded 10
                for _ in range(10):
                    status = self._get_stack_status(stack_name)
                    logger.info(f"status : {status}")
                    if status == AWS_STACK_STATUS_CREATE_COMPLETE:
                        # logging.info('checking existing stack {}'.format(status))
                        # time.sleep(10)
                        break
                    if status == AWS_STACK_STATUS_DELETE_IN_PROGRESS:
                        logging.info('checking deleting in progress stack {}'.format(status))
                        waiter = self.client.get_waiter('stack_delete_complete')
                        waiter.wait(StackName=stack_name)
                        break

            logging.info(f'creating new stack {stack_name} with template {template}')
            stack_result = self.client.create_stack(**params)
            stack_id = stack_result.get('StackId', None)
            return stack_id
        except botocore.exceptions.ClientError as ex:
            error_message = ex.response['Error']['Message']
            if error_message == 'No updates are to be performed.':
                logging.info("No changes")
            else:
                raise

    def delete_stack(self, delete_stack_id):
        if delete_stack_id is None:
            raise ValueError('delete_stack_id argument not provided')

        stack_name = None
        stack = self.get_stack(delete_stack_id)
        if stack is not None:
            stack_name = stack.get('StackName', None)
        if stack_name is None:
            raise ValueError('Invalid delete_stack_id value provided')

        try:
            if not self._stack_exists(stack_name):
                return None

            logging.info(f'Deleting stack {stack_name}')
            del_response = self.client.delete_stack(
                StackName=stack_name,
            )
            return del_response
        except botocore.exceptions.ClientError as ex:
            error_message = ex.response['Error']['Message']
            if error_message == 'No deletes are to be performed.':
                print("No changes")
            else:
                raise

    def json_serial(self, obj):
        """JSON serializer for objects not serializable by default json code"""
        if isinstance(obj, datetime):
            serial = obj.isoformat()
            return serial
        raise TypeError("Type not serializable")

    def _stack_exists(self, stack_name):
        stacks = self.client.list_stacks()['StackSummaries']
        for stack in stacks:
            if stack['StackStatus'] == 'DELETE_COMPLETE':
                continue
            if stack_name == stack['StackName']:
                return True
        return False

    def _get_stack_status(self, stack_name):
        stack_list = self.client.list_stacks()
        for st in stack_list['StackSummaries']:
            print(f"stack on account : {st['StackName']} existing stack: {stack_name}")
            if stack_name in st['StackName']:
                logger.info(f"stack found {st['StackName']}")
                status = st.get('StackStatus', None)
                return status


class CFInputUtil:

    def filter_used_properties(self, cf_template_str, original_properties):
        cf_tpl = load_yaml(cf_template_str)
        # cf_tpl = yaml.safe_load(cf_template_str)
        used_properties = {}
        if 'Parameters' in cf_tpl:
            parameters = cf_tpl.get('Parameters', {})
            if isinstance(original_properties, PropValueMap):
                return self.__filter_from_propvaluemap(parameters, original_properties)
            else:
                return self.__filter_from_dictionary(parameters, original_properties)
        return used_properties

    def __filter_from_dictionary(self, parameters, properties_dict):
        used_properties = {}
        for k, v in parameters.items():
            if k in properties_dict:
                used_properties[k] = properties_dict[k]
        return used_properties

    def __filter_from_propvaluemap(self, parameters, prop_value_map):
        used_properties = {}
        for param_name, param_def in parameters.items():
            if param_name in prop_value_map:
                used_properties[param_name] = self.__extract_property_from_value_map(prop_value_map, param_name)
            elif param_name.endswith(PUBLIC_KEY_SUFFIX):
                key_name = param_name[:len(param_name)-len(PUBLIC_KEY_SUFFIX)]
                if key_name in prop_value_map:
                    full_value = prop_value_map.get_value_and_type(key_name)
                    if full_value.get('type') == 'key' and 'publicKey' in full_value:
                        used_properties[param_name] = full_value.get('publicKey')
            elif param_name.endswith(PRIVATE_KEY_SUFFIX):
                key_name = param_name[:len(param_name)-len(PRIVATE_KEY_SUFFIX)]
                if key_name in prop_value_map:
                    full_value = prop_value_map.get_value_and_type(key_name)
                    if full_value.get('type') == 'key' and 'privateKey' in full_value:
                        used_properties[param_name] = full_value.get('privateKey')
        return used_properties

    def __extract_property_from_value_map(self, prop_value_map, property_name):
        full_value = prop_value_map.get_value_and_type(property_name)
        if full_value.get('type') == 'key':
            return full_value.get('keyName')
        else:
            return prop_value_map[property_name]