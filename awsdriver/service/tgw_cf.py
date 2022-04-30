import ast
from cmath import log
import json
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

        availability_zone = resource_properties.get('availability_zone', None)
        subnet_id = resource_properties.get('subnet_id', None)
        if availability_zone is None:
            raise ResourceDriverError(f'Missing availability_zone property for operation createtgwroutetableassociation on resource {resource_id}')
        else:
            logger.info(f'availability_zone value came as :::::::: {availability_zone}')
        azList = []
        azListVal = resource_properties.get('azList', None)
        if azListVal is None:
            raise ResourceDriverError(f'Missing azList property for operation createtgwroutetableassociation on resource {resource_id}')
        json_obj = json.loads(azListVal)
        for value in json_obj:
            azList.append(value["az"])
        if azList is None or len(azList) < 1:
            raise ResourceDriverError(f'Unable to retrieve availablity zone list  for operation createtgwroutetableassociation on resource {resource_id}')
        else:
            logger.info(f'azlist value came as :::::::: {azList}')
        subnet_index = None
        for az_index,az in enumerate(azList):
            logger.info(f'cuurent az value is  :::: {az}')
            if az == availability_zone:
                subnet_index = az_index
                logger.info(f'Subnet index for subnet {resource_id} is {subnet_index}')
                break
        if subnet_index is None:
             raise ResourceDriverError(f'Unable to determine the subnet execution order, verify the availablity zone of subnet and list of zones provided')

        template_type  = 'cloudformation_tgw_createrta.yaml'

        #for subnet index != 0 , wait for other subnet to complete attachment in order
        if subnet_index > 0:
            template_type = 'cloudformation_tgw_update_attach.yaml'
            wait_for_prior_subnet = True
            tgw_id =  resource_properties['transit_gateway_id']
            vpc_id =  resource_properties['vpc_id']
            logger.info(f'value coming as :::::::::::{tgw_id}  and ::::::::::: {vpc_id}    ')
            while(wait_for_prior_subnet):
                tgw_vpc_attach_resp = aws_location.ec2.describe_transit_gateway_vpc_attachments(
                                    Filters=[
                                        {
                                            'Name': 'transit-gateway-id',
                                            'Values': [
                                                tgw_id,
                                            ]
                                        },
                                        {
                                            'Name': 'vpc-id',
                                            'Values': [
                                                vpc_id,
                                            ]
                                        },
                                    ],
                                )

                
                if tgw_vpc_attach_resp is not None:
                    logger.info(f'New tgw_vpc_attach_resp came as {tgw_vpc_attach_resp}')
                    tgw_vpc_attach_list = tgw_vpc_attach_resp['TransitGatewayVpcAttachments']
                    if len(tgw_vpc_attach_list) == 0:
                        sleepseconds(30)
                        continue
                    tgw_vpc_attach = tgw_vpc_attach_list[0]
                    if str(tgw_vpc_attach["State"]) != 'available' :
                        sleepseconds(30)
                        continue
                    existing_subnets = tgw_vpc_attach["SubnetIds"]
                    tgw_vpc_attach_id = tgw_vpc_attach["TransitGatewayAttachmentId"]
                    if len(existing_subnets) != subnet_index:
                        wait_for_prior_subnet = True
                        logger.info(f'Subnet tgw association has existing subents {existing_subnets} , need to wait for all to complete for subnet index {subnet_index}')
                        sleepseconds(30)
                    else:
                        wait_for_prior_subnet = False
                        resource_properties['updated_subnet_id'] = subnet_id
                        resource_properties['subnet_ids'] = existing_subnets
                        logger.info(f'All subnet association completed prior to subnet index {subnet_index}, proceeding with this subnet association')
                        sleepseconds(60)
                        logger.info(f'Creating subnet association through api  for {subnet_id}')
                        aws_location.ec2.modify_transit_gateway_vpc_attachment(
                            TransitGatewayAttachmentId=tgw_vpc_attach_id,
                            AddSubnetIds=[
                                subnet_id,
                            ],
                        )
                        request_id = build_request_id(CREATE_REQUEST_PREFIX, 'SKIP')

                        ##return only when tgw attach modificaiton is complete
                        check_status = True
                        while(check_status):
                            tgw_vpc_attach_resp_repeat = aws_location.ec2.describe_transit_gateway_vpc_attachments(
                                                Filters=[
                                                    {
                                                        'Name': 'transit-gateway-id',
                                                        'Values': [
                                                            tgw_id,
                                                        ]
                                                    },
                                                    {
                                                        'Name': 'vpc-id',
                                                        'Values': [
                                                            vpc_id,
                                                        ]
                                                    },
                                                ],
                                            )

                            if tgw_vpc_attach_resp_repeat is not None:
                                tgw_vpc_attach_list_repeat = tgw_vpc_attach_resp_repeat['TransitGatewayVpcAttachments']
                                if len(tgw_vpc_attach_list_repeat) == 0:
                                    sleepseconds(30)
                                    continue
                                tgw_vpc_attach_repeat = tgw_vpc_attach_list_repeat[0]
                                if str(tgw_vpc_attach_repeat["State"]) != 'available' :
                                    sleepseconds(30)
                                    continue
                                else:
                                    check_status = False
                                    break
                        return LifecycleExecuteResponse(request_id, associated_topology=associated_topology)




        stack_id = self.get_stack_id(resource_id, lifecycle_name, driver_files, system_properties, resource_properties, request_properties, associated_topology, aws_location)
        if stack_id is None:
            cloudformation_driver = aws_location.cloudformation_driver

            
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
            logger.info(f'finally resourece properties looks like ::::::{resource_properties}')
            resource_name = self.__create_tgwroutetableassociation_resource_name(system_properties, resource_properties, self.get_resource_name(system_properties))
            stack_name = self.get_stack_name(resource_id, resource_name)

            if is_primary:
                # create only for primary (private) subnets
                logger.info(f'createtgwroutetableassociation creating stack')

                cf_template = self.render_template(system_properties, resource_properties, request_properties, template_type)
                cf_parameters = self.get_cf_parameters(resource_properties, system_properties, aws_location, cf_template)
                logger.debug(f'stack_name={stack_name} cf_template={cf_template} cf_parameters={cf_parameters}')

                stack_id = cloudformation_driver.create_stack(stack_name, cf_template, cf_parameters)
                logger.debug(f'Created Stack Id: {stack_id}')
                if stack_id is None: 
                    raise ResourceDriverError('Failed to create cloudformation stack on AWS')

                 # use the name request_id for any operation of this type against a vpc
                request_id = build_request_id(CREATE_REQUEST_PREFIX, stack_name)

                associated_topology.add_stack_id(resource_name, stack_id)
                logger.info(f'completed creation of tgw route table association for resourece :: {resource_id} and resource_prop as :: {resource_properties}')
            else:
                # TODO hacky wait ensure non-primary (private) subnets wait for primary subnet to create the stack
                # This is to address an issue in CP4NA/Daytona which results in the primary vpc assembly SubnetToTgwRoute operations triggering
                # before the subnets have become active (SubnetToTgwRoute operations should trgger on subnets becoming active, but instead
                # they are triggering whenn one of the TGWVPCAttachment operations completes)
                # A better way to handle this might be to allow all these calls to proceed to creating a stack, and in the get_lifecycle_execution
                # method translate the specific failure relating to a duplicate in to a successful operation result.
                sleepseconds(8)
                request_id = build_request_id(CREATE_REQUEST_PREFIX, 'SKIP')

        return LifecycleExecuteResponse(request_id, associated_topology=associated_topology)

    def removetgwroutetableassociation(self, resource_id, lifecycle_name, driver_files, system_properties, resource_properties, request_properties, associated_topology, aws_location):
        self.__create_tgwroutetableassociation_resource_name(system_properties, resource_properties, self.get_resource_name(system_properties))
        return super().remove(resource_id, lifecycle_name, driver_files, system_properties, resource_properties, request_properties, associated_topology, aws_location)

    def __create_tgwroutetableassociation_resource_name(self, system_properties, resource_properties, resource_name):
        vpc_id = resource_properties.get('vpc_id', None)
        if vpc_id is None:
            raise ResourceDriverError(f'vpc_id cannot be null for operation createtgwroutetableassociation for resource {resource_name}')
        system_properties['resourceName'] = self.sanitize_name(vpc_id, '__', resource_properties.get('subnet_id', ''),'_tgwrta')
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
        system_properties['resourceName'] = self.sanitize_name(resource_properties.get('subnet_cidr', ''), '__', resource_properties.get('vpc_id', ''), '__tgwpeerroute')
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