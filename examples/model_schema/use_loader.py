import os
import microbenthos
from microbenthos.model.loader import from_yaml, get_model_schema, yaml
from pprint import pprint

microbenthos.setup_console_logging('microbenthos.model', level=10)


model_path = os.path.join(os.path.dirname(__file__), 'model.yml')
schema_path = os.path.join(os.path.dirname(__file__), 'test_schema.yml')


# inbuilt_schema = get_model_schema()
raw_schema = get_model_schema()
inbuilt_schema = raw_schema['model_schema']
print('Loaded schema with keys: {}'.format(inbuilt_schema.keys()))

print('SCHEMA')
for k,v in inbuilt_schema.items():
    print('  {}  '.format(k.upper()).center(100, '#'))
    pprint(v)
    print('')

# pprint(inbuilt_schema)

with open(model_path) as fp:
    mdict = yaml.load(fp)

model_dict = from_yaml(model_path) # uses inbuilt schema

# model_dict = from_yaml(model_path, schema_path)

print("MODEL")
for k,v in model_dict.items():
    print('\n\n')
    print('  {}  '.format(k.upper()).center(100, '#'))
    pprint(v)
    print('')
