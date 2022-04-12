from awsdriver.service.common import CREATE_REQUEST_PREFIX, build_request_id
from ignition.model.lifecycle import LifecycleExecuteResponse
from ignition.service.resourcedriver import ResourceDriverError
from awsdriver.location import *
from awsdriver.model.exceptions import *
from awsdriver.service.cloudformation import *
from awsdriver.service.topology import AWSAssociatedTopology


logger = logging.getLogger(__name__)

class RouteTableCloudFormation(CloudFormation):

    def create(self, resource_id, lifecycle_name, driver_files, system_properties, resource_properties, request_properties, associated_topology, aws_location):
        stack_id = self.get_stack_id(resource_id, lifecycle_name, driver_files, system_properties, resource_properties, request_properties, associated_topology, aws_location)
        if stack_id is None:
            cloudformation_driver = aws_location.cloudformation_driver

            resource_name = self.__create_resource_name(system_properties, resource_properties, self.get_resource_name(system_properties))
            stack_name = self.get_stack_name(resource_id, resource_name)

            cf_template = self.render_template(system_properties, resource_properties, request_properties, 'cloudformation_rt.yaml')
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

    def remove(self, resource_id, lifecycle_name, driver_files, system_properties, resource_properties, request_properties, associated_topology, aws_location):
        self.__create_resource_name(system_properties, resource_properties, self.get_resource_name(system_properties))
        return super().remove(resource_id, lifecycle_name, driver_files, system_properties, resource_properties, request_properties, associated_topology, aws_location)

    def __create_resource_name(self, system_properties, resource_properties, resource_name):
        system_properties['resourceName'] = self.get_resource_name(system_properties)
        return system_properties['resourceName']

    def addroute(self, resource_id, lifecycle_name, driver_files, system_properties, resource_properties, request_properties, associated_topology, aws_location):
        associated_topology = AWSAssociatedTopology()

        stack_id = self.get_stack_id(resource_id, lifecycle_name, driver_files, system_properties, resource_properties, request_properties, associated_topology, aws_location)
        if stack_id is None:
            cloudformation_driver = aws_location.cloudformation_driver

            public_private = resource_properties.get('public_private', None)
            if public_private is None:
                raise ResourceDriverError(f'public_private is null')
            routetable_type = resource_properties.get('routetable_type', None)
            if routetable_type is None:
                raise ResourceDriverError(f'routetable_type is null')

            if not public_private.lower() == 'private' and not routetable_type.lower() == 'intravpc':
                resource_name = self.__create_route_resource_name(system_properties, resource_properties, self.get_resource_name(system_properties))
                stack_name = self.get_stack_name(resource_id, resource_name)

                cf_template = self.render_template(system_properties, resource_properties, request_properties, 'cloudformation_rt_addroute.yaml')
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

        return LifecycleExecuteResponse(request_id, associated_topology=associated_topology)

    def removeroute(self, resource_id, lifecycle_name, driver_files, system_properties, resource_properties, request_properties, associated_topology, aws_location):
        self.__create_route_resource_name(system_properties, resource_properties, self.get_resource_name(system_properties))
        return super().remove(resource_id, lifecycle_name, driver_files, system_properties, resource_properties, request_properties, associated_topology, aws_location)

    def __create_route_resource_name(self, system_properties, resource_properties, resource_name):
        igw_id = resource_properties.get('igw_id', '')
        transit_gateway_id = resource_properties.get('transit_gateway_id', None)

        if igw_id is not None:
            resource_name = f'{resource_name}__{igw_id}'
        elif transit_gateway_id is not None:
            resource_name = f'{resource_name}__{transit_gateway_id}'
        system_properties['resourceName'] = self.sanitize_name(resource_name, '__route')
        return system_properties['resourceName']

    def addsubnetroute(self, resource_id, lifecycle_name, driver_files, system_properties, resource_properties, request_properties, associated_topology, aws_location):
        associated_topology = AWSAssociatedTopology()

        stack_id = self.get_stack_id(resource_id, lifecycle_name, driver_files, system_properties, resource_properties, request_properties, associated_topology, aws_location)
        if stack_id is None:
            cloudformation_driver = aws_location.cloudformation_driver

            resource_name = self.get_resource_name(system_properties)
            if resource_name is None:
                raise ResourceDriverError(f'resource_name is null')

            public_private = resource_properties.get('public_private', None)
            if public_private is None:
                raise ResourceDriverError(f'public_private is null')

            routetable_type = resource_properties.get('routetable_type', None)
            if routetable_type is None:
                raise ResourceDriverError(f'routetable_type is null')

            subnet_id = resource_properties.get('subnet_id', None)
            if subnet_id is None:
                raise ResourceDriverError(f'Missing subnet_id for adddsubnetroute for resource {resource_name}')

            if (public_private.lower() == 'private' and routetable_type.lower() == 'intravpc') or (public_private.lower() == 'public' and routetable_type.lower() == 'igw'):
                driver_resource_name = self.__create_subnetroute_resource_name(subnet_id, system_properties, resource_name)
                stack_name = self.get_stack_name(resource_id, driver_resource_name)

                cf_template = self.render_template(system_properties, resource_properties, request_properties, 'cloudformation_rt_addsubnetroute.yaml')
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
                associated_topology.add_stack_id(driver_resource_name, stack_id)
            else:
                request_id = build_request_id(CREATE_REQUEST_PREFIX, 'SKIP')

        return LifecycleExecuteResponse(request_id, associated_topology=associated_topology)

    def removesubnetroute(self, resource_id, lifecycle_name, driver_files, system_properties, resource_properties, request_properties, associated_topology, aws_location):
        resource_name = self.get_resource_name(system_properties)
        if resource_name is None:
            raise ResourceDriverError(f'resource_name is null')

        subnet_id = resource_properties.get('subnet_id', None)
        if subnet_id is None:
            raise ResourceDriverError(f'Missing subnet_id for adddsubnetroute for resource {resource_name}')

        self.__create_subnetroute_resource_name(subnet_id, system_properties, resource_name)
        return super().remove(resource_id, lifecycle_name, driver_files, system_properties, resource_properties, request_properties, associated_topology, aws_location)

    def __create_subnetroute_resource_name(self, subnet_id, system_properties, resource_name):
        system_properties['resourceName'] = self.sanitize_name(resource_name, '__', subnet_id, 'subnetroute')
        return system_properties['resourceName']

    def addsubnetinternetroute(self, resource_id, lifecycle_name, driver_files, system_properties, resource_properties, request_properties, associated_topology, aws_location):
        associated_topology = AWSAssociatedTopology()

        stack_id = self.get_stack_id(resource_id, lifecycle_name, driver_files, system_properties, resource_properties, request_properties, associated_topology, aws_location)
        if stack_id is None:
            cloudformation_driver = aws_location.cloudformation_driver

            public_private = resource_properties.get('public_private', None)
            if public_private is None:
                raise ResourceDriverError(f'public_private is null')
            routetable_type = resource_properties.get('routetable_type', None)
            if routetable_type is None:
                raise ResourceDriverError(f'routetable_type is null')

            if (public_private.lower() == 'private' and routetable_type.lower() == 'intravpc') or (public_private.lower() == 'public' and routetable_type.lower() == 'igw'):
                resource_name = self.__create_subnetinternetroute_resource_name(system_properties, resource_properties, self.get_resource_name(system_properties))
                stack_name = self.get_stack_name(resource_id, resource_name)

                cf_template = self.render_template(system_properties, resource_properties, request_properties, 'cloudformation_rt_addsubnetinternetroute.yaml')
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

        return LifecycleExecuteResponse(request_id, associated_topology=associated_topology)

    def removesubnetinternetroute(self, resource_id, lifecycle_name, driver_files, system_properties, resource_properties, request_properties, associated_topology, aws_location):
        self.__create_subnetinternetroute_resource_name(system_properties, resource_properties, self.get_resource_name(system_properties))
        return super().remove(resource_id, lifecycle_name, driver_files, system_properties, resource_properties, request_properties, associated_topology, aws_location)

    def __create_subnetinternetroute_resource_name(self, system_properties, resource_properties, resource_name):
        subnet_id = resource_properties.get('subnet_id', None)
        if subnet_id is None:
            raise ResourceDriverError(f'Must provide subnet_id for createsubnetinternetroute for resource {resource_name}')
        subnet_id = subnet_id.replace("subnet-", "sb")
        system_properties['resourceName'] = self.sanitize_name(resource_name, '__', subnet_id, 'internetsubnetroute')
        return system_properties['resourceName']