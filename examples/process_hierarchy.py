
import logging
from microbenthos.utils.log import ColorizingStreamHandler
sh = ColorizingStreamHandler()
logger = logging.getLogger('microbenthos')
logger.setLevel(10)
logger.addHandler(sh)

PROCESS = """
oxyPS:
    cls: ExprProcess
    init_params:
        formula: Qmax * biomass
        varnames:
            - biomass
        params:
            Qmax: !unit "0.00841 mol/g/h"
        
        responses:
            optimum(par):
                cls: ExprProcess
                init_params:
                    formula: optimum_response(par, Ks, Ki)
                    varnames:
                        - par
                    params:
                        Ks: 1
                        Ki: 10
        
            optimum(oxy):
                cls: ExprProcess
                init_params:
                    formula: optimum_response(oxy, Ks, Ki)
                    varnames:
                        - oxy
                    params:
                        Ks: !unit "0.3e-3 mol/l"
                        Ki: !unit "0.35e-3 mol/l"
                        
formulae:
    optimum_response:        
        variables: [x, Ks, Ki]
        expr: x/(x + Ks)/(1 + x/Ki)

"""

from microbenthos.loader.yaml_loader import yaml
from pprint import pprint
from microbenthos.exprs import ExprProcess
from microbenthos.base import Entity

PDICT = yaml.load(PROCESS)
pprint(PDICT)

# create namespace
from sympy import Lambda, symbols
NS = {}
for name, fdict in PDICT['formulae'].items():
    variables = symbols(fdict['variables'])
    func = Lambda(variables, fdict['expr'])
    print("Created {} func = {}".format(name, func))
    NS[name] = func

pprint(NS)

ExprProcess._sympy_ns.update(NS)

oxyps_init = PDICT['oxyPS']['init_params']

oxyPS = ExprProcess(**oxyps_init)
logger.info('oxyPS: {}'.format(oxyPS))
logger.info('oxyPS expr: {}'.format(oxyPS.expr))
logger.info("Dependents: {}".format(oxyPS.dependent_vars()))


from fipy import Variable
import numpy as np
from matplotlib import pyplot as plt

oxy = Variable(np.linspace(0, 0.01, 1000), name='oxygen', unit='mol/l')
par = Variable(np.linspace(0, 100, len(oxy)), name='par')
biomass = Variable(np.linspace(1, 0, len(oxy)), name='biomass', unit='g/cm**3' )

e = oxyPS.evaluate(D=dict(par=par, oxy=oxy, biomass=biomass))
epar = oxyPS.responses['optimum(par)'].evaluate(D=dict(par=par, oxy=oxy, biomass=biomass))
eoxy = oxyPS.responses['optimum(oxy)'].evaluate(D=dict(par=par, oxy=oxy, biomass=biomass))

print('optimum(par) = {!r}'.format(epar))
print('optimum(oxy) = {!r}'.format(eoxy))
print('oxyPS = {!r}'.format(e))

plt.plot(np.atleast_1d(e/max(e)), label='oxyPS')
plt.plot(np.atleast_1d(par / max(par)), ':', label='par')
plt.plot(np.atleast_1d(oxy / max(oxy)), ':', label='oxy')
plt.plot(np.atleast_1d(biomass / max(biomass)), ':',  label='biomass')
plt.plot(np.atleast_1d(epar / max(epar)), label='opt(par)')
plt.plot(np.atleast_1d(eoxy / max(eoxy)), label='opt(oxy)')
plt.legend()
plt.show()
