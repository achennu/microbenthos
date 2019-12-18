import mock
import pytest
import sympy as sp

from microbenthos import Process, Expression, ProcessEvent


@pytest.fixture()
def proc():
    return Process(expr=dict(formula='x*y*z**3'))


class TestProcess:
    def fail(self):
        pytest.xfail(reason='Not implemented')

    @pytest.mark.parametrize(
        'expr',
        [dict(formula='x*y*z**3'),
         Expression(formula='x*y*z**3')
         ],
        ids=(
            'expr:dict',
            'expr:instance'
            )
        )
    def test_init(self, expr):
        with pytest.raises(TypeError):
            proc = Process()

        proc = Process(expr)
        assert isinstance(proc.expr, Expression)

        # check some defaults
        assert proc.implicit is True
        assert not proc.events

    @mock.patch('sympy.lambdify')
    def test_evaluate(self, lambdify, proc):
        """
        A test that should confirm:

        * sympy expr as input is processed
        * the expr is lambdified
        * params keys are made into symbols
        * proc.events keys are made into symbols
        * param symbol is sourced from params
        * event symbol is sourced as event.event_time
        * rest are sourced from domain

        """
        # proc.evaluate takes a sympy expression as input
        dom = mock.MagicMock(name='domain')
        Z = mock.Mock()
        params = {}

        expr = proc.expr.expr()
        esymbs = {e for e in expr.atoms() if isinstance(e, sp.Symbol)}

        lambdify.return_value = efunc = mock.MagicMock()

        with mock.patch.dict(params, z=Z):
            proc.evaluate(expr, params=params, domain=dom)

        dom.__getitem__.assert_any_call('x')
        dom.__getitem__.assert_any_call('y')
        efunc.assert_called_once_with(dom['x'], dom['y'], Z.inBaseUnits())

    def test_as_source_for(self, proc):
        # since process.evaluate() is tested, we just check here that it returns the variable
        # object and (S0, S1) term
        dom = mock.MagicMock()
        # dom.__getitem__.return_value = v = mock.MagicMock()
        proc.set_domain(dom)

        vobj, S0, S1 = proc.as_source_for('x')
        assert S1 == 0
        assert vobj == proc.evaluate(sp.Symbol('x'))
        assert S0 == proc.evaluate(proc.expr.expr())

    def test_snapshot(self):
        pdict = dict(z=35)
        proc = Process(expr=dict(formula='x*y*z**3'),
                       params=pdict)

        from microbenthos.core import SedimentDBLDomain
        domain = SedimentDBLDomain()
        domain.create_var('y', value=3)
        domain.create_var('x', value=2)
        domain.create_var('z', value=1)

        proc.set_domain(domain)

        state = proc.snapshot()

        statekeys = set(['metadata', 'data'])
        assert set(state) == statekeys

        metakeys = set(['param_names', 'expr'])
        metakeys.update(pdict)
        assert set(state['metadata']) == metakeys

    def test_restore_from(self):
        pdict = dict(z=35)
        proc = Process(expr=dict(formula='x*y*z**3'),
                       params=pdict)

        state = {}
        tidx = 0

        with pytest.raises(TypeError):
            proc.restore_from(state)
            # tidx is missing

        with pytest.raises(RuntimeError):
            proc.restore_from(state, tidx)
            # no domain

        proc.domain = dom = mock.MagicMock()
        proc.restore_from(state, tidx)

    def test_add_event(self):
        p = Process(expr=dict(formula='x*y*d'))
        EVENTDEF = dict(expr=dict(formula='3*d*y**3'))
        NAME = 'eventtt'

        p.add_event(NAME, **EVENTDEF)
        assert NAME in p.events
        assert p.events

    def test_setup(self, proc):
        Evt = mock.MagicMock(ProcessEvent)
        evt = Evt()
        proc.events['evt'] = evt

        proc.setup()
        evt.setup.assert_called_once_with(process=proc)

    def test_on_time_updated(self, proc):
        Evt = mock.MagicMock(ProcessEvent)
        evt = Evt()
        proc.events['evt'] = evt

        dt = object()

        proc.on_time_updated(dt)
        evt.on_time_updated.assert_called_once_with(dt)
