import logging
from pathlib import Path
import re
import os
import uuid
from awsdriver.service.common import DELETE_REQUEST_PREFIX
from ignition.model.lifecycle import LifecycleExecuteResponse
from ignition.service.templating import ResourceTemplateContextService, Jinja2TemplatingService
from ignition.service.resourcedriver import InfrastructureNotFoundError, ResourceDriverError, InvalidRequestError
from ignition.service.framework import interface
from awsdriver.service.topology import AWSAssociatedTopology
from awsdriver.model.exceptions import *
from .common import *


driver_directory = here = Path(__file__).parent.parent

logger = logging.getLogger(__name__)

class StackNameCreator:

    def create(self, resource_id, resource_name):
        potential_name = '{0}-{1}'.format(resource_name, resource_id)
        needs_starting_letter = not potential_name[0].isalpha()
        potential_name = re.sub('[^A-Za-z0-9-]+', '-', potential_name)
        max_size = 125 if needs_starting_letter else 126
        while len(potential_name)>max_size:
            potential_name = potential_name[1:]
        if needs_starting_letter:
            potential_name = 's{0}'.format(potential_name)
        return potential_name


class CloudFormation():
    def __init__(self):
        self.stack_name_creator = StackNameCreator()
        self.props_merger = PropertiesMerger()
        # Jinja2TemplatingService
        self.templating_service = Jinja2TemplatingService()
        # ResourceTemplateContextService
        self.resource_context_service = ResourceTemplateContextService()

    def sanitize_name(self, *names):
        full_name = ''
        for name in names:
            full_name = full_name + name
        return full_name.replace('-', '')

    def get_stack_name(self, resource_id, resource_name):
        if resource_id is not None and resource_name is not None:
            stack_name = self.stack_name_creator.create(resource_id, resource_name)
        else:
            stack_name = 's' + str(uuid.uuid4())
        return stack_name

    def get_resource_name(self, system_properties):
        resource_name = system_properties.get('resourceName', None)
        if resource_name is None:
            raise InvalidRequestError(f'system_properties.resourceName must be provided')
        return self.sanitize_name(resource_name)

    def get_stack_id(self, resource_id, lifecycle_name, driver_files, system_properties, resource_properties, request_properties, associated_topology, aws_location):
        cloudformation_driver = aws_location.cloudformation_driver
        stack_id = None
        logger.debug(f'resource_id:{resource_id},lifecycle_name:{lifecycle_name},driver_files:{driver_files},system_properties:{system_properties}')

        if 'stack_id' in resource_properties:
            input_stack_id = resource_properties.get('stack_id', None)
            logger.debug(f"stack available {input_stack_id}")
            if input_stack_id != None and len(input_stack_id.strip())!=0 and input_stack_id.strip() != "0":
                try:
                    ##Check for valid stack
                    cloudformation_driver.get_stack(input_stack_id.strip())
                except StackNotFoundError as e:
                    raise InfrastructureNotFoundError(str(e)) from e
                else:
                    stack_id = input_stack_id

        return stack_id

    def __get_cf_template(self, cf_template_name):
        template_path = os.path.join(driver_directory, 'config', cf_template_name)
        logger.debug(f'CF template file path for {cf_template_name} is {template_path}')

        with open(template_path, 'r') as f:
            template = f.read()
        return template

    def render_template(self, system_properties, resource_properties, request_properties, cf_template_name):
        template = self.__get_cf_template(cf_template_name)
        return self.templating_service.render(template,
            self.resource_context_service.build(system_properties, resource_properties, request_properties, {}))

    def get_cf_parameters(self, resource_properties, system_properties, aws_location, cf_template):
        input_props = self.props_merger.merge(resource_properties, system_properties)
        return aws_location.get_cf_input_util().filter_used_properties(cf_template, input_props)

    # Will create a CP4NA resource using a Cloudformation template
    @interface
    def create(self, resource_id, lifecycle_name, driver_files, system_properties, resource_properties, request_properties, associated_topology, aws_location):
        pass

    # Remove a CF stack in AWS
    def remove(self, resource_id, lifecycle_name, driver_files, system_properties, resource_properties, request_properties, associated_topology, aws_location):
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
                # if delete_response is None:
                #     raise InfrastructureNotFoundError(f'Stack {stack_id} not found')
                request_id = build_request_id(DELETE_REQUEST_PREFIX, stack_id)
            except Exception as e:
                raise ResourceDriverError(str(e)) from e
        else:
            # nothing to do
            logger.info(f'No stack_id in associated topology for resource with id: {resource_id} name: {resource_name} lifecycle_name: {lifecycle_name}')
            request_id = build_request_id(CREATE_REQUEST_PREFIX, 'SKIP')
        #add topology to remove the stack during uninstall from internal table
        associated_topology.remove_stack_id(resource_name)
        return LifecycleExecuteResponse(request_id, associated_topology)

    def add_resource_property(self, resource_properties, key, type, value):
        resource_property_dict = resource_properties.to_dict()
        resource_property_dict[key] = {'type': type, 'value': value}
        return PropValueMap(resource_property_dict)
