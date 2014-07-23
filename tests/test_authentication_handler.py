#!/usr/bin/python
# -*- coding: utf-8 -*-

# This file is part of bzz.
# https://github.com/heynemann/bzz

# Licensed under the MIT license:
# http://www.opensource.org/licenses/MIT-license
# Copyright (c) 2014 Bernardo Heynemann heynemann@gmail.com

from datetime import datetime
from mock import Mock, patch

import cow.server as server
import tornado.testing as testing
import tornado.gen as gen
from tornado.httpclient import HTTPError
from preggy import expect
import derpconf.config as config

import bzz
import bzz.utils as utils
import tests.base as base
from bzz.auth_handler import GoogleProvider


class MockProvider(bzz.AuthenticationProvider):
    @classmethod
    def get_name(self):
        return 'mock'

    @classmethod
    @gen.coroutine
    def authenticate(cls, access_token):
        raise gen.Return({'id': "123"})

class MockProviderUnauthorized(bzz.AuthenticationProvider):
    @classmethod
    def get_name(cls):
        return 'mock2'

    @classmethod
    @gen.coroutine
    def authenticate(cls, access_token):
        raise gen.Return(None)

def load_json(json_string):
    try:
        return utils.loads(json_string)
    except ValueError:
        return utils.loads(json_string.decode('utf-8'))


class TestServer(server.Server):

    def __init__(self, *args, **kwargs):
        self.io_loop = kwargs.pop('io_loop', None)
        super(TestServer, self).__init__(*args, **kwargs)

    @property
    def handlers_cfg(self):
        return {
            'cookie_name': 'TEST_AUTH_COOKIE',
            'secret_key': 'TEST_SECRET_KEY'
        }

    def get_handlers(self):
        routes = [
            bzz.AuthenticationHandler.routes_for(
                MockProvider(self.io_loop), **self.handlers_cfg),
            bzz.AuthenticationHandler.routes_for(
                MockProviderUnauthorized(self.io_loop), **self.handlers_cfg),
            bzz.AuthenticationHandler.routes_for(
                GoogleProvider(self.io_loop), **self.handlers_cfg),
        ]
        return [route for route_list in routes for route in route_list]


class AuthenticationHandlerTestCase(base.ApiTestCase):
    def setUp(self):
        super(AuthenticationHandlerTestCase, self).setUp()

    def get_config(self):
        return {}

    def get_server(self):
        cfg = config.Config(**self.get_config())
        self.server = TestServer(config=cfg, io_loop=self.io_loop)
        return self.server

    def mock_auth_cookie(
            self, user_id, provider, token='12345',
            expiration=datetime(year=5000, month=11, day=30)):

        jwt = utils.Jwt(self.server.handlers_cfg['secret_key'])
        token = jwt.encode({
            'sub': user_id, 'iss': provider, 'token': token, 'exp': expiration
        })
        return '='.join((
            self.server.handlers_cfg['cookie_name'], token.decode('utf-8')
        ))

    @testing.gen_test
    def test_can_authenticate(self):
        response = yield self.http_client.fetch(
            self.get_url('/authenticate/mock/'),
            method='POST',
            body=utils.dumps(dict(access_token='1234567890'))
        )

        expect(response.code).to_equal(200)
        expect(load_json(response.body)).to_equal(dict(authenticated=True))
        expect(self.server.handlers_cfg['cookie_name'] in response.headers.get('Set-Cookie')).to_equal(True)

    @testing.gen_test
    def test_cant_authenticate(self):
        try:
            yield self.http_client.fetch(
                self.get_url('/authenticate/mock2/'),
                method='POST',
                body=utils.dumps(dict(access_token='1234567890'))
            )
        except HTTPError as e:
            expect(e.response.code).to_equal(401)
            expect(e.response.reason).to_equal('Unauthorized')
            expect(e.response.headers.get('Cookie')).to_equal(None)
            expect(e.response.headers.get('Set-Cookie')).to_equal(None)
        else:
            assert False, 'Should not get this far'

    @testing.gen_test
    def test_can_check_authenticated_request(self):
        response = yield self.http_client.fetch(
            self.get_url('/authenticate/mock/'),
            headers={'Cookie': self.mock_auth_cookie(0, 'mock')}
        )

        expect(response.code).to_equal(200)
        expect(load_json(response.body)).to_equal(dict(authenticated=True))

    @testing.gen_test
    def test_can_check_not_authenticated_request(self):
        response = yield self.http_client.fetch(
            self.get_url('/authenticate/mock/')
        )

        expect(response.code).to_equal(200)
        expect(load_json(response.body)).to_equal(dict(authenticated=False))

    @testing.gen_test
    def test_cannot_authenticate_a_user_with_invalid_google_plus_token(self):
        try:
            response = yield self.http_client.fetch(
                self.get_url('/authenticate/google/'), method='POST',
                body=utils.dumps({
                    'access_token': 'INVALID-TOKEN',
                })
            )
        except HTTPError as e:
            response = e.response
        expect(response.code).to_equal(401)
        expect(response.reason).to_equal('Unauthorized')

    @testing.gen_test
    def test_can_authenticate_a_user_with_valid_google_plus_token(self):
        with patch.object(GoogleProvider, '_fetch_userinfo') as provider_mock:
            result = gen.Future()
            response_mock = Mock(code=200, body=(
                '{"email":"test@gmail.com", "name":"Teste", "id":"56789"}'
            ))
            result.set_result(response_mock)
            provider_mock.return_value = result
            try:
                response = yield self.http_client.fetch(
                    self.get_url('/authenticate/google/'), method='POST',
                    body=utils.dumps({
                        'access_token': 'VALID-TOKEN',
                    })
                )
            except HTTPError as e:
                response = e.response

            expect(response.code).to_equal(200)
            expect(utils.loads(response.body)['authenticated']).to_be_true()
