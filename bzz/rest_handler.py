#!/usr/bin/python
# -*- coding: utf-8 -*-

# This file is part of bzz.
# https://github.com/heynemann/bzz

# Licensed under the MIT license:
# http://www.opensource.org/licenses/MIT-license
# Copyright (c) 2014 Bernardo Heynemann heynemann@gmail.com

import tornado
import tornado.gen as gen

try:
    import ujson as json
except ImportError:
    import json

import bzz.signals as signals


class ModelRestHandler(tornado.web.RequestHandler):
    def initialize(self, model, name, prefix):
        self.model = model
        self.name = name
        self.prefix = prefix

    def write_json(self, obj):
        self.set_header("Content-Type", "application/json")
        self.write(json.dumps(obj))

    @gen.coroutine
    def get(self, pk=None):
        if pk is None:
            yield self.list()
            return

        instance = yield self.get_instance(pk)
        if instance is None:
            self.send_error(status_code=404)
            return

        self.write_json(self.dump_object(instance))
        self.finish()

    @gen.coroutine
    def post(self, pk=None):
        instance = yield self.save_new_instance(self.get_request_data())
        signals.post_create_instance.send(self, instance=instance)
        pk = self.get_instance_id(instance)
        self.set_header('X-Created-Id', pk)
        self.set_header('location', '/%s%s/%s/' % (
            self.prefix,
            self.name,
            pk
        ))
        self.write('OK')

    @gen.coroutine
    def put(self, pk):
        instance, updated = yield self.update_instance(pk, self.get_request_data())
        signals.post_update_instance.send(self, instance=instance, updated_fields=updated)
        self.write('OK')

    @gen.coroutine
    def delete(self, pk):
        instance = yield self.delete_instance(pk)
        if instance:
            signals.post_delete_instance.send(self, instance=instance)
            self.write('OK')
        else:
            self.write('FAIL')

    @gen.coroutine
    def list(self):
        items = yield self.get_list()
        dump = []
        for item in items:
            dump.append(self.dump_object(item))

        self.write_json(dump)

    def get_request_data(self):
        data = {}
        for arg in list(self.request.arguments.keys()):
            data[arg] = self.get_argument(arg)
            if data[arg] == '':  # Tornado 3.0+ compatibility... Hard to test...
                data[arg] = None
        return data

    def dump_object(self, instance):
        return json.dumps(instance)
