#!/usr/bin/python
# -*- coding: utf-8 -*-

# This file is part of bzz.
# https://github.com/heynemann/bzz

# Licensed under the MIT license:
# http://www.opensource.org/licenses/MIT-license
# Copyright (c) 2014 Bernardo Heynemann heynemann@gmail.com

import unittest as unit
import cow.testing as testing
import cow.server as server

import bzz

class TestCase(unit.TestCase):
    pass

class ApiTestCase(testing.CowTestCase, TestCase):
    def get_server(self):
        return TestServer()
