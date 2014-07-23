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
from tornado.web import RequestHandler
from tornado.httpclient import HTTPError
from preggy import expect
import derpconf.config as config

import bzz
import bzz.signals as signals
import bzz.utils as utils
import tests.base as base
from bzz.auth_handler import GoogleProvider


def load_json(json_string):
    try:
        return utils.loads(json_string)
    except ValueError:
        return utils.loads(json_string.decode('utf-8'))


class MockProvider(bzz.AuthProvider):
    @gen.coroutine
    def authenticate(self, access_token):
        raise gen.Return({'id': "123"})


class MockUnauthorizedProvider(bzz.AuthProvider):
    @gen.coroutine
    def authenticate(self, access_token):
        raise gen.Return(None)


class TestAuthHandler(RequestHandler):

    @bzz.auth_handler.authenticated
    def get(self):
        self.write('OK')


class TestServer(server.Server):

    def __init__(self, *args, **kwargs):
        self.io_loop = kwargs.pop('io_loop', None)
        super(TestServer, self).__init__(*args, **kwargs)

    def get_handlers(self):
        handlers_list = bzz.AuthHive.routes_for([
            GoogleProvider(self.io_loop),
            MockUnauthorizedProvider(self.io_loop),
            MockProvider(self.io_loop)
        ])
        handlers_list += [
            ('/test_authentication/', TestAuthHandler)
        ]
        return handlers_list


