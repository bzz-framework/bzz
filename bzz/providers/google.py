#!/usr/bin/python
# -*- coding: utf-8 -*-

# This file is part of bzz.
# https://github.com/heynemann/bzz

# Licensed under the MIT license:
# http://www.opensource.org/licenses/MIT-license
# Copyright (c) 2014 Bernardo Heynemann heynemann@gmail.com

import logging

import tornado.gen as gen
from tornado import httpclient

from bzz.auth import AuthProvider
import bzz.utils as utils


class GoogleProvider(AuthProvider):
    '''
    Provider to perform authentication with Google OAUTH Apis.
    '''
    API_URL = 'https://www.googleapis.com/oauth2/v1/userinfo?access_token={}'

    @gen.coroutine
    def authenticate(self, access_token, proxy_info=None):
        '''
        Try to get Google user info and returns it if
        the given access_token get`s a valid user info in a string
        json format. If the response was not an status code 200 or
        get an error on Json, None was returned.

        Example of return on success::

            {
                id: "1234567890abcdef",
                email: "...@gmail.com",
                name: "Ricardo L. Dani",
                provider: "google"
            }
        '''

        response = yield self._fetch_userinfo(access_token, proxy_info)

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
    def _fetch_userinfo(self, access_token, proxy_info):
        url = self.API_URL.format(access_token)
        logging.info('Requesting %s with proxy %s...' % (url, proxy_info))
        req = httpclient.HTTPRequest(url, **proxy_info) if proxy_info else url
        try:
            response = yield self.http_client.fetch(req)
        except httpclient.HTTPError as e:
            response = e.response
        raise gen.Return(response)
