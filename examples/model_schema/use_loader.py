import logging
from microbenthos.utils.log import ColorizingStreamHandler
import os
from microbenthos.model import from_yaml, get_model_schema, yaml
from pprint import pprint

logger = logging.getLogger('microbenthos')
logger.setLevel(20)
logger.addHandler(ColorizingStreamHandler())


model_path = os.path.join(os.path.dirname(__file__), 'model.yml')
schema_path = os.path.join(os.path.dirname(__file__), 'test_schema.yml')


# inbuilt_schema = get_model_schema()
raw_schema = get_model_schema()
inbuilt_schema = raw_schema['model_schema']
pprint(inbuilt_schema['microbes'])

logger.warning('Opening model file!')
with open(model_path) as fp:
    mdict = yaml.load(fp)

# pprint(mdict['microbes']['cyano'].items())
pprint(mdict['microbes']['cyano']['init_params']['features'])

model_dict = from_yaml(model_path) # uses inbuilt schema

# model_dict = from_yaml(model_path, schema_path)

logger.warning("MODEL LOADED")
pprint(model_dict)
logger.info('DONE')
