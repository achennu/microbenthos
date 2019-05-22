import mock
import pytest
from fipy import PhysicalField

from microbenthos import Expression, Entity, yaml, SedimentDBLDomain, DomainEntity
from microbenthos.model.model import MicroBenthosModel, ModelClock, ModelEquation

DOMAIN_DEF = yaml.unsafe_load("""
cls: SedimentDBLDomain
init_params:
    cell_size: !unit 50 mum
    sediment_length: !unit 20 mm
    dbl_length: !unit 1 mm
    porosity: 0.6
""")

FORMULAE_DEF = yaml.unsafe_load("""
saturation:
    vars: [x, Km]
    expr: x / (Km + x)
""")

VARDEF = yaml.unsafe_load("""
cls: ModelVariable
init_params:
    name: oxy
    create:
        hasOld: true
        value: !unit 0.0 mol/m**3
""")


class TestMicroBenthosModel:
    def fail(self):
        pytest.xfail(reason='Not implemented')

    def test_init_empty(self):

        model = MicroBenthosModel()

        assert model.domain is None
        assert not model.equations
        assert not model.env
        assert not model.microbes
        assert isinstance(model.clock, ModelClock)
        assert model.clock() == 0
        assert model.clock.unit.name() == 'h'

    def test_init_domain(self):

        model = MicroBenthosModel(domain={})
        assert model.domain is None

        model = MicroBenthosModel(domain=DOMAIN_DEF)
        assert model.domain
        assert model.domain.cell_size == DOMAIN_DEF['init_params']['cell_size']
        with pytest.raises(RuntimeError):
            model.create_full_equation()

        # bad input
        with pytest.raises(ValueError):
            model = MicroBenthosModel(domain=3)

    def test_domain(self):
        model = MicroBenthosModel()
        assert model.domain is None

        DOM = object()
        model.domain = DOM
        assert model.domain is DOM

        with pytest.raises(RuntimeError):
            model.domain = DOM
            # domain already set

    def test_init_formulae(self):
        model = MicroBenthosModel(formulae={})
        assert not Expression._sympy_ns

        model = MicroBenthosModel(formulae=FORMULAE_DEF)
        for k in FORMULAE_DEF:
            assert k in Expression._sympy_ns

    def test_create_entity_from(self):
        model = MicroBenthosModel()

        with pytest.raises(RuntimeError):
            entity = model.create_entity_from(VARDEF)
            # no domain available
        model.domain = SedimentDBLDomain()

        entity = model.create_entity_from(VARDEF)
        assert isinstance(entity, Entity)
        assert entity.check_domain()
        assert entity.is_setup

    def test_add_formula(self):

        BAD_FORMULA = dict(
            vars=('x', 'Km'),
            expr='x:3_j',  # unsympifyable
            )

        model = MicroBenthosModel()

        for name, fdef in FORMULAE_DEF.items():
            model.add_formula(name, **fdef)
            assert name in Expression._sympy_ns

        with pytest.raises(ValueError):
            model.add_formula(name='blah', **BAD_FORMULA)

    def test_entities_setup(self):
        model = MicroBenthosModel()
        model.entities_setup()
        # no entities defined

        entity = mock.MagicMock(DomainEntity)
        model.env['var'] = entity
        entity.is_setup = False

        model.entities_setup()
        entity.setup.assert_called_once_with(model=model)

    def test_all_entities_setup(self):
        model = MicroBenthosModel()

        e1 = mock.MagicMock(DomainEntity)
        e2 = mock.MagicMock(DomainEntity)

        # for e in (e1, e2):
        type(e1).is_setup = p = mock.PropertyMock(return_value=True)

        # e1.is_setup.return_value = False
        # e2.is_setup.return_value = True

        model.env['e1'] = e1
        model.microbes['e2'] = e2

        assert model.all_entities_setup

        for e in (e1, e2):
            p.assert_called_once()

        p.return_value = False

        # e1.is_setup.return_value = True
        assert not model.all_entities_setup

    def test_snapshot(self):

        model = MicroBenthosModel()

        e1 = mock.MagicMock(DomainEntity)
        e2 = mock.MagicMock(DomainEntity)
        model.env['e1'] = e1
        model.microbes['e2'] = e2

        state = model.snapshot()

        keys = set(('time', 'domain', 'env', 'microbes', 'equations'))
        assert keys == set(state)

        assert 'e1' in state['env']
        assert 'e2' in state['microbes']

    def test_can_restore_from(self):

        store = mock.Mock()
        model = MicroBenthosModel()

        with mock.patch('microbenthos.model.check_compatibility') as m:

            model.can_restore_from(store)

            m.assert_called_once_with(model.snapshot(), store)

    def test_restore_from(self):
        model = MicroBenthosModel()

        entity = mock.MagicMock(DomainEntity)
        model.env['ent'] = entity
        microbe = mock.MagicMock(DomainEntity)
        model.microbes['microbe'] = microbe

        from h5py import Group
        store = mock.MagicMock(Group)
        store.__getitem__.return_value = mock.MagicMock(Group)

        with mock.patch.multiple(
            'microbenthos.model',
            check_compatibility=mock.DEFAULT,
            truncate_model_data=mock.DEFAULT,
            restore_var=mock.DEFAULT,
            ) as mocks:

            check_compat = mocks['check_compatibility']
            truncate = mocks['truncate_model_data']
            restore_var = mocks['restore_var']

            restore_var.return_value = clockval = PhysicalField(0.5, 's')
            truncate.return_value = 3

            check_compat.side_effect = ValueError

            with pytest.raises(TypeError):
                model.restore_from(store, time_idx=-1)

            check_compat.assert_called_once()

            check_compat.reset_mock()
            check_compat.side_effect = None

            TIDX = -5
            assert model.clock.value != clockval
            snapshot = model.snapshot()
            model.restore_from(store, time_idx=TIDX)

            check_compat.assert_called_once_with(snapshot, store)
            truncate.assert_called_once_with(store, time_idx=TIDX)
            entity.restore_from.assert_called_once_with(store['env']['ent'], -1)
            microbe.restore_from.assert_called_once_with(store['env']['micro'], -1)

            assert model.clock.value == clockval

    @mock.patch('microbenthos.model.ModelEquation')
    def test_add_equation(self, MockEqn):

        model = MicroBenthosModel()

        call = dict(name='myEqn',
                    track_budget=True
                    )
        call['transient'] = [3, 4, 5]

        with pytest.raises(ValueError):
            model.add_equation(**call)
            # transient term should be a tuple of length 2

        call['transient'] = CTERM = ('domain.var', 35)
        with pytest.raises(ValueError):
            model.add_equation(**call)
            # one of diffusion or source term must be given

        call['diffusion'] = 'ab'
        with pytest.raises(ValueError):
            model.add_equation(**call)
            # diffusion should be a pair

        call.pop('diffusion')
        call['sources'] = []
        with pytest.raises(ValueError):
            model.add_equation(**call)
            # sources should be a sequence of pair-tuples

        call.pop('sources')
        call['diffusion'] = CTERM
        model.add_equation(**call)
        assert call['name'] in model.equations
        MockEqn.assert_called_once_with(model, *call['transient'], track_budget=call['track_budget'])
        MockEqn().finalize.assert_called_once()
        MockEqn().add_diffusion_term_from.assert_called_once_with(*call['diffusion'])
        MockEqn().add_source_term_from.assert_not_called()

        MockEqn.reset_mock()
        model.equations.pop(call['name'])

        call['sources'] = [CTERM] * 3
        model.add_equation(**call)
        assert call['name'] in model.equations
        MockEqn.assert_called_once_with(model, *call['transient'],
                                        track_budget=call['track_budget'])
        MockEqn().finalize.assert_called_once()
        MockEqn().add_diffusion_term_from.assert_called_once_with(*call['diffusion'])
        MockEqn().add_source_term_from.call_count == len(call['sources'])
        for mcall in MockEqn().add_source_term_from.call_args_list:
            assert mcall[0] == CTERM
            assert mcall[1] == {}  # no kwargs

    def test_create_full_equation(self):

        model = MicroBenthosModel()
        with pytest.raises(RuntimeError):
            model.create_full_equation()

        Meqn = mock.MagicMock(ModelEquation)
        eqn = Meqn()
        model.equations['eqn'] = eqn
        model.equations['eqn2'] = eqn

        model.create_full_equation()
        eqn.obj.__and__.assert_called_once_with(eqn.obj)

        assert model.full_eqn is not None
        import operator
        import functools
        assert model.full_eqn == functools.reduce(operator.and_, [eqn.obj for eqn in (eqn, eqn)])

    @pytest.mark.parametrize('path, err',[
        ('nodotted', TypeError),
        ('dot.ted', None),
        ])
    def test_get_object(self, path, err):
        model = mock.MagicMock(MicroBenthosModel)
        model.logger = mock.Mock()


        if err:
            with pytest.raises(err):
                MicroBenthosModel.get_object(model, path)
        else:
            try:
                ret = MicroBenthosModel.get_object(model, path)
            except ValueError:
                pass

    @mock.patch('microbenthos.model.ModelClock')
    def test_on_time_updated(self, MClock):
        model = MicroBenthosModel()

        MEntity = mock.MagicMock(DomainEntity)
        enames = list('abcd')
        mnames = list('xbcjkl')
        for e in enames:
            model.env[e] = MEntity()

        for m in mnames:
            model.microbes[m] = MEntity()

        model.on_time_updated()
        MClock.assert_called_once()
        ent = MEntity()

        ent.on_time_updated.call_count = len(enames) + len(mnames)
        for call in ent.on_time_updated.call_args_list:
            args, kwargs = call
            assert args == (MClock()(),)
            assert kwargs == {}


    def test_update_vars(self):
        model = MicroBenthosModel()

        from microbenthos.core import ModelVariable

        Mvar = mock.MagicMock(spec=ModelVariable)
        assert isinstance(Mvar, ModelVariable)
        # Mvar().var = var = mock.Mock()

        varnames = list('abcd')
        for v in varnames:
            model.env[v] = Mvar()
        model.env['nonvar'] = nonvar = mock.Mock()

        model.update_vars()

        nonvar.obj.assert_not_called()
        assert Mvar().var.updateOld.call_count == len(varnames)

    def test_update_equations(self):

        model = MicroBenthosModel()

        eqn = mock.Mock()

        names = ['eqn1', 'eqn2', 'eqn3']
        for n in names:
            model.equations[n] = eqn

        with pytest.raises(TypeError):
            model.update_equations()
            # requires dt argument

        dt = object()
        model.update_equations(dt)

        assert eqn.update_tracked_budget.call_count == len(names)
        for args, kwargs in eqn.update_tracked_budget.call_args_list:
            assert args == (dt,)
            assert kwargs == {}




