#!/usr/bin/python
# -*- coding: utf-8 -*-

# This file is part of bzz.
# https://github.com/heynemann/bzz

# Licensed under the MIT license:
# http://www.opensource.org/licenses/MIT-license
# Copyright (c) 2014 Bernardo Heynemann heynemann@gmail.com

import sys

from bzz.version import __version__  # NOQA
try:
    from bzz.model import ModelHive  # NOQA
    from bzz.mock import MockHive  # NOQA
    from bzz.auth import AuthHive, AuthProvider, authenticated  # NOQA
    from bzz.utils import flatten  # NOQA
except ImportError:
    err = sys.exc_info()[1]
    print("%s. Probably setup.py" % err)
