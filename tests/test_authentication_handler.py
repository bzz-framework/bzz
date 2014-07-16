#!/usr/bin/python
# -*- coding: utf-8 -*-

# This file is part of bzz.
# https://github.com/heynemann/bzz

# Licensed under the MIT license:
# http://www.opensource.org/licenses/MIT-license
# Copyright (c) 2014 Bernardo Heynemann heynemann@gmail.com

import mongoengine
import cow.server as server
import cow.plugins.mongoengine_plugin as mongoengine_plugin
import tornado.testing as testing
import tornado.gen as gen
from tornado.httpclient import HTTPError
from preggy import expect
import derpconf.config as config
import bson.objectid as oid
from ujson import dumps

import bzz
import bzz.signals as signals
import bzz.utils as utils
import tests.base as base
import tests.models.mongoengine_models as models
import tests.fixtures as fix


class MockProvider(bzz.AuthenticationProvider):

    @classmethod
    def get_name(cls):
        return 'mock'

    @classmethod
    @gen.coroutine
    def authenticate(cls, access_token):
        return {'id': "123"}


def load_json(json_string):
    try:
        return utils.loads(json_string)
    except ValueError:
        return utils.loads(json_string.decode('utf-8'))


class TestServer(server.Server):
    def get_handlers(self):
        routes = [
            bzz.AuthenticationHandler.routes_for(MockProvider),
        ]
        return [route for route_list in routes for route in route_list]


class AuthenticationHandlerTestCase(base.ApiTestCase):
    def setUp(self):
        super(AuthenticationHandlerTestCase, self).setUp()

    def get_config(self):
        return {}

    def get_server(self):
        cfg = config.Config(**self.get_config())
        self.server = TestServer(config=cfg)
        return self.server

    from nose_focus import focus
    @focus
    @testing.gen_test
    def test_can_authenticate(self):
        response = yield self.http_client.fetch(
            self.get_url('/authenticate/mock/'),
            method='POST',
            body=dumps(dict(access_token='1234567890'))
        )

        expect(response.code).to_equal(200)
        expect(response.body).to_equal('OK')
        expect('AUTH_TOKEN' in response.headers.get('Set-Cookie')).to_equal(True)
