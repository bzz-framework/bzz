#!/usr/bin/python
# -*- coding: utf-8 -*-

# This file is part of bzz.
# https://github.com/heynemann/bzz

# Licensed under the MIT license:
# http://www.opensource.org/licenses/MIT-license
# Copyright (c) 2014 Bernardo Heynemann heynemann@gmail.com

try:
    import ujson as json
except ImportError:
    import json

import urllib
from nose_focus import focus
import mongoengine
import cow.server as server
import cow.plugins.mongoengine_plugin as mongoengine_plugin
import tornado.testing as testing
from preggy import expect
import derpconf.config as config
import bson.objectid as oid

import bzz.mongoengine_handler as bzz
import bzz.signals as signals
import tests.base as base
import tests.models.mongoengine_models as models
import tests.fixtures as fix


def load_json(json_string):
    try:
        return json.loads(json_string)
    except ValueError:
        return json.loads(json_string.decode('utf-8'))


class TestServer(server.Server):
    def get_plugins(self):
        return [
            mongoengine_plugin.MongoEnginePlugin
        ]

    def get_handlers(self):
        routes = [
            bzz.MongoEngineRestHandler.routes_for(models.User),
            bzz.MongoEngineRestHandler.routes_for(models.OtherUser),
            bzz.MongoEngineRestHandler.routes_for(models.Parent),
            bzz.MongoEngineRestHandler.routes_for(models.Team),
        ]
        return [route for route_list in routes for route in route_list]


