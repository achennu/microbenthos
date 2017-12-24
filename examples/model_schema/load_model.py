import microbenthos
microbenthos.setup_console_logging(level=20)

import os
model_path = os.path.join(os.path.dirname(__file__), 'model.yml')

from microbenthos.model import from_yaml
model_dict = from_yaml(model_path)

from microbenthos.model.model import MicroBenthosModel

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
