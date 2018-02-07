from __future__ import division

import logging

from fipy import PhysicalField, Variable
from fipy.tools import numerix
from scipy.stats import cosine
from .entity import DomainEntity
from ..utils.snapshotters import snapshot_var


class Irradiance(DomainEntity):
    def __init__(self, hours_total = 24, day_fraction = 0.5, channels = None, **kwargs):
        """
        Entity to implement irradiance through the sediment column

        Args:
            hours_total (int, float): Number of hours in the day
            day_fraction (float): Fraction of daylength which is illuminated
            See :meth:`.create_channel` for information on the `channels` argument.
            **kwargs: passed to superclass
        """
        self.logger = kwargs.get('logger') or logging.getLogger(__name__)
        self.logger.debug('Init in Irradiance')
        kwargs['logger'] = self.logger
        super(Irradiance, self).__init__(**kwargs)
        self.channels = {}

        self.hours_total = PhysicalField(hours_total, 'h')
        if not (2 <= self.hours_total.value <= 48):
            raise ValueError('Hours total {} should be between (2, 48)'.format(self.hours_total))
        day_fraction = float(day_fraction)
        if not (0 < day_fraction < 1):
            raise ValueError("Day fraction should be between 0 and 1")

        self.day_fraction = day_fraction
        self.hours_day = day_fraction * self.hours_total
        self.zenith_time = self.hours_day
        self.zenith_level = 100

        C = 1.0 / numerix.sqrt(2 * numerix.pi)
        # to scale the cosine distribution from 0 to 1 (at zenith)
        self._profile = cosine(
            loc=self.zenith_time, scale=C ** 2 * self.hours_day)
        # This profile with loc=zenith means that the day starts at "midnight" and zenith occurs
        # in the center of the daylength

        self.surface_irrad = None

        if channels:
            for chinfo in channels:
                self.create_channel(**chinfo)

        self.logger.debug('Created Irradiance: {}'.format(self))

    def __repr__(self):
        # return '{}(total={},day={:.1f},zenith={:.1f)'.format(self.name, self.hours_total,
        #                                                  self.hours_day, self.zenith_time)
        return 'Irradiance(total={},{})'.format(self.hours_total, '+'.join(self.channels))

    def setup(self, **kwargs):
        """
        When a domain is added, the attenuation for the channels can be setup
        """
        self.check_domain()
        model = kwargs.get('model')

        if self.surface_irrad is None:
            self.surface_irrad = Variable(name='irrad_surface', value=0.0, unit=None)

        for channel in self.channels.itervalues():
            if not channel.has_domain:
                channel.domain = self.domain
            channel.setup(model=model)

    @property
    def is_setup(self):
        return all([c.is_setup for c in self.channels.values()])

    def create_channel(self, name, k0 = 0, k_mods = None, model=None):
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
            channel.setup(model=model)

        return channel

    def on_time_updated(self, clocktime):
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

        # logger.debug('clock % hours_total =  {} % {} = {}'.format(
        #     clock, self.hours_total, clocktime_))
        # logger.debug('Profile level for clock {}: {}'.format(
        #     clock, self._profile.pdf(clocktime_)))

        surface_value = self.zenith_level * self.hours_day.numericValue / 2 * \
                        self._profile.pdf(clocktime_)

        self.surface_irrad.value = surface_value
        self.logger.debug('Updated for time {} surface irradiance: {}'.format(clocktime,
                                                                              self.surface_irrad))

        for channel in self.channels.itervalues():
            #: TODO: remove explicit calling by using Variable?
            channel.update_intensities(self.surface_irrad)

    def snapshot(self, base=False):
        """
        Returns a snapshot of the Irradiance's state

        Args:
            base (bool): Convert to base units?

        Returns:
            Dictionary with structure:
                * `metadata`:
                    * `hours_total`
                    * `day_fraction`
                    * `zenith_time`
                    * `zenith_level`

                * `channels`:
                    `channel_name`: snapshot of :class:`IrradianceChannel`
        """
        self.logger.debug('Snapshot: {}'.format(self))
        self.check_domain()

        state = dict()

        meta = state['metadata'] = {}
        meta['hours_total'] = str(self.hours_total)
        meta['day_fraction'] = self.day_fraction
        meta['zenith_time'] = str(self.zenith_time)
        meta['zenith_level'] = self.zenith_level

        channels = state['channels'] = {}
        for ch, chobj in self.channels.items():
            channels[ch] = chobj.snapshot(base=base)

        return state


