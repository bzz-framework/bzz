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
from preggy import expect
import derpconf.config as config

import bzz.mongoengine_handler as bzz
import tests.base as base
import tests.models.mongoengine_models as models

import tests.fixtures as fix

try:
    import ujson as json
except ImportError:
    import json


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
                    'database': 'bzz_test'
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

    @testing.gen_test
    def test_can_get_user(self):
        user = fix.UserFactory.create()
        response = yield self.http_client.fetch(
            self.get_url('/user/%s' % user.id),
        )
        expect(response.code).to_equal(200)
        obj = json.loads(response.body)
        expect(obj['email']).to_equal(user.email)
        expect(obj['name']).to_equal(user.name)
        expect(obj['slug']).to_equal(user.slug)

    @testing.gen_test
    def test_can_get_list(self):
        models.User.objects.delete()
        for i in xrange(30):
            fix.UserFactory.create()

        response = yield self.http_client.fetch(
            self.get_url('/user/'),
        )
        expect(response.code).to_equal(200)
        objs = json.loads(response.body)
        expect(len(objs)).to_equal(20)

        response = yield self.http_client.fetch(
            self.get_url('/user/?page=2'),
        )
        expect(response.code).to_equal(200)
        objs = json.loads(response.body)
        expect(len(objs)).to_equal(10)

        response = yield self.http_client.fetch(
            self.get_url('/user/?page=3'),
        )
        expect(response.code).to_equal(200)
        objs = json.loads(response.body)
        expect(len(objs)).to_equal(10)

    @testing.gen_test
    def test_can_update(self):
        user = fix.UserFactory.create()
        response = yield self.http_client.fetch(
            self.get_url('/user/%s' % user.id),
            method='PUT',
            headers={
                "Content-Type": "application/x-www-form-urlencoded"
            },
            body='name=Rafael%20Floriano&email=rflorianobr@gmail.com'
        )
        expect(response.code).to_equal(200)
        expect(response.body).to_equal('OK')

        loaded_user = models.User.objects.get(id=user.id)
        expect(loaded_user.name).to_equal('Rafael Floriano')
        expect(loaded_user.slug).to_equal('rafael-floriano')
        expect(loaded_user.email).to_equal('rflorianobr@gmail.com')

    @testing.gen_test
    def test_can_delete(self):
        user = fix.UserFactory.create()
        response = yield self.http_client.fetch(
            self.get_url('/user/%s' % user.id),
            method='DELETE'
        )
        expect(response.code).to_equal(200)
        expect(response.body).to_equal('OK')

        with expect.error_to_happen(mongoengine.errors.DoesNotExist):
            models.User.objects.get(id=user.id)
