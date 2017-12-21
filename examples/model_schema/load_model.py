import microbenthos
microbenthos.setup_console_logging(level=20)

import os
model_path = os.path.join(os.path.dirname(__file__), 'model.yml')

from microbenthos.loader import from_yaml
model_dict = from_yaml(model_path)

from microbenthos.model import MicroBenthosModel

model = MicroBenthosModel(model_dict)

