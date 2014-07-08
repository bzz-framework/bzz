#!/usr/bin/python
# -*- coding: utf-8 -*-

# This file is part of bzz.
# https://github.com/heynemann/bzz

# Licensed under the MIT license:
# http://www.opensource.org/licenses/MIT-license
# Copyright (c) 2014 Bernardo Heynemann heynemann@gmail.com

import tornado.web
import tornado.gen as gen
from six.moves.urllib.parse import unquote

try:
    import ujson as json
except ImportError:
    import json

import bzz.signals as signals
import bzz.utils as utils


AVAILABLE_HANDLERS = {
    'mongoengine': 'bzz.mongoengine_handler.MongoEngineRestHandler'
}


class ModelRestHandler(tornado.web.RequestHandler):
    @classmethod
    def routes_for(cls, handler, model, prefix='', resource_name=None):
        '''
        Returns the tornado routes (as 3-tuples with url, handler, initializers) that correspond to the specified `model`.

        Where:

        * model is the Model class that you want routes for;
        * prefix is an optional argument that can be specified as means to include a prefix route (i.e.: '/api');
        * resource_name is an optional argument that can be specified to change the route name. If no resource_name specified the route name is the __class__.__name__ for the specified model with underscores instead of camel case.

        If you specify a prefix of '/api/' as well as resource_name of 'people' your route would be similar to:

        http://myserver/api/people/ (do a post to this url to create a new person)
        '''
        handler_name = AVAILABLE_HANDLERS.get(handler, handler)
        handler_class = utils.get_class(handler_name)
        name = resource_name
        if name is None:
            name = utils.convert(model.__name__)

        details_regex = r'/(%s(?:/[^/]+)?)((?:/[^/]+)*)/?'
        #^\/(team(?:\/.+?)?)(\/.+(?:\/.+?)?)*$

        if prefix:
            details_regex = ('/%s' % prefix.strip('/')) + details_regex

        routes = [
            (details_regex % name, handler_class, dict(model=model, name=name, prefix=prefix))
        ]

        return routes

    def initialize(self, model, name, prefix):
        self.model = model
        self.name = name
        self.prefix = prefix

    def write_json(self, obj):
        self.set_header("Content-Type", "application/json")
        self.write(json.dumps(obj))

    def parse_arguments(self, args):
        args = [arg.lstrip('/') for arg in args if arg]
        if len(args) == 1:
            return args

        parts = args[1].split('/')

        items = []
        current_item = []
        for part in parts:
            current_item.append(part)
            if len(current_item) == 2:
                items.append('/'.join(current_item))
                current_item = []
        if current_item:
            items.append(current_item[0])

        return [args[0]] + items

    @gen.coroutine
    def get(self, *args, **kwargs):
        args = self.parse_arguments(args)
        if '/' in args[-1]:
            yield self.handle_get_one(args)
        else:
            yield self.handle_get_list(args)

    @gen.coroutine
    def handle_get_one(self, args):
        success, obj = yield self.get_instance_from_args(args)
        if not success:
            return

        if obj is None:
            self.send_error(status_code=404)
            return

        self.write_json(self.dump_instance(obj))
        self.finish()

    @gen.coroutine
    def handle_get_list(self, args):
        if '/' not in args[0] and len(args) > 1:
            # /team/user -> missing user pk
            self.send_error(status_code=400)
            return

        if len(args) == 1:
            items = yield self.get_list()
        else:
            success, items = yield self.get_instance_from_args(args)
            if not success:
                self.send_error(status_code=400)
                return

        self.write_json(self.dump_list(items))
        self.finish()

    @gen.coroutine
    def get_instance_from_args(self, args):
        model, pk = args[0].split('/')
        obj = yield self.get_instance(pk)

        if len(args) == 1:
            raise gen.Return((True, obj))

        obj = yield self.get_instance_property(obj, args[1:])

        if obj is None:
            self.send_error(status_code=404)
            raise gen.Return((False, None))

        raise gen.Return((True, obj))

    @gen.coroutine
    def get_instance_property(self, obj, path):
        parts = [part.lstrip('/').split('/') for part in path if part]
        for part in parts:
            path = part[0]
            pk = None

            if len(part) > 1:
                pk = part[1]

            obj = getattr(obj, path)

            if pk is not None:
                if isinstance(obj, (list, tuple)):
                    for item in obj:
                        instance_id = yield self.get_instance_id(item)
                        if instance_id == pk:
                            obj = item
                else:
                    instance_id = yield self.get_instance_id(item)
                    if instance_id != pk:
                        raise gen.Return(None)

        raise gen.Return(obj)

    @gen.coroutine
    def post(self, *args, **kwargs):
        obj, field_name, model, pk = yield self.get_parent_model(args)
        instance = yield self.save_new_instance(model, self.get_request_data())
        yield self.associate_instance(obj, field_name, instance)
        signals.post_create_instance.send(model, instance=instance, handler=self)
        pk = yield self.get_instance_id(instance)
        self.set_header('X-Created-Id', pk)
        self.set_header('location', '/%s%s/%s/' % (
            self.prefix,
            self.name,
            pk
        ))
        self.write('OK')

    @gen.coroutine
    def get_parent_model(self, args):
        obj = None
        args = [arg for arg in args if arg]
        model = None
        id_ = None

        for part in args[:-1]:
            property_, property_id = part.split('/')

            if obj is None:
                obj = yield self.get_instance(property_id)
            else:
                obj = getattr(obj, property_)

        field_name = args[-1].lstrip('/')
        if '/' in field_name:
            field_name, id_ = field_name.split('/')
            if obj is None:
                obj = yield self.get_instance(id_)
                model = obj.__class__
            else:
                obj = getattr(obj, field_name)

        if model is None:
            model = yield self.get_model(obj, field_name)

        raise gen.Return([obj, field_name, model, id_])

    @gen.coroutine
    def put(self, *args, **kwargs):
        obj, field_name, model, pk = yield self.get_parent_model(args)
        instance, updated = yield self.update_instance(pk, self.get_request_data())
        signals.post_update_instance.send(self.model, instance=instance, updated_fields=updated, handler=self)
        self.write('OK')

    @gen.coroutine
    def delete(self, *args, **kwargs):
        obj, field_name, model, pk = yield self.get_parent_model(args)
        instance = yield self.delete_instance(pk)
        if instance:
            signals.post_delete_instance.send(self.model, instance=instance, handler=self)
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

        if self.request.body:
            items = self.request.body.decode('utf-8').split('&')
            for item in items:
                key, value = item.split('=')
                data[key] = unquote(value)
        else:
            for arg in list(self.request.arguments.keys()):
                data[arg] = self.get_argument(arg)
                if data[arg] == '':  # Tornado 3.0+ compatibility... Hard to test...
                    data[arg] = None

        return data

    def dump_object(self, instance):
        return json.dumps(instance)
