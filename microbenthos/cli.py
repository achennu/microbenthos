# -*- coding: utf-8 -*-

import os

import click

try:
    import click_completion

    click_completion.init()
except ImportError:
    click_completion = None


def _matplotlib_style_callback(ctx, param, value):
    if not value:
        return

    try:
        from matplotlib import style
        STYLES = style.available
    except ImportError:
        click.secho(
            'Feature not available. Install "matplotlib" package first.',
            fg='red')
        raise click.Abort()

    if value in STYLES:
        return value
    else:
        raise click.BadParameter(
            'Plot style {!r} not in known: {}'.format(value, STYLES))


def _matplotlib_writer_callback(ctx, param, value):
    if not value:
        return

    try:
        from matplotlib import animation
        writers_available = animation.writers.list()
    except ImportError:
        click.secho(
            'Feature not available. Install "matplotlib" package first.',
            fg='red')
        raise click.Abort()

    if value in writers_available:
        return value
    else:
        raise click.BadParameter('Animation writer {!r} not in available: {}'.format(
            value, writers_available
        ))


def _fipy_solver_callback(ctx, param, value):
    if value:
        from microbenthos.model import Simulation
        if value in Simulation.FIPY_SOLVERS:
            return value
        else:
            raise click.BadParameter(
                'FiPy solver {!r} not in known: {}'.format(value,
                                                           Simulation.FIPY_SOLVERS))


def _completion_shell_callback(ctx, param, value):
    try:
        import click_completion
    except ImportError:
        click.secho(
            'Feature not available. Run "pip install click-completion" to enable.',
            fg='red')
        raise click.Abort

    if value:
        if value in click_completion.shells:
            return value
        else:
            raise click.BadParameter(
                '{!r} not in known shells: {}'.format(value,
                                                      click_completion.shells))


def _figsize_callback(ctx, param, value):
    if value:
        try:
            w, h = [float(_) for _ in value.split('x')]
            assert w > 0
            assert h > 0
            return (w, h)
        except:
            raise click.BadParameter(
                'Input not of type "WxH", for example "15x8"')


def _simtime_lims_callback(ctx, param, value):
    if value:
        try:
            low, high = [float(_) for _ in value.strip().split()]
            assert 0 < low < high
            return (low, high)
        except:
            raise click.BadParameter('Input not of type "2 200" or "2s 200s"')


def _simtime_total_callback(ctx, param, value):
    if value:
        try:
            value = float(value)
        except ValueError:
            from fipy import PhysicalField
            try:
                value = PhysicalField(str(value)).inUnitsOf('h')
            except:
                raise click.BadParameter(
                    'simtime_total {} could not be intepreted as hours (example "3.5h")'.format(
                        value))

        if value > 0:
            return value
        else:
            raise click.BadParameter(
                'simtime_total {!r} should be > 0'.format(value))


@click.group('microbenthos')
@click.option('-v', '--verbosity', count=True,
              help='Set verbosity of console logging')
@click.option('--logger',
              help='Set specified logger to loglevel (example: microbenthos.model 20)',
              multiple=True, type=(str, click.IntRange(10, 40)))
def cli(verbosity, logger):
    """Console entry point for microbenthos"""
    loglevel = 0
    if verbosity:
        if verbosity == 1:
            loglevel = 40
        elif verbosity == 2:
            loglevel = 30
        elif verbosity == 3:
            loglevel = 20
        elif verbosity >= 4:
            loglevel = 10

    else:
        loglevel = 40

    from microbenthos import setup_console_logging
    setup_console_logging(level=loglevel)

    if logger:
        for name, level in logger:
            setup_console_logging(name=name, level=level)


@cli.group('setup')
def setup():
    """Setup configuration"""


@setup.command('completion')
@click.option('--shell', callback=_completion_shell_callback,
              default='bash', help='The shell to install completion',
              required=True)
