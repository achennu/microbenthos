import pytest
from fipy import PhysicalField

from microbenthos import SedimentDBLDomain


class TestModelDomain:
    """
    Test the sediment domain model
    """

    def test_init_empty(self):
        domain = SedimentDBLDomain()
        assert domain.mesh
        assert 'porosity' in domain.VARS
        assert len(domain.VARS['porosity']) == domain.mesh.nx

    def test_init_physical(self):
        cell_size = PhysicalField('20 mum')
        sediment_length = PhysicalField('1. cm')
        dbl_length = PhysicalField('1.0 mm')
        domain = SedimentDBLDomain(
            cell_size=cell_size,
            sediment_length=sediment_length,
            dbl_length=dbl_length
            )

        # internally converted to mm
        assert domain.cell_size.unit.name() == 'mm'

        assert domain.cell_size == cell_size
        assert domain.sediment_length == sediment_length
        assert domain.DBL_length == dbl_length
        assert 'sed_mask' in domain

    def test_init_float(self):
        # interpreted as millimeters
        cell_size = 0.3
        sediment_length = 30
        dbl_length = 3

        domain = SedimentDBLDomain(
            cell_size=cell_size,
            sediment_length=sediment_length,
            dbl_length=dbl_length
            )

        assert domain.cell_size.unit.name() == 'mm'

        assert domain.cell_size == PhysicalField(cell_size, 'mm')
        assert domain.sediment_length == PhysicalField(sediment_length, 'mm')
        assert domain.DBL_length == PhysicalField(dbl_length, 'mm')

    def test_fractional_cell_size(self):
        """
        When the sediment or DBL lengths are not divisible by the cell size, the sediment_length
        and DBL_length attributes get updated after number of cells is calculateds
        """

        cell_size = 0.2
        sediment_length = 10.1
        dbl_length = 1.35
        Nsed = int(sediment_length / cell_size)
        Ndbl = int(dbl_length / cell_size)

        domain = SedimentDBLDomain(cell_size=cell_size, sediment_length=sediment_length,
                                   dbl_length=dbl_length)

        assert Nsed == domain.sediment_cells
        assert Ndbl == domain.DBL_cells
        assert domain.sediment_length.value != sediment_length
        assert domain.sediment_length.value == Nsed * cell_size
        assert domain.DBL_length.value != dbl_length
        assert domain.DBL_length.value == Ndbl * cell_size

    def test_porosity(self):
        domain = SedimentDBLDomain()
        assert domain.sediment_porosity

        P = 0.35
        domain = SedimentDBLDomain(porosity=P)
        assert domain.sediment_porosity == P
        assert (domain.var_in_DBL('porosity') == 1.0).all()
        assert (domain.var_in_sediment('porosity') == P).all()

        # check that no new domain variable is created when just setting value
        Pvar = domain.VARS['porosity']
        newPvar = domain.set_porosity(0.66)
        assert newPvar is Pvar

    @pytest.mark.parametrize(
        'value, unit, err',
        [
            (4, None, None),
            (4.0, None, None),
            (3, 'kg', None),
            ('3.5', 'kg', ValueError),
            (PhysicalField(3, 'kg'), None, None),
            (PhysicalField(3, 'kg'), 'g', None)
            ]
        )
    def test_create_var(self, value, unit, err):

        domain = SedimentDBLDomain()
        if err:
            with pytest.raises(err):
                var = domain.create_var(name='myvar', value=value, unit=unit)
        else:
            var = domain.create_var(name='myvar', value=value, unit=unit)
            val = PhysicalField(value, unit)
            assert var.shape == domain.mesh.shape
            assert (var == val).all()
            if isinstance(value, PhysicalField):
                assert var.unit == value.unit
                # this overrides any supplied unit in creating cellvariables
            else:
                assert var.unit == val.unit

    def test_snapshot(self):
        domain = SedimentDBLDomain()
        state = domain.snapshot()

        statekeys = ('metadata', 'depths', 'distances')
        assert set(statekeys) == set(state)

        metakeys = ('cell_size', 'sediment_length', 'DBL_length', 'sediment_cells', 'DBL_cells',
                    'sediment_porosity', 'idx_surface', 'total_cells', 'total_length')
        assert set(state['metadata']) == set(metakeys)

        assert len(state['depths']['data_static'][0]) == len(domain.mesh.x())
        assert len(state['distances']['data_static'][0]) == len(domain.mesh.scaledCellDistances) - 1

        for k in ('depths', 'distances'):
            # check that the units are that of distances
            p = PhysicalField(1, state[k]['data_static'][1]['unit']).inUnitsOf('m')
            assert p.value > 0
