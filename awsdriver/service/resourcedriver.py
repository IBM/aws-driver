import logging
from pathlib import Path
from ignition.model.lifecycle import LifecycleExecution, STATUS_IN_PROGRESS, STATUS_COMPLETE, STATUS_FAILED
import ignition.model.references as reference_model
from ignition.service.framework import Service, Capability
from ignition.service.resourcedriver import ResourceDriverHandlerCapability, InfrastructureNotFoundError, ResourceDriverError, InvalidRequestError
from ignition.model.failure import FailureDetails, FAILURE_CODE_INFRASTRUCTURE_ERROR
from ignition.service.config import ConfigurationPropertiesGroup
from ignition.service.framework import ServiceRegistration
from awsdriver.location.deployment_location import RateLimitException
from awsdriver.service.common import DELETE_REQUEST_PREFIX, REQUEST_ID_SEPARATOR
from awsdriver.location import *
from awsdriver.model.exceptions import *
from awsdriver.service.cloudformation import *
from .vpc_cf import *
from .subnet_cf import *
from .tgw_cf import *
from .igw_cf import *
from .route_table_cf import *
from .tgw_peer_attach_cf import *


driver_directory = here = Path(__file__).parent.parent

logger = logging.getLogger(__name__)

CLOUDFORMATION_TEMPLATE_TYPE = 'CLOUDFORMATION'

VPC_RESOURCE_TYPE = 'VPC'

AWS_STACK_STATUS_CREATE_IN_PROGRESS = 'CREATE_IN_PROGRESS'
AWS_STACK_STATUS_CREATE_FAILED = 'CREATE_FAILED'
AWS_STACK_STATUS_ROLLBACK_COMPLETE = ['ROLLBACK_COMPLETE', 'ROLLBACK_IN_PROGRESS']
AWS_STACK_STATUS_CREATE_COMPLETE = 'CREATE_COMPLETE'

AWS_STACK_STATUS_DELETE_IN_PROGRESS = 'DELETE_IN_PROGRESS'
AWS_STACK_STATUS_DELETE_FAILED = 'DELETE_FAILED'
AWS_STACK_STATUS_DELETE_COMPLETE = 'DELETE_COMPLETE'

class AdditionalResourceDriverProperties(ConfigurationPropertiesGroup, Service, Capability):

    def __init__(self):
        super().__init__('resource_driver')
        self.aws_api_backoff = 10


class AWSDriverConfigurator():

    def __init__(self):
        pass

    def configure(self, configuration, service_register):
        service_register.add_service(ServiceRegistration(ResourceDriverHandler, AdditionalResourceDriverProperties))