@click.option('--show-code', is_flag=True,
              help='Show the installed code')
def setup_completion(shell, show_code):
    """Setup CLI completion for shell"""
    click.echo('Setup completion for shell {!r}'.format(shell))

    if show_code:
        code = click_completion.get_code(shell=shell)
        click.echo('Installing code: \n{}'.format(code))

    shell_, path = click_completion.install(shell=shell)
    click.secho('Installed completion in path {!r}'.format(path))


@cli.command('simulate')
@click.option('-o', '--output-dir', type=click.Path(file_okay=False),
              default=os.getcwd(),
              help='Output directory for simulation')
@click.option('-x', '--export', multiple=True,
              type=(str, str),
              help="Add an exporter to run. Form: -x <name> <export_type>")
@click.option('-sTime', '--simtime_total', callback=_simtime_total_callback,
              help='Total simulation time. Example: "10h"')
@click.option('-sLims', '--simtime-lims', callback=_simtime_lims_callback,
              help='Simulation time step limits. Example: "1s 500s"')
@click.option('-sSweeps', '--max-sweeps', type=click.IntRange(3),
              help='Max number of sweeps of equation in each timestep')
@click.option('-sRes', '--max-residual', type=float,
              help='The max residual allowed for the time steps')
@click.option('-sSolver', '--fipy-solver', help='Solver type to use from fipy',
              callback=_fipy_solver_callback)
@click.option('-O', '--overwrite', help='Overwrite file, if exists',
              is_flag=True)
@click.option('-c', '--compression', type=click.IntRange(0, 9), default=6,
              help='Compression level for data (default: 6)')
@click.option('--confirm/--no-confirm', ' /-Y', default=True,
              help='Confirm before running simulation')
@click.option('--progress/--no-progress', help='Show progress bar',
              default=True)
@click.option('--plot/--no-plot', help='Show graphical plot of model data',
              default=False)
@click.option('--video/--no-video',
              help='Save video of simulation plot. This can slow things '
                   'down. ',
              default=False)
@click.option('--frames/--no-frames',
              help='Save frames of simulation plot. This can slow things '
                   'down. ',
              default=False)
@click.option('--budget', is_flag=True,
              help='Track variable budget over time and show in plot',
              default=False)
@click.option('--resume', type=int,
              help='Resume simulation by restoring from stored data at time index',
              )
@click.option('-eqns', '--show-eqns', is_flag=True,
              help='Show equations that will be solved')
