from ast import Not
from awsdriver.service.common import CREATE_REQUEST_PREFIX, build_request_id, FILTER_NAME_TAG_CREATOR, FILTER_VALUE_TAG_CREATOR
from ignition.model.lifecycle import LifecycleExecuteResponse
from ignition.service.resourcedriver import ResourceDriverError
from awsdriver.location import *
from awsdriver.model.exceptions import *
from awsdriver.service.cloudformation import *
from awsdriver.service.topology import AWSAssociatedTopology
from awsdriver.service.tgw_cf import  AWS_TGW_DELETING_STATUS, AWS_TGW_DELETED_STATUS, AWS_TGW_AVAILABLE_STATUS, MAX_TGW_CHECK_TIMEOUT

import time


logger = logging.getLogger(__name__)

class VPCCloudFormation(CloudFormation):

    # Will create a VPC using a Cloudformation template
    def create(self, resource_id, lifecycle_name, driver_files, system_properties, resource_properties, request_properties, associated_topology, aws_location):
        logger.info(f'invoking creation of vpc for request :: {resource_id} and resource_prop as :: {resource_properties}')
        stack_id = self.get_stack_id(resource_id, lifecycle_name, driver_files, system_properties, resource_properties, request_properties, associated_topology, aws_location)
        if stack_id is None:
            #TODO find cloud formation way of creating key-pair so that rollback can be supported.
            '''
            Create/import the new key pair for velocloud, before creating the vpc in that region.
            Using ec2 client for automation of key-pair 
            '''
            input_key_name = resource_properties.get('ssh_key_name', None)
            if input_key_name is not None: #key name is none means its secondary vpc creation, so ignore
                try:
                    #check if key exist in AWS
                    try:
                        key_response = aws_location.ec2.describe_key_pairs(
                            KeyNames=[
                                input_key_name,
                            ],
                            IncludePublicKey=True
                        )

                        key_pairs = key_response.get('KeyPairs', None)
                        if key_pairs is None:
                            self.import_new_key_pair(resource_properties, aws_location, input_key_name)
                        else:
                            existing_public_key = key_pairs[0].get('PublicKey',None)
                            input_publicKeyValue = resource_properties.get('ssh_pub_key_value', None)
                            #check if key exists with same name but content is diff, cll aws so as to throw existing key error
                            #If key and public key value are same, ignore and continue with vpc creatino.
                            if input_publicKeyValue is not None and existing_public_key is not None:
                                #aws return key with key name, split on space and 
                                existing_public_key_val = " ".join(existing_public_key.split(" ", 2)[:2])
                                if  existing_public_key_val != input_publicKeyValue:
                                    logger.error("Key alreday exist with different value and cannot be overwritten , please provide valid key")
                                    raise ResourceDriverError("Key alreday exist with different value and cannot be overwritten , please provide valid key")
                    except Exception as key_resp:
                        if "InvalidKeyPair.NotFound" in str(key_resp):
                                self.import_new_key_pair(resource_properties, aws_location, input_key_name)
                        else:
                            logger.error("Failed importing the key pair value before creating the vpc", key_resp)
                            raise ResourceDriverError(str(key_resp)) from key_resp
                except Exception as keyExp:
                    logger.error("Failed importing the key pair value before creating the vpc", keyExp)
                    raise ResourceDriverError(str(keyExp)) from keyExp
                    
            cloudformation_driver = aws_location.cloudformation_driver

            resource_name = self.__create_resource_name(system_properties, resource_properties, self.get_resource_name(system_properties))
            stack_name = self.get_stack_name(resource_id, resource_name)

            cf_template = self.render_template(system_properties, resource_properties, request_properties, 'cloudformation_vpc.yaml')
            cf_parameters = self.get_cf_parameters(resource_properties, system_properties, aws_location, cf_template)
            logger.debug(f'stack_name={stack_name} cf_template={cf_template} cf_parameters={cf_parameters}')

            try:
                self.__wait_for_transitgateway_route_availability(aws_location, resource_properties)
                stack_id = cloudformation_driver.create_stack(stack_name, cf_template, cf_parameters)
                logger.debug(f'Created Stack Id: {stack_id}')
                logger.debug(f'wait blindly for 30 sec for tgw completion')
                time.sleep(30)
            except Exception as e:
                raise ResourceDriverError(str(e)) from e

            if stack_id is None:
                raise ResourceDriverError('Failed to create cloudformation stack on AWS')


        request_id = build_request_id(CREATE_REQUEST_PREFIX, stack_id)
        associated_topology = AWSAssociatedTopology()
        associated_topology.add_stack_id(resource_name, stack_id)
        logger.info(f'completed creation of vpc for request :: {resource_id} and resource_prop as :: {resource_properties}')
        return LifecycleExecuteResponse(request_id, associated_topology=associated_topology)

    def import_new_key_pair(self, resource_properties, aws_location, publicKey):
        publicKeyValue = resource_properties.get('ssh_pub_key_value', None)
        if publicKeyValue is not None:
            logger.info(f'importing existing key for vpc creation as key :: {publicKey}')
            aws_location.ec2.import_key_pair(KeyName=publicKey,PublicKeyMaterial=publicKeyValue)
        else:
            logger.error("Value is mandantory for creating the key pair for non-existing key-pair, please provide valid key-pair value with public key value as well")
            raise ResourceDriverError("Please provide existing key name or upload public key value to import it")


    def remove(self, resource_id, lifecycle_name, driver_files, system_properties, resource_properties, request_properties, associated_topology, aws_location):
        logger.info(f'invoking removal of vpc for request :: {resource_id} and resource_prop as :: {resource_properties}')
        self.__create_resource_name(system_properties, resource_properties, self.get_resource_name(system_properties))
        return super().remove(resource_id, lifecycle_name, driver_files, system_properties, resource_properties, request_properties, associated_topology, aws_location)

    def __create_resource_name(self, system_properties, resource_properties, resource_name):
        system_properties['resourceName'] = self.get_resource_name(system_properties)
        return system_properties['resourceName']
    
    def __get_transitgateway_routetable_id(self, aws_client, resource_properties):
        '''Gets the Transit Gateway Route Table ID which is in Pending or available state'''
        transit_gateway_routetable_id = None
        tgw_route_table_tag_value = resource_properties.get('transit_gateway_name', None)
        transit_gateways_route_table = aws_client.ec2.describe_transit_gateway_route_tables(
                                    Filters=[
                                        {
                                            'Name': FILTER_NAME_TGW_ROUTE_TAG,
                                            'Values': [
                                                tgw_route_table_tag_value,
                                            ]
                                        }
                                    ])
        for tgw_rt in transit_gateways_route_table['TransitGatewayRouteTables']:
            if tgw_rt['State'] not in  [AWS_TGW_DELETING_STATUS, AWS_TGW_DELETED_STATUS]:
                transit_gateway_routetable_id = tgw_rt['TransitGatewayRouteTableId']
                logger.debug(f'Got the TGW route table with id {transit_gateway_routetable_id} which is in {tgw_rt["State"]}')
                break
        return transit_gateway_routetable_id
            
            
        
    def __wait_for_transitgateway_route_availability(self, aws_client, resource_properties):
        '''Wait for the Transit Gatway route table to be available in the required AWS'''
        transit_gateway_routetable_id = None
        tgw_route_table_tag_value = resource_properties.get('transit_gateway_name', None)
        startTime = time.time() 
        
        while True:
            if time.time()-startTime >= MAX_TGW_CHECK_TIMEOUT:
                raise ResourceDriverError(f'Timeout waiting for the Transit Gateway route table availability')
            if  transit_gateway_routetable_id is None:
                transit_gateway_routetable_id = self.__get_transitgateway_routetable_id(aws_client, resource_properties)
                time.sleep(2)
                logger.debug('waiting for 2 seconds to check for the Transit Gateway route table availability')
                continue
            transit_gateways_rtbs = aws_client.ec2.describe_transit_gateway_route_tables(
                                    Filters=[
                                        {
                                            'Name': FILTER_NAME_TGW_ROUTE_TAG,
                                            'Values': [
                                                tgw_route_table_tag_value,
                                            ]
                                        },
                                        {
                                            'Name': 'transit-gateway-route-table-id',
                                            'Values': [
                                                transit_gateway_routetable_id,
                                            ]
                                        },
                                    ])
            transit_gateways_rtb = transit_gateways_rtbs['TransitGatewayRouteTables'][0]
            if transit_gateways_rtb['State'] == AWS_TGW_AVAILABLE_STATUS:
                logger.debug(f'TGW with id {transit_gateway_routetable_id} is in available state')
                break
            else:
                time.sleep(10)
                logger.debug('waiting for 10 seconds to check for the Transit Gateway route table availability')
                continue
                  
    