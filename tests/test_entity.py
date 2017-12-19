import pytest
from fipy import PhysicalField

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
        'unit, vtype, err',
        [('mol', 'cell', None),
         ('kg/s', 'basic', None),
         ('junk', 'basic', ValueError),
         (('kg', 'm'), 'basic', ValueError),
         ('m/s', 'junk', ValueError),
         ]
        )
    def test_create_check(self, unit, vtype, err):
        D = dict(unit=unit, vtype=vtype)

        if err:
            with pytest.raises(err):
                Variable.check_create(**D)
        else:
            Variable.check_create(**D)

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

    def test_create_cellvar(self):
        # check that domain is required
        # check that it returns the variable
        # Check that the conditions mentioned in the docstring are tested for inputs
        create = dict(value=3, unit='mol/l', hasOld=1, vtype='cell')
        name = 'var'
        v = Variable(name=name, create=create)

        domain = SedimentDBLDomain()
        v.set_domain(domain)

        v.setup()
        assert v.var is not None
        assert v.var.name == v.name
        assert v.var.shape == (domain.domain_Ncells,)
        assert (v.var == PhysicalField(3.0, 'mol/l')).all()


    def test_create_basicvar(self):
        # check that domain is required
        # check that it returns the variable
        # Check that the conditions mentioned in the docstring are tested for inputs
        create = dict(value=3, unit='mol/l', hasOld=1, vtype='basic')
        name = 'var'
        v = Variable(name=name, create=create)

        domain = SedimentDBLDomain()
        v.set_domain(domain)

        v.setup()
        assert v.var is not None
        assert v.var.name == v.name
        assert v.var.shape == ()
        assert (v.var == PhysicalField(3.0, 'mol/l')).all()


    def test_constrain(self):
        # test that boundary conditions get applied
        create = dict(value=3, unit='mol/l', vtype='cell')
        name = 'var'
        constraints = dict(
            top=PhysicalField(0.2e-3, 'mol/l'),
            bottom=PhysicalField(0.2e-3, 'mol/l'),
            dbl = PhysicalField(0.1e-3, 'mol/l'),
            sediment = PhysicalField(0.3e-4, 'mol/l')
            )

        v = Variable(name=name, create=create, constraints=constraints)

        domain = SedimentDBLDomain()
        v.set_domain(domain)

        v.setup()
        assert v.var is not None
        assert v.var.name == v.name
        assert len(v.var.constraints) == len(constraints)

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

        create = dict(value=3., unit=varunit, vtype='cell')
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
            assert v.var[0]() == conval
            print(v.var)

