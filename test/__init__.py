# -*- coding: utf-8 -*-
import atexit
import os.path
import subprocess
import logging


class SetupException(Exception):
    pass


def setup():
    root_path = os.path.dirname(__file__)
    config_path = os.path.join(root_path, 'ngircd.conf')

    result = subprocess.Popen([
        'ngircd',
        '--nodaemon',
        '--config',
        config_path
    ], cwd=root_path, stdout=subprocess.PIPE)

    # Prevents us from hanging forever if ngircd didn't actually
    # start properly (typically because the port was in use)
    if result.returncode not in (0, None):
        raise SetupException('An error occured trying to init ngircd.')

    def _cleanup():
        result.terminate()
        result.wait()

    # Make sure we cleanup ngircd when we're done or we'll have
    # conflicts with the next run.
    atexit.register(_cleanup)

    # Keep reading ngircd's stdout until it has finished setting up
    # and is now listening for incoming connections.
    while True:
        line = result.stdout.readline()
        if 'now listening' in line.lower():
            break

    # Default configuration for the LogPlugin.
    logger = logging.getLogger('LogPlugin')
    logger.setLevel(logging.DEBUG)
