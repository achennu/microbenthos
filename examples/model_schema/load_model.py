import microbenthos

microbenthos.setup_console_logging(level=20)

import os


from microbenthos.model import from_yaml
from microbenthos.model.model import MicroBenthosModel


model_path = os.path.join(os.path.dirname(__file__), 'model.yml')
model_dict = from_yaml(model_path)
model = MicroBenthosModel.from_definition(model_dict)

state = model.snapshot()


def chart_nested_dict(thisdict, keys = [], indent = 0):
    from collections import Mapping
    path = ' -> '.join(keys) + ' '
    print(path + str(thisdict.keys()))
    for k, v in thisdict.items():
        if isinstance(v, Mapping):
            kk = list(keys)
            kk.append(k)
            chart_nested_dict(v, kk, indent + 2)
        else:
            print(path + ' -> {} :: {}'.format(k, type(v)))

    print('')


inp = raw_input('\nShow de-nested model snapshot? [y/N] : ')
if inp in ('y', 'Y'):
    chart_nested_dict(state)