@click.argument('model_file', type=click.File())
def cli_simulate(model_file, output_dir, export, overwrite, compression,
                 confirm, progress,
                 simtime_total, simtime_lims, max_sweeps, max_residual, fipy_solver,
                 plot, video, frames, budget, resume, show_eqns):
    """
    Run simulation from model file
    """

    click.secho('Starting MicroBenthos simulation', fg='green')
    from microbenthos.utils import yaml

    click.echo('Loading model from {}'.format(model_file.name))
    defs = yaml.load(model_file)
    if 'simulation' not in defs:
        defs['simulation'] = {}

    data_outpath = os.path.join(output_dir, 'simulation_data.h5')

    if resume == 0:
        click.secho(
            'Resume = 0 implies to restart simulation. Setting overwrite=True instead',
            fg='yellow')
        resume = None
        overwrite = True

    # both overwrite and resume cannot be true by the user
    if os.path.exists(data_outpath):
        if overwrite and resume is not None:
            click.secho('Both overwrite and resume cannot be set', fg='red')
            raise click.Abort()

        if not confirm and (not resume) and (not overwrite):
            click.secho(
                'Ambiguous case with --no-confirm: file exists and neither --overwrite nor'
                ' --resume were specified',
                fg='red')
            raise click.Abort()

        else:
            if resume:
                overwrite = False
            else:
                click.confirm(
                    'Overwrite existing file: {}?'.format(data_outpath),
                    abort=True)
                overwrite = True
                click.secho('Deleting output path: {}'.format(data_outpath), fg='red')
                os.remove(data_outpath)

    # we want to override the keys in the loaded simulation dictionary,
    # so that when it is created the definition stored on the instance and
    # eventually exported to file includes these user overrides

    sim_kwargs = dict(
        simtime_total=simtime_total,
        fipy_solver=fipy_solver,
        max_sweeps=max_sweeps,
        simtime_lims=simtime_lims,
        max_residual=max_residual,
    )
    for k, v in sim_kwargs.items():
        if v is None:
            continue
        else:
            defs['simulation'][k] = v

    from microbenthos.runners import SimulationRunner
    runner = SimulationRunner(output_dir=output_dir,
                              model=defs['model'],
                              simulation=defs['simulation'])
    if resume:

        import h5py as hdf
        from fipy import PhysicalField

        # open the store and read out the time info
        with hdf.File(data_outpath, 'r') as store:
            tds = store['/time/data']
            nt = len(tds)
            target_time = tds[resume]
            latest_time = tds[-1]
            time_unit = tds.attrs['unit']

        target_time = PhysicalField(target_time, time_unit)
        latest_time = PhysicalField(latest_time, time_unit)

        click.secho(
            '\n\nModel resume set: rewind from latest {} ({}) to {} ({})?'.format(
                latest_time, nt,
                target_time, resume
            ), fg='red')

        if confirm:
            click.confirm('Rewinding model clock can lead to data loss! Continue?',
                          default=False, abort=True)

        try:
            with hdf.File(data_outpath, 'a') as store:
                runner.model.restore_from(store, time_idx=resume)
            click.secho('Model restore successful. Clock = {}\n\n'.format(runner.model.clock),
                        fg='green')
            runner.simulation.simtime_step = 1
            # set a small simtime to start
        except:
            click.secho('Simulation could not be restored from given data file!', fg='red')
            raise  # click.Abort()

    from microbenthos.utils import find_subclasses_recursive
    from microbenthos.exporters import BaseExporter

    _exporters = {e._exports_: e for e in
                  find_subclasses_recursive(BaseExporter)}

    runner._exporter_classes = _exporters

    runner.add_exporter('model_data', compression=compression,
                        overwrite=overwrite)

    if progress:
        runner.add_exporter('progress')

    if plot or video or frames:
        runner.add_exporter('graphic', write_video=video, show=plot,
                            track_budget=budget, write_frames=frames)
        if resume and video:
            click.secho('Video will begin from this simulation run, since resume is set!',
                        fg='yellow')

    for name, exptype in export:
        runner.add_exporter(exptype=exptype, name=name)

    if show_eqns:
        click.secho('Solving the equation(s):', fg='green')
        for neqn, eqn in runner.model.equations.items():
            click.secho(eqn.as_pretty_string(), fg='green')

    click.secho(
        'Simulation setup: solver={0.fipy_solver} '
        'max_sweeps={0.max_sweeps} max_residual={0.residual_target} '
        'timestep_lims=({1}, {2})'.format(
            runner.simulation, *runner.simulation.simtime_lims),
        fg='yellow')
    click.secho('Simulation clock at {}. Run till {}'.format(runner.model.clock,
                                                             runner.simulation.simtime_total),
                fg='yellow')
    if confirm:
        click.confirm('Proceed with simulation run?',
                      default=True, abort=True)

    click.secho('Starting simulation...', fg='green')
    runner.run()
    click.secho('Simulation done.', fg='green')


@cli.group('export')
def export():
    """
    Export options
    """


@export.command('video')
@click.argument('datafile', type=click.Path(dir_okay=False, exists=True))
@click.option('-o', '--outfile', type=click.Path(dir_okay=False),
              help='Name of the output file')
@click.option('-O', '--overwrite', help='Overwrite file, if exists',
              is_flag=True)
@click.option('--style', callback=_matplotlib_style_callback,
              help='Plot style name from matplotlib')