class MongoEngineRestHandlerTestCase(base.ApiTestCase):
    def setUp(self):
        super(MongoEngineRestHandlerTestCase, self).setUp()
        signals.post_create_instance.receivers = {}
        signals.post_update_instance.receivers = {}
        signals.post_delete_instance.receivers = {}

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
        obj = load_json(response.body)
        expect(obj['email']).to_equal(user.email)
        expect(obj['name']).to_equal(user.name)
        expect(obj['slug']).to_equal(user.slug)

    @testing.gen_test
    def test_getting_invalid_user_fails_with_404(self):
        objectid = oid.ObjectId()
        response = self.fetch(
            '/user/%s' % objectid
        )
        expect(response.code).to_equal(404)

    @testing.gen_test
    def test_can_create_other_user(self):
        response = yield self.http_client.fetch(
            self.get_url('/other_user/'),
            method='POST',
            body='name=Bernardo%20Heynemann&email=heynemann@gmail.com'
        )

        expect(response.code).to_equal(200)
        expect(response.body).to_equal('OK')
        expect(response.headers).to_include('X-Created-Id')
        expect(response.headers['X-Created-Id']).to_equal('bernardo-heynemann')
        expect(response.headers).to_include('location')

        expected_url = '/other_user/%s/' % response.headers['X-Created-Id']
        expect(response.headers['location']).to_equal(expected_url)

    @testing.gen_test
    def test_can_get_other_user(self):
        user = fix.OtherUserFactory.create()
        response = yield self.http_client.fetch(
            self.get_url('/other_user/%s' % user.slug),
        )
        expect(response.code).to_equal(200)
        obj = load_json(response.body)
        expect(obj['user']).to_equal('%s <%s>' % (user.name, user.email))

    @testing.gen_test
    def test_can_get_list(self):
        models.User.objects.delete()
        for i in range(30):
            fix.UserFactory.create()

        response = yield self.http_client.fetch(
            self.get_url('/user/'),
        )
        expect(response.code).to_equal(200)
        obj = load_json(response.body)
        expect(obj).to_length(20)

        response = yield self.http_client.fetch(
            self.get_url('/user/?page=2'),
        )
        expect(response.code).to_equal(200)
        obj = load_json(response.body)
        expect(obj).to_length(10)

        response = yield self.http_client.fetch(
            self.get_url('/user/?page=3'),
        )
        expect(response.code).to_equal(200)
        obj = load_json(response.body)
        expect(obj).to_length(10)

        response = yield self.http_client.fetch(
            self.get_url('/user/?page=qwe'),
        )
        expect(response.code).to_equal(200)
        obj = load_json(response.body)
        expect(obj).to_length(20)

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

    @testing.gen_test
    def test_can_delete_not_found_instance(self):
        response = yield self.http_client.fetch(
            self.get_url('/other_user/invalid'),
            method='DELETE'
        )
        expect(response.code).to_equal(200)
        expect(response.body).to_equal('FAIL')

    @testing.gen_test
    def test_can_subscribe_to_create_signal(self):
        instances = {}

        def handle_post_create(sender, instance, handler):
            instances[instance.slug] = instance

        signals.post_create_instance.connect(handle_post_create)

        response = yield self.http_client.fetch(
            self.get_url('/user/'),
            method='POST',
            body='name=Bernardo%20Heynemann&email=heynemann@gmail.com'
        )

        expect(response.code).to_equal(200)
        expect(instances).to_include('bernardo-heynemann')

    @testing.gen_test
    def test_can_subscribe_to_update_signal(self):
        instances = {}
        updated = {}

        def handle_post_update(sender, instance, updated_fields, handler):
            instances[instance.slug] = instance
            updated[instance.slug] = updated_fields

        signals.post_update_instance.connect(handle_post_update)

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

        expect(instances).to_include('rafael-floriano')
        expect(updated).to_include('rafael-floriano')
        expect(updated['rafael-floriano']).to_be_like({
            'name': {
                'from': user.name,
                'to': 'Rafael Floriano'
            },
            'email': {
                'from': user.email,
                'to': 'rflorianobr@gmail.com'
            }
        })

    @testing.gen_test
    def test_can_subscribe_to_delete_signal(self):
        instances = {}

        def handle_post_create(sender, instance, handler):
            instances[instance.slug] = instance

        signals.post_delete_instance.connect(handle_post_create)

        user = fix.UserFactory.create()
        response = yield self.http_client.fetch(
            self.get_url('/user/%s' % user.id),
            method='DELETE'
        )
        expect(response.code).to_equal(200)
        expect(instances).to_include(user.slug)

    @testing.gen_test
    def test_can_save_parent_with_child(self):
        response = yield self.http_client.fetch(
            self.get_url('/parent/'),
            method='POST',
            body='name=Bernardo%20Heynemann&child.first_name=Rodrigo&child.last_name=Lucena'
        )

        expect(response.code).to_equal(200)
        expect(response.body).to_equal('OK')
        expect(response.headers).to_include('X-Created-Id')
        expect(response.headers).to_include('location')

        parent = models.Parent.objects.get(id=response.headers['X-Created-Id'])
        expect(parent.name).to_equal('Bernardo Heynemann')
        expect(parent.child).not_to_be_null()
        expect(parent.child.first_name).to_equal('Rodrigo')
        expect(parent.child.last_name).to_equal('Lucena')

    @testing.gen_test
    def test_can_save_parent_with_grandchild(self):
        response = yield self.http_client.fetch(
            self.get_url('/parent/'),
            method='POST',
            body='name=Bernardo%20Heynemann'
            '&child.first_name=Rodrigo'
            '&child.last_name=Lucena'
            '&child.child.first_name=Polo'
            '&child.child.last_name=Norte'
        )

        expect(response.code).to_equal(200)
        expect(response.body).to_equal('OK')
        expect(response.headers).to_include('X-Created-Id')
        expect(response.headers).to_include('location')

        parent = models.Parent.objects.get(id=response.headers['X-Created-Id'])
        expect(parent.name).to_equal('Bernardo Heynemann')

        expect(parent.child).not_to_be_null()
        expect(parent.child.first_name).to_equal('Rodrigo')
        expect(parent.child.last_name).to_equal('Lucena')

        expect(parent.child.child).not_to_be_null()
        expect(parent.child.child.first_name).to_equal('Polo')
        expect(parent.child.child.last_name).to_equal('Norte')

    @testing.gen_test
    def test_can_update_grandchild(self):
        parent = models.Parent.objects.create(name="test-user")

        response = yield self.http_client.fetch(
            self.get_url('/parent/%s/' % str(parent.id)),
            method='PUT',
            body='child.first_name=Rodrigo'
            '&child.last_name=Lucena'
            '&child.child.first_name=Polo'
            '&child.child.last_name=Norte'
        )

        expect(response.code).to_equal(200)
        expect(response.body).to_equal('OK')

        loaded = models.Parent.objects.get(id=parent.id)

        expect(loaded.child).not_to_be_null()
        expect(loaded.child.first_name).to_equal('Rodrigo')
        expect(loaded.child.last_name).to_equal('Lucena')

        expect(loaded.child.child).not_to_be_null()
        expect(loaded.child.child.first_name).to_equal('Polo')
        expect(loaded.child.child.last_name).to_equal('Norte')

    #@testing.gen_test
    #def test_can_save_parent_then_child(self):
        #response = yield self.http_client.fetch(
            #self.get_url('/parent/'),
            #method='POST',
            #body='name=Bernardo%20Heynemann'
        #)

        #expect(response.code).to_equal(200)
        #expect(response.body).to_equal('OK')
        #expect(response.headers).to_include('X-Created-Id')
        #pk = response.headers['X-Created-Id']

        #response = yield self.http_client.fetch(
            #self.get_url('/parent/%s/child/' % pk),
            #method='POST',
            #body='first_name=Rodrigo&last_name=Lucena'
        #)

        #expect(response.code).to_equal(200)
        #expect(response.body).to_equal('OK')

        #parent = models.Parent.objects.get(id=pk)
        #expect(parent.name).to_equal('Bernardo Heynemann')
        #expect(parent.child).not_to_be_null()
        #expect(parent.child.first_name).to_equal('Rodrigo')
        #expect(parent.child.last_name).to_equal('Lucena')

    @testing.gen_test
    def test_can_save_user_team(self):
        team = models.Team.objects.create(name="test-team")

        response = yield self.http_client.fetch(
            self.get_url('/team/%s/users/' % str(team.id)),
            method='POST',
            body='name=Bernardo%20Heynemann&email=foo@bar.com'
        )

        team = models.Team.objects.get(id=team.id)

        expect(response.code).to_equal(200)
        expect(team.users).to_length(1)
