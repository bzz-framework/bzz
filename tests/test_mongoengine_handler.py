#!/usr/bin/python
# -*- coding: utf-8 -*-

# This file is part of bzz.
# https://github.com/heynemann/bzz

# Licensed under the MIT license:
# http://www.opensource.org/licenses/MIT-license
# Copyright (c) 2014 Bernardo Heynemann heynemann@gmail.com

import cow.server as server
import cow.plugins.mongoengine_plugin as mongoengine_plugin
import tornado.testing as testing
from preggy import expect
import derpconf.config as config

import bzz.mongoengine_handler as bzz
import tests.base as base
import tests.models.mongoengine_models as models


class TestServer(server.Server):
    def get_plugins(self):
        return [
            mongoengine_plugin.MongoEnginePlugin
        ]

    def get_handlers(self):
        return bzz.MongoEngineRestHandler.routes_for(models.User)


class MongoEngineRestHandlerTestCase(base.ApiTestCase):
    def get_config(self):
        return dict(
            MONGO_DATABASES={
                'default': {
                    'host': 'localhost',
                    'port': 3334,
                    'database': 'marketplace_test'
                }
            },
        )

    def get_server(self):
        cfg = config.Config(**self.get_config())
        self.server = TestServer(config=cfg)
        return self.server

    @testing.gen_test
    def test_can_create_user(self):
        response = yield self.http_client.fetch(
            self.get_url('/user/'),
            method='POST',
            body='name=Bernardo%20Heynemann&email=heynemann@gmail.com'
        )

        expect(response.code).to_equal(200)
        expect(response.body).to_equal('OK')
        expect(response.headers).to_include('X-Created-Id')
        expect(response.headers).to_include('location')

        expected_url = '/user/%s/' % response.headers['X-Created-Id']
        expect(response.headers['location']).to_equal(expected_url)
