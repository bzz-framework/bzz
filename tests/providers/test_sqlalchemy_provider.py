#!/usr/bin/python
# -*- coding: utf-8 -*-

# This file is part of bzz.
# https://github.com/heynemann/bzz

# Licensed under the MIT license:
# http://www.opensource.org/licenses/MIT-license
# Copyright (c) 2014 Bernardo Heynemann heynemann@gmail.com

import locale

import cow.server as server
import cow.plugins.sqlalchemy_plugin as sqlalchemy_plugin
import tornado.testing as testing
from tornado.httpclient import HTTPError
from preggy import expect
import derpconf.config as config
import bson.objectid as oid

import bzz
import bzz.signals as signals
import bzz.utils as utils
import tests.base as base
import tests.models.sqlalchemy_models as models
import tests.fixtures as fix


def load_json(json_string):
    try:
        return utils.loads(json_string)
    except ValueError:
        return utils.loads(json_string.decode('utf-8'))


class TestServer(server.Server):
    def get_plugins(self):
        return [
            sqlalchemy_plugin.SQLAlchemyPlugin
        ]

    def get_handlers(self):
        routes = [
            bzz.ModelHive.routes_for('sqlalchemy', models.CustomQuerySet),
        ]
        return bzz.flatten(routes)


class SQLAlchemyTestCase(base.ApiTestCase):
    def setUp(self):
        super(SQLAlchemyTestCase, self).setUp()
        self.server.application.db = self.server.application.get_sqlalchemy_session()
        models.Base.metadata.create_all(bind=self.server.application.db.connection())
        self.server.application.db.query(models.CustomQuerySet).delete()

    def get_config(self):
        return dict(
            SQLALCHEMY_AUTO_FLUSH=True,
            SQLALCHEMY_POOL_MAX_OVERFLOW=1,
            SQLALCHEMY_POOL_SIZE=1,
            SQLALCHEMY_CONNECTION_STRING="mysql://root@localhost/test_bzz"
        )

    def get_server(self):
        cfg = config.Config(**self.get_config())
        self.server = TestServer(config=cfg)
        return self.server

    @testing.gen_test
    def test_can_get_user_list_with_custom_queryset(self):
        user = models.CustomQuerySet(prop="Bernardo Heynemann")
        user.save(self.server.application.db)

        user = models.CustomQuerySet(prop="Rafael Floriano")
        user.save(self.server.application.db)

        response = yield self.http_client.fetch(
            self.get_url('/custom_query_set'),
        )

        expect(response.code).to_equal(200)
        expect(response.body).not_to_be_empty()

        obj = load_json(response.body)
        expect(obj).to_length(1)

        expect(obj[0]['prop']).to_equal('Bernardo Heynemann')

    @testing.gen_test
    def test_can_get_user_instance_with_custom_queryset(self):
        user = models.CustomQuerySet(prop="Bernardo Heynemann")
        user.save(self.server.application.db)

        user = models.CustomQuerySet(prop="Rafael Floriano")
        user.save(self.server.application.db)

        err = expect.error_to_happen(HTTPError)
        with err:
            yield self.http_client.fetch(
                self.get_url('/custom_query_set/%s' % user.id),
            )
        expect(err.error.code).to_equal(404)