class AuthHandlerTestCase(base.ApiTestCase):
    def setUp(self):
        super(AuthHandlerTestCase, self).setUp()

    def get_config(self):
        return {}

    def get_app(self):
        app = super(AuthHandlerTestCase, self).get_app()
        config = {
            'cookie_name': 'TEST_AUTH_COOKIE',
            'secret_key': 'TEST_SECRET_KEY',
            'expiration': 1200
        }
        bzz.AuthHive.configure(app, **config)
        return app

    def get_server(self):
        cfg = config.Config(**self.get_config())
        self.server = TestServer(config=cfg, io_loop=self.io_loop)
        return self.server

    def mock_auth_cookie(
            self, user_id, provider, data={}, token='12345',
            expiration=datetime(year=5000, month=11, day=30)):

        jwt = self.server.application.authentication_options['jwt']
        token = jwt.encode({
            'sub': user_id, 'data': data, 'iss': provider, 'token': token,
            'exp': expiration
        })
        cookie_name = self.server.application.authentication_options['cookie_name']
        return '='.join((
            cookie_name, token.decode('utf-8')
        ))

    @testing.gen_test
    def test_cant_authenticate_with_invalid_provider(self):
        try:
            response = yield self.http_client.fetch(
                self.get_url('/authenticate/'),
                method='POST',
                body=utils.dumps({
                    'access_token': '1234567890', 'provider': 'invalid'
                })
            )
        except HTTPError as e:
            response = e.response

        expect(response.code).to_equal(401)
        expect(response.reason).to_equal('Unauthorized')

    @testing.gen_test
    def test_automagic_provider_name(self):
        class TestProvider(bzz.AuthProvider):
            pass
        instance = TestProvider()
        expect(instance.get_name()).to_equal('test')

    @testing.gen_test
    def test_can_authenticate(self):
        response = yield self.http_client.fetch(
            self.get_url('/authenticate/'),
            method='POST',
            body=utils.dumps({
                'access_token': '1234567890', 'provider': 'mock'
            })
        )

        expect(response.code).to_equal(200)
        expect(load_json(response.body)).to_equal(dict(authenticated=True))
        cookie_name = self.server.application.authentication_options['cookie_name']
        expect(cookie_name in response.headers.get('Set-Cookie')).to_equal(True)

    @testing.gen_test
    def test_cant_authenticate(self):
        try:
            yield self.http_client.fetch(
                self.get_url('/authenticate/'),
                method='POST',
                body=utils.dumps({
                    'access_token': '1234567890', 'provider': 'mockunauthorized'
                })
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
            self.get_url('/authenticate/'),
            headers={'Cookie': self.mock_auth_cookie(0, 'mock', data={'id': 0})}
        )

        expect(response.code).to_equal(200)
        expect(load_json(response.body)).to_equal(dict(
            authenticated=True, user_data={'id': 0}
        ))

    @testing.gen_test
    def test_can_check_not_authenticated_request(self):
        response = yield self.http_client.fetch(
            self.get_url('/authenticate/')
        )

        expect(response.code).to_equal(200)
        expect(load_json(response.body)).to_equal(dict(authenticated=False))

    @testing.gen_test
    def test_cannot_authenticate_a_user_with_invalid_google_plus_token(self):
        with patch.object(GoogleProvider, '_fetch_userinfo') as provider_mock:
            result = gen.Future()
            response_mock = Mock(code=401, reason='Unauthorized')
            result.set_result(response_mock)
            provider_mock.return_value = result
            try:
                response = yield self.http_client.fetch(
                    self.get_url('/authenticate/'), method='POST',
                    body=utils.dumps({
                        'access_token': 'INVALID-TOKEN', 'provider': 'google'
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
                '{"email":"test@gmail.com", "name":"teste", "id":"56789"}'
            ))
            result.set_result(response_mock)
            provider_mock.return_value = result
            try:
                response = yield self.http_client.fetch(
                    self.get_url('/authenticate/'), method='POST',
                    body=utils.dumps({
                        'access_token': 'VALID-TOKEN', 'provider': 'google'
                    })
                )
            except HTTPError as e:
                response = e.response

            expect(response.code).to_equal(200)
            expect(utils.loads(response.body)['authenticated']).to_be_true()

    @testing.gen_test
    def test_can_send_signal_on_post_authentication(self):

        test_result = {}

        @signals.authorized_user.connect
        def test_signal(provider, user_data=None):
            test_result['provider'] = 'google'
            expect(provider).to_equal('google')
            expect(user_data).to_equal({
                "provider": "google",
                "email":"test@gmail.com", "name":"Teste", "id":"56789"
            })

        with patch.object(GoogleProvider, '_fetch_userinfo') as provider_mock:
            result = gen.Future()
            response_mock = Mock(code=200, body=(
                '{"email":"test@gmail.com", "name":"Teste", "id":"56789"}'
            ))
            result.set_result(response_mock)
            provider_mock.return_value = result
            response = yield self.http_client.fetch(
                self.get_url('/authenticate/'), method='POST',
                body=utils.dumps({
                    'access_token': 'VALID-TOKEN', 'provider': 'google'
                })
            )
            expect(response.code).to_equal(200)
            expect(utils.loads(response.body)['authenticated']).to_be_true()
            expect(test_result).to_include('provider')

    @testing.gen_test
    def test_can_send_signal_on_post_unauthorized(self):

        test_result = {}

        @signals.unauthorized_user.connect
        def test_signal(provider):
            test_result['provider'] = provider

        with patch.object(GoogleProvider, '_fetch_userinfo') as provider_mock:
            result = gen.Future()
            response_mock = Mock(code=401, reason='Unauthorized')
            result.set_result(response_mock)
            provider_mock.return_value = result
            try:
                response = yield self.http_client.fetch(
                    self.get_url('/authenticate/'), method='POST',
                    body=utils.dumps({
                        'access_token': 'VALID-TOKEN', 'provider': 'google'
                    })
                )
            except HTTPError as e:
                response = e.response
            expect(response.code).to_equal(401)
            expect(test_result).to_include('provider')

    from nose_focus import focus
    @focus
    @testing.gen_test
    def test_can_make_a_request_in_a_decorated_method_as_authenticated(self):
        response = yield self.http_client.fetch(
            self.get_url('/test_authentication/'),
            headers={'Cookie': self.mock_auth_cookie(0, 'mock', data={'id': 0})}
        )

        expect(response.code).to_equal(200)
        expect(response.body).to_equal('OK')

    from nose_focus import focus
    @focus
    @testing.gen_test
    def test_cant_make_a_request_in_a_decorated_method_as_anonymous(self):
        try:
            response = yield self.http_client.fetch(
                self.get_url('/test_authentication/'),
            )
        except HTTPError as e:
            response = e.response

        expect(response.code).to_equal(401)
        expect(response.reason).to_equal('Unauthorized')

