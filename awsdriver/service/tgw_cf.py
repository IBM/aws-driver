from cmath import log
import random
from time import sleep as sleepseconds
from awsdriver.service.common import CREATE_REQUEST_PREFIX, build_request_id
from ignition.model.lifecycle import LifecycleExecuteResponse
from ignition.service.resourcedriver import InfrastructureNotFoundError, ResourceDriverError
from awsdriver.location import *
from awsdriver.model.exceptions import *
from awsdriver.service.cloudformation import *
from awsdriver.service.topology import AWSAssociatedTopology


logger = logging.getLogger(__name__)

class TGWCloudFormation(CloudFormation):

    def create(self, resource_id, lifecycle_name, driver_files, system_properties, resource_properties, request_properties, associated_topology, aws_location):
        logger.info(f'invoking creation of tgw resource and tgw route tabe for resourece :: {resource_id} and resource_prop as :: {resource_properties}')
        stack_id = self.get_stack_id(resource_id, lifecycle_name, driver_files, system_properties, resource_properties, request_properties, associated_topology, aws_location)
        if stack_id is None:
            cloudformation_driver = aws_location.cloudformation_driver

            resource_name = self.__create_resource_name(system_properties, resource_properties, self.get_resource_name(system_properties))
            stack_name = self.get_stack_name(resource_id, resource_name)

            cf_template = self.render_template(system_properties, resource_properties, request_properties, 'cloudformation_tgw.yaml')
            cf_parameters = self.get_cf_parameters(resource_properties, system_properties, aws_location, cf_template)

            try:
                stack_id = cloudformation_driver.create_stack(stack_name, cf_template, cf_parameters)
                logger.debug(f'Created Stack Id: {stack_id}')
            except Exception as e:
                raise ResourceDriverError(str(e)) from e

            if stack_id is None:
                raise ResourceDriverError('Failed to create cloudformation stack on AWS')

        request_id = build_request_id(CREATE_REQUEST_PREFIX, stack_id)
        associated_topology = AWSAssociatedTopology()
        associated_topology.add_stack_id(resource_name, stack_id)
        logger.info(f'completed creation of tgw resource and tgw route tabe for resourece :: {resource_id} and resource_prop as :: {resource_properties}')
        return LifecycleExecuteResponse(request_id, associated_topology=associated_topology)

    def remove(self, resource_id, lifecycle_name, driver_files, system_properties, resource_properties, request_properties, associated_topology, aws_location):
        logger.info(f'invoking removal of tgw resource and tgw route tabe for resourece :: {resource_id} and resource_prop as :: {resource_properties}')
        self.__create_resource_name(system_properties, resource_properties, self.get_resource_name(system_properties))
        return self.removeIgnoringResource(resource_id, lifecycle_name, driver_files, system_properties, resource_properties, request_properties, associated_topology, aws_location)

    def __create_resource_name(self, system_properties, resource_properties, resource_name):
        system_properties['resourceName'] = self.get_resource_name(system_properties)
        return system_properties['resourceName']

    def createtgwroutetableassociation(self, resource_id, lifecycle_name, driver_files, system_properties, resource_properties, request_properties, associated_topology, aws_location):
        logger.info(f'invoking creation of tgw route table association for resourece :: {resource_id} and resource_prop as :: {resource_properties}')
        associated_topology = AWSAssociatedTopology()

        stack_id = self.get_stack_id(resource_id, lifecycle_name, driver_files, system_properties, resource_properties, request_properties, associated_topology, aws_location)
        if stack_id is None:
            cloudformation_driver = aws_location.cloudformation_driver

            subnet_id = resource_properties.get('subnet_id', None)
            if subnet_id is None:
                public_private = request_properties.get('subnet_id', None)

            public_private = resource_properties.get('public_private', None)
            if public_private is None:
                public_private = request_properties.get('public_private', None)
                if public_private is None:
                    raise ResourceDriverError(f'Missing public_private property for operation createtgwroutetableassociation on resource {resource_id}')

            is_primary = resource_properties.get('primary', None)
            if is_primary is None:
                is_primary = request_properties.get('primary', None)
            logger.info(f'createtgwroutetableassociation1 subnet_id = {subnet_id}, public_private = {public_private}, is_primary = {is_primary}')

            is_primary = self.__as_boolean(is_primary)

            logger.info(f'createtgwroutetableassociation2 subnet_id = {subnet_id}, public_private = {public_private}, is_primary = {is_primary}')

            resource_name = self.__create_tgwroutetableassociation_resource_name(system_properties, resource_properties, self.get_resource_name(system_properties))
            stack_name = self.get_stack_name(resource_id, resource_name)

            if is_primary:
                # create only for primary (private) subnets
                logger.info(f'createtgwroutetableassociation creating stack')

                cf_template = self.render_template(system_properties, resource_properties, request_properties, 'cloudformation_tgw_createrta.yaml')
                cf_parameters = self.get_cf_parameters(resource_properties, system_properties, aws_location, cf_template)
                logger.debug(f'stack_name={stack_name} cf_template={cf_template} cf_parameters={cf_parameters}')

                stack_id = cloudformation_driver.create_stack(stack_name, cf_template, cf_parameters)
                logger.debug(f'Created Stack Id: {stack_id}')
                if stack_id is None: 
                    raise ResourceDriverError('Failed to create cloudformation stack on AWS')

                associated_topology.add_stack_id(resource_name, stack_id)
            else:
                # TODO hacky wait ensure non-primary (private) subnets wait for primary subnet to create the stack
                # This is to address an issue in CP4NA/Daytona which results in the primary vpc assembly SubnetToTgwRoute operations triggering
                # before the subnets have become active (SubnetToTgwRoute operations should trgger on subnets becoming active, but instead
                # they are triggering whenn one of the TGWVPCAttachment operations completes)
                # A better way to handle this might be to allow all these calls to proceed to creating a stack, and in the get_lifecycle_execution
                # method translate the specific failure relating to a duplicate in to a successful operation result.
                sleepseconds(8)

        # use the name request_id for any operation of this type against a vpc
        request_id = build_request_id(CREATE_REQUEST_PREFIX, stack_name)
        logger.info(f'completed creation of tgw route table association for resourece :: {resource_id} and resource_prop as :: {resource_properties}')
        return LifecycleExecuteResponse(request_id, associated_topology=associated_topology)

    def removetgwroutetableassociation(self, resource_id, lifecycle_name, driver_files, system_properties, resource_properties, request_properties, associated_topology, aws_location):
        self.__create_tgwroutetableassociation_resource_name(system_properties, resource_properties, self.get_resource_name(system_properties))
        return super().remove(resource_id, lifecycle_name, driver_files, system_properties, resource_properties, request_properties, associated_topology, aws_location)

    def __create_tgwroutetableassociation_resource_name(self, system_properties, resource_properties, resource_name):
        vpc_id = resource_properties.get('vpc_id', None)
        if vpc_id is None:
            raise ResourceDriverError(f'vpc_id cannot be null for operation createtgwroutetableassociation for resource {resource_name}')
        system_properties['resourceName'] = self.sanitize_name(vpc_id, '_tgwrta')
        return system_properties['resourceName']

    def addtgwroute(self, resource_id, lifecycle_name, driver_files, system_properties, resource_properties, request_properties, associated_topology, aws_location):
        associated_topology = AWSAssociatedTopology()

        rn = self.get_resource_name(system_properties)
        logger.info(f'invoking addtgwroute resource_id: {resource_id} resource_name: {rn} resource_properties: {resource_properties} ')
        stack_id = self.get_stack_id(resource_id, lifecycle_name, driver_files, system_properties, resource_properties, request_properties, associated_topology, aws_location)
        if stack_id is None:
            cloudformation_driver = aws_location.cloudformation_driver

            access_domain_state = resource_properties.get('access_domain_state', None)
            if access_domain_state is None:
                raise ResourceDriverError(f'access_domain_state is null for resource_id {resource_id}')

            if access_domain_state == 'global':
                resource_name = self.__create_tgwroute_resource_name(system_properties, resource_properties, rn)
                stack_name = self.get_stack_name(resource_id, resource_name)

                # get the transit_gateway_attachment_id for this vpc from the CPA resource_properties
                vpc_id = resource_properties.get('vpc_id', None)
                if vpc_id is None:
                    raise ResourceDriverError(f'Missing vpc_id in request_properties {request_properties} for resource_id {resource_id} resource_name {rn} for operation addtgwroute')
                vpc_id = vpc_id.replace("-", "")
                transit_gateway_attachment_id_prop = f'{vpc_id}TGWATTACHID'
                transit_gateway_attachment_id = resource_properties.get(transit_gateway_attachment_id_prop, None)
                if transit_gateway_attachment_id is None:
                    raise ResourceDriverError(f'Cannot find {transit_gateway_attachment_id_prop} in resource_properties {resource_properties} for resource_id {resource_id} resource_name {rn} for operation addtgwroute')
                # and add it to the request_properties (not the resource_properties, because it will be overwritten and it doesn't apply to the CPA)
                request_properties["transit_gateway_attachment_id"] = transit_gateway_attachment_id

                cf_template = self.render_template(system_properties, resource_properties, request_properties, 'cloudformation_tgw_addtgwroute.yaml')
                cf_parameters = self.get_cf_parameters(resource_properties, system_properties, aws_location, cf_template)
                logger.debug(f'stack_name={stack_name} cf_template={cf_template} cf_parameters={cf_parameters}')

                try:
                    stack_id = cloudformation_driver.create_stack(stack_name, cf_template, cf_parameters)
                    logger.debug(f'Created Stack Id: {stack_id}')
                except Exception as e:
                    raise ResourceDriverError(str(e)) from e

                if stack_id is None:
                    raise ResourceDriverError('Failed to create cloudformation stack on AWS')

                request_id = build_request_id(CREATE_REQUEST_PREFIX, stack_id)
                associated_topology.add_stack_id(resource_name, stack_id)
            else:
                request_id = build_request_id(CREATE_REQUEST_PREFIX, 'SKIP')
        logger.info(f'completed addtgwroute for resource_name: {rn} resource_properties: {resource_properties} ')
        return LifecycleExecuteResponse(request_id, associated_topology=associated_topology)

    def removetgwroute(self, resource_id, lifecycle_name, driver_files, system_properties, resource_properties, request_properties, associated_topology, aws_location):
        self.__create_tgwroute_resource_name(system_properties, resource_properties, self.get_resource_name(system_properties))
        return super().remove(resource_id, lifecycle_name, driver_files, system_properties, resource_properties, request_properties, associated_topology, aws_location)

    def __create_tgwroute_resource_name(self, system_properties, resource_properties, resource_name):
        subnet_id = resource_properties.get('subnet_id', None)
        if subnet_id is None:
            raise Exception(f'Must provide subnet_id')
        system_properties['resourceName'] = self.sanitize_name(resource_name, '_', subnet_id, '__', resource_properties.get('vpc_id', ''), '__tgwsubnetroute')
        return system_properties['resourceName']

    def createtgwroutetable(self, resource_id, lifecycle_name, driver_files, system_properties, resource_properties, request_properties, associated_topology, aws_location):
        return ResourceDriverError(f'TGW.createtgwroutetable not implemented')

    def removetgwroutetable(self, resource_id, lifecycle_name, driver_files, system_properties, resource_properties, request_properties, associated_topology, aws_location):
        return ResourceDriverError(f'TGW.removetgwroutetable not implemented')

    
    def createtgwattachment(self, resource_id, lifecycle_name, driver_files, system_properties, resource_properties, request_properties, associated_topology, aws_location):
        stack_id = self.get_stack_id(resource_id, lifecycle_name, driver_files, system_properties, resource_properties, request_properties, associated_topology, aws_location)
        if stack_id is None:
            cloudformation_driver = aws_location.cloudformation_driver

            resource_name = self.__create_tgwattachment_resource_name(system_properties, resource_properties, self.get_resource_name(system_properties))
            stack_name = self.get_stack_name(resource_id, resource_name)

            cf_template = self.render_template(system_properties, resource_properties, request_properties, 'cloudformation_tgw_createtgwattachment_template.yaml')
            cf_parameters = self.get_cf_parameters(resource_properties, system_properties, aws_location, cf_template)
            logger.debug(f'stack_name={stack_name} cf_template={cf_template} cf_parameters={cf_parameters}')

            try:
                stack_id = cloudformation_driver.create_stack(stack_name, cf_template, cf_parameters)
                logger.debug(f'Created Stack Id: {stack_id}')
            except Exception as e:
                raise ResourceDriverError(str(e)) from e

            if stack_id is None:
                raise ResourceDriverError('Failed to create cloudformation stack on AWS')

        request_id = build_request_id(CREATE_REQUEST_PREFIX, stack_id)
        associated_topology = AWSAssociatedTopology()
        associated_topology.add_stack_id(resource_name, stack_id)
        return LifecycleExecuteResponse(request_id, associated_topology=associated_topology)

    def removetgwattachment(self, resource_id, lifecycle_name, driver_files, system_properties, resource_properties, request_properties, associated_topology, aws_location):
        self.__create_tgwattachment_resource_name(system_properties, resource_properties, self.get_resource_name(system_properties))
        return super().remove(resource_id, lifecycle_name, driver_files, system_properties, resource_properties, request_properties, associated_topology, aws_location)

    def __create_tgwattachment_resource_name(self, system_properties, resource_properties, resource_name):
        system_properties['resourceName'] = self.sanitize_name(resource_name, '__', resource_properties.get('vpc_id', ''), '__tgwattachment')
        return system_properties['resourceName']

    
    def __create_tgwpeerroute_resource_name(self, system_properties, resource_properties, resource_name):
        system_properties['resourceName'] = self.sanitize_name(resource_properties.get('subnet_name', ''), '__', resource_properties.get('vpc_id', ''), '__tgwpeerroute')
        return system_properties['resourceName']

    def addtgwpeerroute(self, resource_id, lifecycle_name, driver_files, system_properties, resource_properties, request_properties, associated_topology, aws_location):
            
            logger.info(f'invoking addtgwpeerroute peer routing for request :: {resource_id} and resource_prop as :: {resource_properties}')
            stack_id = self.get_stack_id(resource_id, lifecycle_name, driver_files, system_properties, resource_properties, request_properties, associated_topology, aws_location)
            if stack_id is None:
                cloudformation_driver = aws_location.cloudformation_driver
                resource_name = self.__create_tgwpeerroute_resource_name(system_properties, resource_properties, self.get_resource_name(system_properties))
                stack_name = self.get_stack_name(resource_id, resource_name)

                cf_template = self.render_template(system_properties, resource_properties, request_properties, 'cloudformation_tgw_peerroute.yaml')
                cf_parameters = self.get_cf_parameters(resource_properties, system_properties, aws_location, cf_template)

                #add this route in tgw if subnet is global
                access_domain_state = resource_properties.get('access_domain_state', None)
                if access_domain_state is None:
                    raise ResourceDriverError(f'access_domain_state is null for resource_id {resource_id}')
                
                tgw_peer_attachment_id = resource_properties.get('tgw_peer_attachment_id', None)
                if tgw_peer_attachment_id is None:
                    raise ResourceDriverError(f'TransitGatewayAttachmentId is null for resource_id {resource_id}')

                if access_domain_state.lower() == 'global':
                    try:
                        stack_id = cloudformation_driver.create_stack(stack_name, cf_template, cf_parameters)
                    except Exception as e:
                        logger.error("Error occured ", e)
                        raise ResourceDriverError(str(e)) from e

            request_id = build_request_id(CREATE_REQUEST_PREFIX, stack_id)

            associated_topology = AWSAssociatedTopology()
            associated_topology.add_stack_id(resource_name, stack_id)
            logger.info(f'completed addtgwpeerroute peer routing for request :: {resource_id} and resource_prop as :: {resource_properties}')
            return LifecycleExecuteResponse(request_id, associated_topology=associated_topology)

    def removetgwpeerroute(self, resource_id, lifecycle_name, driver_files, system_properties, resource_properties, request_properties, associated_topology, aws_location):
        logger.info(f'invoking remove tgw peerroute routing for request :: {resource_id} and resource_prop as :: {resource_properties}')
        self.__create_tgwpeerroute_resource_name(system_properties, resource_properties, self.get_resource_name(system_properties))
        return super().remove(resource_id, lifecycle_name, driver_files, system_properties, resource_properties, request_properties, associated_topology, aws_location)


    

    def __create_subnetpeerroute_resource_name(self, system_properties, resource_properties, resource_name):
        system_properties['resourceName'] = self.sanitize_name(resource_properties.get('vpc_id', ''), '__',resource_properties.get('subnet_name', ''), '__subnetpeerroute')
        return system_properties['resourceName']

    def addsubnetpeerroute(self, resource_id, lifecycle_name, driver_files, system_properties, resource_properties, request_properties, associated_topology, aws_location):
        
        logger.info(f'invoking subnet peer routing for resourece :: {resource_id} and resource_prop as :: {resource_properties}')
        stack_id = self.get_stack_id(resource_id, lifecycle_name, driver_files, system_properties, resource_properties, request_properties, associated_topology, aws_location)
        if stack_id is None:
            cloudformation_driver = aws_location.cloudformation_driver
            resource_name = self.__create_subnetpeerroute_resource_name(system_properties, resource_properties, self.get_resource_name(system_properties))
            stack_name = self.get_stack_name(resource_id, resource_name)

            cf_template = self.render_template(system_properties, resource_properties, request_properties, 'cloudformation_subnet_peerroute.yaml')
            cf_parameters = self.get_cf_parameters(resource_properties, system_properties, aws_location, cf_template)

            #add this route in tgw if subnet is global
            access_domain_state = resource_properties.get('access_domain_state', None)
            if access_domain_state is None:
                raise ResourceDriverError(f'access_domain_state is null for resource_id {resource_id}')

            if access_domain_state == 'global':
                #check if entry already there for same destination vpc, then ignore
                destination_vpc_cidr = resource_properties.get('destination_vpc_cidr', None)
                if destination_vpc_cidr is None:
                    raise ResourceDriverError('Destination vpc cidr is mandatory for inter-connectivity subnet route table')

                vpc_route_table_id = resource_properties.get('route_table_id', None)
                if vpc_route_table_id is None:
                    raise ResourceDriverError('Vpc route table id is mandatory for inter-connectivity')

                response = aws_location.ec2.describe_route_tables(
                    Filters=[
                    {
                        'Name': 'route.destination-cidr-block',
                        'Values': [
                            destination_vpc_cidr,
                        ]
                    },
                    ]
                    ,RouteTableIds=[
                        vpc_route_table_id,
                    ],
                )
                if response is not None and len(response['RouteTables']) > 0:
                    #already we have an entry for same cidr, ignore and proceed further
                    logger.warn("Duplicate global subnet found for route table. Ignore and proceed")
                    request_id = build_request_id(CREATE_REQUEST_PREFIX, 'SKIP')
                else:
                    #no destination cidr found go with updating route table
                    try:
                        stack_id = cloudformation_driver.create_stack(stack_name, cf_template, cf_parameters)
                        if stack_id is None:
                            raise ResourceDriverError('Failed to create cloudformation stack on AWS')
                        request_id = build_request_id(CREATE_REQUEST_PREFIX, stack_id)

                        associated_topology = AWSAssociatedTopology()
                        associated_topology.add_stack_id(resource_name, stack_id)
                        logger.info(f'completed subnet peer routing for resourece :: {resource_id} and resource_prop as :: {resource_properties}')
                    except Exception as ex:
                        if ex.__class__.__name__ == "AlreadyExistsException":
                            logger.warn(f'Duplicate global subnet found for route table with resource :: {resource_properties}. Ignore and proceed')
                            request_id = build_request_id(CREATE_REQUEST_PREFIX, 'SKIP')
                        else:
                            logger.error("Error occured creating stack for route entry in global subnet", ex)
                            raise ResourceDriverError(str(ex)) from ex

            else:
            # nothing to do
                logger.info(f'No stack_id in associated topology for resource with id: {resource_id} name: {resource_name} lifecycle_name: {lifecycle_name}')
                request_id = build_request_id(CREATE_REQUEST_PREFIX, 'SKIP')
        
        return LifecycleExecuteResponse(request_id, associated_topology=associated_topology)

    def removesubnetpeerroute(self, resource_id, lifecycle_name, driver_files, system_properties, resource_properties, request_properties, associated_topology, aws_location):
        logger.info(f'invoking removesubnetpeerroute routing for request :: {resource_id} and resource_prop as :: {resource_properties}')
        self.__create_subnetpeerroute_resource_name(system_properties, resource_properties, self.get_resource_name(system_properties))
        return self.removeIgnoringResource(resource_id, lifecycle_name, driver_files, system_properties, resource_properties, request_properties, associated_topology, aws_location)

    def removeIgnoringResource(self, resource_id, lifecycle_name, driver_files, system_properties, resource_properties, request_properties, associated_topology, aws_location):
        resource_id = system_properties.get('resourceId', None)
        if resource_id is None:
            raise InvalidRequestError(f'system_properties.resource_id must be provided')

        resource_name = system_properties.get('resourceName', None)
        if resource_name is None:
            raise InvalidRequestError(f'system_properties.resourceName must be provided')

        associated_topology.__class__ = AWSAssociatedTopology
        
        stack_id = associated_topology.get_stack_id(resource_name)

        if stack_id is not None:

            try:
                delete_response = aws_location.cloudformation_driver.delete_stack(stack_id)
                logger.info(f'delete response is {delete_response} , ignore and proceed')
                request_id = build_request_id(DELETE_REQUEST_PREFIX, stack_id)
            except Exception as e:
                raise ResourceDriverError(str(e)) from e
        else:
            # nothing to do
            logger.info(f'No stack_id in associated topology for resource with id: {resource_id} name: {resource_name} lifecycle_name: {lifecycle_name}')
            request_id = build_request_id(CREATE_REQUEST_PREFIX, 'SKIP')

        return LifecycleExecuteResponse(request_id)
            
    def __as_boolean(self, val):
        if val is None:
            logger.info(f'__as_boolean1 val = {val}')
            return False
        elif isinstance(val, bool):
            logger.info(f'__as_boolean2 val = {val}')
            return val
        elif isinstance(val, str):
            val_lower = val.lower()
            if val_lower == 'true':
                logger.info(f'__as_boolean3 val = {val} val_lower = {val_lower}')
                return True
            else:
                logger.info(f'__as_boolean4 val = {val} val_lower = {val_lower}')
                return False
        else:
            return False