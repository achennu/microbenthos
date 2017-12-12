from pprint import pprint

import yaml
from microbenthos.loader.model_loader import ModelSchemaValidator

with open('schema.yml') as fp:
    schema = yaml.load(fp)['model_schema']

print('Schema is:')
pprint(schema)


V = ModelSchemaValidator(schema)

print(V)

with open('model.yml') as fp:
    document = yaml.load(fp)

print('Document is')
pprint(document)
print(type(document['entities']))

print('Validated: {}'.format(V.validate(document)))
print('Errors: {}'.format(V.errors))

pprint(V.document)


