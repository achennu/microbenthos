import mock
import pytest
from fipy import PhysicalField
from fipy.tools import numerix

from microbenthos import ModelVariable, SedimentDBLDomain

PF = PhysicalField


class TestVariable:
    def test_init_empty(self):
        with pytest.raises(TypeError):
            ModelVariable()

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
                ModelVariable.check_create(**D)
        else:
            ModelVariable.check_create(**D)

    def test_create_check_name(self):
        # supplying name in create params should raise an error
        with pytest.raises(ValueError):
            ModelVariable.check_create(name='heh ho')

        ModelVariable.check_create()

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
                ModelVariable.check_constraints(constraints)
        else:
            ModelVariable.check_constraints(constraints)

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
        # creation casts it into base units
        create = dict(value=value, unit=unit, hasOld=hasOld)
        name = 'myVar'
        v = ModelVariable(name=name, create=create)

        domain = SedimentDBLDomain()
        v.set_domain(domain)
        v.setup()
        assert v.var is domain[name]
        assert v.var.name == v.name
        assert v.var.shape == domain.mesh.shape
        assert (v.var() == PhysicalField(value, unit).inBaseUnits()).all()

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
            # [('sediment', PhysicalField('0.4e-3 mol/l')), ('bottom', PhysicalField(0.8e-3,
            # 'mol/l'))],
            ],
        ids=['top', 'bottom', 'dbl', 'sediment', 'top+bottom', 'dbl+bottom', 'sediment+top']
        )
    def test_constrain(self, constraints):
        # test that boundary conditions get applied
        create = dict(value=3.3, unit='mol/l')
        name = 'var'

        constraints = dict(constraints)

        v = ModelVariable(name=name, create=create, constraints=constraints)

        domain = SedimentDBLDomain()
        v.set_domain(domain)

        v.setup()
        assert v.var is not None
        assert v.var.name == v.name
        constraints_count = sum([1 for c in constraints if c not in ('top', 'bottom')])
        assert len(v.var.constraints) == constraints_count, 'Var constraints: {} does not match ' \
                                                            'specified: {}'.format(
            (v.var.constraints), constraints
            )
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
            # (' ', 'kg'),
            # ('kg', ' '),
            ('mol/l', '10**-3*mol/l'),
            ('mol/l', 'mol/m**3'),
            ('kg', 'g'),
            ('m/min', 'km/h'),

            ]
        )
    def test_constrain_with_unit(self, varunit, conunit):

        create = dict(value=3., unit=varunit, hasOld=True)
        name = 'MyVar'
        conval = PhysicalField(5, conunit)
        constraints = dict(
            top=conval,
            )

        v = ModelVariable(name=name, create=create, constraints=constraints)

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
            v.var.updateOld()
            assert v.var.faceValue[0] == conval

    def test_seed(self):
        v = ModelVariable(name='myvar',
                     create=dict(unit='mol/l'),
                     seed=None)
        assert True

    @pytest.mark.parametrize(
        'unit,loc,scale,coeff,error',
        [
            (None, 3, 2, 1, None),
            (None, PF(3, 'mm'), PF(2, 'mm'), 1, None),
            ('mol/l', PF(3, 'mm'), PF(2, 'mm'), PF(1, "mol/m**3"), None),
            ('mol/l', PF(3, 'mm'), PF(2, 'mm'), PF(1, "mol/s"), ValueError),
            ]
        )
    def test_seed_normal(self, unit, loc, scale, coeff, error):

        create = dict(value=3., unit=unit, hasOld=True)
        name = 'MyVar'
        seed = dict(
            profile='normal',
            params=dict(
                loc=loc,
                scale=scale,
                coeff=coeff)
            )
        v = ModelVariable(name=name, create=create, seed=seed)

        domain = SedimentDBLDomain()
        v.domain = domain
        if error:
            with pytest.raises(error):
                v.setup()
            return

        else:

            v.setup()

            from scipy.stats import norm
            from fipy.tools import numerix

            C = 1.0 / numerix.sqrt(2 * numerix.pi)

            # loc and scale should be in units of the domain mesh
            if hasattr(loc, 'unit'):
                loc_ = loc.inUnitsOf(domain.depths.unit).value
            else:
                loc_ = loc

            if hasattr(scale, 'unit'):
                scale_ = scale.inUnitsOf(domain.depths.unit).value
            else:
                scale_ = scale

            if unit:
                coeff = PF(coeff, unit)

            normrv = norm(loc=loc_, scale=C ** 2 * scale_)
            val = coeff * normrv.pdf(domain.depths) * C * scale_

            # from pprint import pprint
            # pprint(zip(v.var, val))
            print(type(val), type(v.var))
            if unit:
                # array comparison between variable & physicalfield is problematic
                val = val.numericValue

            assert numerix.allclose(v.var.numericValue, val)

    @pytest.mark.parametrize(
        'params,constraints,error',
        [

            (None, None, ValueError),  # no profile params nor constraints given
            (None, dict(top=13, bottom=34), None),
            (dict(start=14), dict(bottom=18), None),
            (dict(stop=19), dict(top=3), None),
            (dict(stop=PhysicalField(19, 'km/kg')), dict(top=3), None),
            (dict(stop=PhysicalField(19, 'km/kg')), dict(top=PhysicalField(3, 'km/kg')), None),
            (dict(stop=19), dict(top=PhysicalField(3, 'km/kg')), None),
            (None, dict(top=PhysicalField(3, 'km/kg'), bottom=PhysicalField(17, 'km/kg')), None),
            (None, dict(top=PhysicalField(3, 'm/g'), bottom=PhysicalField(17, 'km/kg')), None),
            (None, dict(top=PhysicalField(3, 'm/g'), bottom=PhysicalField(17, 'm/kg')), None),
            (None, dict(top=PhysicalField(3, 'm'), bottom=PhysicalField(17, 'm/kg')), TypeError),
            # wrong units
            ]
        )
    def test_seed_linear_from_constraints(self, params, constraints, error):

        seed = dict(profile='linear')
        if params:
            seed['params'] = params

        unit = 'km/kg'
        N = 10

        v = ModelVariable(name='mvar', create=dict(value=3.2, unit=unit),
                     seed=seed, constraints=constraints,
                     )
        v.domain = mock.Mock(SedimentDBLDomain)
        v.domain.create_var.return_value = PhysicalField([34] * N, unit)
        v.domain.mesh = mock.Mock()
        v.domain.idx_surface = mock.Mock()
        v.constrain = mock.Mock()

        if error:
            with pytest.raises(error):
                v.setup()

        else:
            v.setup()

            if params is None:
                params = {}

            if constraints is None:
                constraints = {}

            startval = PhysicalField(params.get('start', constraints.get('top')), unit).inUnitsOf(
                unit).value
            stopval = PhysicalField(params.get('stop', constraints.get('bottom')), unit).inUnitsOf(
                unit).value

            expected = PhysicalField(numerix.linspace(startval, stopval, N), unit)

            assert numerix.array_equal(v.var, expected)