class IrradianceChannel(DomainEntity):
    def __init__(self, name, k0 = PhysicalField(0, '1/cm'), k_mods = None, **kwargs):
        """
        An irradiance channel

        This creates variables for the channel intensities, for the attenuation values.

        Args:
            name: The channel name
            source: The :class:`Irradiance` source
            k0: The base attenuation for this channel through the sediment

        Returns:
        """
        self.logger = kwargs.get('logger') or logging.getLogger(__name__)
        self.logger.debug('Init in Irradiance')
        kwargs['logger'] = self.logger
        super(IrradianceChannel, self).__init__(**kwargs)

        self.name = name
        self.intensities = None

        try:
            self.k0 = PhysicalField(k0, '1/cm')
        except TypeError:
            raise ValueError('Invalid value for k0: {}'.format(k0))

        self.k_var = None
        self.k_mods = k_mods or []
        self._mods_added = {}
        self.logger.debug('created irradiance channel {}'.format(self))

    def __repr__(self):
        return '{}:{!r}'.format(self.name, self.k_var)

    def setup(self, **kwargs):
        """
        Define attenuations when domain is available

        Args:
            model (object): The model object to perform object lookups on if necessary. This
            object should have a callable :meth:`get_object(path)`
        Returns:

        """
        self.check_domain()
        model = kwargs.get('model')

        if self.intensities is None:
            self.intensities = self.domain.create_var(self.name)

            self.define_attenuation()

        for source in self.k_mods:
            var, coeff = source
            self.add_attenuation_source(var=var, coeff=coeff, model=model)

    @property
    def k_name(self):
        return '{}_k'.format(self.name)

    def define_attenuation(self):
        """
        Create the attenuation variable for the channel
        """
        assert hasattr(self.k0, 'unit'), 'k0 should have attribute unit'
        if self.k_name not in self.domain:
            k_var = self.domain.create_var(self.k_name, value=self.k0, store=False)
            k_var[:self.domain.idx_surface] = 0
            self.k_var = k_var

    def add_attenuation_source(self, var, coeff, model=None):
        """
        Add an extra source of attenuation to this channel, for example through biomass that
        attenuates light intensity

        The term `var * coeff` should have dimensions of 1/length

        `var` should be a string like "csb_biomass" in which case it is looked up from the
        domain, else it can be a model reference such as "microbes.cyano.biomass".

        Args:
            var (str): The name for the variable as attenuation source
            coeff: The coefficient to multiply with
            model (object): The model object to perform object lookups on if necessary.

        Returns:

        """
        self.check_domain()
        if var in self._mods_added:
            raise RuntimeError('attenuation source {} already added!')

        if '.' in var:
            # this is a model object like: microbes.cyano.biomass
            if model is None:
                self.logger.warning("Attenuation source {} needs model, but is None".format(var))
                return
            else:
                try:
                    atten_source = model.get_object(var) * coeff
                except ValueError:
                    self.logger.warning('Could not find attenuation source: {!r}'.format(var))
                    return
        else:
            atten_source = self.domain[var] * coeff

        try:
            atten_source.inUnitsOf('1/m')
        except TypeError:
            raise ValueError('Units of var * coeff is not 1/length, but {}'.format(
                atten_source.inBaseUnits().unit.name()))

        self.k_var += atten_source
        self._mods_added[var] = atten_source
        self.logger.info('Added attenuation source {!r} and coeff={}'.format(var, coeff))

    @property
    def is_setup(self):
        pending = set([k[0] for k in self.k_mods]).difference(set(self._mods_added))
        if pending:
            self.logger.warning('Attenuation sources for {!r} still pending: {}'.format(
                self,
                pending))
        return not bool(len(pending))

    @property
    def attenuation_profile(self):
        """
        Calculates the attenuation profile for this channel

        This returns the cumulative product of attenuation factors in each cell of the domain,
        allowing this to be multiplied by a surface value to get the irradiance profile.

        """
        if not self.is_setup:
            self.logger.warning('Attenuation definition may be incomplete!')

        return numerix.cumprod(numerix.exp(-1 * self.k_var * self.domain.distances))

    def update_intensities(self, surface_level):
        """
        Update the intensities of the channel based on the surface level

        Args:
            surface_level: The variable indicating the surface intensity

        Returns:
            The light profile
        """
        self.logger.debug('Updating intensities for surface value: {}'.format(surface_level))
        intensities = self.attenuation_profile * surface_level
        self.intensities.value = intensities
        return intensities

    def snapshot(self, base=False):
        """
        Returns a snapshot of the channel's state

        Args:
            base (bool): Convert to base units?

        Returns:
            Dictionary with structure:
            * `attenuation`:
                * `data`: (:attr:`.k_var`, dict(unit=unit))
                * `metadata`:
                    * dict of (`varname`, `coeff`)

            * `intensity`:
                * `data`: (:attr:`.intensities`, dict(unit=unit))
                *  `metadata`:
                    * unit: physical unit

            *`metadata`:
                * k0 for channel
        """
        self.logger.debug('Snapshot: {}'.format(self))

        self.check_domain()

        state = dict(
            metadata = dict()
            )
        meta = state['metadata']
        meta['k0'] = str(self.k0)

        atten = state['attenuation'] = {}
        ameta = atten['metadata'] = {}
        for varname, val in self.k_mods:
            ameta[varname] = str(val)
        atten['data'] = snapshot_var(self.k_var, base=base)

        inten = state['intensity'] = {}
        inten['data'] = snapshot_var(self.intensities, base=base)

        return state
