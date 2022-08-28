import unittest
from unittest import mock
from unittest.mock import MagicMock, PropertyMock, create_autospec, patch
import uuid
import time
from awsdriver.location.deployment_location import AWSDeploymentLocation, CloudFormationDriver
from ignition.model.lifecycle import STATUS_COMPLETE, STATUS_FAILED
from ignition.service.templating import ResourceTemplateContextService, Jinja2TemplatingService
from ignition.utils.propvaluemap import PropValueMap
from awsdriver.service.resourcedriver import AWS_STACK_STATUS_CREATE_COMPLETE, ResourceDriverHandler, PropertiesMerger, AdditionalResourceDriverProperties
from awsdriver.service.tgw_cf import TGWCloudFormation
from awsdriver.service.topology import AWSAssociatedTopology
from awsdriver.service.vpc_cf import VPCCloudFormation


class TestResourceDriver(unittest.TestCase):
    def setUp(self):
       # self.resource_driver_config = AdditionalResourceDriverProperties()
        self.props_merger = PropertiesMerger()
        self.templating_service = Jinja2TemplatingService()
        self.resource_context_service = ResourceTemplateContextService()
        self.resource_driver = ResourceDriverHandler(resource_driver_properties=None)
    
    @patch.object(CloudFormationDriver, 'get_stack')
    def wait_lifecycle_execution(self, request_id, deployment_location, mock_get_stack):
        mock_get_stack.return_value = {'StackName': 'dummy', 'StackId' : 'vpc027feb89f989e3318-1d0ced5c-46de-4839-9d01-9bfc8f2ac82b', 'StackStatus': AWS_STACK_STATUS_CREATE_COMPLETE}
        lifecycle_execution = self.resource_driver.get_lifecycle_execution(request_id, deployment_location)
        while not lifecycle_execution.status == STATUS_COMPLETE and not lifecycle_execution.status == STATUS_FAILED:
            print(f'lifecycle_execution={lifecycle_execution}, waiting')
            time.sleep(5)
            lifecycle_execution = self.resource_driver.get_lifecycle_execution(request_id, deployment_location)
        return lifecycle_execution

    @patch.object(CloudFormationDriver, 'create_stack')
    @patch.object(VPCCloudFormation, '_VPCCloudFormation__wait_for_transitgateway_route_availability', new_callable=PropertyMock)
    @patch.object(TGWCloudFormation, 'get_aws_vpc_attach')
    def test_driver_1(self, mock_tgwvpc_associations, mock_tgw_availability, create_stack_mock):
        stack_name = 'vpc027feb89f989e3318-tgwrta-1d0ced5c-46de-4839-9d01-9bfc8f2ac82b'
        deployment_location = {
            'name': 'dummy',
            'properties': {
                AWSDeploymentLocation.AWS_ACCESS_KEY_ID: 'dummy',
                AWSDeploymentLocation.AWS_SECRET_ACCESS_KEY: 'dummy'
            }
        }
        create_stack_mock.return_value = stack_name
        mock_tgwvpc_associations.return_value = self.__get_tgw_vpc_attachments()
        print(f'tgw aasociation mock data: {mock_tgwvpc_associations.retun_value}')
        vpc_resource_id = str(uuid.uuid4())

        lifecycle_name = 'create'
        driver_files = None
        system_properties = PropValueMap({
            'resourceId': vpc_resource_id,
            'resourceName': 'vpc1',
            'resourceType': 'resource::AWSVPC::1.0'
        })
        resource_properties = PropValueMap({
            'cidr_block': '10.4.0.0/16',
            'vpc_name': 'vpc1',
            'transit_gateway_name': 'tgw1'
        })
        request_properties = PropValueMap({
        })
        associated_topology = AWSAssociatedTopology()
        
        aws_location = AWSDeploymentLocation.from_dict(deployment_location)
        cloudformationDriver = aws_location.cloudformation_driver
        cloudformationDriver.get_stack =  mock.Mock(return_value=stack_name)
        cloudformationDriver.get_stack = mock.Mock(return_value={'StackId', stack_name})
        stack = cloudformationDriver.get_stack(stack_name)
        
      #  with mock.patch('AWSDeploymentLocation.ec2.describe_transit_gateway_route_tables', return_value=None):
      #  aws_location = AWSDeploymentLocation.from_dict(deployment_location)
      #  ec2Client = aws_location.ec2
      #  ec2Client.describe_transit_gateway_route_tables = mock.Mock(return_value=None)
        create_vpc_response = self.resource_driver.execute_lifecycle(lifecycle_name, driver_files, system_properties, resource_properties, request_properties, associated_topology, deployment_location)
        print(f"create_vpc_response={create_vpc_response}")
        lifecycle_execution = self.wait_lifecycle_execution(create_vpc_response.request_id, deployment_location)
        print(f'VPC create done {lifecycle_execution}')
        
        tgw_resource_id = str(uuid.uuid4())

        lifecycle_name = 'create'
        driver_files = None
        system_properties = PropValueMap({
            'resourceId': tgw_resource_id,
            'resourceName': "tgw1",
            'resourceType': 'resource::AWSTransitGateway::1.0'
        })
        resource_properties = PropValueMap({
            'transit_gateway_name': 'sg1',
            'aws_side_asn': '64512',
            'description': '',
            'association_default_route_table_id': 'disable',
            'auto_accept_shared_attachments': 'disable',
            'default_route_table_association': 'disable',
            'default_route_table_propagation': 'disable',
            'dns_support': 'disable',
            'multicast_support': 'disable',
            'propagation_default_route_tableId': 'disable',
            'vpn_ecmp_support': 'disable'
        })
        request_properties = PropValueMap({
        })
        associated_topology = AWSAssociatedTopology()
        create_tgw_response = self.resource_driver.execute_lifecycle(lifecycle_name, driver_files, system_properties, resource_properties, request_properties, associated_topology, deployment_location)
        print(f"create_tgw_response={create_tgw_response}")
        lifecycle_execution = self.wait_lifecycle_execution(create_tgw_response.request_id, deployment_location)
        print(f'TGW create done {lifecycle_execution}')

        lifecycle_name = 'createtgwroutetableassociation'
        driver_files = None
        system_properties = PropValueMap({
            'resourceId': tgw_resource_id,
            'resourceName': "tgw1",
            'resourceType': 'resource::AWSTransitGateway::1.0'
        })
        resource_properties = PropValueMap({
            'primary': True,
            'public_private': 'private',
            'subnet_id': 'subnet-090b86d04b976f828',
            'vpc_id': 'vpc-0968b84e59c141190',
            'transit_gateway_id': 'tgw-0619734b83b4d508a',
            'transit_route_table_id': 'tgw-rtb-01a54f7c0c4aedd5b',
            'availability_zone': 'us-east-1a',
            'azList' : '[{\"az\":\"us-east-1a\"}]',
            'global_route': False
        })
        request_properties = PropValueMap({
        })
        associated_topology = AWSAssociatedTopology()
        create_tgw_rta_response1 = self.resource_driver.execute_lifecycle(lifecycle_name, driver_files, system_properties, resource_properties, request_properties, associated_topology, deployment_location)
        print(f"create_tgw_rta_response1={create_tgw_rta_response1}")

        lifecycle_name = 'createtgwroutetableassociation'
        driver_files = None
        system_properties = PropValueMap({
            'resourceId': tgw_resource_id,
            'resourceName': "tgw1",
            'resourceType': 'resource::AWSTransitGateway::1.0'
        })
        resource_properties = PropValueMap({
            # 'primary': False,
            'public_private': 'private',
            'subnet_id': 'subnet-0d9298165ef173edc',
            'vpc_id': 'vpc-0968b84e59c141190',
            'transit_gateway_id': 'tgw-0619734b83b4d508a',
            'transit_route_table_id': 'tgw-rtb-01a54f7c0c4aedd5b',
            'global_route': False,
            'availability_zone': 'us-east-1a',
            'azList' : '[{\"az\":\"us-east-1a\"}]'
        })
        request_properties = PropValueMap({
        })
        associated_topology = AWSAssociatedTopology()
        create_tgw_rta_response2 = self.resource_driver.execute_lifecycle(lifecycle_name, driver_files, system_properties, resource_properties, request_properties, associated_topology, deployment_location)
        print(f"create_tgw_rta_response2={create_tgw_rta_response2}")

        lifecycle_execution = self.wait_lifecycle_execution(create_tgw_rta_response2.request_id, deployment_location)
        print(f'TGW RTA2 create done {lifecycle_execution}')

        lifecycle_execution = self.wait_lifecycle_execution(create_tgw_rta_response1.request_id, deployment_location)
        print(f'TGW RTA1 create done {lifecycle_execution}')
        
    def __get_tgw_vpc_attachments(self):
        return {
            "TransitGatewayVpcAttachments": [
           {
            "TransitGatewayAttachmentId": "tgw-attach-0619734b83b4d508a",
            "TransitGatewayId": "tgw-0619734b83b4d508a",
            "VpcId": "vpc-0968b84e59c141190",
            "State": "available",
            "SubnetIds": [
                "subnet-090b86d04b976f828"
            ]
           },
           {
            "TransitGatewayAttachmentId": "tgw-attach-tgw-0619734b83b4d508a24",
            "TransitGatewayId": "tgw-0619734b83b4d508a",
            "VpcId": "vpc-0968b84e59c141190",
            "State": "available",
            "SubnetIds": [
                "subnet-0d9298165ef173edc"
            ]
           }
          ] 
        }