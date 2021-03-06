#!/usr/bin/python
# -*- coding: utf-8 -*-

# This file is part of bzz.
# https://github.com/heynemann/bzz

# Licensed under the MIT license:
# http://www.opensource.org/licenses/MIT-license
# Copyright (c) 2014 Bernardo Heynemann heynemann@gmail.com

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
from bzz.providers.google import GoogleProvider
from bzz.providers.mock import MockProvider


def load_json(json_string):
    try:
        return utils.loads(json_string)
    except ValueError:
        return utils.loads(json_string.decode('utf-8'))


class MockUnauthorizedProvider(bzz.AuthProvider):
    @gen.coroutine
    def authenticate(self, access_token, proxy_info=None, post_data=None):
        raise gen.Return(None)


class TestAuthHandler(RequestHandler):

    @bzz.authenticated
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


class TestPrefixServer(server.Server):

    def __init__(self, *args, **kwargs):
        self.io_loop = kwargs.pop('io_loop', None)
        super(TestPrefixServer, self).__init__(*args, **kwargs)

    def get_handlers(self):
        handlers_list = bzz.AuthHive.routes_for([
            GoogleProvider(self.io_loop)
        ], prefix="api")

        return handlers_list


class BaseAuthHiveTestCase(base.ApiTestCase):

    def setUp(self):
        super(BaseAuthHiveTestCase, self).setUp()
        signals.authorized_user.receivers = {}
        signals.pre_get_instance.receivers = {}
        signals.pre_get_list.receivers = {}
        signals.pre_create_instance.receivers = {}
        signals.pre_update_instance.receivers = {}
        signals.pre_delete_instance.receivers = {}

    def get_config(self):
        return {}

    def tearDown(self):
        super(BaseAuthHiveTestCase, self).tearDown()
        signals.authorized_user.receivers = {}
        signals.pre_get_instance.receivers = {}
        signals.pre_get_list.receivers = {}
        signals.pre_create_instance.receivers = {}
        signals.pre_update_instance.receivers = {}
        signals.pre_delete_instance.receivers = {}


