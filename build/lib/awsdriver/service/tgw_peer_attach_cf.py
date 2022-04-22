from cmath import log
import random
from time import sleep as sleepseconds
import time
from awsdriver.service.common import CREATE_REQUEST_PREFIX, build_request_id
from ignition.model.lifecycle import LifecycleExecuteResponse
from ignition.service.resourcedriver import InfrastructureNotFoundError, ResourceDriverError
from awsdriver.location import *
from awsdriver.model.exceptions import *
from awsdriver.service.cloudformation import *
from awsdriver.service.topology import AWSAssociatedTopology


logger = logging.getLogger(__name__)

class TGWPACloudFormation(CloudFormation):


    def __create_tgwpeerattachment_resource_name(self, system_properties, resource_properties, resource_name):
        system_properties['resourceName'] = self.sanitize_name(resource_properties.get('region', ''), '__', resource_properties.get('peer_region_name', ''),
        '__', resource_properties.get('vpc_id', ''), '__tgwpeerattachment')
        return system_properties['resourceName']

    def __create_tgwpeerroute_resource_name(self, system_properties, resource_properties, resource_name):
        system_properties['resourceName'] = self.sanitize_name(resource_properties.get('region', ''), '__', resource_properties.get('peer_region_name', ''),
        '__', resource_properties.get('vpc_id', ''), '__tgwpeerroute')
        return system_properties['resourceName']

    def create(self, resource_id, lifecycle_name, driver_files, system_properties, resource_properties, request_properties, associated_topology, aws_location):
        logger.info(f'invoking of tgw peering attachment for resoure {resource_id} with resoure property {resource_properties} ')
        stack_id = self.get_stack_id(resource_id, lifecycle_name, driver_files, system_properties, resource_properties, request_properties, associated_topology, aws_location)
        if stack_id is None:
            requestor_region = resource_properties.get('region', None)
            if requestor_region is None:
                raise ResourceDriverError('Requestor region is mandatory for connectivity')
            acceptor_region = resource_properties.get('peer_region_name', None)
            if acceptor_region is None:
                raise ResourceDriverError('Acceptor region is mandatory for connectivity')
            if requestor_region == acceptor_region:
                raise ResourceDriverError('Requestor and Acceptor region cannot be same for connectivity')

            cloudformation_driver = aws_location.cloudformation_driver
            resource_name = self.__create_tgwpeerattachment_resource_name(system_properties, resource_properties, self.get_resource_name(system_properties))
            stack_name = self.get_stack_name(resource_id, resource_name)


            #get target/peer account id
            peer_aws_location = None
            try:
                #create new aws client with acceptor region
                kwargs = {}
                peer_region_name = resource_properties['peer_region_name']
                if  peer_region_name is not None:
                    kwargs = {'aws_default_region': peer_region_name}
                peer_aws_location = AWSDeploymentLocation(aws_location.name, aws_location.aws_access_key_id, aws_location.aws_secret_access_key, **kwargs)
                #TODO get get peer account id using sts client
                peer_account_id = peer_aws_location.sts.get_caller_identity().get('Account')
                #TODO add some default or throw exception if peer account not there.
                if peer_account_id is None:
                    raise ResourceDriverError(f'Unable to get peer account id for tgw peering for region {peer_region_name}') 
            except Exception as e:
                logger.error("Error occured while getting peer account id during tgw peer connection ", e)
                raise ResourceDriverError(str(e)) from e

            #set peer account id in template
            resource_properties['peer_account_id'] = peer_account_id
              
            cf_template = self.render_template(system_properties, resource_properties, request_properties, 'cloudformation_tgw_createtgwpeerattachment_template.yaml')
            cf_parameters = self.get_cf_parameters(resource_properties, system_properties, aws_location, cf_template)

            try:
                stack_id = cloudformation_driver.create_stack(stack_name, cf_template, cf_parameters)
            except Exception as e:
                logger.error("Error occured while creating tgw peer attachment stack", e)
                raise ResourceDriverError(str(e)) from e

            if stack_id is None:
                raise ResourceDriverError('Failed to create cloudformation stack on AWS')

        request_id = build_request_id(CREATE_REQUEST_PREFIX, stack_id)

        #accept the peer attachment once creation completed
        try:
            self.__acceptpeerattachment(request_id,resource_id, lifecycle_name, driver_files, system_properties, resource_properties, request_properties, associated_topology, aws_location)
        except Exception as e:
            logger.error("Error occured while accepting tgw peer attachment", e)
            raise ResourceDriverError(str(e)) from e

        associated_topology = AWSAssociatedTopology()
        associated_topology.add_stack_id(resource_name, stack_id)
        logger.info(f'complete  tgw peering attachment and acceptance for resoure {resource_id} with resoure property {resource_properties} ')
        return LifecycleExecuteResponse(request_id, associated_topology=associated_topology)
    
    def remove(self, resource_id, lifecycle_name, driver_files, system_properties, resource_properties, request_properties, associated_topology, aws_location):
        self.__create_tgwpeerattachment_resource_name(system_properties, resource_properties, self.get_resource_name(system_properties))
        return super().remove(resource_id, lifecycle_name, driver_files, system_properties, resource_properties, request_properties, associated_topology, aws_location)

    def check_tgw_peer_state(self, awsclient, tgwpeerid):
        logger.info(f'checking tgw peer attachement state for {tgwpeerid}')
        state = 'pendingAcceptance'
        maxtry = 0
        #TODO improvise never ending call with max retry
        while str(state) != 'available':
            if maxtry > 45:
                break
            maxtry = maxtry +1
            logger.info(f'current state of TGW peer attachment is {state}  for id {tgwpeerid}')
            time.sleep(10)
            result = awsclient.ec2.describe_transit_gateway_attachments(
                TransitGatewayAttachmentIds=[
                tgwpeerid,
                ],
            )
            if result is not None:
                tgwpa = result['TransitGatewayAttachments']
                if tgwpa is not None:
                    state = tgwpa[0].get('State')

    def __acceptpeerattachment(self, request_id, resource_id, lifecycle_name, driver_files, system_properties, resource_properties, request_properties, associated_topology, aws_location):
        
        logger.info(f'invoking acceptance of tgw peer attachment for request :: {request_id} and resource_prop as :: {resource_properties}')
        request_type, stack_id, operation_id = tuple(request_id.split(REQUEST_ID_SEPARATOR))
        cloudformation_driver = aws_location.cloudformation_driver
        # stack = cloudformation_driver.get_stack(stack_id)
        waiter =  cloudformation_driver.client.get_waiter('stack_create_complete')
        if waiter is not None:
            waiter.wait(StackName=stack_id)
        
        newstack = cloudformation_driver.get_stack(stack_id)

        ##fetch tgw peer attach id and accept using ec2 api
        if request_type == CREATE_REQUEST_PREFIX:
            outputs_from_stack = newstack.get('Outputs', [])
            if outputs_from_stack is not None:
                stack_output = outputs_from_stack[0]
                twg_peer_attach_id = stack_output.get('OutputValue')
                ##try creating directly
                peer_aws_location = None
                try:
                    #create new aws client with acceptor region
                    kwargs = {}
                    peer_region_name = resource_properties['peer_region_name']
                    if  peer_region_name is not None:
                        kwargs = {'aws_default_region': peer_region_name}
                    peer_aws_location = AWSDeploymentLocation(aws_location.name, aws_location.aws_access_key_id, aws_location.aws_secret_access_key, **kwargs)
                    peer_aws_location.ec2.accept_transit_gateway_peering_attachment(
                        TransitGatewayAttachmentId= twg_peer_attach_id,
                    )
                    logger.info(f'Waiting for tgw peer attachment to be accepted ')
                    self.check_tgw_peer_state(peer_aws_location,twg_peer_attach_id)
                except Exception as e:
                    logger.error("Error occured while accepting tgw peer attach", e)
                    raise ResourceDriverError(str(e)) from e
                finally:
                    if peer_aws_location is not None:
                        peer_aws_location.close()
        else:
            logger.warn(f'No create request found for connectivity acceptance, unable to accept the tgw peer attachment for resource {resource_properties}')
            # outputs_from_stack = newstack.get('Outputs', [])
        logger.info("completed accepting the tgw peer attachment , proceed with tgw route table update")
        

