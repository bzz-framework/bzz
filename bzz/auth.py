#!/usr/bin/python
# -*- coding: utf-8 -*-

# This file is part of bzz.
# https://github.com/heynemann/bzz

# Licensed under the MIT license:
# http://www.opensource.org/licenses/MIT-license
# Copyright (c) 2014 Bernardo Heynemann heynemann@gmail.com

'''
The bzz framework gives you a AuthHive class to allow easy OAuth2 authentication with a few steps.
'''

import functools
from datetime import datetime, timedelta

import tornado.web
import tornado.gen as gen
from tornado import ioloop
from tornado import httpclient

import bzz.signals as signals
import bzz.utils as utils
import bzz.core as core


def authenticated(method):
    '''Decorate methods with this to require the user to be authenticated.

    If the user is not logged in (cookie token expired, invalid or no token),
    a 401 unauthorized status code will be returned.

    If the user is authenticated, the token cookie will be renewed
    with more `expiration` seconds (configured in `AuthHive.configure` method).

    Usage:

    .. testcode:: auth_example_2

        import tornado
        import bzz

        class MyHandler(tornado.web.RequestHandler):

            @bzz.authenticated
            def get(self):
                self.write('I`m authenticated! :)')
    '''
    @functools.wraps(method)
    def wrapper(self, *args, **kwargs):
        authenticated, payload = AuthHandler.is_authenticated(self)
        if authenticated:
            AuthHandler._renew_authentication(self, payload)
        else:
            AuthHandler._set_unauthorized(self)
        return method(self, *args, **kwargs)
    return wrapper


class AuthHive(object):
    '''
    The AuthHive is the responsible for integrating authentication into your API.
    '''

    @classmethod
    def configure(
            cls, app, secret_key, expiration=1200, cookie_name='AUTH_TOKEN',
            proxy_host=None, proxy_port=None, proxy_username=None,
            proxy_password=None
            ):
        '''Configure the application to the authentication ecosystem.

        :param app: The tornado application to configure
        :type app: tornado.web.Application instance
        :param secret_key: A string to use for encoding/decoding Jwt that must
                           be private
        :type secret_key: str
        :param expiration: Time in seconds to the expiration (time to live) of
                           the token
        :type expiration: int
        :param cookie_name: The name of the cookie
        :type cookie_name: str
        :param proxy_host: Host of the Proxy
        :type proxy_host: str
        :param proxy_port: Port of the Proxy
        :type proxy_port: str
        :param proxy_username: Username of the Proxy
        :type proxy_username: str
        :param proxy_password: Password of the Proxy
        :type proxy_password: str

        '''
        app.authentication_options = {
            'secret_key': secret_key,
            'expiration': expiration,
            'cookie_name': cookie_name,
            'proxy_info': {
                'proxy_port': proxy_port,
                'proxy_host': proxy_host,
                'proxy_username': proxy_username,
                'proxy_password': proxy_password,
            },
            'jwt': utils.Jwt(secret_key)
        }

    @classmethod
    def routes_for(cls, providers, prefix=''):
        '''Returns the list of routes for the authentication ecosystem with the
        given providers configured.

        The routes returned are for these URLs:

        * [prefix]/auth/me/ -- To get user data and check if authenticated
        * [prefix]/auth/signin/ -- To sign in using the specified provider
        * [prefix]/auth/signout/ -- To sign out using the specified provider

        :param providers: A list of providers
        :type providers: AuthProvider class or instance
        :param prefix: An optional argument that can be specified as means to include a prefix route (i.e.: '/api');
        :type prefix: String
        :returns: list of tornado routes (url, handler, initializers)
        '''
        options = {
            'providers': dict([
                (provider.get_name(), utils.ensure_instance(provider))
                for provider in providers
            ])
        }

        url = functools.partial(utils.add_prefix, prefix)

        return core.RouteList([
            (url('/auth/me/'), AuthMeHandler, options),
            (url('/auth/signin/'), AuthSigninHandler, options),
            (url('/auth/signout/'), AuthSignoutHandler, options),
        ])


class AuthHandler(tornado.web.RequestHandler):

    def initialize(self, providers):
        self.providers = providers
        self.jwt = self.application.authentication_options['jwt']
        self.expiration = self.application.authentication_options['expiration']
        self.cookie_name = self.application.authentication_options['cookie_name']

    @classmethod
    def _set_unauthorized(cls, handler):
        handler.set_status(401, reason='Unauthorized')
        raise tornado.web.Finish()

    @classmethod
    def is_authenticated(cls, handler):
        jwt = handler.application.authentication_options['jwt']
        cookie_name = handler.application.authentication_options['cookie_name']
        return jwt.try_to_decode(handler.get_cookie(cookie_name))

    @classmethod
    def _renew_authentication(cls, handler, payload):
        payload.update(dict(
            iat=datetime.utcnow(),
            exp=datetime.utcnow() + timedelta(
                seconds=handler.application.authentication_options['expiration']
            )
        ))
        cookie_name = handler.application.authentication_options['cookie_name']
        jwt = handler.application.authentication_options['jwt']
        token = jwt.encode(payload)
        handler.set_cookie(cookie_name, token)


class AuthMeHandler(AuthHandler):

    def get(self):
        '''
        Returns if request is authenticated, if is, returns user`s data too.
        '''
        authenticated, payload = AuthHandler.is_authenticated(self)
        result = dict(authenticated=authenticated)
        if authenticated:
            result['userData'] = payload['data']
            signals.pre_get_user_details.send(
                payload['iss'], user_data=result, handler=self
            )
        self.set_status(200)
        self.write(result)


class AuthSigninHandler(AuthHandler):

    @gen.coroutine
    def post(self):
        '''
        Try to authenticate user with the access_token POST data.
        If the `self.authenticate` method returns the user, create a JSON
        Web Token (JWT) and set a `cookie_name` cookie with the encoded
        value. Otherwise returns a unauthorized request.
        '''
        post_data = utils.loads(self.request.body)
        access_token = post_data.get('access_token')
        provider_name = post_data.get('provider')

        provider = self.providers.get(provider_name, None)
        if provider is None:
            AuthHandler._set_unauthorized(self)

        user_data = yield provider.authenticate(
            access_token, self.application.authentication_options['proxy_info'], post_data=post_data
        )
        if user_data:
            payload = dict(
                sub=user_data['id'],
                data=user_data,
                iss=provider_name,
                token=access_token,
                iat=datetime.utcnow(),
                exp=datetime.utcnow() + timedelta(seconds=self.expiration)
            )
            auth_token = self.jwt.encode(payload)

            user_data['authenticated'] = True
            signals.authorized_user.send(
                provider_name, user_data=user_data, handler=self
            )
            self.set_cookie(self.cookie_name, auth_token)
            self.write(user_data)
        else:
            signals.unauthorized_user.send(provider_name, handler=self)
            AuthHandler._set_unauthorized(self)


class AuthSignoutHandler(AuthHandler):

    def post(self):
        self.clear_cookie(self.cookie_name)
        self.write({'loggedOut': True})


class AuthProvider(object):

    def __init__(self, io_loop=None):
        if not io_loop:
            io_loop = ioloop.IOLoop.instance()
        self.http_client = httpclient.AsyncHTTPClient(io_loop=io_loop)

    @classmethod
    def get_name(cls):
        '''Returns the lowercase class name without `Provider`'''
        return cls.__name__.split('Provider')[0].lower()

    @gen.coroutine
    def authenticate(self, access_token, proxy_info=None, post_data=None):
        raise NotImplementedError('Provider.authenticate method must be implemented')
