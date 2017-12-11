import logging
logger = logging.getLogger('microbenthos')
logger.setLevel(10)
from logutils.colorize import ColorizingStreamHandler
logger.addHandler(ColorizingStreamHandler())

from microbenthos.utils import yaml
from microbenthos.base import Entity
from pprint import pprint

YAML_TEXT = """

entities:
    
    irradiance:
        cls: microbenthos.irradiance.Irradiance
        init_params:
            hours_total: !unit 24 h
            day_fraction: 0.5
        
        _jnk:
            - &kappa_biomass1 !unit 16623 cm**2/g
        
        channels:
            - name: par
              k0: !unit 16.1 1/cm
              k_mods: 
                - [biomass1, *kappa_biomass1]

"""

cdict = yaml.load(YAML_TEXT)
print('Loaded config dict!')
pprint(cdict)

for ename, einfo in cdict['entities'].iteritems():
    print('Creating entity: {}'.format(ename))

    e = Entity.from_dict(einfo)
