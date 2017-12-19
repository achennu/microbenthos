import pytest

from microbenthos.irradiance import Irradiance, IrradianceChannel


class TestIrradianceChannel:
    def test_init_empty(self):
        with pytest.raises(TypeError):
            ch = IrradianceChannel()

    def test_init(self):
        ch = IrradianceChannel('par')
        assert ch.name == 'par'
        assert ch.intensities is None
        assert not ch.k_mods

    @pytest.mark.xfail(reason='Not implemented')
    def test_domain(self):
        # Test that adding domain works correctly
        raise NotImplementedError

    @pytest.mark.xfail(reason='Not implemented')
    def test_setup(self):
        # test that calling setup multiple times does not affect the state
        # check that intensities is unitless
        raise NotImplementedError

    @pytest.mark.xfail(reason='Not implemented')
    def test_k_mods(self):
        # Test that k_mods can be given in the call to __init__ as well as the call to setup(),
        # and they are both combined
        raise NotImplementedError

    @pytest.mark.xfail(reason='Not implemented')
    def test_attenuation(self):
        # Ensure that k_var * domain.distances is dimensionless
        raise NotImplementedError

    @pytest.mark.xfail(reason='Not implemented')
    def test_update_intensity(self):
        # check that setting surface intensity updates the intensity profile
        raise NotImplementedError


class TestIrradiance:
    def test_init_empty(self):
        I = Irradiance()
        assert I.hours_total.value == 24
        assert I.day_fraction == 0.5
        assert I.max_level == 100
        assert I._profile

    def test_hours(self):
        H = 20
        I = Irradiance(hours_total=H)
        assert I.hours_total.value == H

        # Limits for hours_total is (4, 48)
        with pytest.raises(ValueError):
            I = Irradiance(hours_total=3.99)

        with pytest.raises(ValueError):
            I = Irradiance(hours_total=48.01)

    @pytest.mark.xfail(reason='Not implemented')
    def test_setup(self):
        # check that setting domain:
        # creates surface_irrad variable
        # also sets domain on channels
        # sets up channel
        raise NotImplementedError

    @pytest.mark.xfail(reason='Not implemented')
    def test_channel_create(self):
        # test creation of IrradianceChannel
        raise NotImplementedError

    @pytest.mark.xfail(reason='Not implemented')
    def test_update_time(self):
        # test that updating time changes the surface_irrad value
        # test for inputs float, PhysicalField and Variable
        raise NotImplementedError
