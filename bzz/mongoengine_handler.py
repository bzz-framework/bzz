#!/usr/bin/python
# -*- coding: utf-8 -*-

# This file is part of bzz.
# https://github.com/heynemann/bzz

# Licensed under the MIT license:
# http://www.opensource.org/licenses/MIT-license
# Copyright (c) 2014 Bernardo Heynemann heynemann@gmail.com

import tornado.gen as gen

import bzz.rest as bzz


class MongoEngineRestHandler(bzz.ModelRestHandler):
    @classmethod
    def routes_for(cls, document_type, prefix=None, resource_name=None):
        if prefix is None:
            prefix = ''

        name = resource_name
        if name is None:
            name = document_type.__name__.lower()

        details_url = r'/%s%s(?:/(?P<pk>[^/]+)?)/?' % (prefix, name)

        return [
            (details_url, cls, dict(model=document_type, name=name, prefix=prefix))
        ]

    def initialize(self, model, name, prefix):
        self.model = model
        self.name = name
        self.prefix = prefix

    @gen.coroutine
    def save_new_instance(self, data):
        values = {}
        for key, value in data.items():
            values[key] = value[0]

        instance = self.model(**values)
        instance.save()

        raise gen.Return(instance)

    def collect_arguments(self):
        return self.request.arguments

    def get_model_id(self, instance):
        return getattr(instance, 'get_id', lambda: str(instance.id))()

    @gen.coroutine
    def post(self, pk=None):
        result = yield self.save_new_instance(self.collect_arguments())

        self.write('OK')
        model_id = self.get_model_id(result)
        self.set_header('X-Created-Id', model_id)
        self.set_header('location', '/%s%s/%s/' % (
            self.prefix,
            self.name,
            model_id
        ))
