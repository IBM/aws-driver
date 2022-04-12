import unittest
import uuid
import time
from awsdriver.location.deployment_location import AWSDeploymentLocation
from ignition.model.lifecycle import STATUS_COMPLETE, STATUS_FAILED
from ignition.service.templating import ResourceTemplateContextService, Jinja2TemplatingService
from ignition.utils.propvaluemap import PropValueMap
from awsdriver.service.resourcedriver import ResourceDriverHandler, PropertiesMerger
from awsdriver.service.topology import AWSAssociatedTopology


class TestResourceDriver(unittest.TestCase):
    def setUp(self):
        self.props_merger = PropertiesMerger()
        self.templating_service = Jinja2TemplatingService()
        self.resource_context_service = ResourceTemplateContextService()
        self.resource_driver = ResourceDriverHandler()

    def wait_lifecycle_execution(self, request_id, deployment_location):
        lifecycle_execution = self.resource_driver.get_lifecycle_execution(request_id, deployment_location)
        while not lifecycle_execution.status == STATUS_COMPLETE and not lifecycle_execution.status == STATUS_FAILED:
            print(f'lifecycle_execution={lifecycle_execution}, waiting')
            time.sleep(5)
            lifecycle_execution = self.resource_driver.get_lifecycle_execution(request_id, deployment_location)
        return lifecycle_execution

    def test_driver_1(self):
        deployment_location = {
            'name': 'aws1',
            'properties': {
                AWSDeploymentLocation.AWS_ACCESS_KEY_ID: 'AKIAYAP65K3CEVGLRQEC',
                AWSDeploymentLocation.AWS_SECRET_ACCESS_KEY: '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'
            }
        }

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
            'vpc_name': 'vpc1'
        })
        request_properties = PropValueMap({
        })
        associated_topology = AWSAssociatedTopology()
        create_vpc_response = self.resource_driver.execute_lifecycle(lifecycle_name, driver_files, system_properties, resource_properties, request_properties, associated_topology, deployment_location)
        print(f"create_vpc_response={create_vpc_response.to_dict()}")
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
        print(f"create_tgw_response={create_tgw_response.to_dict()}")
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
            # 'primary': True,
            'public_private': 'private',
            'subnet_id': 'subnet-090b86d04b976f828',
            'vpc_id': 'vpc-0968b84e59c141190',
            'transit_id': 'tgw-0619734b83b4d508a',
            'transit_route_table_id': 'tgw-rtb-01a54f7c0c4aedd5b',
            'global_route': False
        })
        request_properties = PropValueMap({
        })
        associated_topology = AWSAssociatedTopology()
        create_tgw_rta_response1 = self.resource_driver.execute_lifecycle(lifecycle_name, driver_files, system_properties, resource_properties, request_properties, associated_topology, deployment_location)
        print(f"create_tgw_rta_response1={create_tgw_rta_response1.to_dict()}")

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
            'transit_id': 'tgw-0619734b83b4d508a',
            'transit_route_table_id': 'tgw-rtb-01a54f7c0c4aedd5b',
            'global_route': False
        })
        request_properties = PropValueMap({
        })
        associated_topology = AWSAssociatedTopology()
        create_tgw_rta_response2 = self.resource_driver.execute_lifecycle(lifecycle_name, driver_files, system_properties, resource_properties, request_properties, associated_topology, deployment_location)
        print(f"create_tgw_rta_response2={create_tgw_rta_response2.to_dict()}")

        lifecycle_execution = self.wait_lifecycle_execution(create_tgw_rta_response2.request_id, deployment_location)
        print(f'TGW RTA2 create done {lifecycle_execution}')

        lifecycle_execution = self.wait_lifecycle_execution(create_tgw_rta_response1.request_id, deployment_location)
        print(f'TGW RTA1 create done {lifecycle_execution}')