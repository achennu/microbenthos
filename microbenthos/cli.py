# -*- coding: utf-8 -*-

import os

import click

from microbenthos.model import Simulation

SOLVERS = Simulation.FIPY_SOLVERS

from microbenthos.utils import find_subclasses_recursive
from microbenthos.exporters import BaseExporter

_exporters = {e._exports_: e for e in find_subclasses_recursive(BaseExporter)}

try:
    from matplotlib import style

    STYLES = style.available
except ImportError:
    STYLES = []


@click.group('microbenthos')
@click.option('-v', '--verbosity', count=True, help='Set verbosity of console logging')
@click.option('--logger', help='Set specified logger to loglevel (example: microbenthos.model 20)',
              multiple=True, type=(str, click.IntRange(10, 40)))
def cli(verbosity, logger):
    """Console entry point for microbenthos"""
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


@cli.command('simulate')
@click.option('-o', '--output-dir', type=click.Path(file_okay=False), default=os.getcwd(),
              help='Output directory for simulation')
@click.option('-x', '--export', multiple=True,
              type=(str, str),
              help="Add an exporter to run. Form: -x <name> <export_type>")
@click.option('-T', '--simtime_total', type=str, help='Total simulation time. Example: "10h"')
@click.option('-dt', '--simtime_step', type=str, help='Total simulation time. Example: "10s"')
@click.option('--solver', help='Solver type to use from fipy', type=click.Choice(SOLVERS))
@click.option('-O', '--overwrite', help='Overwrite file, if exists', is_flag=True)
@click.option('-c', '--compression', type=click.IntRange(0, 9), default=6,
              help='Compression level for data (default: 6)')
@click.option('--confirm/--no-confirm', ' /-Y', default=True,
              help='Confirm before running simulation')
@click.option('--progress/--no-progress', help='Show progress bar', default=True)
@click.option('--plot/--no-plot', help='Show graphical plot of model data',
              default=False)
@click.option('--video/--no-video', help='Save video of simulation plot. This can slow things '
                                         'down. ',
              default=False)
@click.option('--budget', is_flag=True, help='Track variable budget over time and show in plot',
              default=False)
@click.argument('model_file', type=click.File())
def cli_simulate(model_file, output_dir, export, overwrite, compression, confirm, progress,
                 simtime_total, simtime_step, solver, plot, video, budget):
    """
    Run simulation from model file
    """

    click.secho('Starting MicroBenthos simulation', fg='green')
    from microbenthos.utils import yaml
    from microbenthos.runners import SimulationRunner

    click.echo('Loading model from {}'.format(model_file.name))
    defs = yaml.load(model_file)

    data_outpath = os.path.join(output_dir, 'simulation_data.h5')
    if os.path.exists(data_outpath) and not overwrite:
        if not confirm:
            overwrite = True
        else:
            click.confirm('Overwrite existing file: {}?'.format(data_outpath),
                          abort=True)
            overwrite = True

    runner = SimulationRunner(output_dir=output_dir,
                              model=defs['model'],
                              simulation=defs['simulation'])
    from fipy import PhysicalField

    if simtime_total:
        simtime_total = PhysicalField(str(simtime_total))
        click.echo('Setting simtime_total = {}'.format(simtime_total))
        runner.simulation.simtime_total = simtime_total

    if simtime_step:
        simtime_step = PhysicalField(str(simtime_step))
        click.echo('Setting simtime_step = {}'.format(simtime_step))
        runner.simulation.simtime_step = PhysicalField(simtime_step)

    if solver:
        click.echo('Setting fipy_solver to {!r}'.format(solver))
        runner.simulation.fipy_solver = solver

    runner._exporter_classes = _exporters

    runner.add_exporter('model_data', compression=compression, overwrite=overwrite)

    if progress:
        runner.add_exporter('progress')

    if plot or video:
        runner.add_exporter('graphic', write_video=video, show=plot, track_budget=budget)

    for name, exptype in export:
        runner.add_exporter(exptype=exptype, name=name)

    click.secho('Full equation: {}'.format(runner.model.full_eqn), fg='red')

    click.secho(
        'Simulation setup: solver={0.fipy_solver} total={0.simtime_total} step={0.simtime_step} '
        'steps={0.total_steps}'.format(
            runner.simulation), fg='green')

    if confirm:
        click.confirm('Proceed with simulation run?',
                      default=True, abort=True)

    click.secho('Starting simulation...', fg='green')
    runner.run()
    click.secho('Simulation done.', fg='green')


@cli.group('export')
def export():
    """
    Export simulation data
    """


@export.command('video')
@click.argument('datafile', type=click.Path(dir_okay=False, exists=True))
@click.option('-o', '--outfile', type=click.Path(dir_okay=False),
              help='Name of the output file')
@click.option('-O', '--overwrite', help='Overwrite file, if exists', is_flag=True)
@click.option('--style', type=click.Choice(STYLES),
              help='Matplotlib style name')
@click.option('--figsize', type=(float, float), default=(9.6, 5.4),
              help='Figure size in inches (default: 9.6, 5.4)')
@click.option('--dpi', type=click.IntRange(100, 300), default=200,
              help='Dots per inch for figure export (default: 200)')
@click.option('--show', is_flag=True, help='Show figure on screen during export')
@click.option('--budget', is_flag=True, help='Show temporal budget error of variables',
              default=False)
def export_video(datafile, outfile, overwrite, style, figsize, dpi, show, budget):
    """
    Export video from model data
    """
    from microbenthos.dataview import HDFModelData, ModelPlotter
    from matplotlib import animation
    from tqdm import tqdm
    import h5py as hdf

    if outfile:
        if os.path.exists(outfile) and not overwrite:
            click.confirm('Overwrite existing file: {}?'.format(outfile),
                          abort=True)
    else:
        # outfile = datafile.replace('.h5', '.mp4')
        outfile = os.path.join(os.path.dirname(datafile), 'simulation.mp4')

    if not os.path.splitext(outfile)[1] == '.mp4':
        outfile += '.mp4'

    try:
        Writer = animation.writers['ffmpeg']
    except:
        click.secho('Animation writer ffmpeg not available. Is it installed?', fg='red')
        click.Abort()

    writer = Writer(fps=15, bitrate=1800,
                    metadata=dict(artist='Microbenthos - Arjun Chennu', copyright='2018'))

    with hdf.File(datafile, 'r') as hf:
        dm = HDFModelData(store=hf)

        plot = ModelPlotter(model=dm, style=style, figsize=figsize, dpi=dpi, track_budget=budget)
        if show:
            plot.show(block=False)

        click.secho('Exporting video to {} with size {} and dpi {}'.format(outfile, figsize,
                                                                           dpi), fg='green')

        with writer.saving(plot.fig, outfile, dpi=dpi):

            for i in tqdm(range(len(dm.times))):
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
        defs = defs[key]

    try:
        valid = validate_dict(defs, key='model')
        from pprint import pformat
        if verbose:
            click.secho('Validated dictionary!', fg='green')

        click.secho(yaml.dump(valid, indent=4, explicit_start=True, explicit_end=True), fg='yellow')

    except ValueError:
        click.secho('Model definition not validated!', fg='red')
        click.Abort()
    finally:
        if verbose:
            click.secho('Model export done', fg='green')






if __name__ == "__main__":
    cli()
