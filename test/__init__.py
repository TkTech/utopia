# -*- coding: utf-8 -*-
import os.path
import subprocess
import logging

import psutil


def setup():
    root_path = os.path.dirname(__file__)
    config_path = os.path.join(root_path, 'ngircd.conf')
    pid_path = os.path.join(root_path, 'ngircd.pid')

    result = subprocess.Popen([
        'ngircd',
        '--nodaemon',
        '--config',
        config_path
    ], cwd=root_path, stdout=subprocess.PIPE)

    with open(pid_path, 'w') as fout:
        fout.write(str(result.pid))

    while True:
        line = result.stdout.readline()
        if 'now listening' in line.lower():
            break

    # Default configuration for the LogPlugin.
    logger = logging.getLogger('LogPlugin')
    logger.setLevel(logging.DEBUG)


def teardown():
    root_path = os.path.dirname(__file__)
    pid_path = os.path.join(root_path, 'ngircd.pid')

    with open(pid_path, 'r') as fin:
        pid = int(fin.read())

        p = psutil.Process(pid)
        p.terminate()
