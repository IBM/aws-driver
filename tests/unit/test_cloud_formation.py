import unittest
from pathlib import Path
import uuid
import os
from ignition.service.templating import ResourceTemplateContextService, Jinja2TemplatingService
from ignition.utils.propvaluemap import PropValueMap
from awsdriver.service.resourcedriver import ResourceDriverHandler, TGWCloudFormation, PropertiesMerger
from awsdriver.location.deployment_location import AWSDeploymentLocation


class TestCloudFormation(unittest.TestCase):
    def setUp(self):
        self.props_merger = PropertiesMerger()
        self.templating_service = Jinja2TemplatingService()
        self.resource_context_service = ResourceTemplateContextService()

    def __get_cf_template(self, cf_template_name):
        template_path = os.path.join('awsdriver', 'config', cf_template_name)
        print(f'CF template file path for {cf_template_name} is {template_path}')

        with open(template_path, 'r') as f:
            template = f.read()
        return template

    def __render_template(self, system_properties, resource_properties, request_properties, cf_template_name):
        template = self.__get_cf_template(cf_template_name)
        return self.templating_service.render(template,
            self.resource_context_service.build(system_properties, resource_properties, request_properties, {}))

    def __get_cf_parameters(self, resource_properties, system_properties, aws_location, cf_template):
        input_props = self.props_merger.merge(resource_properties, system_properties)
        return aws_location.get_cf_input_util().filter_used_properties(cf_template, input_props)

    def test_cloud_formation_1(self):
        aws_deployment_location = AWSDeploymentLocation.from_dict({
            'name': 'aws1',
            'properties': {
                'aws_access_key_id': 'AKIAYAP65K3CEVGLRQEC',
                'aws_secret_access_key': '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'
            }
        })
        tgw_cloud_formation = TGWCloudFormation()
        stack_name = "sgstack2"
        template = Path('awsdriver/config/cloudformation_tgw_createrta.yaml').read_text()
        parameters = {
            'EnvironmentName': 'sg1'
        }

        # cloud_formation.create_or_update_stack(stack_name, template, parameters)

        resource_id = str(uuid.uuid4())
        lifecycle_name = 'createtgwroutetableassociation'
        driver_files = None
        system_properties = PropValueMap({
            'resourceName': "sgresource1"
        })
        resource_properties = PropValueMap({
            'public_private': 'private',
            'subnet_id': 'subnet-0d9298165ef173edc',
            'vpc_id': 'vpc-0968b84e59c141190',
            'transit_id': 'tgw-0619734b83b4d508a',
            'transit_route_table_id': 'tgw-rtb-01a54f7c0c4aedd5b',
            'global_route': False
        })
        request_properties = PropValueMap({

        })
        # associated_topology = AWSAssociatedTopology()


        cloudformation_driver = aws_deployment_location.cloudformation_driver

        cf_template = self.__render_template(system_properties, resource_properties, request_properties, 'cloudformation_tgw_createrta.yaml')
        cf_parameters = self.__get_cf_parameters(resource_properties, system_properties, aws_deployment_location, cf_template)
        # logger.debug(f'stack_name={stack_name} cf_template={cf_template} cf_parameters={cf_parameters}')

        try:
            stack_id = cloudformation_driver.create_stack(stack_name, cf_template, cf_parameters)
            print(f'1 Created Stack Id: {stack_id}')
        except Exception as e:
            if 'EntityAlreadyExistsException' == e.__class__.__name__:
                print(f'EXISTS')
            print(f'1 exc: {e}')

        try:
            stack_id = cloudformation_driver.create_stack(stack_name, cf_template, cf_parameters)
            print(f'2 Created Stack Id: {stack_id}')
        except Exception as e:
            if 'EntityAlreadyExistsException' == e.__class__.__name__:
                print(f'EXISTS')
            print(f'2 exc: {e}')

        # response1 = tgw_cloud_formation.createtgwroutetableassociation(resource_id, lifecycle_name, driver_files, system_properties, resource_properties, request_properties, associated_topology, aws_deployment_location)
        # print(f"response1={response1.to_dict()}")

        # response2 = tgw_cloud_formation.createtgwroutetableassociation(resource_id, lifecycle_name, driver_files, system_properties, resource_properties, request_properties, associated_topology, aws_deployment_location)
        # print(f"response1={response2.to_dict()}")

    def test_cloud_formation_2(self):
        aws_deployment_location = AWSDeploymentLocation.from_dict({
            'name': 'aws1',
            'properties': {
                AWSDeploymentLocation.AWS_ACCESS_KEY_ID: 'AKIAYAP65K3CEVGLRQEC',
                AWSDeploymentLocation.AWS_SECRET_ACCESS_KEY: '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'
            }
        })
        cloudformation_driver = aws_deployment_location.cloudformation_driver

        stack_name = 'vpc027feb89f989e3318-tgwrta-1d0ced5c-46de-4839-9d01-9bfc8f2ac82b'
        stack = cloudformation_driver.get_stack(stack_name)
        print(f'Got Stack {stack}')
