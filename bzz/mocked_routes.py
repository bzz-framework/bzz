#!/usr/bin/python
# -*- coding: utf-8 -*-

# This file is part of bzz.
# https://github.com/heynemann/bzz

# Licensed under the MIT license:
# http://www.opensource.org/licenses/MIT-license
# Copyright (c) 2014 Bernardo Heynemann heynemann@gmail.com

import tornado.web
from collections import OrderedDict


class MockedRoutesHandler(tornado.web.RequestHandler):
    def __init__(self, *args, **kwargs):
        self.handler_methods = kwargs.pop('handler_methods')
        super(MockedRoutesHandler, self).__init__(*args, **kwargs)


    def prepare(self):
        if self.request.method in self.handler_methods or '*' in self.handler_methods:
            response = self.handler_methods.get(self.request.method, None) or self.handler_methods.get('*')
            status = response.get('status', 200)
            body = response.get('body', '')

            if hasattr(body, '__call__'):
                body = body(self.request)

            if status >= 400:
                raise tornado.web.HTTPError(status, body)

            if 'cookies' in response:
                for cookie, value in response['cookies'].items():
                    self.set_cookie(cookie, value)

            self.write(body)
            self.set_status(status)
            self.finish()


class MockedRoutes(object):
    def __init__(self, routes_tuple):
        self.routes_tuple = routes_tuple
        self.routes = OrderedDict()
        # self.tornado_routes = []


    def handlers(self):
        """
        Returns a tuples list of paths, tornado ready
        """
        tornado_routes = []
        for route in self.routes_tuple:
            if not route[1] in self.routes:
                self.routes[route[1]] = {}
            if not route[0] in self.routes[route[1]]:
                self.routes[route[1]][route[0]] = {}
            if len(route) > 2:
                result = route[2]
            else:
                result = {'body': '', 'status': 200}

            self.routes[route[1]][route[0]] = result


        return [(route, MockedRoutesHandler, dict(handler_methods=methods)) for route, methods in self.routes.items()]

