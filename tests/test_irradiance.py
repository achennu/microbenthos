import numpy as np
import pytest
from fipy import PhysicalField, CellVariable, Variable
from fipy.tools import numerix

from microbenthos import SedimentDBLDomain, Irradiance, IrradianceChannel


@pytest.fixture()
def domain():
    return SedimentDBLDomain()


@pytest.fixture(
    params=[
        [],
        [('cyano', PhysicalField(230, 'cm**2/g'))],
        [('psb', PhysicalField(13, 'cm**2/g'))],
        [('cyano', PhysicalField(230, 'cm**2/g')), ('psb', PhysicalField(13, 'cm**2/g'))],
        ],
    ids=('no_atten', 'cyano', 'psb', 'cyano+psb')
    )
def chan(request, domain):
    ch = IrradianceChannel('solar', k_mods=request.param)
    ch.set_domain(domain)

    for var, val in request.param:
        domain.create_var(var, value=numerix.random.random_sample(domain.mesh.shape) * 10,
                          unit='mg/cm**3')

    return ch


@pytest.fixture(params=[
    dict(name='par', k0=PhysicalField(15.3, '1/cm')),
    dict(name='par', k0=PhysicalField(12.1, '1/cm'),
         k_mods=[('cyano', PhysicalField(230, 'cm**2/g')),
                 ('psb', PhysicalField(13, 'cm**2/g'))]),
    ],
    ids=('par_k0', 'par_k0+k_mods')
    )
def irrad(request, domain):
    print('IRRAD FROM {} {}'.format(type(request.param), request.param))
    irrad = Irradiance(channels=[request.param])
    irrad.set_domain(domain)

    for var, val in request.param.get('k_mods', []):
        domain.create_var(var, value=numerix.random.random_sample(domain.mesh.shape) * 10,
                          unit='mg/cm**3')

    return irrad


class TestIrradianceChannel:
    def test_init_empty(self):
        with pytest.raises(TypeError):
            ch = IrradianceChannel()

    def test_init(self):
        ch = IrradianceChannel('par')
        assert ch.name == 'par'
        assert ch.intensities is None
        assert not ch.k_mods

    def test_domain(self, domain):
        # Test that adding domain works correctly
        ch = IrradianceChannel('solar')

        assert ch.intensities is None

        with pytest.raises(RuntimeError):
            ch.setup()

        ch.set_domain(domain)
        ch.setup()

        assert ch.intensities is not None
        assert ch.check_domain()

    def test_setup_atten(self, chan):
        # test that calling setup multiple times raises RuntimeError if k_mods are present

        assert chan.intensities is None
        chan.setup()

        assert chan.intensities is not None
        if chan.k_mods:
            with pytest.raises(RuntimeError):
                chan.setup()

    def test_setup_intensities(self, chan):
        chan.setup()
        assert isinstance(chan.intensities, CellVariable)
        assert chan.name == chan.intensities.name

    def test_attenuation_dimensionless(self, chan):
        # Ensure that k_var * domain.distances is dimensionless
        chan.setup()
        assert isinstance(chan.attenuation_profile, np.ndarray)
        assert isinstance(chan.attenuation_profile, numerix.ndarray)

    def test_update_intensity(self, chan):
        # check that setting surface intensity updates the intensity profile
        chan.setup()
        I = chan.intensities.numericValue
        assert (I == 0).all()

        chan.update_intensities(100)
        assert numerix.allclose((100 * chan.attenuation_profile), chan.intensities.numericValue)

    def test_snapshot(self, chan):
        # test the structure of snapshot dict
        # test that snapshot contains keys attenuation, intensity and metadata
        chan.setup()

        state = chan.snapshot()

        keys = ('attenuation', 'metadata', 'intensity')
        assert all(k in state for k in keys)

        att = state['attenuation']
        assert 'data' in att
        assert att['data'][1]['unit'] == chan.k_var.unit.name()

        assert 'metadata' in att
        for var, val in chan.k_mods:
            assert att['metadata'][var] == str(val)

        inten = state['intensity']
        assert 'data' in inten
        assert inten['data'][1]['unit'] == '1'
        # intensity is unitless
        assert 'metadata' not in inten

        assert 'k0' in state['metadata']
        assert state['metadata']['k0'] == chan.k0


class TestIrradiance:
    def test_init_empty(self):
        I = Irradiance()
        assert I.hours_total.value == 24
        assert I.day_fraction == 0.5
        assert I.zenith_level == 100
        assert I._profile

    def test_init_physicalfield(self):
        ht = PhysicalField(8, 'h')
        I = Irradiance(hours_total=ht)
        assert I.hours_total == ht

    @pytest.mark.parametrize('hours_total', (3, 4, 10, 18, 24, 32, 48, 50))
    @pytest.mark.parametrize('day_fraction', (0, 0.1, 0.2, 0.5, 0.8, 0.9, 1.0))
    def test_fractions_hours(self, hours_total, day_fraction):
        if not 2 <= hours_total <= 48:
            with pytest.raises(ValueError):
                I = Irradiance(hours_total=hours_total, day_fraction=day_fraction)
        elif not 0 < day_fraction < 1:
            with pytest.raises(ValueError):
                I = Irradiance(hours_total=hours_total, day_fraction=day_fraction)
        else:
            I = Irradiance(hours_total=hours_total, day_fraction=day_fraction)

            assert I.hours_total.value == hours_total
            assert I.day_fraction == day_fraction

    def test_setup(self, irrad):
        # check that setting domain:
        # creates surface_irrad variable
        # also sets domain on channels
        # sets up channel
        irrad.setup()
        assert isinstance(irrad.surface_irrad, Variable)
        assert not isinstance(irrad.surface_irrad, CellVariable)  # should be single-valued
        assert float(irrad.surface_irrad) == 0.0

    def test_update_time(self):
        # test that updating time changes the surface_irrad value
        # test for inputs float, PhysicalField and Variable

        H = 4
        irrad = Irradiance(hours_total=H)
        irrad.set_domain(SedimentDBLDomain())
        irrad.setup()

        # irrad.setup(SedimentDBLDomain())
        assert irrad.surface_irrad is not None
        irrad.setup()
        old = irrad.surface_irrad.copy()
        irrad.on_time_updated(irrad.hours_total)
        assert irrad.surface_irrad() == old

        old = irrad.surface_irrad.copy()
        irrad.on_time_updated(H / 2.0 * 3600.0)
        assert irrad.surface_irrad() == irrad.zenith_level

    def test_snapshot(self, irrad):
        # Irradiance snapshot should have metadata & channels

        irrad.setup()
        state = irrad.snapshot()

        meta = state['metadata']
        keys = ('hours_total', 'day_fraction', 'zenith_time', 'zenith_level')
        assert set(keys) == set(meta)
        for k in keys:
            attr = getattr(irrad, k)
            if isinstance(attr, PhysicalField):
                assert meta[k] == str(attr)

            else:
                assert meta[k] == attr

        channels = state['channels']
        for ch in irrad.channels:
            assert ch in channels
            # just check one field to confirm snapshot of channel
            assert channels[ch]['metadata']['k0'] == str(irrad.channels[ch].k0)
