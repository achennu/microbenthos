import pytest
from sympy import sympify
import copy

from fipy.tools import numerix
from microbenthos import Process, ExprProcess, SedimentDBLDomain

@pytest.fixture()
def domain():
    return SedimentDBLDomain()

def test_process_base_init():
    with pytest.raises(TypeError):
        Process()


class TestExprProcess:

    def test_init_empty(self):
        with pytest.raises(TypeError):
            ExprProcess()


GOODS = dict()
_BASE_INP = dict(
    formula='X**2 / k1 * sin(Y)/ alpha - z',
    varnames=['X', 'Y', 'z'],
    params=dict(k1=23.0, alpha=2.0),
    responses=None,
    )

GOODS['no_resp'] = copy.deepcopy(_BASE_INP)

GOODS['resp_as_dict'] = copy.deepcopy(_BASE_INP)
GOODS['resp_as_dict']['responses'] = {
    'some(X)': dict(
        cls='ExprProcess',
        init_params=dict(
            formula='X / (dx + X)',
            params=dict(
                dx=15
                ),
            varnames=['X'],
            ),
        ),
    }

BADS = {}

BADS['empty'] = {}
BADS['empty']['expect_err'] = TypeError

BADS['formula_bad'] = copy.deepcopy(_BASE_INP)
BADS['formula_bad']['formula'] += ' alpha'
BADS['formula_bad']['expect_err'] = ValueError

BADS['varnames_bad'] = copy.deepcopy(_BASE_INP)
BADS['varnames_bad']['varnames'].append('x a')
BADS['varnames_bad']['expect_err'] = ValueError

BADS['params_bad'] = copy.deepcopy(_BASE_INP)
BADS['params_bad']['params']['a a'] = 30
BADS['params_bad']['expect_err'] = ValueError


def pytest_generate_tests(metafunc):
    if metafunc.cls is None:
        return
    if not hasattr(metafunc.cls, 'scenarios'):
        return
    idlist = []
    argvalues = []
    # print("Scenarios: {}".format(metafunc.cls.scenarios))
    for scenario, params in metafunc.cls.scenarios:
        idlist.append(scenario)
        argnames = ['case', 'params']
        argvalues.append((scenario, params))

    # for n,v in zip(argnames, argvalues):
    #     print('Now {} = {}'.format(n, v))

    metafunc.parametrize(argnames, argvalues, ids=idlist, scope="function")


class TestExprInputs:
    scenarios = GOODS.items() + BADS.items()

    def test_creation_and_snapshot(self, case, params, domain):

        expected_error = params.pop('expect_err', None)
        if expected_error:
            with pytest.raises(expected_error):
                proc = ExprProcess(**params)

        else:
            proc = ExprProcess(**params)
            assert proc.expr == sympify(params['formula'])

            # create variables on domain
            varnames = params['varnames']
            for v in varnames:
                domain.create_var(v, value=5)

            proc = ExprProcess(**params)
            proc.set_domain(domain)
            proc.setup()
            state = proc.snapshot()

            statekeys = ('metadata', 'data', 'responses')
            assert set(statekeys) == set(state)

            metakeys = ('formula', 'varnames', 'dependent_vars', 'expected_unit') + tuple(
                proc.params.keys())
            assert set(metakeys) == set(state['metadata'])

            respkeys = proc.responses.keys()
            assert set(respkeys) == set(state['responses'])

            assert state['data'][1]['unit'] == proc.evaluate().unit.name()
            assert numerix.allclose(state['data'][0], proc.evaluate(domain=domain))
