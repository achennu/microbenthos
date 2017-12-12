
from __future__ import division

import logging
logger = logging.getLogger(__name__)
from .base.entity import Entity
from scipy.stats import cosine
from fipy.tools import numerix
from fipy import PhysicalField


class Irradiance(Entity):

    def __init__(self, hours_total = 24, day_fraction=0.5):
        """
        Entity to implement irradiance through the sediment column

        Args:
            hours_total (int, float): Number of hours in the day
            day_fraction (float): Fraction of daylength which is illuminated
        """
        super(Irradiance, self).__init__()
        self.channels = self.features

        self.hours_total = PhysicalField(hours_total, 'h')
        if not (4 < self.hours_total.value < 48):
            raise ValueError('Hours total {} should be between (4, 48)'.format(self.hours_total))
        day_fraction = float(day_fraction)
        if not (0 < day_fraction < 1):
            raise ValueError("Day fraction should be between 0 and 1")

        self.day_fraction = day_fraction
        self.hours_day = day_fraction * self.hours_total
        self.clocktime_zenith = self.hours_day
        self.max_level = 100

        C = 1.0 / numerix.sqrt(2 * numerix.pi)
        # to scale the cosine distribution from 0 to 1 (at zenith)
        self._profile = cosine(
            loc=self.clocktime_zenith, scale=C**2 * self.hours_day)
        # This profile with loc=zenith means that the day starts at "midnight" and zenith occurs
        # in the center of the daylength

        logger.debug('Created Irradiance: {}'.format(self))

    def __repr__(self):
        # return '{}(total={},day={:.1f},zenith={:.1f)'.format(self.name, self.hours_total,
        #                                                  self.hours_day, self.clocktime_zenith)
        return 'Irradiance(total={},{})'.format(self.hours_total, '+'.join(self.channels))

    def setup(self, channels=None):
        """
        When a domain is added, the attenuation channels can be setup

        See :meth:`.create_channel` for information on the `channels` argument.
        Returns:
        """
        self.check_domain()

        self.surface_irrad = self.domain.create_var('irrad_surface', vtype='basic')

        if channels:
            for chname, chinfo in channels.iteritems():
                self.create_channel(chname, **chinfo)

        for channel in self.channels.itervalues():
            if not channel.has_domain:
                channel.domain = self.domain
            channel.setup()

    def create_channel(self, name, k0=0, k_mods=None):
        """
        Add a channel of irradiance, such as PAR or NIR

        This creates variables for the channel intensities, for the attenuation values.

        Args:
            name: The channel name
            k0: The base attenuation for this channel through the sediment
            k_mods: A list of (var, coeff) pairs to add attenuation sources to k0

        Returns:

        """
        if name in self.channels:
            raise RuntimeError('Channel {} already created'.format(name))

        channel = IrradianceChannel(name=name, k0=k0, k_mods=k_mods)
        self.channels[name] = channel

        if self.has_domain:
            channel.domain = self.domain
            channel.setup()

        return channel

    def update_time(self, clocktime):
        """
        Update the surface irradiance according to the clock time

        Args:
            clocktime: The simulation clock time (if just a number, it is in seconds)

        Returns:

        """
        if isinstance(clocktime, PhysicalField):
            clocktime_ = clocktime.inBaseUnits() % self.hours_total.inBaseUnits()
        else:
            clocktime_ = clocktime % self.hours_total.numericValue

        # logger.debug('clocktime % hours_total =  {} % {} = {}'.format(
        #     clocktime, self.hours_total, clocktime_))
        # logger.debug('Profile level for clocktime {}: {}'.format(
        #     clocktime, self._profile.pdf(clocktime_)))

        surface_value = self.max_level * self.hours_day.numericValue / 2 * \
                        self._profile.pdf(clocktime_)

        self.surface_irrad.value = surface_value
        logger.debug('Updated for time {} surface irradiance: {}'.format(clocktime,
                                                                      self.surface_irrad))

        for channel in self.channels.itervalues():
            channel.update_intensities(self.surface_irrad)


class IrradianceChannel(Entity):

    def __init__(self, name, k0=PhysicalField(0, '1/cm'), k_mods=None):
        """
        An irradiance channel

        This creates variables for the channel intensities, for the attenuation values.

        Args:
            name: The channel name
            source: The :class:`Irradiance` source
            k0: The base attenuation for this channel through the sediment

        Returns:
        """
        super(IrradianceChannel, self).__init__()
        self.name = name
        self.intensities = None

        try:
            self.k0 = PhysicalField(k0, '1/cm')
        except TypeError:
            raise ValueError('Invalid value for k0: {}'.format(k0))

        self.k_var = None
        self.k_mods = k_mods or []
        self._mods_added = {}
        logger.debug('created irradiance channel {}'.format(self))

    def __repr__(self):
        return '{}:{!r}'.format(self.name, self.k_var)

    def setup(self, k_mods=None):
        """
        Define attenuations when domain is available
        Returns:

        """
        self.check_domain()

        if self.intensities is None:
            self.intensities = self.domain.create_var(self.name)

            self.define_attenuation()

        if k_mods:
            self.k_mods.extend(k_mods)

        for source in self.k_mods:
            var, coeff = source
            self.add_attenuation_source(var=var, coeff=coeff)

    @property
    def k_name(self):
        return '{}_k'.format(self.name)

    def define_attenuation(self):
        """
        Create the attenuation variable for the channel
        """
        if self.k_name not in self.domain.VARS:
            k_var = self.domain.create_var(self.k_name, value=self.k0.value,
                                            unit=self.k0.unit)
            k_var[:self.domain.idx_surface] = 0
            self.k_var = k_var

    def add_attenuation_source(self, var, coeff):
        """
        Add an extra source of attenuation to this channel, for example through biomass that
        attenuates light intensity

        The term `var * coeff` should have dimensions of 1/length

        Args:
            var (str): The domain variable for the source
            coeff: The coefficient to multiply with

        Returns:

        """
        self.check_domain()
        if var in self._mods_added:
            raise RuntimeError('attenuation source {} already added!')

        atten_source = self.domain.VARS[var] * coeff
        try:
            atten_source.inUnitsOf('1/m')
        except TypeError:
            raise ValueError('Units of var * coeff is not 1/length, but {}'.format(
                atten_source.inBaseUnits().unit.name()))

        self.k_var += atten_source
        self._mods_added[var] = atten_source
        logger.info('Added attenuation source from {!r} and coeff={}'.format(var, coeff))

    @property
    def attenuation_profile(self):
        """
        Calculates the attenuation profile for this channel

        This returns the cumulative product of attenuation factors in each cell of the domain,
        allowing this to be multiplied by a surface value to get the irradiance profile.

        """
        return numerix.cumprod(numerix.exp(-1 * self.k_var * self.domain.distances))

    def update_intensities(self, surface_level):
        """
        Update the intensities of the channel based on the surface level

        Args:
            surface_level: The variable indicating the surface intensity

        Returns:
            The light profile
        """
        logger.debug('Updating intensities for surface value: {}'.format(surface_level))
        intensities = self.attenuation_profile * surface_level
        self.intensities.value = intensities
        return intensities