class AuthHiveTestCase(BaseAuthHiveTestCase):

    def get_app(self):
        app = super(AuthHiveTestCase, self).get_app()
        bzz.AuthHive.configure(
            app,
            cookie_name='TEST_AUTH_COOKIE',
            secret_key='TEST_SECRET_KEY',
            expiration=1200,
            authenticated_create=True,
            authenticated_update=True,
            authenticated_delete=True,
            authenticated_get=True
        )
        return app

    def get_server(self):
        cfg = config.Config(**self.get_config())
        self.server = TestServer(config=cfg, io_loop=self.io_loop)
        return self.server

    @testing.gen_test
    def test_cant_authenticate_with_invalid_provider(self):
        try:
            response = yield self.http_client.fetch(
                self.get_url('/auth/signin/'),
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
            self.get_url('/auth/signin/'),
            method='POST',
            body=utils.dumps({
                'access_token': '1234567890', 'provider': 'mock'
            })
        )

        expect(response.code).to_equal(200)
        expect(load_json(response.body)).to_be_like(dict(authenticated=True, id="123"))
        cookie_name = self.server.application.authentication_options['cookie_name']
        expect(cookie_name in response.headers.get('Set-Cookie')).to_equal(True)

    @testing.gen_test
    def test_can_authenticate_with_custom_params(self):
        response = yield self.http_client.fetch(
            self.get_url('/auth/signin/'),
            method='POST',
            body=utils.dumps({
                'access_token': '1234567890',
                'provider': 'mock',
                'name': 'Much Name',
                'email': 'Such@email.doge'
            })
        )

        expect(response.code).to_equal(200)
        expect(load_json(response.body)).to_be_like(dict(authenticated=True, id="123", name='Much Name', email='Such@email.doge'))
        cookie_name = self.server.application.authentication_options['cookie_name']
        expect(cookie_name in response.headers.get('Set-Cookie')).to_equal(True)

    @testing.gen_test
    def test_cant_authenticate(self):
        try:
            yield self.http_client.fetch(
                self.get_url('/auth/signin/'),
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
            self.get_url('/auth/me/'),
            headers={'Cookie': self.mock_auth_cookie(0, 'mock', data={'id': 0})}
        )

        expect(response.code).to_equal(200)
        expect(load_json(response.body)).to_equal(dict(
            authenticated=True, userData={'id': 0}
        ))

    @testing.gen_test
    def test_can_check_not_authenticated_request(self):
        response = yield self.http_client.fetch(
            self.get_url('/auth/me/')
        )

        expect(response.code).to_equal(200)
        expect(load_json(response.body)).to_equal(dict(authenticated=False))

    @testing.gen_test
    def test_can_send_signal_on_pre_get_user_details(self):

        @signals.pre_get_user_details.connect
        def test_signal(provider, user_data=None, handler=None):
            expect(provider).to_equal('mock')
            expect(user_data).to_equal({
                'userData': {u'id': 0}, 'authenticated': True
            })
            user_data['username'] = 'holmes'

        response = yield self.http_client.fetch(
            self.get_url('/auth/me/'),
            headers={'Cookie': self.mock_auth_cookie(0, 'mock', data={'id': 0})}
        )

        expect(response.code).to_equal(200)
        expect(load_json(response.body)).to_equal(dict(
            authenticated=True, userData={'id': 0}, username='holmes'
        ))

    @testing.gen_test
    def test_cannot_authenticate_a_user_with_invalid_google_plus_token(self):
        with patch.object(GoogleProvider, '_fetch_userinfo') as provider_mock:
            result = gen.Future()
            response_mock = Mock(code=401, reason='Unauthorized')
            result.set_result(response_mock)
            provider_mock.return_value = result
            try:
                response = yield self.http_client.fetch(
                    self.get_url('/auth/signin/'), method='POST',
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
                    self.get_url('/auth/signin/'), method='POST',
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
        def test_signal(provider, user_data=None, handler=None):
            test_result['provider'] = 'google'
            expect(provider).to_equal('google')
            expect(user_data).to_equal({
                "authenticated": True,
                "provider": "google",
                "email": "test@gmail.com", "name": "Teste", "id": "56789"
            })
            user_data['something'] = 'else'

        with patch.object(GoogleProvider, '_fetch_userinfo') as provider_mock:
            result = gen.Future()
            response_mock = Mock(code=200, body=(
                '{"email":"test@gmail.com", "name":"Teste", "id":"56789"}'
            ))
            result.set_result(response_mock)
            provider_mock.return_value = result
            response = yield self.http_client.fetch(
                self.get_url('/auth/signin/'), method='POST',
                body=utils.dumps({
                    'access_token': 'VALID-TOKEN', 'provider': 'google'
                })
            )
            expect(response.code).to_equal(200)
            data = utils.loads(response.body)
            expect(data['authenticated']).to_be_true()
            expect(data['something']).to_equal('else')
            expect(test_result).to_include('provider')

    @testing.gen_test
    def test_can_send_signal_on_post_unauthorized(self):

        test_result = {}

        @signals.unauthorized_user.connect
        def test_signal(provider, handler=None):
            test_result['provider'] = provider

        with patch.object(GoogleProvider, '_fetch_userinfo') as provider_mock:
            result = gen.Future()
            response_mock = Mock(code=401, reason='Unauthorized')
            result.set_result(response_mock)
            provider_mock.return_value = result
            try:
                response = yield self.http_client.fetch(
                    self.get_url('/auth/signin/'), method='POST',
                    body=utils.dumps({
                        'access_token': 'VALID-TOKEN', 'provider': 'google'
                    })
                )
            except HTTPError as e:
                response = e.response
            expect(response.code).to_equal(401)
            expect(test_result).to_include('provider')

    @testing.gen_test
    def test_can_make_a_request_in_a_decorated_method_as_authenticated(self):
        response = yield self.http_client.fetch(
            self.get_url('/test_authentication/'),
            headers={'Cookie': self.mock_auth_cookie(
                user_id=0, provider='mock', data={'id': 0}
            )}
        )

        expect(response.code).to_equal(200)
        expect(response.body).to_equal('OK')

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

    @testing.gen_test
    def test_can_signout_when_logged_in(self):
        response = yield self.http_client.fetch(
            self.get_url('/auth/signout/'), method='POST', body='',
            headers={'Cookie': self.mock_auth_cookie(
                user_id=0, provider='mock', data={'id': 0}
            )}
        )

        expect(response.code).to_equal(200)
        expect(utils.loads(response.body)).to_equal({'loggedOut': True})

    @testing.gen_test
    def test_can_signout_when_logged_out(self):
        response = yield self.http_client.fetch(
            self.get_url('/auth/signout/'), method='POST', body='',
        )

        expect(response.code).to_equal(200)
        expect(utils.loads(response.body)).to_equal({'loggedOut': True})


class PrefixedAuthHiveTestCase(BaseAuthHiveTestCase):

    def get_app(self):
        app = super(PrefixedAuthHiveTestCase, self).get_app()
        bzz.AuthHive.configure(
            app,
            cookie_name='TEST_AUTH_COOKIE',
            secret_key='TEST_SECRET_KEY',
            expiration=1200,
            authenticated_create=True,
            authenticated_update=True,
            authenticated_delete=True,
            authenticated_get=True
        )
        return app

    def get_server(self):
        cfg = config.Config(**self.get_config())
        self.server = TestPrefixServer(config=cfg, io_loop=self.io_loop)
        return self.server

    @testing.gen_test
    def test_can_authenticate_a_user_with_valid_google_plus_token_with_prefix_in_authentication_url(self):
        with patch.object(GoogleProvider, '_fetch_userinfo') as provider_mock:
            result = gen.Future()
            response_mock = Mock(code=200, body=(
                '{"email":"test@gmail.com", "name":"teste", "id":"56789"}'
            ))
            result.set_result(response_mock)
            provider_mock.return_value = result
            try:
                response = yield self.http_client.fetch(
                    self.get_url('/api/auth/signin/'), method='POST',
                    body=utils.dumps({
                        'access_token': 'VALID-TOKEN', 'provider': 'google'
                    })
                )
            except HTTPError as e:
                response = e.response

            expect(response.code).to_equal(200)
            expect(utils.loads(response.body)['authenticated']).to_be_true()


class ProxyAuthHiveTestCase(BaseAuthHiveTestCase):

    def get_app(self):
        app = super(ProxyAuthHiveTestCase, self).get_app()
        bzz.AuthHive.configure(
            app,
            cookie_name='TEST_AUTH_COOKIE',
            secret_key='TEST_SECRET_KEY',
            expiration=1200,
            authenticated_create=True,
            authenticated_update=True,
            authenticated_delete=True,
            authenticated_get=True,
            proxy_host='10.10.10.10',
            proxy_port='666',
            proxy_username='ricardo.dani',
            proxy_password='password'
        )
        return app

    def get_server(self):
        cfg = config.Config(**self.get_config())
        self.server = TestServer(config=cfg, io_loop=self.io_loop)
        return self.server

    @testing.gen_test
    def test_can_fetch_userinfo_with_proxy_credentials(self):
        with patch.object(GoogleProvider, '_fetch_userinfo') as provider_mock:
            result = gen.Future()
            response_mock = Mock(code=200, body=(
                '{"email":"test@gmail.com", "name":"teste", "id":"56789"}'
            ))
            result.set_result(response_mock)
            provider_mock.return_value = result
            try:
                response = yield self.http_client.fetch(
                    self.get_url('/auth/signin/'), method='POST',
                    body=utils.dumps({
                        'access_token': 'VALID-TOKEN', 'provider': 'google'
                    })
                )
            except HTTPError as e:
                response = e.response

            expect(provider_mock.call_args[0][1]).to_equal(
                {'proxy_port': '666', 'proxy_username': 'ricardo.dani',
                 'proxy_password': 'password', 'proxy_host': '10.10.10.10'}
            )
            expect(response.code).to_equal(200)
            expect(utils.loads(response.body)['authenticated']).to_be_true()


class TestSignalsHandler(RequestHandler):

    def get(self, id=None):
        if id:
            signals.pre_get_instance.send(handler=self)
            self.write('GET OK')
        else:
            signals.pre_get_list.send(handler=self)
            self.write('GET LIST OK')

    def post(self, id=None):
        signals.pre_create_instance.send(handler=self)
        self.write('POST OK')

    def put(self, id=None):
        signals.pre_update_instance.send(handler=self)
        self.write('UPDATE OK')

    def delete(self, id=None):
        signals.pre_delete_instance.send(handler=self)
        self.write('DELETE OK')


class TestSignalServer(server.Server):

    def __init__(self, *args, **kwargs):
        self.io_loop = kwargs.pop('io_loop', None)
        super(TestSignalServer, self).__init__(*args, **kwargs)

    def get_handlers(self):
        handlers_list = bzz.AuthHive.routes_for([
            MockProvider(self.io_loop)
        ])
        handlers_list += [
            (r'/test_signals(?:/([0-9]*))?', TestSignalsHandler),
        ]
        return handlers_list


class AuthenticationSignalsTestCase(BaseAuthHiveTestCase):

    def get_app(self):
        app = super(AuthenticationSignalsTestCase, self).get_app()
        bzz.AuthHive.configure(
            app, 'SECRET',
            authenticated_create=False,
            authenticated_update=False,
            authenticated_delete=False,
            authenticated_get=False
        )
        return app

    def get_server(self):
        cfg = config.Config(**self.get_config())
        self.server = TestSignalServer(config=cfg, io_loop=self.io_loop)
        return self.server

    @gen.coroutine
    def fetch_alias(self, url, method, auth_cookie=False):
        kwargs = {'body': ''} if method in ('POST', 'PUT') else {}
        if auth_cookie:
            kwargs.update({
                'headers': {
                    'Cookie': self.mock_auth_cookie(0, 'mock')
                }
            })
        try:
            response = yield self.http_client.fetch(
                self.get_url(url), method=method, **kwargs
            )
        except HTTPError as e:
            response = e.response
        raise gen.Return(response)

    @testing.gen_test
    def test_if_authentications_signals_are_empty_and_not_authenticating(self):
        expect(signals.pre_get_instance.receivers).to_equal({})
        response = yield self.fetch_alias('/test_signals/1', 'GET')
        expect(response.code).to_equal(200)
        expect(response.body).to_equal('GET OK')

        expect(signals.pre_get_list.receivers).to_equal({})
        response = yield self.fetch_alias('/test_signals', 'GET')
        expect(response.code).to_equal(200)
        expect(response.body).to_equal('GET LIST OK')

        expect(signals.pre_create_instance.receivers).to_equal({})
        response = yield self.fetch_alias('/test_signals', 'POST')
        expect(response.code).to_equal(200)
        expect(response.body).to_equal('POST OK')

        expect(signals.pre_update_instance.receivers).to_equal({})
        response = yield self.fetch_alias('/test_signals', 'PUT')
        expect(response.code).to_equal(200)
        expect(response.body).to_equal('UPDATE OK')

        expect(signals.pre_delete_instance.receivers).to_equal({})
        response = yield self.fetch_alias('/test_signals', 'DELETE')
        expect(response.code).to_equal(200)
        expect(response.body).to_equal('DELETE OK')

    @testing.gen_test
    def test_if_authenticate_get_option_is_autheticating_sended_handlers(self):
        bzz.AuthHive.configure(
            self.get_app(), 'SECRET',
            authenticated_create=False,
            authenticated_update=False,
            authenticated_delete=False,
            authenticated_get=True
        )
        expect(signals.pre_get_instance.receivers).to_length(1)
        response = yield self.fetch_alias('/test_signals/1', 'GET')
        expect(response.code).to_equal(401)
        expect(response.reason).to_equal('Unauthorized')
        response = yield self.fetch_alias('/test_signals/1', 'GET', auth_cookie=True)
        expect(response.code).to_equal(200)
        expect(response.body).to_equal('GET OK')

        expect(signals.pre_get_list.receivers).to_length(1)
        response = yield self.fetch_alias('/test_signals', 'GET')
        expect(response.code).to_equal(401)
        expect(response.reason).to_equal('Unauthorized')
        response = yield self.fetch_alias('/test_signals', 'GET', auth_cookie=True)
        expect(response.code).to_equal(200)
        expect(response.body).to_equal('GET LIST OK')

    @testing.gen_test
    def test_if_authenticate_create_option_is_autheticating_sended_handlers(self):
        bzz.AuthHive.configure(
            self.get_app(), 'SECRET',
            authenticated_create=True,
            authenticated_update=False,
            authenticated_delete=False,
            authenticated_get=False
        )

        expect(signals.pre_create_instance.receivers).to_length(1)
        response = yield self.fetch_alias('/test_signals', 'POST')
        expect(response.code).to_equal(401)
        expect(response.reason).to_equal('Unauthorized')
        response = yield self.fetch_alias('/test_signals', 'POST', auth_cookie=True)
        expect(response.code).to_equal(200)
        expect(response.body).to_equal('POST OK')

    @testing.gen_test
    def test_if_authenticate_update_option_is_autheticating_sended_handlers(self):
        bzz.AuthHive.configure(
            self.get_app(), 'SECRET',
            authenticated_create=False,
            authenticated_update=True,
            authenticated_delete=False,
            authenticated_get=False
        )

        expect(signals.pre_update_instance.receivers).to_length(1)
        response = yield self.fetch_alias('/test_signals', 'PUT')
        expect(response.code).to_equal(401)
        expect(response.reason).to_equal('Unauthorized')
        response = yield self.fetch_alias('/test_signals', 'PUT', auth_cookie=True)
        expect(response.code).to_equal(200)
        expect(response.body).to_equal('UPDATE OK')

    @testing.gen_test
    def test_if_authenticate_delete_option_is_autheticating_sended_handlers(self):
        bzz.AuthHive.configure(
            self.get_app(), 'SECRET',
            authenticated_create=False,
            authenticated_update=False,
            authenticated_delete=True,
            authenticated_get=False
        )

        expect(signals.pre_delete_instance.receivers).to_length(1)
        response = yield self.fetch_alias('/test_signals', 'DELETE')
        expect(response.code).to_equal(401)
        expect(response.reason).to_equal('Unauthorized')
        response = yield self.fetch_alias('/test_signals', 'DELETE', auth_cookie=True)
        expect(response.code).to_equal(200)
        expect(response.body).to_equal('DELETE OK')
