import pytest
from fipy import PhysicalField
from fipy.tools import numerix

from microbenthos import Entity, SedimentDBLDomain, DomainEntity, Variable


class TestEntity:
    def test_init(self):
        e = Entity()
        assert e

    def test_update_time(self):
        # update to clock time
        e = Entity()
        with pytest.raises(TypeError):
            e.update_time()
        e.update_time(2)
        e.update_time(3.5)
        e.update_time(PhysicalField('35 s'))

    @pytest.mark.xfail(reason='not implemented')
    def test_from_params(self):
        raise NotImplementedError('For Entity.from_params()')

    @pytest.mark.xfail(reason='not implemented')
    def test_from_dict(self):
        raise NotImplementedError('For Entity.from_dict()')


class TestDomainEntity:
    def test_add_domain(self):
        e = DomainEntity()
        D = SedimentDBLDomain()

        # with pytest.raises(TypeError):
        #     e.domain = tuple()
        # This no longer raises a TypeError, but just issues a log warning

        e.domain = D

        assert e.domain is D

        with pytest.raises(RuntimeError):
            e.domain = D

    def test_setup(self):
        # should be not implemented

        e = DomainEntity()
        with pytest.raises(NotImplementedError):
            e.setup()


class TestVariable:
    def test_init_empty(self):
        with pytest.raises(TypeError):
            Variable()

    @pytest.mark.parametrize(
        'unit, err',
        [('mol', None),
         ('kg/s', None),
         ('junk', ValueError),
         (('kg', 'm'), ValueError),
         ('m/s', None),
         ]
        )
    def test_create_check_unit(self, unit, err):
        D = dict(unit=unit)

        if err:
            with pytest.raises(err):
                Variable.check_create(**D)
        else:
            Variable.check_create(**D)

    def test_create_check_name(self):
        # supplying name in create params should raise an error
        with pytest.raises(ValueError):
            Variable.check_create(name='heh ho')

        Variable.check_create()

    @pytest.mark.parametrize(
        'constraints, err',
        [
            ([('top', 1)], None),
            ([('bottom', 1)], None),
            ([('dbl', 1)], None),
            ([('sediment', 1)], None),
            ([('top', 0), ('bottom', 1)], None),
            ([('atop', 0), ('bottom', 1)], ValueError),
            ([('atop', 0), ('badttom', 1)], ValueError),
            ([('unknown', 1)], ValueError),
            (('top', 1), ValueError),
            (None, ValueError),
            ('234', ValueError),
            ([('top', [3, 4])], ValueError),
            ([('top', 'abc')], ValueError),
            ([('top', '1.3')], None),
            ([('top', ['1.3'])], ValueError),
            ]
        )
    def test_constraints_check(self, constraints, err):
        if err:
            with pytest.raises(err):
                Variable.check_constraints(constraints)
        else:
            Variable.check_constraints(constraints)

    @pytest.mark.parametrize(
        'value, unit, hasOld',
        [
            (3, 'mol/l', 0),
            (3.0, 'mol/l', 0),
            (3.0, 'mol/l', 1),
            (2.3, None, 0)
        ]
        )
    def test_create_var(self, value, unit, hasOld):
        create = dict(value=value, unit=unit, hasOld=hasOld)
        name = 'myVar'
        v = Variable(name, create=create)

        domain = SedimentDBLDomain()
        v.set_domain(domain)
        v.setup()
        assert v.var is domain[name]
        assert v.var.name == v.name
        assert v.var.shape == domain.mesh.shape
        assert (v.var == PhysicalField(value, unit)).all()


    @pytest.mark.parametrize(
        'constraints',
        [
            [('top', PhysicalField('0.2e-3 mol/l'))],
            [('bottom', PhysicalField('0.2e-3 mol/l'))],
            [('dbl', PhysicalField('0.2e-3 mol/l'))],
            [('sediment', PhysicalField('0.4e-3 mol/l'))],
            [('top', PhysicalField('0.2e-3 mol/l')), ('bottom', PhysicalField(0, 'mol/l'))],
            [('dbl', PhysicalField('0.4e-3 mol/l')), ('bottom', PhysicalField(0.8e-3, 'mol/l'))],
            [('sediment', PhysicalField('0.4e-3 mol/l')), ('top', PhysicalField(0.8e-3, 'mol/l'))],
            # TODO: Figure out a pragmatic policy for these invalid pairs
            # [('dbl', PhysicalField('0.4e-3 mol/l')), ('top', PhysicalField(0.8e-3, 'mol/l'))],
            # [('sediment', PhysicalField('0.4e-3 mol/l')), ('bottom', PhysicalField(0.8e-3,'mol/l'))],
            ],
        ids=['top', 'bottom', 'dbl', 'sediment', 'top+bottom', 'dbl+bottom', 'sediment+top']
        )
    def test_constrain(self, constraints):
        # test that boundary conditions get applied
        create = dict(value=3.3, unit='mol/l')
        name = 'var'

        constraints = dict(constraints)

        v = Variable(name=name, create=create, constraints=constraints)

        domain = SedimentDBLDomain()
        v.set_domain(domain)

        v.setup()
        assert v.var is not None
        assert v.var.name == v.name
        assert len(v.var.constraints) == len(constraints)
        if 'top' in constraints:
            numerix.array_equal(v.var[0], constraints['top'])
        if 'bottom' in constraints:
            numerix.array_equal(v.var[-1], constraints['bottom'])
        if 'dbl' in constraints:
            assert (v.var[:domain.idx_surface] == constraints['dbl']).all()
        if 'sediment' in constraints:
            assert (v.var[domain.idx_surface:] == constraints['sediment']).all()

    @pytest.mark.parametrize(
        'varunit, conunit',
        [
            (' ', 'kg'),
            ('kg', ' '),
            ('mol/l', '10**-3*mol/l'),
            ('mol/l', 'mol/m**3'),
            ('kg', 'g'),
            ('m/min', 'km/h'),

            ]
        )
    def test_constrain_with_unit(self, varunit, conunit):

        create = dict(value=3., unit=varunit)
        name = 'MyVar'
        conval = PhysicalField(5, conunit)
        constraints = dict(
            top=conval,
            )

        v = Variable(name=name, create=create, constraints=constraints)

        domain = SedimentDBLDomain()
        v.set_domain(domain)

        try:
            varval = conval.inUnitsOf(varunit)
        except TypeError:
            # incompatible units
            varval = None

        if varval is None:
            with pytest.raises(TypeError):
                v.setup()

        else:
            v.setup()
            assert numerix.allclose(v.var.numericValue[0], conval.numericValue)
            assert v.var[0].unit.name() == varunit
