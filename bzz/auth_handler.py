#!/usr/bin/python
# -*- coding: utf-8 -*-

# This file is part of bzz.
# https://github.com/heynemann/bzz

# Licensed under the MIT license:
# http://www.opensource.org/licenses/MIT-license
# Copyright (c) 2014 Bernardo Heynemann heynemann@gmail.com

from datetime import datetime, timedelta

import tornado.web
import tornado.gen as gen

# import bzz.signals as signals
import bzz.utils as utils


class AuthenticationHandler(tornado.web.RequestHandler):

    @classmethod
    def routes_for(
            cls, provider, expiration=1200, secret_key='SECRET_KEY',
            cookie_name='AUTH_TOKEN'):

        options = dict(
            provider=provider, expiration=expiration, secret_key=secret_key, cookie_name=cookie_name
        )
        routes = [
            ('/authenticate/%s/' % provider.get_name(), cls, options)
        ]

        return routes

    def initialize(self, provider, expiration, secret_key, cookie_name):
        self.jwt = utils.Jwt(secret_key)
        self.provider = provider
        self.expiration = expiration
        self.cookie_name = cookie_name

    def get(self):
        '''
        Only returns true or false if is a valid authenticated request
        '''
        self.set_status(200)
        user = self.get_authenticated_user()
        if user:
            self.write(dict(authenticated=True))
        else:
            self.write(dict(authenticated=False))

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

        user = yield self._authenticate(access_token)
        if user:
            payload = dict(
                sub=user['id'],
                iss=self.provider.get_name(),
                token=access_token,
                iat=datetime.utcnow(),
                exp=datetime.utcnow() + timedelta(seconds=self.expiration)
            )
            auth_token = self.jwt.encode(payload)

            self.set_cookie(self.cookie_name, auth_token)
            self.write(dict(authenticated=True))
        else:
            self.__set_unauthorized()

    def __set_unauthorized(self):
        self.set_status(401, reason='Unauthorized')
        self.finish()

    @gen.coroutine
    def _authenticate(self, access_token):
        oauth_user = yield self.provider.authenticate(access_token)
        raise gen.Return(oauth_user)

    def is_authenticated(self):
        return self.jwt.try_to_decode(self.get_cookie(self.cookie_name))

    def get_authenticated_user(self):
        authenticated, payload = self.is_authenticated()
        if authenticated:
            user_id = payload['sub']
            return {'id': user_id}
        else:
            return None


class AuthenticationProvider(object):
    @classmethod
    def get_name(cls):
        raise NotImplementedError()

    @classmethod
    @gen.coroutine
    def authenticate(cls, access_token):
        raise NotImplementedError()
