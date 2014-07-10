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
    created_at = me.DateTimeField()


class Team(me.Document):
    name = me.StringField()
    owner = me.ReferenceField("User")
    members = me.ListField(me.ReferenceField("User"))
    projects = me.ListField(me.EmbeddedDocumentField("Project"))


class Project(NamedEmbeddedDocument):
    module = me.EmbeddedDocumentField("Module")


class Module(NamedEmbeddedDocument):
    pass


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

    def __get_test_data(self):
        return [
            ('GET', '/user', dict(), 200, lambda body: load_json(body), []),
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

        body = transform_body(response.body)
        expect(body).to_be_like(expected_body)
