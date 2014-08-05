#!/usr/bin/python
# -*- coding: utf-8 -*-

# This file is part of bzz.
# https://github.com/heynemann/bzz

# Licensed under the MIT license:
# http://www.opensource.org/licenses/MIT-license
# Copyright (c) 2014 Bernardo Heynemann heynemann@gmail.com

from datetime import datetime

import unittest as unit
import cow.testing as testing
import cow.server as server
import cow.plugins.mongoengine_plugin as mongoengine_plugin
import derpconf.config as config


class TestCase(unit.TestCase):
    pass


class TestServer(server.Server):
    def get_plugins(self):
        return [
            mongoengine_plugin.MongoEnginePlugin
        ]

    def get_handlers(self):
        routes = []
        return routes


class ApiTestCase(testing.CowTestCase, TestCase):
    def get_config(self):
        return dict(
            MONGO_DATABASES={
                'default': {
                    'host': 'localhost',
                    'port': 3334,
                    'database': 'bzz_test'
                }
            },
        )

    def get_server(self):
        cfg = config.Config(**self.get_config())
        self.server = TestServer(config=cfg)
        return self.server

    def mock_auth_cookie(self, user_id, provider, data=None, token='12345', expiration=None):
        if data is None:
            data = {}

        if expiration is None:
            expiration = datetime(year=5000, month=11, day=30)

        jwt = self.server.application.authentication_options['jwt']
        token = jwt.encode({
            'sub': user_id, 'data': data, 'iss': provider, 'token': token,
            'exp': expiration
        })
        cookie_name = self.server.application.authentication_options['cookie_name']
        return '='.join((
            cookie_name, token.decode('utf-8')
        ))
