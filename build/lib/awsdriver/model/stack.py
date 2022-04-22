

class Stack():
    def __init__(self, id, name, status):
        self.id = id
        self.name = name
        self.status = status

    def __str__(self):
      return f'id: {self.id} name: {self.name} status: {self.status}'

    @classmethod
    def from_dict(cls, dict):
        return Stack(dict.get('StackId', None), dict.get('StackName', None), dict.get('StackStatus', None))

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'status': self.status
        }