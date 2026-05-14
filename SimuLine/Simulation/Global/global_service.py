import json
import os


class GlobalVariance():
    def __init__(self, name='SimuLine-GlobalVariance-Batch00'):
        self._name = name
        self._variance_file = f"./SimuLine/Simulation/Global/variances/{self._name}.json"
        os.makedirs(os.path.dirname(self._variance_file), exist_ok=True)
        self._variance = {}
    
    def write_file(self):
        os.makedirs(os.path.dirname(self._variance_file), exist_ok=True)
        with open(self._variance_file, 'w') as f:
            f.write(json.dumps(self._variance))
    
    def read_file(self):
        with open(self._variance_file, 'r') as f:
            self._variance = json.loads(f.read())
    
    def set_value(self, key, value):
        self._variance[key] = value

    @property
    def variance(self):
        return self._variance

