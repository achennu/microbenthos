import microbenthos
microbenthos.setup_console_logging(level=10)

import os
model_path = os.path.join(os.path.dirname(__file__), 'model.yml')

from microbenthos.model import from_yaml
model_dict = from_yaml(model_path)

from microbenthos.model.model import MicroBenthosModel
from microbenthos.viewer import MicroBenthosViewer

model = MicroBenthosModel(model_dict)

state = model.snapshot()


def chart_nested_dict(thisdict, keys=[], indent=0):
    from collections import Mapping
    path = ' -> '.join(keys) + ' '
    print(path + str(thisdict.keys()))
    for k,v in thisdict.items():
        if isinstance(v, Mapping):
            kk = list(keys)
            kk.append(k)
            chart_nested_dict(v, kk, indent+2)
        else:
            print(path + ' -> {} :: {}'.format(k, type(v)))

    print('')


# chart_nested_dict(state)
# uncomment this for a detailed view of the nested structure of the snapshot
from fipy.tools import numerix
# oxy = model.domain['oxy']
# oxy.value = numerix.linspace(oxy.numericValue[0], oxy.numericValue[-1], len(oxy))
# h2s = model.domain['h2s']
# h2s.value = numerix.linspace(h2s.numericValue[0], h2s.numericValue[-1], len(h2s))
# print('Set oxy: {}'.format(oxy))
# print('Set h2s: {}'.format(h2s))
print('Porosity: {}'.format(model.domain['porosity']))

# viewer = MicroBenthosViewer(model)

model.solve(5)
