from ignition.model.associated_topology import AssociatedTopology

STACK_RESOURCE_TYPE = 'AWS'
STACK_NAME = 'InfrastructureStack'

class AWSAssociatedTopology(AssociatedTopology):

    def add_stack_id(self, resource_name, stack_id):
        self.add_entry(resource_name, stack_id, STACK_RESOURCE_TYPE)

    def get_stack_id(self, resource_name):
        entry = self.get(resource_name)
        if entry is not None:
            return entry.to_dict()['id']
        else:
            return None
