import itertools
import logging
from collections import defaultdict, OrderedDict
from decimal import Decimal

import matplotlib.pyplot as plt
from cycler import cycler
from fipy import PhysicalField
from fipy.tools import numerix as np
from mpl_toolkits.axes_grid1 import Grid

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
    # nman = digits[0]
    if len(digits) > 1:
        digs = '{}.{}'.format(digits[0], digits[1])
    else:
        digs = str(digits[0])
    return digs, nexp


def flabel(number):
    try:
        return r' ${%s}\times\mathregular{10^{%d}}$' % frepr(number)
    except:
        return r' ${%s}\timesERROR' % number


class ModelPlotter(object):
    def __init__(self, model = None,
                 style = None,
                 figsize = None,
                 dpi = None,
                 unit_env = 'mol/l',
                 unit_microbes = 'mg/cm**3',
                 unit_sources = 'mol/l/min',
                 unit_process = 'mol/l/min',
                 track_budget = False,
                 ):
        self.logger = logging.getLogger(__name__)
        self.logger.addHandler(logging.NullHandler())
        self.logger.debug('Initializing model plotter')

        self._model = None
        #: :class:`ModelData`

        self.fig = None
        self._depths = None
        self.axes_depth = []
        self.axes_time = []
        self.axes_depth_linked = defaultdict(list)
        self.axes_time_linked = defaultdict(list)
        self.artist_paths = OrderedDict()

        self.unit_env = unit_env
        self.unit_microbes = unit_microbes
        self.unit_process = unit_process
        self.unit_sources = unit_sources

        self.track_budget = track_budget

        style = style or 'seaborn-colorblind'

        plt.style.use((style, {'axes.grid': False}))

        figsize = figsize or (8, 6)
        dpi = dpi or 100

        self._fig_kwds = dict(figsize=figsize, dpi=dpi)
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

    def _create_figure(self, **kwargs):
        """
        Create the figure based on the model data structure.

        The following vs-depth axes are created by default:
            * Microbes (for microbial features & irradiance distribution)
            * Environment (for  eqn variable distribution)
            * Sources (eqn source totals distribution)
            * Processes (eqn process expression distribution)

        If :attr:`track_budget` is True and corresponding data is available in model, then the
        `time_vars` axes is created.

        Returns:

        """
        self.logger.debug('Determining axes for model {}'.format(self.model))

        # if track_budget is True and there are tracked quantities in the model store, then add a
        # time panel for the estimated budget error on variables
        assert isinstance(self.model, ModelData)

        vars_panel = len(self.model.eqn_var_actual) and bool(self.track_budget)

        self.logger.debug('Creating figure: {}'.format(self._fig_kwds))

        # self.fig = plt.figure('MicroBenthos Simulation', **kwargs)

        axes_depth = self.axes_depth
        axes_time = self.axes_time

        xMIN = 0.05
        xMAX = 0.93 + 0.05
        yMIN = 0.08
        yMAX = 0.92
        yPAD = 0.04

        if vars_panel:
            # time axes are required
            num_time_axis = int(vars_panel)  # + int(error_panel)
            ySPACE = 0.15 * num_time_axis  # 15% per time axis
            depth_xspan = xMAX - xMIN
            depth_yspan = yMAX - (yMIN + ySPACE)
            depth_ymin = yMIN + ySPACE
            depth_rect = [xMIN, depth_ymin + yPAD, depth_xspan, depth_yspan]

            time_rect = [xMIN, yMIN, depth_xspan, ySPACE - yPAD]
            time_nrows_ncols = (num_time_axis, 1)

        else:
            depth_rect = [0.05, 0.1, 0.93, 0.8]
            time_rect = []

        self._depth_rect = depth_rect

        # axgrid_depths = Grid(fig=self.fig, rect=depth_rect,
        #                      nrows_ncols=(1, 4), share_y=True,
        #                      axes_pad=0.08)

        # if time_rect:
        #     axgrid_time = Grid(fig=self.fig, rect=time_rect,
        #                        nrows_ncols=time_nrows_ncols,
        #                        share_x=True,
        #                        )
        #     self.axError = axgrid_time.axes_all[0]

        # self.axMicrobes, self.axEnv, self.axSources, self.axProcesses = axgrid_depths.axes_all
        # self.axMicrobes, self.axProcesses, self.axSources, self.axEnv, = axgrid_depths.axes_all

        self.fig, axes = plt.subplots(nrows=1, ncols=4, sharey=True,
                                      #gridspec_kw=dict(wspace=0.02),
                                      **kwargs)
        assert isinstance(self.fig, plt.Figure)
        self.axMicrobes, self.axProcesses, self.axSources, self.axEnv = axes

        ax = self.axMicrobes
        ax.name = 'Microbes'
        ax.invert_yaxis()
        ax.data_unit_ = self.unit_microbes
        ax.data_normed_ = False
        axes_depth.append(ax)

        ax = self.axEnv
        ax.name = 'Environment'
        ax.data_unit_ = self.unit_env
        ax.data_normed_ = True
        axes_depth.append(ax)

        ax = self.axSources
        ax.name = 'Sources'
        ax.data_unit_ = self.unit_sources
        ax.data_normed_ = True
        ax.set_xlim(-1, 1)
        axes_depth.append(ax)

        ax = self.axProcesses
        ax.name = 'Processes'
        ax.data_unit_ = self.unit_process
        ax.data_normed_ = True
        ax.set_xlim(-1, 1)
        axes_depth.append(ax)

        self.axIrrad = ax = plt.twiny(self.axMicrobes)
        self.axes_depth_linked[self.axMicrobes] = ax
        ax.name = 'Irradiance'
        ax.data_normed_ = False
        ax.set_xscale('log')
        ax.set_xlim(0.01, 100)
        ax.skip_legend_ = True

        if vars_panel:

            ax = self.axError
            ax.name = 'BudgetError'
            # unit will be determined from data
            ax.data_unit_ = None
            ax.data_normed_ = False
            axes_time.append(ax)
            ax.set_xlim(0)

        else:
            self.axError = None

        linked_axes = self.axes_depth_linked.values()

        for ax in self.axes_depth:

            # on top left of axis dict(xy=(-0.1, 0.98) ha=right, rotation=90)
            # on top within axis dict(xy=(0.5, 0.95), ha=center)
            ax.annotate(ax.name, xycoords='axes fraction', size='small',
                        xy=(0.5, 0.97), ha='center')

            if ax.data_unit_:
                ax.set_xlabel(ax.data_unit_)
            ax.skip_legend_ = False
            ax.autoscale(tight=True, axis='y')
            ax.autoscale(tight=False, axis='x')
            try:
                ax.ticklabel_format(axis='x', style='sci', scilimits=(-2, 2),
                                    useMathText=True)
            except:
                self.logger.debug('Could not set {} axes to scientific notation'.format(ax.name))

        # for ax in self.axes_time:
        #
        #     if ax is self.axes_time[-1]:
        #         ax.set_xlabel('Time (h)')
        #         # ax.set_ylabel(r'$\frac{actual-expected}{expected}$')
        #         ax.set_ylabel('Budget Error')
        #
        #     ax.skip_legend_ = False
        #     ax.annotate(ax.name, xycoords='axes fraction', size='medium',
        #                 xy=(1.05, 0.5), ha='center', va='center', rotation=90)
        #     # defer ylabel setting till first data access
        #
        #     ax.autoscale(True)
        #
        #     try:
        #         ax.ticklabel_format(axis='y', style='sci', scilimits=(-2, 2),
        #                             useMathText=True)
        #     except:
        #         self.logger.debug('Could not set {} axes to scientific notation'.format(ax.name))

        # self.fig.tight_layout(rect=self._depth_rect, pad=1.02)
        self.logger.debug('Created figure')

    @property
    def axes_all(self):
        return itertools.chain(self.axes_depth_all, self.axes_time_all)

    @property
    def axes_depth_all(self):
        return itertools.chain(self.axes_depth, self.axes_depth_linked.values())

    @property
    def axes_time_all(self):
        return itertools.chain(self.axes_time, self.axes_time_linked.values())

    def setup_model(self):
        self.logger.debug('Setting model data: {}'.format(self.model))

        if self.model.store is None:
            self.logger.debug('Cannot setup model, since store is empty')
            return

        if self.fig is None:
            self._create_figure(**self._fig_kwds)

        depth_unit = 'mm'
        self.depths = D = np.array(self.model.depths.inUnitsOf(depth_unit).value)
        self.axMicrobes.set_ylabel(f'Depth ({depth_unit})')

        for ax in self.axes_depth:
            ax.axhspan(min(D), 0, color='aquamarine', alpha=0.4, zorder=0)
            ax.axhspan(0, max(D), color='xkcd:brown', alpha=0.4, zorder=0)

        self._init_artist_styles()

        self.create_artists()

        self.update_legends()

        self.logger.propagate = False

        self._clock = PhysicalField(0, 's')

        self.update_artists(tidx=0)

        self.fig.tight_layout()#rect=self._depth_rect, pad=1.02)

    def _get_label(self, path):
        """
        Create the artist label from the path
        Args:
            path (str): A "/" nested path

        Returns:
            A string that can be used as the label
        """
        # self.logger.debug('Getting label for {}'.format(path))
        parts = path.split('/')
        assert len(parts) >= 2

        if parts[0] == 'env':
            if parts[1] == 'irradiance':
                label = 'env.{}'.format(parts[3])

            elif parts[-1] in ('sources_total', 'actual', 'expected', 'difference', 'error'):
                label = '{}.{}'.format(parts[1], parts[-1])

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

        self.logger.debug('Got label for {} --> {}'.format(path, label))
        return label

    def _init_artist_styles(self):
        """
        Create the styles for the artists

        Prepare color cycle and line styles so that entities from the same group get the same color

        """
        colcycler = plt.rcParams['axes.prop_cycle']
        mcycler = cycler('marker', ['s', '^', 'o', 'd', 'v', ])
        lwcycler = cycler('lw', [1.25])
        lscycler = cycler('ls', ['-', '--', ':'])
        mscycler = cycler('ms', [5])
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
        """
        Create the artists for the model plotter, and store it in :attr:`.artists`
        """

        self.create_clock_artist()

        artist_sets = [
            (self.model.microbe_features, self.axMicrobes),
            (self.model.eqn_vars, self.axEnv),
            (self.model.eqn_source_totals, self.axSources),
            (self.model.eqn_processes, self.axProcesses),
            (self.model.irradiance_intensities, self.axIrrad),
            ]

        if self.axes_time:
            # artist_sets.append((self.model.eqn_var_actual, self.axVars))
            artist_sets.append((self.model.eqn_var_difference, self.axError))

        for data_paths, ax in artist_sets:
            self.create_line_artists(data_paths, ax)

    def create_clock_artist(self):

        self.clockstr = '{0:02d}h {1:02d}m {2:02d}s (+{3:02d} s)'
        self.clock_artist = self.axEnv.annotate(
            self.clockstr.format(0, 0, 0, 0),
            # xy=(0.01, 0.01),
            xy=(0.5, 1.01),
            xycoords='axes fraction',
            size='medium',
            ha='center',
            color='r')

    def create_line_artists(self, data_paths, ax):
        self.logger.debug('Creating artists for {}: {}'.format(ax.name, data_paths))
        label_paths = {self._get_label(p): p for p in data_paths}
        plot_order = sorted(label_paths)
        self.logger.debug('Plot order for {} ax: {}'.format(ax.name, plot_order))

        zeros = np.zeros_like(self.model.depths)
        # all_depth_axes = itertools.chain(self.axes_depth, self.axes_depth_linked.values())
        # all_time_axes = itertools.chain(self.axes_time, self.axes_time_linked.values())

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

                if 'irradiance' in path:
                    style['ls'] = '--'

                self.artist_style[label] = style

            if ax in self.axes_depth_all:
                artist = ax.plot(zeros, self.depths, label=label, **self.artist_style[label])[0]
            elif ax in self.axes_time_all:
                self.artist_style[label].update(dict(markevery=1, ls=':', marker='.'))
                artist = ax.plot([], [], label=label, **self.artist_style[label])[0]

            else:
                raise ValueError('Unknown artist axes {}: {}'.format(ax, ax.name))

            self.artist_paths[artist] = path
            self.logger.debug('Created artist for {}: {} from {}'.format(label, artist, path))

    def update_legends(self, axes = None):

        legkwds = dict(loc='lower center', framealpha=0, fontsize='small')

        if axes is None:
            axes = self.axes_all

        for ax in axes:
            if ax.legend_ is None or getattr(ax, 'data_normed_', False):

                if getattr(ax, 'skip_legend_', False):
                    continue

                axlink = self.axes_depth_linked.get(ax)
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
        dt = int(np.ceil((clocktime - self._clock).numericValue))
        H, M, S = [int(s.value) for s in clocktime.inUnitsOf('h', 'min', 's')]
        hmstr = self.clockstr.format(H, M, S, dt)
        self._clock = clocktime

        self.clock_artist.set_text(hmstr)
        self.logger.debug('Time: {}'.format(hmstr))

        # self.axes_all
        # all_depth_axes = itertools.chain(self.axes_depth, self.axes_depth_linked.values())
        # all_time_axes = itertools.chain(self.axes_time, self.axes_time_linked.values())

        for artist, dpath in self.artist_paths.items():

            ax = artist.axes
            self.logger.info('Updating {} artist {} from {}'.format(ax.name, artist, dpath))

            # get the data
            data = self.model.get_data(dpath, tidx=tidx)
            data_unit = data.unit.name()
            self.logger.debug('Got data {} {} of unit: {!r}'.format(data.__class__.__name__,
                                                                    data.shape,
                                                                    data_unit))

            # cast to units
            if not getattr(ax, 'data_unit_', None):
                ax.data_unit_ = data.unit.name()
                self.logger.debug('Set axes {} to unit: {}'.format(ax.name, ax.data_unit_))
                # if ax in all_time_axes:
                #     ax.set_ylabel(ax.data_unit_)
            ax_unit = ax.data_unit_

            try:
                D = data.inUnitsOf(ax_unit).value
                self.logger.debug('Got data {} dtype {} --> {}'.format(D.dtype, D.min(), D.max()))

            except TypeError:
                self.logger.error("Error casting {} units from {} to {}".format(
                    dpath, data_unit, ax_unit
                    ))
                # raise
                D = data.value

            # now data D is a numpy array

            label_base = self._get_label(dpath)

            # normalize if necessary
            data_normed = getattr(ax, 'data_normed_', False)

            if data_normed:
                Dabs = abs(D)
                Dabsmax = float(Dabs.max())
                Dabsmin = float(Dabs.min())
                Drange = Dabsmax - Dabsmin
                if Drange <= 1e-15:
                    self.logger.debug('abs(data) max = min = {:.2g}'.format(Dabsmax, Dabsmin))
                    if Dabsmax == 0.0:
                        Drange = 1.0
                        self.logger.debug('all data is zero, normalizing by 1.0')
                    else:
                        Drange = Dabsmax
                        self.logger.debug('normalizing by abs(data).max = {:.2g}'.format(Dabsmax))
                else:
                    self.logger.debug('abs(data) range {:.2g} --> {:.2g}'.format(Dabsmin, Dabsmax))
                    Drange = Dabsmax

                D = D / Drange

                self.logger.info('Normalized {} data by {:.3g}: {:.3g} --> {:.3g}'.format(
                    label_base, Drange, D.min(), D.max()))

                label = label_base + flabel(Drange)

                if D.max() > 1.01:
                    self.logger.error('data max {} is not <=1.01'.format(D.max()))
                    self.logger.warning(D)
                    self.logger.warning('Drange: {}'.format(Drange))
                    self.logger.warning('Original data: {}'.format(data.inUnitsOf(ax_unit).value))
                    raise RuntimeError('Data normalization of {} failed!'.format(dpath))

            else:
                label = label_base

            # now ready to set data and label
            if ax in self.axes_depth_all:
                artist.set_xdata(D)
                artist.set_label(label)

            elif ax in self.axes_time_all:
                xdata, ydata = artist.get_data()
                t = self.model.get_data('/time', tidx=tidx)
                artist.set_xdata(np.append(xdata, t.inUnitsOf('h').value))
                artist.set_ydata(np.append(ydata, D))
                artist.set_label(label + ' {}'.format(ax.data_unit_))

            self.logger.debug('{} updated'.format(artist))

        self.update_legends()

        for ax in self.axes_depth + self.axes_time:
            ax.relim()
            ax.autoscale_view(scalex=True, scaley=True)

    def draw(self):
        """
        Draw the changes on to the canvas. This is meant to be called after each
        :meth:`update_artists`
        """
        if not self.fig:
            return
        try:
            self.fig.canvas.draw_idle()
            self.fig.canvas.flush_events()
            plt.pause(0.001)
        except KeyboardInterrupt:
            self.logger.warning('KeyboardInterrupt caught while updating canvas. Re-raising.')
            raise

    def show(self, block = False):
        if not self.fig:
            return
        plt.show(block=block)
        self.draw()

    def close(self):
        if not self.fig:
            return
        plt.close(self.fig)
