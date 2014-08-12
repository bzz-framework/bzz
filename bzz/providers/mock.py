#!/usr/bin/python
# -*- coding: utf-8 -*-

# This file is part of bzz.
# https://github.com/heynemann/bzz

# Licensed under the MIT license:
# http://www.opensource.org/licenses/MIT-license
# Copyright (c) 2014 Bernardo Heynemann heynemann@gmail.com
import tornado.gen as gen

from bzz.auth import AuthProvider


class MockProvider(AuthProvider):
    @gen.coroutine
    def authenticate(self, access_token, proxy_info=None, post_data=None):
        result = {'id': "123"}
        if post_data:
            if 'id' in post_data:
                result['id'] = post_data['id']
            if 'name' in post_data:
                result['name'] = post_data['name']
            if 'email' in post_data:
                result['email'] = post_data['email']
        raise gen.Return(result)
