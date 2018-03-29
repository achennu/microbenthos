import logging

from fipy import PhysicalField, Variable
from fipy.tools import numerix
from scipy.stats import cosine

from .entity import DomainEntity
from ..utils.snapshotters import snapshot_var, restore_var


class Irradiance(DomainEntity):
    """
    Class that represents a source of irradiance in the model domain.

    The irradiance is discretized into separate "channels" (see :class:`IrradianceChannel`),
    representing a range of the light spectrum. This is useful to define channels such as PAR (
    photosynthetically active radiation) or NIR (near-infrared), etc.

    The irradiance has a :attr:`.surface_level` which is modulated as ``cos(time)``, to mimic the
    cosinusoidal variation of solar radiance during a diel period. The diel period is considered
    to run from midnight to midnight. The intensity in each channel is then represented as a
    fraction of the surface level (set at 100).

    """

    def __init__(self, hours_total = 24, day_fraction = 0.5, channels = None, **kwargs):
        """
        Initialize an irradiance source in the model domain

        Args:
            hours_total (int, float, PhysicalField): Number of hours in a diel period

            day_fraction (float): Fraction (between 0 and 1) of diel period which is illuminated
                (default: 0.5)

            channels: See :meth:`.create_channel`

            **kwargs: passed to superclass

        """
        self.logger = kwargs.get('logger') or logging.getLogger(__name__)
        self.logger.debug('Init in {}'.format(self.__class__.__name__))
        kwargs['logger'] = self.logger
        super(Irradiance, self).__init__(**kwargs)

        #: the channels in the irradiance entity
        self.channels = {}

        #: the number of hours in a diel period
        self.hours_total = PhysicalField(hours_total, 'h')
        if not (1 <= self.hours_total.value <= 48):
            raise ValueError('Hours total {} should be between (1, 48)'.format(self.hours_total))
        # TODO: remove (1, 48) hour constraint on hours_total

        day_fraction = float(day_fraction)
        if not (0 < day_fraction < 1):
            raise ValueError("Day fraction should be between 0 and 1")

        #: fraction of diel period that is illuminated
        self.day_fraction = day_fraction
        #: numer of hours in the illuminated fraction
        self.hours_day = day_fraction * self.hours_total
        #: the time within the diel period which is the zenith of radiation
        self.zenith_time = self.hours_day
        #: the intensity level at the zenith time
        self.zenith_level = 100.0

        C = 1.0 / numerix.sqrt(2 * numerix.pi)
        # to scale the cosine distribution from 0 to 1 (at zenith)

        self._profile = cosine(
            loc=self.zenith_time, scale=C ** 2 * self.hours_day)
        # This profile with loc=zenith means that the day starts at "midnight" and zenith occurs
        # in the center of the daylength

        #: a :class:`Variable` for the momentary radiance level at the surface
        self.surface_irrad = Variable(name='irrad_surface', value=0.0, unit=None)

        if channels:
            for chinfo in channels:
                self.create_channel(**chinfo)

        self.logger.debug('Created Irradiance: {}'.format(self))

    def __repr__(self):
        return 'Irradiance(total={},{})'.format(self.hours_total, '+'.join(self.channels))

    def setup(self, **kwargs):
        """
        With an available `model` instance, setup the defined :attr:`.channels`.
        """
        self.check_domain()
        model = kwargs.get('model')

        for channel in self.channels.values():
            if not channel.has_domain:
                channel.domain = self.domain
            channel.setup(model=model)

    @property
    def is_setup(self):
        """
        Returns:
            bool: True if all the :attr:`.channels` are setup
        """
        return all([c.is_setup for c in self.channels.values()])

    def create_channel(self, name, k0 = 0, k_mods = None, model = None):
        """
        Add a channel with :class:`IrradianceChannel`, such as PAR or NIR

        Args:
            name (str): The channel name stored in :attr:`.channels`

            k0 (int, `PhysicalField`): The base attenuation for this channel through the sediment

            k_mods (list): ``(var, coeff)`` pairs to add attenuation sources to k0 for the channel

            model (None, object): instance of the model, if available

        Returns:
            The created :class:`IrradianceChannel` instance

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
            clocktime (:class:`PhysicalField`): The model clock time

        """
        if isinstance(clocktime, PhysicalField):
            clocktime_ = clocktime.inBaseUnits() % self.hours_total.inBaseUnits()
        else:
            clocktime_ = clocktime % self.hours_total.numericValue

        # logger.debug('clock % hours_total =  {} % {} = {}'.format(
        #     clock, self.hours_total, clocktime_))
        # logger.debug('Profile level for clock {}: {}'.format(
        #     clock, self._profile.pdf(clocktime_)))

        surface_value = self.zenith_level * self.hours_day.numericValue / 2.0 * \
                        self._profile.pdf(clocktime_)

        self.surface_irrad.value = surface_value
        self.logger.debug('Updated for time {} surface irradiance: {}'.format(clocktime,
                                                                              self.surface_irrad))

        for channel in self.channels.values():
            #: TODO: remove explicit calling by using Variable?
            channel.update_intensities(self.surface_irrad)

    def snapshot(self, base = False):
        """
        Returns a snapshot of the Irradiance's state with the structure

            * "channels"
                * "name" : :meth:`IrradianceChannel.snapshot` of each channel

            * "metadata"
                * `"hours_total"`: str(:attr:`.hours_total`)
                * `"day_fraction"`: :attr:`.day_fraction`
                * `"zenith_time"`: str(:attr:`.zenith_time`)
                * `"zenith_level"`: :attr:`.zenith_level`

        Args:
            base (bool): Convert to base units?

        Returns:
            dict: the state dictionary
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

    def restore_from(self, state, tidx):
        """
        Restore state of each irradiance channel
        """
        self.logger.debug('Restoring {} from state: {}'.format(self, tuple(state)))
        self.check_domain()

        for ch, chobj in self.channels.items():
            chobj.restore_from(state['channels'][ch], tidx)


class IrradianceChannel(DomainEntity):
    """
    Class that represents a single scalar irradiance channel in :class:`Irradiance`
    """

    def __init__(self, name, k0 = PhysicalField(0, '1/cm'), k_mods = None, **kwargs):
        """
        A scalar irradiance channel.

        This creates variables for the channel intensities, for the attenuation values.

        Args:
            name (str): The channel name

            k0 (float, PhysicalField): The base attenuation for this channel through the sediment
                with units of (1/cm)

            k_mods (None, list): ``(var, coeff)`` pairs that modify `k0` based on the value of the
                variable pointed at by `var` (example: `"microbes.cyano.biomass"`) and multiplied
                with a `coeff`. `coeff` must have the units such that `var * coeff` has the units
                of `k0`.

        Raises:
            ValueError: if the units of `k0` are not compatible with 1/cm

        """
        self.logger = kwargs.get('logger') or logging.getLogger(__name__)
        self.logger.debug('Init in {}'.format(self.__class__.__name__))
        kwargs['logger'] = self.logger
        super(IrradianceChannel, self).__init__(**kwargs)

        self.name = name

        #: CellVariable to hold the intensities of the irradiance channel through the domain
        self.intensities = None

        try:
            #: the base attenuation through the sediment
            self.k0 = PhysicalField(k0, '1/cm')
        except TypeError:
            raise ValueError('Invalid value for k0: {}'.format(k0))

        #: variable that represents the net attenuation
        self.k_var = None
        #: list of modulations for the attenuation in :attr:`.k0`
        self.k_mods = k_mods or []
        self._mods_added = {}
        self.logger.debug('Created irradiance channel {}'.format(self))

    def __repr__(self):
        return '{}:{!r}'.format(self.name, self.k_var)

    def setup(self, **kwargs):
        """
        Define attenuations when domain is available

        This initializes the :attr:`.intensities` of the channel through the domain.

        Args:
            model (object): The model object lookups sources for :attr:`.k_mods`. It should have
                a callable :meth:`get_object(path)`

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
        """
        Returns:
            str: name for the attenuation variable in the domain
        """
        return '{}_k'.format(self.name)

    def define_attenuation(self):
        """
        Create the attenuation :attr:`.k0` for the channel
        """
        assert hasattr(self.k0, 'unit'), 'k0 should have attribute unit'
        if self.k_name not in self.domain:
            k_var = self.domain.create_var(self.k_name, value=self.k0, store=False)
            k_var[:self.domain.idx_surface] = 0
            self.k_var = k_var

    def add_attenuation_source(self, var, coeff, model = None):
        """
        Add an extra source of attenuation to this channel, for example through biomass that
        attenuates light intensity

        Args:
            var (str): The name for the variable as attenuation source. `var` should be a string
                to a model variable (example ``"microbes.cyano.biomass"``) in which case it is
                looked up from the `model`.

            coeff: The coefficient to multiply with. The term ``var * coeff`` should have
                dimensions of 1/length

            model (object): The model object to perform object lookups on if necessary with
                :meth:`model.get_object(var)`

        Raises:
            ValueError: If the units of `var * coeff` not compatible with 1/m

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
                    atten_source_var = model.get_object(var)
                    if not isinstance(atten_source_var, Variable):
                        atten_source_var = atten_source_var.var
                    atten_source = atten_source_var * coeff
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
        """
        Returns:
            bool: True if all pending attenuation sources in :attr:`.k_mods` have been added
        """
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
        allowing this to be multiplied by a surface value to get the irradiance intensity profile.
        """
        if not self.is_setup:
            self.logger.warning('Attenuation definition may be incomplete!')
        return numerix.cumprod(numerix.exp(-1 * self.k_var * self.domain.distances))

    def update_intensities(self, surface_level):
        """
        Update the :attr:`.intensities` of the channel based on the surface level

        Args:
            surface_level: The variable indicating the surface intensity

        Returns:
            :class:`numpy.ndarray`: The intensity profile through the domain
        """
        self.logger.debug('Updating intensities for surface value: {}'.format(surface_level))
        intensities = self.attenuation_profile * surface_level
        self.intensities.value = intensities
        return intensities

    def snapshot(self, base = False):
        """
        Returns a snapshot of the channel's state, with the structure

            * "attenuation"
                * "data" : (:attr:`.k_var`, dict(unit = :attr:`.k_var.unit`))

                * "metadata"
                    * "varname": str(coeff) of the sources in :attr:`.k_mods`

            * "intensity" : ( :attr:`.intensities`, dict(unit = :attr:`.intensities.unit` ) )

            * "metadata"
                * "k0" : str(:attr:`.k0`)

        Args:
            base (bool): Convert to base units?

        Returns:
            dict: state dictionary

        """
        self.logger.debug('Snapshot: {}'.format(self))

        self.check_domain()

        state = dict(
            metadata=dict()
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

    def restore_from(self, state, tidx):
        """
        Restore the :attr:`.intensities` from the state
        """
        self.logger.debug('Restoring {} from state: {}'.format(self, tuple(state)))
        self.check_domain()

        self.intensities.setValue(restore_var(state['intensity'], tidx))
        # cannot set attenuation as this is determined as a binary operation between other variables
        # self.k_var.setValue(restore_var(state['attenuation'])[tidx])
