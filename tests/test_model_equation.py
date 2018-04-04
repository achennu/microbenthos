import mock
import pytest
from fipy import CellVariable, PhysicalField, Variable, TransientTerm, DiffusionTerm, \
    ImplicitSourceTerm
from fipy.tools import numerix as np

from microbenthos import MicroBenthosModel
from microbenthos.model.equation import ModelEquation


@pytest.fixture()
def model():
    m = mock.Mock(MicroBenthosModel)
    m.get_object.return_value = rv = mock.Mock(CellVariable)
    # rv.as_term = rvt = mock.Mock()
    # rvt.return_value = Variable()
    return m


class TestModelEquation:
    def fail(self):
        pytest.xfail('Not implemented')

    def test_init(self, model):

        with pytest.raises(TypeError):
            eqn = ModelEquation()

        COEFF = 3
        eqn = ModelEquation(model, 'domain.abc', coeff=COEFF)
        assert eqn.varpath == 'domain.abc'
        assert eqn.term_transient == TransientTerm(var=eqn.var, coeff=COEFF)
        assert eqn.term_transient.coeff == COEFF
        assert eqn.term_diffusion is None
        assert eqn.sources_total is None
        assert not eqn.track_budget

    def test_finalize(self, model):

        eqn = ModelEquation(model, 'domain.abc', coeff=3)

        assert not eqn.finalized

        model.get_object.return_value = rv = mock.MagicMock(CellVariable)
        eqn.var.unit.name.return_value = 'mol/l'

        varpath = 'domain.var1'
        coeff = 1.1

        # model.get_object.return_value = rv = mock.MagicMock(CellVariable)
        rv.as_term = mock.Mock(return_value=mock.MagicMock(CellVariable))

        eqn.add_diffusion_term_from(varpath, coeff)

        print(eqn.var)

        with mock.patch('fipy.tools.numerix.zeros_like') as npMock:
            npMock.return_value = np.arange(10)

            eqn.finalize()
            assert eqn.finalized

            eqn.finalize()
            # should not raise an error

    def test_add_diffusion_term_from(self, model):
        # input should be path, coeff
        eqn = ModelEquation(model, 'domain.abc', coeff=5)

        model.get_object.return_value = rv = mock.Mock(CellVariable)
        rv.as_term = rvt = mock.Mock()
        rvt.return_value = v = Variable(1.5)

        varpath = 'domain.var1'
        coeff = 1.1

        assert eqn.term_diffusion is None
        assert eqn.diffusion_def is ()

        eqn.add_diffusion_term_from(varpath, coeff)
        assert eqn.term_diffusion == DiffusionTerm(var=eqn.var, coeff=v * coeff)
        assert eqn.diffusion_def == (varpath, coeff)

    def test_add_source_term_from(self, model):

        eqn = ModelEquation(model, 'domain.abc', coeff=5)
        model.get_object.return_value = rv = mock.Mock(CellVariable)
        rv.as_term = fullexpr = mock.Mock(CellVariable)
        fullexpr.return_value = mock.MagicMock(Variable)
        rv.expr = expr = mock.MagicMock(CellVariable)
        rv.as_source_for = source = mock.Mock()
        S0 = eqn.var
        S1 = 3
        S1term = ImplicitSourceTerm(var=eqn.var, coeff=S1)
        source.return_value = eqn.var, S0, S1

        varpath = 'domain.var1'
        coeff = 1.5

        with pytest.raises(ValueError):
            eqn.add_source_term_from(varpath, coeff=None)

        eqn.add_source_term_from(varpath, coeff)

        assert varpath in eqn.source_terms
        assert varpath in eqn.source_exprs
        assert varpath in eqn.source_formulae

        assert eqn.source_exprs[varpath] == coeff * fullexpr()
        assert eqn.source_formulae[varpath] == coeff * expr()
        # assert eqn.source_terms[varpath] == S0 + S1term

        with pytest.raises(RuntimeError):
            eqn.add_source_term_from(varpath, coeff)

    @pytest.mark.parametrize('track', [False, True])
    def test_snapshot(self, model, track):

        varpath = 'domain.var1'
        VAL = 1.5
        UNIT = 'mol/l'
        DCOEFF = 1.0

        model.get_object.return_value = var = mock.MagicMock(CellVariable)
        var.__getitem__.return_value = var0 = mock.MagicMock(CellVariable)
        model.domain.depths = depths = mock.MagicMock(CellVariable)
        depths.__getitem__.return_value = depth0 = mock.Mock()
        unitMock = var0 * depth0
        unitMock.inBaseUnits.return_value.unit = UNIT

        with mock.patch('fipy.tools.numerix.trapz') as trapzMock:
            trapzMock.return_value = 30

            eqn = ModelEquation(model=model, varpath=varpath, coeff=5, track_budget=track)
            eqn.sources_total = stotal = mock.MagicMock(CellVariable)

            # eqn not finalized
            with pytest.raises(RuntimeError):
                eqn.snapshot()

            eqn.finalized = True

            state = eqn.snapshot()

            assert isinstance(state, dict)

            statekeys = set(['sources', 'diffusion', 'transient', 'metadata'])
            if track:
                statekeys.add('tracked_budget')

            assert statekeys == set(state.keys())

            sourcekeys = ('data', 'metadata')
            assert set(sourcekeys) == set(state['sources'])

            assert set(('variable',)) == set(state['metadata'])

            diffkeys = ('metadata',)
            assert set(diffkeys) == set(state['diffusion'])

            transient = ('metadata',)
            assert set(transient) == set(state['transient'])

            if track:
                track_keys = ('var_expected', 'var_actual', 'sources_change',
                              'transport_change', 'time_step')
                assert set(track_keys) == set(state['tracked_budget'])

    def test_restore_from(self, model):

        varpath = 'domain.var1'
        VAL = [1.5]  # make a single value array in PhysicalField
        UNIT = 'mol/l'

        model.get_object.return_value = var = mock.MagicMock(CellVariable)
        var.__getitem__.return_value = var0 = mock.MagicMock(CellVariable)
        model.domain.depths = depths = mock.MagicMock(CellVariable)
        depths.__getitem__.return_value = depth0 = mock.Mock()
        unitMock = var0 * depth0
        unitMock.inBaseUnits.return_value.unit = UNIT

        with mock.patch('fipy.tools.numerix.trapz') as trapzMock:
            trapzMock.return_value = 0.0

            eqn = ModelEquation(model=model, varpath=varpath, coeff=5)

            trackedMock = mock.MagicMock(dict)
            trackedMock.__getitem__.return_value = (VAL, dict(unit=UNIT))
            PV = PhysicalField(VAL, UNIT)
            FIELDS = eqn.Tracked._fields

            eqn.restore_from(dict(tracked_budget=trackedMock), tidx=None)

            assert eqn.tracked == (PV,) * len(FIELDS)

    def test_sources_rate(self):
        self.fail()

    def test_transport_rate(self):
        self.fail()

    def test_var_quantity(self):
        self.fail()

    def test_update_tracked_budget(self):
        self.fail()

    def test_track_budget(self):
        self.fail()
