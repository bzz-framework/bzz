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

from datetime import datetime
import types

import mongoengine as me
import cow.server as server
import cow.plugins.mongoengine_plugin as mongoengine_plugin
from preggy import expect
import derpconf.config as config

import bzz
import bzz.signals as signals
import tests.base as base


def load_json(json_string):
    try:
        return json.loads(json_string)
    except ValueError:
        return json.loads(json_string.decode('utf-8'))


class NamedEmbeddedDocument(me.EmbeddedDocument):
    meta = { 'allow_inheritance': True }

    name = me.StringField()


class User(me.Document):
    meta = {'collection': 'EndToEndUser'}

    name = me.StringField()
    age = me.IntField()
    created_at = me.DateTimeField(default=datetime.now)

    @classmethod
    def get_id_field_name(self):
        return User.name


class Team(me.Document):
    name = me.StringField()
    owner = me.ReferenceField("User")
    members = me.ListField(me.ReferenceField("User"))
    projects = me.ListField(me.EmbeddedDocumentField("Project"))

    @classmethod
    def get_id_field_name(self):
        return Team.name


class Project(NamedEmbeddedDocument):
    module = me.EmbeddedDocumentField("Module")

    @classmethod
    def get_id_field_name(self):
        return Project.name


class Module(NamedEmbeddedDocument):
    @classmethod
    def get_id_field_name(self):
        return Module.name


class TestServer(server.Server):
    def get_plugins(self):
        return [
            mongoengine_plugin.MongoEnginePlugin
        ]

    def get_handlers(self):
        routes = [
            bzz.ModelRestHandler.routes_for('mongoengine', User),
            bzz.ModelRestHandler.routes_for('mongoengine', Team),
        ]
        return [route for route_list in routes for route in route_list]


class MongoEngineEndToEndTestCase(base.ApiTestCase):
    def setUp(self):
        super(MongoEngineEndToEndTestCase, self).setUp()
        signals.post_create_instance.receivers = {}
        signals.post_update_instance.receivers = {}
        signals.post_delete_instance.receivers = {}
        User.objects.delete()
        Team.objects.delete()

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

    def __assert_user_data(self, created_at=None, age=None, id_=None, name=None):
        def handle(obj):
            if isinstance(obj, (list, tuple)):
                obj = obj[0]

            if created_at is not None:
                expect(obj['created_at']).to_be_like(created_at)

            if age is not None:
                expect(obj['age']).to_equal(age)

            if id_ is not None:
                expect(obj['id']).to_be_like(id_)

            if name is not None:
                expect(obj['name']).to_equal(name)

        return handle

    def __assert_len(self, expected_length):
        def handle(obj):
            expect(obj).not_to_be_null()
            expect(obj).to_be_instance_of(list)
            expect(obj).to_length(expected_length)
        return handle

    def __get_test_data(self):
        return [
            ('GET', '/user', dict(), 200, lambda body: load_json(body), []),
            ('POST', '/user', dict(body="name=test%20user&age=32"), 200, None, 'OK'),
            ('GET', '/user', dict(), 200, lambda body: load_json(body), self.__assert_user_data(name="test user", age=32)),
            ('GET', '/user/test%20user', dict(), 200, lambda body: load_json(body), self.__assert_user_data(name="test user", age=32)),
            ('PUT', '/user/test%20user', dict(body="age=31"), 200, None, 'OK'),
            ('GET', '/user/test%20user', dict(), 200, lambda body: load_json(body), self.__assert_user_data(name="test user", age=31)),
            ('POST', '/user', dict(body="name=test-user2&age=32"), 200, None, 'OK'),
            ('DELETE', '/user/test-user2', dict(), 200, None, 'OK'),
            ('GET', '/user', dict(), 200, lambda body: load_json(body), self.__assert_len(1)),
        ]

    def test_end_to_end_flow(self):
        data = self.__get_test_data()

        print("")
        print("")
        print("")
        print("Doing end-to-end test:")
        print("")
        for url_arguments in data:
            self.validate_request(url_arguments)
        print("")

    def validate_request(self, (method, url, options, expected_status_code, transform_body, expected_body)):
        self.http_client.fetch(
            self.get_url(url),
            method=method,
            callback=self.stop,
            **options
        )
        response = self.wait()
        expect(response.code).to_equal(expected_status_code)
        print("%s %s - %s" % (method, url, response.code))

        body = response.body
        if transform_body is not None:
            body = transform_body(response.body)

        if isinstance(expected_body, types.FunctionType):
            expected_body(body)
        else:
            expect(body).to_be_like(expected_body)
