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
        self.write(utils.dumps(obj))

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
        is_multiple = yield self.is_multiple(args)

        if is_multiple and '/' not in args[-1]:
            yield self.handle_get_list(args)
        else:
            yield self.handle_get_one(args)

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

        obj, parent = yield self.get_instance_property(obj, args[1:])

        if obj is None:
            self.send_error(status_code=404)
            raise gen.Return((False, None))

        raise gen.Return((True, obj))

    @gen.coroutine
    def get_instance_property(self, obj, path):
        parts = [part.lstrip('/').split('/') for part in path if part]
        parent = obj
        for part in parts:
            path = part[0]
            pk = None

            if len(part) > 1:
                pk = part[1]

            obj = getattr(parent, path)

            if pk is not None:
                if isinstance(obj, (list, tuple)):
                    for item in obj:
                        instance_id = yield self.get_instance_id(item)
                        if instance_id == pk:
                            obj = item
                        if part != parts[-1]:
                            parent = obj

        raise gen.Return([obj, parent])

    @gen.coroutine
    def post(self, *args, **kwargs):
        args = self.parse_arguments(args)
        instance = None

        if len(args) == 1:
            if '/' in args[0]:
                self.send_error(400)
                return

            instance = yield self.handle_create_one(args)
        else:
            is_reference = yield self.is_reference(args)
            if is_reference:
                instance = yield self.handle_find_and_associate(args)
            else:
                instance = yield self.handle_create_and_associate(args)

        signals.post_create_instance.send(
            instance.__class__,
            instance=instance,
            handler=self
        )
        pk = yield self.get_instance_id(instance)
        self.set_header('X-Created-Id', pk)
        self.set_header('location', '/%s%s/%s/' % (
            self.prefix,
            self.name,
            pk
        ))
        self.write('OK')

    @gen.coroutine
    def handle_create_one(self, args):
        instance = yield self.save_new_instance(self.model, self.get_request_data())
        raise gen.Return(instance)

    @gen.coroutine
    def handle_create_and_associate(self, args):
        path, pk = args[0].split('/')
        root = yield self.get_instance(pk)
        model_type = self.get_model_type(root, args[1:])
        instance = yield self.save_new_instance(model_type, self.get_request_data())
        instance = yield self.associate_instance(root, args[-1], instance)
        raise gen.Return(instance)

    @gen.coroutine
    def handle_find_and_associate(self, args):
        path, pk = args[0].split('/')
        root = yield self.get_instance(pk)

        _, parent = yield self.get_instance_property(root, args[1:])
        request_data = self.get_request_data()
        model_type = self.get_property_model(parent, args[-1])
        instance = yield self.get_instance(request_data['item'], model=model_type)
        instance = yield self.associate_instance(root, args[-1], instance)
        raise gen.Return(instance)

    def get_model_type(self, obj, args):
        for index, arg in enumerate(args[:-1]):
            property_name, pk = arg.split('/')
            obj = getattr(obj, property_name)

        return self.get_property_model(obj, args[-1])

    @gen.coroutine
    def put(self, *args, **kwargs):
        args = self.parse_arguments(args)
        instance = None

        if len(args) == 1 and '/' not in args[0]:
            self.send_error(400)
            return

        is_multiple = yield self.is_multiple(args)
        is_reference = yield self.is_reference(args)
        if is_multiple and is_reference:
            self.send_error(400)
            return

        instance, updated, model = yield self.handle_update(args)
        signals.post_update_instance.send(model, instance=instance, updated_fields=updated, handler=self)
        self.write('OK')

    @gen.coroutine
    def handle_update(self, args):
        path, pk = args[0].split('/')
        root = yield self.get_instance(pk)
        model_type = root.__class__
        instance = parent = None
        if len(args) > 1:
            instance, parent = yield self.get_instance_property(root, args[1:])
            model_type = instance.__class__
            property_name, pk = args[-1].split('/')
        instance, updated = yield self.update_instance(pk, self.get_request_data(), model_type, instance, parent)
        raise gen.Return([instance, updated, model_type])

    @gen.coroutine
    def delete(self, *args, **kwargs):
        args = self.parse_arguments(args)

        if len(args) == 1 and '/' not in args[0]:
            self.send_error(400)
            return

        path, pk = args[0].split('/')
        root = yield self.get_instance(pk)
        model_type = root.__class__
        instance = None

        if len(args) > 1:
            instance, parent = yield self.get_instance_property(root, args[1:])
            model_type = instance.__class__
            property_name, pk = args[-1], None
            if '/' in property_name:
                property_name, pk = property_name.split('/')
            instance = yield self.handle_delete_association(parent, instance, property_name)
        else:
            instance = yield self.handle_delete_instance(pk)

        if instance:
            signals.post_delete_instance.send(model_type, instance=instance, handler=self)
            self.write('OK')
        else:
            self.write('FAIL')

    @gen.coroutine
    def handle_delete_instance(self, pk):
        instance = yield self.delete_instance(pk)
        raise gen.Return(instance)

    @gen.coroutine
    def handle_delete_association(self, parent, instance, property_name):
        field = parent._fields.get(property_name)
        if self.is_list_field(field):
            property_list = getattr(parent, property_name, [])

            try:
                property_list.remove(instance)
            except ValueError:
                self.send_error(400)
                return
        else:
            setattr(parent, property_name, None)

        parent.save()

        raise gen.Return(instance)

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
                if '=' in item:
                    key, value = item.split('=')
                else:
                    key, value = 'item', item

                data[key] = unquote(value)
        else:
            for arg in list(self.request.arguments.keys()):
                data[arg] = self.get_argument(arg)
                if data[arg] == '':  # Tornado 3.0+ compatibility... Hard to test...
                    data[arg] = None

        return data

    def dump_object(self, instance):
        return utils.dumps(instance)
