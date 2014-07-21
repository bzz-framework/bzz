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
from tornado import ioloop
from tornado import httpclient

# import bzz.signals as signals
import bzz.utils as utils


class AuthenticationHandler(tornado.web.RequestHandler):

    @classmethod
    def routes_for(
            cls, provider, expiration=1200, secret_key='SECRET_KEY',
            cookie_name='AUTH_TOKEN'):

        options = dict(
            provider=provider, expiration=expiration, secret_key=secret_key,
            cookie_name=cookie_name
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
        user = self._get_authenticated_user()
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

    def _is_authenticated(self):
        return self.jwt.try_to_decode(self.get_cookie(self.cookie_name))

    def _get_authenticated_user(self):
        authenticated, payload = self._is_authenticated()
        if authenticated:
            user_id = payload['sub']
            return {'id': user_id}
        else:
            return None

    @gen.coroutine
    def _authenticate(self, access_token):
        oauth_user = yield self.provider.authenticate(access_token)
        # TODO: send signal to get or create persisted user
        raise gen.Return(oauth_user)


class AuthenticationProvider(object):

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
        raise NotImplementedError()


class GoogleProvider(AuthenticationProvider):

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
            fullname: "Ricardo L. Dani",
        }
        '''

        response = yield self._fetch_userinfo(access_token)

        if response.code == 200:
            body = utils.loads(response.body)
            if not body.get('error'):
                raise gen.Return({
                    'email': body.get("email"),
                    'fullname': body.get("name"),
                    'id': body.get("id")
                })

        raise gen.Return(None)

    @gen.coroutine
    def _fetch_userinfo(self, access_token):
        google_api_url = 'https://www.googleapis.com/oauth2/v1/userinfo'
        url = '%s?access_token=%s' % (google_api_url, access_token)

        try:
            response = yield self.http_client.fetch(url)
        except httpclient.HTTPError as e:
            response = e.response

        raise gen.Return(response)