@click.option('--writer', callback=_matplotlib_writer_callback,
              help='Animation writer class to use', default='ffmpeg')
@click.option('--figsize', callback=_figsize_callback,
              help='Figure size in inches (example: "9.6x5.4")')
@click.option('--dpi', type=click.IntRange(100, 400),
              help='Dots per inch for figure export')
@click.option('--show', is_flag=True,
              help='Show figure on screen during export')
@click.option('--budget', is_flag=True,
              help='Show temporal budget error of variables',
              default=False)
@click.option('--fps', help='Frames per second for export (default: 10)',
              default=10, type=click.IntRange(10, 100))
@click.option('--bitrate', help='Bitrate for video encoding (default: 1400)',
              type=click.IntRange(800, 4000), default=1400)
@click.option('--artist-tag', help='Artist tag in metadata')
def export_video(datafile, outfile, overwrite,
                 style, dpi, figsize, writer,
                 show, budget,
                 fps, bitrate, artist_tag,
                 ):
    """
    Export video from model data
    """

    from matplotlib import animation
    dirname = os.path.dirname(datafile)
    outfile = outfile or os.path.join(dirname, 'simulation.mp4')

    if not os.path.splitext(outfile)[1] == '.mp4':
        outfile += '.mp4'

    if os.path.exists(outfile) and not overwrite:
        click.confirm('Overwrite existing file: {}?'.format(outfile),
                      abort=True)

    try:
        Writer = animation.writers[writer]
    except:
        click.secho('Animation writer {!r} not available. Is it installed?'.format(writer),
                    fg='red')
        click.Abort()

    artist_tag = artist_tag or 'MicroBenthos - Arjun Chennu'
    from datetime import datetime
    year = datetime.today().year

    writer = Writer(fps=fps, bitrate=bitrate,
                    metadata=dict(artist=artist_tag, copyright=str(year)))

    from microbenthos.dataview import HDFModelData, ModelPlotter
    from tqdm import tqdm
    import h5py as hdf

    with hdf.File(datafile, 'r') as hf:
        dm = HDFModelData(store=hf)

        plot = ModelPlotter(model=dm, style=style, figsize=figsize, dpi=dpi,
                            track_budget=budget)
        if show:
            plot.show(block=False)

        click.secho(
            'Exporting video to {} (size={}, dpi={})'.format(outfile, figsize,
                                                             dpi), fg='green')

        with writer.saving(plot.fig, outfile, dpi=dpi):

            for i in tqdm(range(len(dm.times)), leave=False, desc=os.path.basename(dirname)):
                plot.update_artists(tidx=i)
                plot.draw()
                writer.grab_frame()

        click.secho('Video export completed', fg='green')


@export.command('model')
@click.argument('model_file', type=click.File())
@click.option('--key', help='Load this key from the input file')
@click.option('-v', '--verbose', is_flag=True, default=False,
              help='Set this to see verbose output')
def export_model(model_file, key, verbose):
    """
    Load a model from a file and export it after validation.
    """
    if verbose:
        click.secho('Loading model from {}'.format(model_file), fg='green')

    from microbenthos.utils import yaml, validate_dict

    defs = yaml.load(model_file)
    if key:
        try:
            defs = defs[key]
        except KeyError:
            click.secho('Could not get key {!r}! Found: {}'.format(
                key, defs.keys()
            ))
            raise click.Abort()

    try:
        valid = validate_dict(defs, key='model')
        from pprint import pformat
        if verbose:
            click.secho('Validated dictionary!', fg='green')

        click.secho(
            yaml.dump(valid, indent=4, explicit_start=True, explicit_end=True),
            fg='yellow')

    except ValueError:
        click.secho('Model definition not validated!', fg='red')
        click.Abort()
    finally:
        if verbose:
            click.secho('Model export done', fg='green')


if __name__ == "__main__":
    cli()
