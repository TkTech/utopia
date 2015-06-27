#!/usr/bin/env python
# -*- coding: utf8 -*-
from setuptools import setup, find_packages

setup(
    name="utopia",
    version="1.0.0",
    description="Yet another IRC framework.",
    url="http://github.com/TkTech/utopia",
    author="Tyler Kennedy",
    author_email="tk@tkte.ch",
    classifiers=[
        "Programming Language :: Python",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Developers",
    ],
    packages=find_packages(),
    install_requires=[
        'gevent',
        'blinker'
    ],
    tests_require=[
        'sniffer',
        'nose'
    ],
    test_suite='nose.collector'
)
