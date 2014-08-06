#!/usr/bin/python
# -*- coding: utf-8 -*-

# This file is part of bzz.
# https://github.com/heynemann/bzz

# Licensed under the MIT license:
# http://www.opensource.org/licenses/MIT-license
# Copyright (c) 2014 Bernardo Heynemann heynemann@gmail.com

'''
CacheHive allows for a decoupled unobstrusive caching of API routes.
'''

import re

import tornado.web as web
import tornado.gen as gen
from tornado import iostream
from tornado.concurrent import is_future


class InMemoryStorage(object):
    def __init__(self):
        self.data = {}

    @gen.coroutine
    def put(self, uri, data):
        self.data[uri] = data

    @gen.coroutine
    def get(self, uri):
        return self.data.get(uri, None)


class CachedHandler(web.RequestHandler):
    def initialize(self, *args, **kw):
        self.is_caching = False
        self.cache_parts = []
        self.handler_args = args
        self.handler_kw = kw
        self.handler_class = self.handler_kw.pop('handler')
        self._instance = None
        self._instance_write = None

    @gen.coroutine
    def _execute(self, transforms, *args, **kwargs):
        if self.is_cached_route:
            self.start_caching()

        self.handler._transforms = transforms
        try:
            if self.request.method not in self.SUPPORTED_METHODS:
                raise web.HTTPError(405)
            self.path_args = [self.decode_argument(arg) for arg in args]
            self.path_kwargs = dict((k, self.decode_argument(v, name=k))
                                    for (k, v) in kwargs.items())
            # If XSRF cookies are turned on, reject form submissions without
            # the proper cookie
            if self.request.method not in ("GET", "HEAD", "OPTIONS") and \
                    self.application.settings.get("xsrf_cookies"):
                self.check_xsrf_cookie()

            result = self.handler.prepare()
            if is_future(result):
                result = yield result
            if result is not None:
                raise TypeError("Expected None, got %r" % result)
            if self._prepared_future is not None:
                # Tell the Application we've finished with prepare()
                # and are ready for the body to arrive.
                self._prepared_future.set_result(None)
            if self._finished:
                return

            if web._has_stream_request_body(self.__class__):
                # In streaming mode request.body is a Future that signals
                # the body has been completely received.  The Future has no
                # result; the data has been passed to self.data_received
                # instead.
                try:
                    yield self.request.body
                except iostream.StreamClosedError:
                    return

            method_string = self.request.method.lower()
            method = getattr(self.handler, method_string)

            got_from_cache = False
            if method_string == 'get':
                result = yield self.application.cache_storage.get(self.request.uri)
                if result is not None:
                    self._instance_write(result)
                    got_from_cache = True

            if not got_from_cache:
                result = method(*self.path_args, **self.path_kwargs)
                if is_future(result):
                    result = yield result
                if result is not None:
                    raise TypeError("Expected None, got %r" % result)

            yield self.end_caching()

            if self._auto_finish and not self._finished:
                self.handler.finish()

        except Exception as e:
            self._handle_request_exception(e)
            if (self._prepared_future is not None and
                    not self._prepared_future.done()):
                # In case we failed before setting _prepared_future, do it
                # now (to unblock the HTTP server).  Note that this is not
                # in a finally block to avoid GC issues prior to Python 3.4.
                self._prepared_future.set_result(None)

    @property
    def handler(self):
        if not self._instance:
            self._instance = self.handler_class(self.application, self.request, **self.handler_kw)
            self._instance_write = self._instance.write

        setattr(self._instance, 'write', self.write)
        return self._instance

    def write(self, chunk):
        handler = self.handler  # NOQA
        self._instance_write(chunk)

        if self.is_caching:
            self.cache_parts.append(chunk)

    @property
    def is_cached_route(self):
        for route in self.application.cached_routes:
            if route.match(self.request.uri):
                return True
        return False

    @gen.coroutine
    def end_caching(self):
        yield self.application.cache_storage.put(self.request.uri, "".join(self.cache_parts))
        self.is_caching = False
        self.cache_parts = []

    def start_caching(self):
        self.is_caching = True
        self.cache_parts = []


class RequestDispatcher(web._RequestDispatcher):
    def _find_handler(self):
        super(RequestDispatcher, self)._find_handler()
        self.handler_kwargs['handler'] = self.handler_class
        self.handler_class = CachedHandler


class CacheHive(object):
    @classmethod
    def start_request(cls, application):
        def handle(connection):
            return RequestDispatcher(application, connection)
        return handle

    @classmethod
    def init(cls, application, storage, cached_routes):
        setattr(application, 'cache_storage', storage)
        setattr(application, 'start_request', cls.start_request(application))
        setattr(application, 'cached_routes', cls.parse_routes(cached_routes))

    @classmethod
    def parse_routes(cls, routes):
        return [
            re.compile(route)
            for route in routes
        ]


#class CacheMixin(object):
    #def __new__(typ, *args, **kw):
        #instance = object.__new__(typ, *args, **kw)
        #instance.is_caching = False
        #instance._old_write = instance.write
        #instance._old_get = instance.get
        #setattr(instance, 'write', instance._cached_write)
        #setattr(instance, 'get', instance._cached_get)
        #return instance

    #def _cached_write(self, chunk):
        #self._old_write(chunk)

        #if self.is_caching:
            #self.cache_parts.append(chunk)

    #def is_cached_route(self, uri):
        #return True

    #def start_caching(self):
        #self.is_caching = True
        #self.cache_parts = []

    #@property
    #def cached_routes(self):
        #return getattr(self.application, 'cached_routes', [])

    #@property
    #def storage(self):
        #if not hasattr(self.application, 'storage'):
            #self.application.storage = InMemoryStorage()

        #return self.application.storage

    #def store_cache(self):
        #result = "".join(self.cache_parts)
        #self.storage.put(self.request.uri, result)

    #def get_cached_results(self):
        #return self.storage.get(self.request.uri)

    #@gen.coroutine
    #def _cached_get(self, *args, **kw):
        #if not self.is_cached_route(self.request.uri):
            #yield self._old_get(*args, **kw)
            #return

        #result = self.get_cached_results()
        #if result is None:
            #self.start_caching()
            #yield self._old_get(*args, **kw)
            #self.store_cache()