class ResourceDriverHandler(Service, ResourceDriverHandlerCapability):

    def __init__(self, resource_driver_properties):
        self.resource_driver_properties = resource_driver_properties
        self.stack_name_creator = StackNameCreator()
        self.props_merger = PropertiesMerger()
        self.handlers = {
            'resource::AWSVPC::1.0': VPCCloudFormation(),
            'resource::AWSSubnet::1.0': SubnetCloudFormation(),
            'resource::AWSRouteTable::1.0': RouteTableCloudFormation(),
            'resource::AWSTransitGateway::1.0': TGWCloudFormation(),
            'resource::AWSInternetGateway::1.0': IGWCloudFormation(),
            'resource::AWSTransitGatewayPeerAttachment::1.0': TGWPACloudFormation(),
        }

    def execute_lifecycle(self, lifecycle_name, driver_files, system_properties, resource_properties, request_properties, associated_topology, deployment_location):
        logger.debug(f'lifecycle_name:{lifecycle_name},driver_files:{driver_files},system_properties:{system_properties}')
        aws_location = None
        try:
            regionRcvd = resource_properties.get("region")
            if regionRcvd:
                logger.info(f'received region as {regionRcvd} and cloud formation will be created here')
                deployment_location[AWSDeploymentLocation.PROPERTIES][AWSDeploymentLocation.AWS_DEFAULT_REGION] = regionRcvd

            aws_location = AWSDeploymentLocation.from_dict(deployment_location)

            resource_type = system_properties.get('resourceType', None)
            if resource_type is None:
                raise InvalidRequestError(f'system_properties.resourceType must be provided')

            resource_id = system_properties.get('resourceId', None)
            if resource_id is None:
                raise InvalidRequestError(f'system_properties.resource_id must be provided')

            resource_name = system_properties.get('resourceName', None)
            if resource_name is None:
                raise InvalidRequestError(f'system_properties.resourceName must be provided')

            method_name = lifecycle_name.lower()

            handler = self.handlers.get(resource_type, None)
            if handler is None:
                raise InvalidRequestError(f'No handler for resourceType {resource_type}')

            if method_name == 'delete' or method_name == 'uninstall':
                method_name = 'remove'
            elif method_name == 'install':
                method_name = 'create'
            method = getattr(handler, method_name)
            if method is not None:
                return method(resource_id, lifecycle_name, driver_files, system_properties, resource_properties, request_properties, associated_topology, aws_location)
            else:
                raise InvalidRequestError(f'Handler does not support lifecycle {lifecycle_name}')
        finally:
            if aws_location is not None:
                aws_location.close()
            logger.debug("exit execute")

    def get_lifecycle_execution(self, request_id, deployment_location):
        aws_location = AWSDeploymentLocation.from_dict(deployment_location)
        cloudformation_driver = aws_location.cloudformation_driver
        request_type, stack_id, operation_id = self.__split_request_id(request_id)

        if stack_id == 'SKIP':
            return LifecycleExecution(request_id, STATUS_COMPLETE, failure_details=None, outputs={})

        try:
            # limit calls to rate-limited AWS describe stack API
            # if random.randint(1, self.x)%2 == 0:
            #     return LifecycleExecution(request_id, STATUS_IN_PROGRESS)
            stack = cloudformation_driver.get_stack(stack_id)
            if stack is None:
                # TODO
                return LifecycleExecution(request_id, STATUS_IN_PROGRESS)                    
            logger.debug('Stack found: %s', stack)
        except StackNotFoundError as e:
            logger.debug('Stack not found: %s', stack_id)
            if request_type == DELETE_REQUEST_PREFIX:
                logger.debug('Stack not found on delete request, returning task as successful: %s', stack_id)
                return LifecycleExecution(request_id, STATUS_COMPLETE)
            else:
                raise InfrastructureNotFoundError(str(e)) from e
        except RateLimitException as ex:
            return LifecycleExecution(request_id, STATUS_IN_PROGRESS)                    

        if stack is None:
            logger.debug('Stack not found: %s', stack_id)
            if request_type == DELETE_REQUEST_PREFIX:
                logger.debug('Stack not found on delete request, returning task as successful: %s', stack_id)
                return LifecycleExecution(request_id, STATUS_COMPLETE)
            else:
                raise InfrastructureNotFoundError(f'Cannot find stack {stack_id}')

        logger.debug(f'Retrieved stack: {stack}')
        return self.__build_execution_response(stack, request_id, cloudformation_driver)

    def __split_request_id(self, request_id):
        return tuple(request_id.split(REQUEST_ID_SEPARATOR))

    def __build_execution_response(self, stack, request_id, cloudformation_driver):
        request_type, stack_id, operation_id = self.__split_request_id(request_id)
        stack_status = stack.get('StackStatus', None)
        failure_details = None
        if request_type == CREATE_REQUEST_PREFIX:
            status = self.__determine_create_status(request_id, stack_id, stack_status)
        else:
            status = self.__determine_delete_status(request_id, stack_id, stack_status)
        if status == STATUS_FAILED:
            description = cloudformation_driver.get_stack_failure(stack_id)
            failure_details = FailureDetails(FAILURE_CODE_INFRASTRUCTURE_ERROR, description)
        outputs = None
        if request_type == CREATE_REQUEST_PREFIX:
            outputs_from_stack = stack.get('Outputs', [])
            outputs = self.__translate_outputs_to_values_dict(outputs_from_stack)

        logger.info(f'request_id {request_id} stack: {stack} outputs: {outputs}')

        return LifecycleExecution(request_id, status, failure_details=failure_details, outputs=outputs)

    def __change_outputs_key(self, key):
        if key == 'VPCID':
            key = 'vpc_id'
        elif key == 'SUBNETID':
            key = 'subnet_id'
        elif key == 'IGWID':
            key = 'igw_id'
        elif key == 'ROUTETABLEID':
            key = 'route_table_id'
        elif key == 'TGWID':
            key = 'transit_gateway_id'
        elif key == 'TGWRTID':
            key = 'transit_route_table_id'
        elif key == 'TGWPAID':
            key = 'tgw_peer_attachment_id'
        return key

    def __translate_outputs_to_values_dict(self, stack_outputs):
        if len(stack_outputs) == 0:
            return None
        outputs = {}
        for stack_output in stack_outputs:
            key = stack_output.get('OutputKey')
            value = stack_output.get('OutputValue')
            outputs[self.__change_outputs_key(key)] = value

        logger.info(f'stack outputs: {stack_outputs} to outputs: {outputs}')

        return outputs

    def __determine_create_status(self, request_id, stack_id, stack_status):
        if stack_status in [AWS_STACK_STATUS_CREATE_IN_PROGRESS]:
            create_status = STATUS_IN_PROGRESS
        elif stack_status in [AWS_STACK_STATUS_CREATE_COMPLETE]:
            create_status = STATUS_COMPLETE
        elif stack_status in [AWS_STACK_STATUS_CREATE_FAILED]:
            create_status = STATUS_FAILED
        elif stack_status in AWS_STACK_STATUS_ROLLBACK_COMPLETE:
            create_status = STATUS_FAILED
        else:
            raise ResourceDriverError(f'Cannot determine status for request \'{request_id}\' as the current Stack status is \'{stack_status}\' which is not a valid value for the expected transition')
        logger.debug('Stack %s has stack_status %s, setting status in response to %s', stack_id, stack_status, create_status)
        return create_status

    def __determine_delete_status(self, request_id, stack_id, stack_status):
        if stack_status in [AWS_STACK_STATUS_DELETE_IN_PROGRESS]:
            delete_status = STATUS_IN_PROGRESS
        elif stack_status in [AWS_STACK_STATUS_DELETE_COMPLETE]:
            delete_status = STATUS_COMPLETE
        elif stack_status in [AWS_STACK_STATUS_DELETE_FAILED]:
            delete_status = STATUS_FAILED
        else:
            raise ResourceDriverError(f'Cannot determine status for request \'{request_id}\' as the current Stack status is \'{stack_status}\' which is not a valid value for the expected transition')
        logger.debug('Stack %s has stack_status %s, setting status in response to %s', stack_id, stack_status, delete_status)
        return delete_status

    def find_reference(self, instance_name, driver_files, deployment_location):
        """
        Find a Resource, returning the necessary property output values and internal resources from those instances

        :param str instance_name: name used to filter the Resource to find
        :param ignition.utils.file.DirectoryTree driver_files: object for navigating the directory intended for this driver from the Resource package. The user should call 'remove_all' when the files are no longer needed
        :param dict deployment_location: the deployment location to find the instance in
        :return: an ignition.model.references.FindReferenceResponse

        :raises:
            ignition.service.resourcedriver.InvalidDriverFilesError: if the scripts are not valid
            ignition.service.resourcedriver.InvalidRequestError: if the request is invalid e.g. if no script can be found to execute the transition/operation given by lifecycle_name
            ignition.service.resourcedriver.TemporaryResourceDriverError: there is an issue handling this request at this time
            ignition.service.resourcedriver.ResourceDriverError: there was an error handling this request
        """
        return reference_model.FindReferenceResponse()


