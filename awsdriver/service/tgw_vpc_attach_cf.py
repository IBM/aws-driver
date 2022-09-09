import logging
from awsdriver.service.cloudformation import CloudFormation
from awsdriver.service.common import CREATE_REQUEST_PREFIX, build_request_id, FILTER_NAME_TAG_CREATOR, FILTER_VALUE_TAG_CREATOR, FILTER_NAME_TAG_PRIMARY
from awsdriver.service.topology import AWSAssociatedTopology
from ignition.model.lifecycle import LifecycleExecuteResponse
from ignition.service.resourcedriver import ResourceDriverError


logger = logging.getLogger(__name__)

class TGWVPCAttachCloudFormation(CloudFormation):
    
    def create(self, resource_id, lifecycle_name, driver_files, system_properties, resource_properties, request_properties, associated_topology, aws_location):
        logger.info(f'invoking TGW VPC attachment {resource_id} with resoure property {resource_properties} ')
        associated_topology = AWSAssociatedTopology()
        subnet_id_list = []
        cloudformation_driver = aws_location.cloudformation_driver
        vpc_id = resource_properties.get('vpc_id', None)
        isPrimary = resource_properties.get('primary', None)
        subnets_res =  aws_location.ec2.describe_subnets(
               Filters=[
                   {
                       'Name': FILTER_NAME_TAG_CREATOR,
                       'Values': [
                           FILTER_VALUE_TAG_CREATOR,
                       ]
                   },
                   {
                       'Name': 'vpc-id',
                           'Values': [
                               vpc_id,
                       ]
                   },
                   {
                       'Name': FILTER_NAME_TAG_PRIMARY,
                           'Values': [
                               isPrimary.lower(),
                       ]
                   }
               ]
           )
        logger.info(f'Primary subnet list are {subnets_res}')

        # reparing subnet ids list from subnets
        for subnet in subnets_res['Subnets']:
            subnet_id_list.append(subnet['SubnetId'])

        logger.debug(f'Primary Subnets Ids for vpc {vpc_id} are {subnet_id_list}')
        resource_properties = super().add_resource_property(resource_properties, 'subnet_id_list', 'list', subnet_id_list)
        
        resource_name = self.__create_tgwvpcattachment_resource_name(system_properties, resource_properties,  self.get_resource_name(system_properties))
        stack_name = self.get_stack_name(resource_id, resource_name)
        template_type  = 'cloudformation_tgw_createrta.yaml'
        
        logger.info(f'creating stack for TGW VPC Attachment')

        cf_template = self.render_template(system_properties, resource_properties, request_properties, template_type)
        cf_parameters = self.get_cf_parameters(resource_properties, system_properties, aws_location, cf_template)
        logger.debug(f'stack_name={stack_name} cf_template={cf_template} cf_parameters={cf_parameters}')

        stack_id = cloudformation_driver.create_stack(stack_name, cf_template, cf_parameters)
        logger.debug(f'Created Stack Id: {stack_id}')
        if stack_id is None: 
            raise ResourceDriverError('Failed to create cloudformation stack on AWS')

        associated_topology.add_stack_id(resource_name, stack_id)
        request_id = build_request_id(CREATE_REQUEST_PREFIX, stack_name)
        logger.info(f'Creation of TGW VPC association for resourece :: {resource_id} and resource_prop as :: {resource_properties}')
        return LifecycleExecuteResponse(request_id, associated_topology=associated_topology)
    
    def remove(self, resource_id, lifecycle_name, driver_files, system_properties, resource_properties, request_properties, associated_topology, aws_location):
        self.__create_tgwvpcattachment_resource_name(system_properties, resource_properties,  self.get_resource_name(system_properties))
        return super().remove(resource_id, lifecycle_name, driver_files, system_properties, resource_properties, request_properties, associated_topology, aws_location)
    
    def __create_tgwvpcattachment_resource_name(self, system_properties, resource_properties, resource_name):
        system_properties['resourceName'] = self.sanitize_name(resource_name, '__', resource_properties.get('vpc_id', ''))
        return system_properties['resourceName']
