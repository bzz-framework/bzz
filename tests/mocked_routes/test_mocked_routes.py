#!/usr/bin/python
# -*- coding: utf-8 -*-

# This file is part of bzz.
# https://github.com/heynemann/bzz

# Licensed under the MIT license:
# http://www.opensource.org/licenses/MIT-license
# Copyright (c) 2014 Bernardo Heynemann heynemann@gmail.com

import cow.server as server
from preggy import expect
import tornado.testing as testing
import derpconf.config as config
from tornado.httpclient import HTTPError

import tests.base as base
import bzz


class TestServer(server.Server):

    def get_handlers(self):
        routes = bzz.MockHive.routes_for([
            ('GET', '/much/api', dict(body='much api')),
            ('POST', '/much/api'),
            ('*', '/much/match', dict(body='such match')),
            ('*', r'/such/.*', dict(body='such match')),
            ('GET', '/much/error', dict(body='WOW', status=404)),
            ('GET', '/much/authentication', dict(body='WOW', cookies={'super': 'cow'})),
            ('GET', '/much/function', dict(body=lambda x: x.method)),
            ('GET', '/much/come/first', dict(body='FIRST')),
            ('*', '/much/come/first', dict(body='NOT FIRTH')),
        ])
        return routes


class TestMockedRoutes(base.ApiTestCase):
    def get_config(self):
        return {}

    def get_server(self):
        cfg = config.Config(**self.get_config())
        self.server = TestServer(config=cfg)
        return self.server

    @testing.gen_test
    def test_can_get_exactly_match(self):
        response = yield self.http_client.fetch(
            self.get_url('/much/api'),
        )
        expect(response.code).to_equal(200)
        expect(response.body).to_equal('much api')

    @testing.gen_test
    def test_can_post_exactly_match(self):
        response = yield self.http_client.fetch(
            self.get_url('/much/api'),
            method='POST',
            body='much anything'
        )
        expect(response.code).to_equal(200)
        expect(response.body).to_equal('')

    @testing.gen_test
    def test_can_get_method_wildcard(self):
        response = yield self.http_client.fetch(
            self.get_url('/much/match'),
        )
        expect(response.code).to_equal(200)
        expect(response.body).to_equal('such match')

    @testing.gen_test
    def test_can_post_method_wildcard(self):
        response = yield self.http_client.fetch(
            self.get_url('/much/match'),
            method='POST',
            body='much wow'
        )
        expect(response.code).to_equal(200)
        expect(response.body).to_equal('such match')

    @testing.gen_test
    def test_can_get_url_regex(self):
        response = yield self.http_client.fetch(
            self.get_url('/such/match'),
        )
        expect(response.code).to_equal(200)
        expect(response.body).to_equal('such match')

    @testing.gen_test
    def test_can_post_url_regex(self):
        response = yield self.http_client.fetch(
            self.get_url('/such/match'),
            method='POST',
            body='such magic'
        )
        expect(response.code).to_equal(200)
        expect(response.body).to_equal('such match')

    @testing.gen_test
    def test_can_get_cookies(self):
        response = yield self.http_client.fetch(
            self.get_url('/much/authentication')
        )
        expect(response.code).to_equal(200)
        expect(response.body).to_equal('WOW')
        expect(response.headers['Set-Cookie']).to_equal('super=cow; Path=/')

    @testing.gen_test
    def test_can_set_error(self):
        err = expect.error_to_happen(HTTPError)
        with err:
            yield self.http_client.fetch(
                self.get_url('/much/error'),
                method='GET'
            )
        expect(err).to_have_an_error_message_of('HTTP 404: Not Found')

    @testing.gen_test
    def test_cant_delete_exactly_match(self):
        err = expect.error_to_happen(HTTPError)
        with err:
            yield self.http_client.fetch(
                self.get_url('/much/api'),
                method='DELETE'
            )
        expect(err).to_have_an_error_message_of('HTTP 405: Method Not Allowed')

    @testing.gen_test
    def test_body_can_be_a_function(self):
        response = yield self.http_client.fetch(
            self.get_url('/much/function')
        )
        expect(response.code).to_equal(200)
        expect(response.body).to_equal('GET')

    @testing.gen_test
    def test_should_respect_definition_order(self):
        response = yield self.http_client.fetch(
            self.get_url('/much/come/first')
        )
        expect(response.code).to_equal(200)
        expect(response.body).to_equal('FIRST')
