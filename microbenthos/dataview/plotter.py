import logging
from collections import defaultdict, OrderedDict
from decimal import Decimal

import matplotlib.pyplot as plt
import numpy as np
from cycler import cycler

from . import ModelData


# from https://stackoverflow.com/a/45359185
def fexp(number):
    (sign, digits, exponent) = Decimal(number).as_tuple()
    return len(digits) + exponent - 1

def fman(number):
    return int(Decimal(number).scaleb(-fexp(number)).normalize().to_integral())

def frepr(number):
    d = Decimal(number)
    (sign, digits, exponent) = d.as_tuple()
    nexp = len(digits) + exponent - 1
    nman = digits[0]
    return nman, nexp

def flabel(number):
    return r' ${%d}\times\mathregular{10^{%d}}$' % frepr(number)


class ModelPlotter(object):
    def __init__(self, model = None,
                 style = None,
                 figsize = (9.6, 5.4),
                 dpi = 100,
                 unit_env = 'mol/l',
                 unit_microbes = 'mg/cm**3',
                 unit_process = 'mol/l/h'
                 ):
        self.logger = logging.getLogger(__name__)
        self.logger.debug('Initializing model plotter')

        self._model = None
        #: :class:`ModelData`

        self.fig = None
        self._depths = None
        self.axes = []
        self.axes_linked = {}
        self.artist_paths = OrderedDict()

        self.unit_env = unit_env
        self.unit_microbes = unit_microbes
        self.unit_process = unit_process

        style = style or 'seaborn-colorblind'

        plt.style.use((style, {'axes.grid': False}))
        # with plt.style.context(style):
        self.create_figure(figsize=figsize, dpi=dpi)
        if model:
            self.model = model

    @property
    def model(self):
        return self._model

    @model.setter
    def model(self, m):
        assert isinstance(m, ModelData)
        self._model = m
        self.setup_model()

    def create_figure(self, **kwargs):
        self.logger.debug('Creating figure with params: {}'.format(kwargs))
        self.fig, axes = plt.subplots(nrows=1, ncols=4, sharey=True, **kwargs)

        assert isinstance(self.fig, plt.Figure)
        self.axEnv, self.axMicrobes, self.axProc, self.axProcNorm = axes
        # self.axEnvB = plt.twiny(self.axEnv)


        for ax, title, unit in zip(
            (self.axEnv, self.axMicrobes, self.axProc, self.axProcNorm),
            ('Environment', 'Microbes', 'Processes', 'Processes(norm)'),
            (self.unit_env, self.unit_microbes, self.unit_process, self.unit_process)
            ):
            # on top left of axis dict(xy=(-0.1, 0.98) ha=right, rotation=90)
            # on top within axis dict(xy=(0.5, 0.95), ha=center)
            ax.annotate(title, xycoords='axes fraction', size='small',
                        xy=(0.5, 0.97), ha='center')
            ax.name = title
            ax.data_unit_ = unit
            ax.set_xlabel(unit)
            ax.autoscale(tight=True, axis='y')
            ax.autoscale(tight=False, axis='x')

        self.axEnv.invert_yaxis()
        self.axEnv.set_ylabel('Depth (mm)')

        self.axIrrad = plt.twiny(self.axMicrobes)
        self.axes_linked[self.axMicrobes] = self.axIrrad
        self.axIrrad.name = 'Irradiance'
        self.axIrrad.set_xscale('log')
        self.axIrrad.set_xlim(0.01, 100)
        self.axIrrad.skip_legend_ = True

        self.axProc.skip_legend_ = True

        self.axEnv.data_normed_ = True
        self.axProcNorm.data_normed_ = True

        self.axes.extend(axes)
        self.logger.debug('Created {} panels'.format(len(self.axes) + len(self.axes_linked)))

    @property
    def axes_all(self):
        return self.axes + self.axes_linked.values()

    def setup_model(self):
        self.logger.debug('Setting model data: {}'.format(self.model))

        if self.model.store is None:
            self.logger.debug('Cannot setup model, since store is empty')
            return

        depth_unit = 'mm'
        self.depths = D = np.array(self.model.depths.inUnitsOf(depth_unit).value)

        for ax in self.axes:
            ax.axhspan(min(D), 0, color='aquamarine', alpha=0.4, zorder=0)
            ax.axhspan(0, max(D), color='xkcd:brown', alpha=0.4, zorder=0)

        for ax in self.axes:
            self.logger.debug('Setting scientific notation on {}'.format(ax.name))
            try:
                ax.ticklabel_format(axis='x', style='sci', scilimits=(-2, 2),
                                    useMathText=True)
                # self.format_exponent(ax, axis='y')
            except:
                self.logger.debug('Could not set {} axes to scientific notation'.format(ax.name))

        self._init_artist_styles()

        self.create_artists()

        self.update_legends()

        self.update_artists(tidx=0)
        self.fig.tight_layout()

    def _get_label(self, path):
        """
        Create the artist label from the path
        Args:
            path (str): A "/" nested path

        Returns:
            A string that can be used as the label
        """
        self.logger.debug('Getting label for {}'.format(path))
        parts = path.split('/')
        assert len(parts) >= 2

        if parts[0] == 'env':
            if parts[1] == 'irradiance':
                label = 'env.{}'.format(parts[3])

            else:
                label = parts[1]

        elif parts[0] == 'domain':
            label = parts[1]

        elif parts[0] == 'microbes':
            microbe = parts[1]

            if parts[2] == 'features':
                label = '{}.{}'.format(microbe, parts[3])

            elif parts[2] == 'processes':
                label = '{}.{}'.format(microbe, parts[3])

        else:
            label = path.replace('/', '.')

        return label

    def _init_artist_styles(self):
        # prepare color cycle so that entities from a group only get the same color
        colcycler = plt.rcParams['axes.prop_cycle']
        mcycler = cycler('marker', ['s', '^', 'o', 'd', 'v', ])
        lwcycler = cycler('lw', [1.25])
        lscycler = cycler('ls', ['-', '--', ':'])
        mscycler = cycler('ms', [3])
        mevery = cycler('markevery', [len(self.depths) // 20])
        # animcycler = cycler('animated', [True])

        artiststyle_cycler = lscycler * mcycler * mscycler * mevery * lwcycler  # * animcycler

        color_iter = colcycler()
        artiststyle_iter = artiststyle_cycler()
        colstyles = defaultdict(lambda: next(color_iter))
        linestyles = defaultdict(lambda: artiststyle_cycler())
        self.styles_color = colstyles
        self.styles_lines = linestyles
        self.artist_style = {}

    def create_artists(self):

        self.create_clock_artist()

        artist_sets = [
            (self.model.microbe_features, self.axMicrobes),
            (self.model.eqn_vars, self.axEnv),
            (self.model.eqn_sources, self.axProc),
            (self.model.eqn_sources, self.axProcNorm),
            (self.model.irradiance_intensities, self.axIrrad),
            ]

        for data_paths, ax in artist_sets:
            self.create_line_artists(data_paths, ax)

    def create_clock_artist(self):

        self.clockstr = '{0:02d}h {1:02d}min'
        self.clock_artist = plt.annotate(self.clockstr.format(0, 0),
                                         xy=(0.01, 0.01),
                                         xycoords='figure fraction',
                                         size='medium',
                                         color='r')

    def create_line_artists(self, data_paths, ax):
        self.logger.debug('Creating artists for {}: {}'.format(ax.name, data_paths))
        label_paths = {self._get_label(p): p for p in data_paths}
        plot_order = sorted(label_paths)
        self.logger.debug('Plot order for {} ax: {}'.format(ax.name, plot_order))

        zeros = np.zeros_like(self.model.depths)

        for label in plot_order:
            path = label_paths[label]

            style = self.artist_style.get(label)
            if style:
                self.logger.debug('Retrieved style for {}: {}'.format(label, sorted(style.items())))
            else:
                sourcename = label.split('.')[0]
                style = self.styles_color[sourcename].copy()
                # copy required to not leak dict state across subentities
                style.update(next(self.styles_lines[sourcename]))
                self.logger.debug(
                    'Created style for {} = {}'.format(label, sorted(style.items()))
                    )
                assert label not in self.artist_style
                self.artist_style[label] = style

            artist = ax.plot(zeros, self.depths, label=label, **self.artist_style[label])[0]
            self.artist_paths[artist] = path
            self.logger.debug('Created artist for {}: {} from {}'.format(label, artist, path))

    def update_legends(self, axes = None):

        legkwds = dict(loc='lower center', framealpha=0, fontsize='x-small')

        if axes is None:
            axes = self.axes

        for ax in axes:
            if ax.legend_ is None or getattr(ax, 'data_normed_', False):

                if getattr(ax, 'skip_legend_', False):
                    continue

                axlink = self.axes_linked.get(ax)
                H, L = ax.get_legend_handles_labels()
                if axlink:
                    h, l = axlink.get_legend_handles_labels()
                else:
                    h, l = [], []

                ax.legend(H + h, L + l, **legkwds)

    def update_artists(self, tidx):
        """
        Update the data of the line artists for time point

        Args:
            tidx (int): The time index

        """
        self.logger.info(
            'Updating artist_paths for time step #{}'.format(tidx))

        clocktime = self.model.times[tidx]
        H, M, S = [int(s.value) for s in clocktime.inUnitsOf('h', 'min', 's')]
        hmstr = self.clockstr.format(H, M)
        self.clock_artist.set_text(hmstr)
        self.logger.debug('Time: {}'.format(hmstr))

        for artist, dpath in self.artist_paths.items():

            ax = artist.axes
            self.logger.debug('Updating {} artist {} from {}'.format(ax.name, artist, dpath))

            # get the data
            data = self.model.get_data(dpath, tidx=tidx)
            data_unit = data.unit.name()
            self.logger.debug('Got data {} of unit: {!r}'.format(data.shape, data_unit))

            # cast to units
            if not hasattr(ax, 'data_unit_'):
                ax.data_unit_ = data.unit.name()
            ax_unit = ax.data_unit_

            try:
                D = data.inUnitsOf(ax_unit).value
            except TypeError:
                self.logger.error("Error casting {} units from {} to {}".format(
                    dpath, data_unit, ax_unit
                    ))
                raise

            # now data is a numpy array

            label_base = self._get_label(dpath)

            # normalize if necessary
            data_normed = getattr(ax, 'data_normed_', False)

            if data_normed:
                self.logger.debug('Normalizing data')
                Dabs = abs(D)
                Dabsmax = Dabs.max()
                Dabsmin = Dabs.min()
                Drange = float(Dabsmax - Dabsmin)
                if Drange == 0:
                    if Dabsmax == 0:
                        Drange = 1
                    else:
                        Drange = float(Dabsmax)

                D = D / Drange
                label = label_base + flabel(Drange)

            else:
                label = label_base

            # now ready to set data and label
            artist.set_xdata(D)
            artist.set_label(label)
            self.logger.debug('{} updated'.format(artist))

        self.update_legends()

        for ax in self.axes:
            ax.relim()
            ax.autoscale_view(scalex=True, scaley=True)

    def draw(self):
        """
        Draw the changes on to the canvas. This is meant to be called after each
        :meth:`update_artists`
        """
        try:
            self.fig.canvas.draw_idle()
            self.fig.canvas.flush_events()
        except KeyboardInterrupt:
            self.logger.warning('KeyboardInterrupt caught while updating canvas. Re-raising.')
            raise

    def show(self, block = False):
        plt.show(block=block)

    def close(self):
        plt.close(self.fig)
