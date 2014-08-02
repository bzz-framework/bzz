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

import tornado.gen as gen


class InMemoryStorage(object):
    def __init__(self):
        self.data = {}

    def put(self, uri, data):
        self.data[uri] = data

    def get(self, uri):
        return self.data.get(uri, None)


class CacheMixin(object):
    def __new__(typ, *args, **kw):
        instance = object.__new__(typ, *args, **kw)
        instance.is_caching = False
        instance._old_write = instance.write
        instance._old_get = instance.get
        setattr(instance, 'write', instance._cached_write)
        setattr(instance, 'get', instance._cached_get)
        return instance

    def _cached_write(self, chunk):
        self._old_write(chunk)

        if self.is_caching:
            self.cache_parts.append(chunk)

    def is_cached_route(self, uri):
        return True

    def start_caching(self):
        self.is_caching = True
        self.cache_parts = []

    @property
    def cached_routes(self):
        return getattr(self.application, 'cached_routes', [])

    @property
    def storage(self):
        if not hasattr(self.application, 'storage'):
            self.application.storage = InMemoryStorage()

        return self.application.storage

    def store_cache(self):
        result = "".join(self.cache_parts)
        self.storage.put(self.request.uri, result)

    def get_cached_results(self):
        return self.storage.get(self.request.uri)

    @gen.coroutine
    def _cached_get(self, *args, **kw):
        if not self.is_cached_route(self.request.uri):
            yield self._old_get(*args, **kw)
            return

        result = self.get_cached_results()
        if result is None:
            self.start_caching()
            yield self._old_get(*args, **kw)
            self.store_cache()
