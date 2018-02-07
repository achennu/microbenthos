import logging
from microbenthos.utils.log import ColorizingStreamHandler
import os
from microbenthos import from_dict, get_schema, yaml
from pprint import pprint

logger = logging.getLogger('microbenthos')
logger.setLevel(20)
logger.addHandler(ColorizingStreamHandler())


model_path = os.path.join(os.path.dirname(__file__), 'model.yml')
schema_path = os.path.join(os.path.dirname(__file__), 'test_schema.yml')


# inbuilt_schema = get_schema()
inbuilt_schema = get_schema()['model']
pprint(inbuilt_schema['microbes'])

logger.warning('Opening model file!')
with open(model_path) as fp:
    mdict = yaml.load(fp)


# pprint(mdict['microbes']['cyano'].items())
pprint(mdict['microbes']['cyano']['init_params']['features'])

model_dict = from_dict(mdict, key='model') # uses inbuilt schema

# model_dict = from_yaml(model_path, open(schema_path))

logger.warning("MODEL LOADED")
pprint(model_dict)
logger.info('DONE')
