#!/usr/bin/python
# -*- coding: utf-8 -*-

# This file is part of bzz.
# https://github.com/heynemann/bzz

# Licensed under the MIT license:
# http://www.opensource.org/licenses/MIT-license
# Copyright (c) 2014 Bernardo Heynemann heynemann@gmail.com

import inspect
import functools
from datetime import datetime, timedelta

import tornado.web
import tornado.gen as gen
from tornado import ioloop
from tornado import httpclient

import bzz.signals as signals
import bzz.utils as utils


def authenticated(method):
    """Decorate methods with this to require that the user be logged in.

    If the user is not logged in, a 401 unauthorized status code will return.
    """
    @functools.wraps(method)
    def wrapper(self, *args, **kwargs):
        authenticated, payload = AuthHandler._is_authenticated(self)
        if authenticated:
            AuthHandler._renew_authentication(self, payload)
        else:
            AuthHandler._set_unauthorized(self)
        return method(self, *args, **kwargs)
    return wrapper


class AuthHive(object):

    @classmethod
    def configure(cls, app, secret_key, expiration=1200, cookie_name='AUTH_TOKEN'):
        app.authentication_options = {
            'secret_key': secret_key,
            'expiration': expiration,
            'cookie_name': cookie_name,
            'jwt': utils.Jwt(secret_key)
        }

    @classmethod
    def routes_for(cls, providers):

        ensure_instance = lambda provider: (
            provider() if inspect.isclass(provider) else provider
        )
        options = {
            'providers': dict([
                (provider.get_name(), ensure_instance(provider))
                for provider in providers
            ])
        }
        routes = [('/authenticate/', AuthHandler, options)]

        return routes


class AuthHandler(tornado.web.RequestHandler):

    def initialize(self, providers):
        self.providers = providers
        self.jwt = self.application.authentication_options['jwt']
        self.expiration = self.application.authentication_options['expiration']
        self.cookie_name = self.application.authentication_options['cookie_name']

    def get(self):
        '''
        Only returns true or false if is a valid authenticated request
        '''
        authenticated, payload = AuthHandler._is_authenticated(self)
        result = dict(authenticated=authenticated)
        if authenticated:
            result['user_data'] = payload['data']
        self.set_status(200)
        self.write(result)

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

        user_data = yield provider.authenticate(access_token)
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

            signals.authorized_user.send(provider_name, user_data=user_data)
            self.set_cookie(self.cookie_name, auth_token)
            self.write(dict(authenticated=True))
        else:
            signals.unauthorized_user.send(provider_name)
            AuthHandler._set_unauthorized(self)

    @classmethod
    def _set_unauthorized(cls, handler):
        handler.set_status(401, reason='Unauthorized')
        raise tornado.web.Finish()

    @classmethod
    def _is_authenticated(cls, handler):
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
    def authenticate(self, access_token):
        raise NotImplementedError('Provider.authenticate method must be implemented')


class GoogleProvider(AuthProvider):
    API_URL = 'https://www.googleapis.com/oauth2/v1/userinfo?access_token={}'

    @gen.coroutine
    def authenticate(self, access_token):
        '''
        Try to get Google user info and returns it if
        the given access_token get`s a valid user info in a string
        json format. If the response was not an status code 200 or
        get an error on Json, None was returned.

        Example of return on success:
        {
            id: "1234567890abcdef",
            email: "...@gmail.com",
            name: "Ricardo L. Dani",
            provider: "google"
        }
        '''

        response = yield self._fetch_userinfo(access_token)

        if response.code == 200:
            body = utils.loads(response.body)
            if not body.get('error'):
                raise gen.Return({
                    'email': body.get("email"),
                    'name': body.get("name"),
                    'id': body.get("id"),
                    'provider': self.get_name()
                })

        raise gen.Return(None)

    @gen.coroutine
    def _fetch_userinfo(self, access_token):
        try:
            response = yield self.http_client.fetch(
                self.API_URL.format(access_token)
            )
        except httpclient.HTTPError as e:
            response = e.response
        raise gen.Return(response)
