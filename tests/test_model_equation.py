import mock
import pytest
from fipy import CellVariable, PhysicalField

from microbenthos import MicroBenthosModel
from microbenthos.model.model import ModelEquation
from microbenthos.utils import snapshotters


@pytest.fixture()
def model():
    m = mock.Mock(MicroBenthosModel)
    m.get_object.return_value = mock.Mock(CellVariable)
    return m


# @pytest.mark.xfail(reason='Not implemented')
class TestModelEquation:
    def fail(self):
        pytest.xfail('Not implemented')

    def test_init(self, model):

        with pytest.raises(TypeError):
            eqn = ModelEquation()

        eqn = ModelEquation(model, 'domain.abc', coeff=3)
        assert eqn.varpath == 'domain.abc'
        assert eqn.term_transient.coeff == 3
        assert eqn.term_diffusion is None
        assert eqn.sources_total == 0
        assert not eqn.track_budget

    def test_finalize(self):
        self.fail()

    def test_term_transient(self):
        self.fail()

    def test__get_term_obj(self):
        self.fail()

    def test__add_diffusion_term(self):
        self.fail()

    def test_add_diffusion_term_from(self):
        self.fail()

    def test_term_diffusion(self):
        self.fail()

    def test_add_source_term_from(self):
        self.fail()

    def test_RHS_terms(self):
        self.fail()

    def test_sources_total(self):
        self.fail()

    @pytest.mark.parametrize('track', [False, True])
    def test_snapshot(self, model, track):

        v = PhysicalField([3, 4, 5])

        with mock.patch('microbenthos.utils.snapshot_var') as msnapshot:

            msnapshot.return_value = (v.value, {'unit': v.unit.name()})

            ret = snapshotters.snapshot_var(34)
            print(ret)

            eqn = ModelEquation(model, 'domain.abc', 4)

            with mock.patch.multiple(ModelEquation,
                                     var_quantity=mock.DEFAULT,
                                     sources_rate=mock.DEFAULT,
                                     transport_rate=mock.DEFAULT,
                                     ) as mobj:

                mobj['var_quantity'].return_value = v
                mobj['sources_rate'].return_value = v
                mobj['transport_rate'].return_value = v

                eqn.track_budget = True

                state = eqn.snapshot()
                print('Got state with keys: {}'.format(state.keys()))

                vv = eqn.var_quantity()
                assert vv is v

                statekeys = ['sources', 'diffusion', 'transient', 'metadata']

                if eqn.track_budget:
                    statekeys.append('tracked_budget')

                assert set(statekeys) == set(state)

                assert set(('variable',)) == set(state['metadata'])

                sourcekeys = ('data', 'metadata')
                assert set(sourcekeys) == set(state['sources'])

                diffkeys = ('metadata',)
                assert set(diffkeys) == set(state['diffusion'])

                transient = ('metadata',)
                assert set(transient) == set(state['transient'])

                if track:
                    track_keys = ('var_expected', 'var_actual', 'sources_change',
                                  'transport_change', 'time_step')
                    assert set(track_keys) == set(state['tracked_budget'])

    def test_sources_rate(self):
        self.fail()

    def test_transport_rate(self):
        self.fail()

    def test_var_quantity(self):
        self.fail()

    def test_update_tracked_quantities(self):
        self.fail()

    def test_track_quantites(self):
        self.fail()
