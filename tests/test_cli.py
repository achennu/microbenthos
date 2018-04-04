#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
test_microbenthos
----------------------------------

Tests for `microbenthos` module.
"""

from click.testing import CliRunner

from microbenthos import cli


def test_command_line_interface():
    runner = CliRunner()
    result = runner.invoke(cli.cli)
    assert result.exit_code == 0
    assert 'Console entry point for microbenthos' in result.output
    help_result = runner.invoke(cli.cli, ['--help'])
    assert help_result.exit_code == 0
    assert 'Show this message and exit.' in help_result.output
