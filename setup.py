#!/usr/bin/env python
# -*- coding: utf8 -*-
from setuptools import setup, find_packages

setup(
    name="UtopiaIRC",
    version="0.1.2",
    description="Simple gevent-based IRC bot, because why not.",
    url="http://github.com/TkTech/utopia",
    author="Tyler Kennedy",
    author_email="tk@tkte.ch",
    keywords=[
        "irc",
        "bot"
    ],
    classifiers=[
        "Programming Language :: Python",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Developers",
    ],
    packages=find_packages()
)
