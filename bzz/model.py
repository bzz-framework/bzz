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

import bzz.core as core
import bzz.signals as signals
import bzz.utils as utils


AVAILABLE_PROVIDERS = {
    'mongoengine': 'bzz.providers.mongoengine_provider.MongoEngineProvider'
}


class ModelHive(object):
    @classmethod
    def routes_for(cls, provider, model, prefix='', resource_name=None):
        '''
        Returns the list of routes for the specified model.

        * [POST] Create new instances;
        * [PUT] Update existing instances;
        * [DELETE] Delete existing instances;
        * [GET] Retrieve existing instances with the id for the instance;
        * [GET] List existing instances (and filter them);

        :param provider: The ORM provider to be used for this model
        :type provider: Full-name provider or built-in provider
        :param model: The model to be mapped
        :type model: Class Type
        :param prefix: Optional argument to include a prefix route (i.e.: '/api');
        :type prefix: string
        :param resource_name: an optional argument that can be specified to change the route name. If no resource_name specified the route name is the __class__.__name__ for the specified model with underscores instead of camel case.
        :type resource_name: string
        :returns: route list (can be flattened with bzz.flatten)

        If you specify a prefix of '/api/' as well as resource_name of 'people' your route would be similar to:

        http://myserver/api/people/ (do a post to this url to create a new person)

        Usage:

        .. testcode:: model_hive_example_1

           import tornado.web
           from mongoengine import *
           import bzz

           server = None

           # just create your own documents
           class User(Document):
              __collection__ = "MongoEngineHandlerUser"
              name = StringField()

           def create_user():
              # let's create a new user by posting it's data
              http_client.fetch(
                 'http://localhost:8890/user/',
                 method='POST',
                 body='name=Bernardo%20Heynemann',
                 callback=handle_user_created
              )

           def handle_user_created(response):
              # just making sure we got the actual user
              try:
                 assert response.code == 200, response.code
              finally:
                 io_loop.stop()

           # bzz includes a helper to return the routes for your models
           # returns a list of routes that match '/user/<user-id>/' and allows for:
           routes = bzz.ModelHive.routes_for('mongoengine', User)

           User.objects.delete()
           application = tornado.web.Application(routes)
           server = HTTPServer(application, io_loop=io_loop)
           server.listen(8895)
           io_loop.add_timeout(1, create_user)
           io_loop.start()
        '''
        provider_name = AVAILABLE_PROVIDERS.get(provider, provider)
        provider_class = utils.get_class(provider_name)
        name = resource_name
        if name is None:
            name = utils.convert(model.__name__)

        details_regex = r'/(%s(?:/[^/]+)?)((?:/[^/]+)*)/?'

        details_regex = utils.add_prefix(prefix, details_regex)

        tree = provider_class.get_tree(model)

        options = dict(model=model, name=name, prefix=prefix, tree=tree)
        routes = core.RouteList()

        routes.append(
            (details_regex % name, provider_class, options)
        )

        return routes


class ModelProvider(tornado.web.RequestHandler):
    @classmethod
    def get_tree(cls, model, node=None):
        if node is None:
            node = core.Node(cls.get_model_name(model), is_root=True)

        node.target_name = cls.get_model_collection(model)
        node.is_multiple = False

        if node.target_name is None:
            node.target_name = node.slug

        node.model_type = model

        cls.parse_children(model, node.children)

        return node

    @classmethod
    def parse_children(cls, model, collection):
        for field_name, field in cls.get_model_fields(model).items():
            child_node = core.Node(field_name)
            collection[field_name] = child_node

            child_node.is_multiple = cls.is_list_field(field)
            child_node.target_name = cls.get_field_target_name(field)
            child_node.allows_create_on_associate = \
                cls.allows_create_on_associate(field)
            child_node.is_lazy_loaded = \
                cls.is_lazy_loaded(field)

            child_node.model_type = cls.get_model(field)

            if child_node.model_type is not None:
                cls.parse_children(child_node.model_type, child_node.children)

    def get_node(self, path):
        if '.' not in path:
            return self.tree.get(path, None)

        node = self.tree
        for item in path.split('.'):
            node = node.get(item, None)
            if node is None:
                return None

        return node

    def initialize(self, model, name, prefix, tree):
        self.model = model
        self.name = name
        self.prefix = prefix
        self.tree = tree

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

    @classmethod
    def get_path_from_args(cls, args):
        path = ".".join([arg.split('/')[0] for arg in args[1:]])
        return path

    @gen.coroutine
    def get(self, *args, **kwargs):
        args = self.parse_arguments(args)
        path = self.get_path_from_args(args)
        node = self.tree.find_by_path(path)

        if (node.is_root or node.is_multiple) and '/' not in args[-1]:
            yield signals.pre_get_list.send(node.model_type, arguments=args, handler=self)
            yield self.handle_get_list(args)
        else:
            yield signals.pre_get_instance.send(node.model_type, arguments=args, handler=self)
            yield self.handle_get_one(args)

    @gen.coroutine
    def handle_get_one(self, args):
        success, obj, parent = yield self.get_instance_from_args(args)
        if not success:
            return

        if obj is None:
            self.send_error(status_code=404)
            return

        yield signals.post_get_instance.send(obj.__class__, instance=obj, handler=self)

        self.write_json(self.dump_instance(obj))
        self.finish()

    @gen.coroutine
    def handle_get_list(self, args):
        if '/' not in args[0] and len(args) > 1:
            # /team/user -> missing user pk
            self.send_error(status_code=400)
            return

        if len(args) == 1:
            request_data = self.get_request_data()
            try:
                page = int(request_data.pop('page', 1))
            except ValueError:
                page = 1

            try:
                per_page = int(request_data.pop('per_page', 20))
            except ValueError:
                per_page = 20

            items = yield self.get_list(page=page, per_page=per_page, filters=request_data)
            model_type = self.model
        else:
            success, items, parent = yield self.get_instance_from_args(args)
            if not success:
                self.send_error(status_code=400)
                return

            model_type = self.get_property_model(parent, args[-1])

        yield signals.post_get_list.send(model_type, items=items, handler=self)

        self.write_json(self.dump_list(items))
        self.finish()

    @gen.coroutine
    def get_instance_from_args(self, args):
        model, pk = args[0].split('/')
        obj = yield self.get_instance(pk)

        if len(args) == 1:
            raise gen.Return((True, obj, None))

        obj, parent = yield self.get_instance_property(obj, args[1:])

        if obj is None:
            self.send_error(status_code=404)
            raise gen.Return((False, None))

        raise gen.Return((True, obj, parent))

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
        model_type = yield self.get_model_from_path(args)

        yield signals.pre_create_instance.send(
            model_type,
            arguments=args,
            handler=self,
        )

        instance = None

        if len(args) == 1:
            if '/' in args[0]:
                self.send_error(400)
                return

            instance, error = yield self.handle_create_one(args)
        else:
            is_reference = yield self.is_reference(args)
            if is_reference:
                instance, error = yield self.handle_find_and_associate(args)
            else:
                instance, error = yield self.handle_create_and_associate(args)

        if error is not None:
            status_code, error = error
            self.set_status(status_code)
            self.write(str(error))
            return

        yield signals.post_create_instance.send(
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
        instance, error = yield self.save_new_instance(self.model, self.get_request_data())
        raise gen.Return((instance, error))

    @gen.coroutine
    def handle_create_and_associate(self, args):
        path, pk = args[0].split('/')
        root = yield self.get_instance(pk)
        model_type = self.get_model_type(root, args[1:])
        instance, error = yield self.save_new_instance(model_type, self.get_request_data())
        if error is not None:
            raise gen.Return((None, error))

        _, error = yield self.associate_instance(root, args[-1], instance)
        if error is not None:
            raise gen.Return((None, error))

        raise gen.Return((instance, error))

    @gen.coroutine
    def handle_find_and_associate(self, args):
        path, pk = args[0].split('/')
        root = yield self.get_instance(pk)

        _, parent = yield self.get_instance_property(root, args[1:])
        request_data = self.get_request_data()
        model_type = self.get_property_model(parent, args[-1])
        key = "%s[]" % args[-1]
        value = request_data[key]
        instance = yield self.get_instance(value, model=model_type)

        _, error = yield self.associate_instance(root, args[-1], instance)
        if error is not None:
            raise gen.Return((None, error))

        raise gen.Return((instance, None))

    def get_model_type(self, obj, args):
        for index, arg in enumerate(args[:-1]):
            property_name, pk = arg.split('/')
            obj = getattr(obj, property_name)

        return self.get_property_model(obj, args[-1])

    @gen.coroutine
    def put(self, *args, **kwargs):
        args = self.parse_arguments(args)
        model_type = yield self.get_model_from_path(args)

        yield signals.pre_update_instance.send(
            model_type,
            arguments=args,
            handler=self
        )

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
        yield signals.post_update_instance.send(model, instance=instance, updated_fields=updated, handler=self)
        self.write('OK')

    @gen.coroutine
    def handle_update(self, args):
        path, pk = args[0].split('/')
        root = yield self.get_instance(pk)
        model_type = root.__class__
        instance = parent = None

        if not self.validate_update_request_data(root, model_type):
            self.send_error(400, reason="Invalid multiple field")
            raise tornado.web.Finish()

        if len(args) > 1:
            instance, parent = yield self.get_instance_property(root, args[1:])
            model_type = instance.__class__
            property_name, pk = args[-1].split('/')
        error, instance, updated = yield self.update_instance(pk, self.get_request_data(), model_type, instance, parent)

        if error is not None:
            status_code, error = error
            self.set_status(status_code)
            self.write(str(error))
            return

        raise gen.Return([instance, updated, model_type])

    def validate_update_request_data(self, root, model_type):
        data = self.get_request_data()

        for key, value in data.items():
            if key.endswith('[]'):
                return False

        return True

    @gen.coroutine
    def delete(self, *args, **kwargs):
        args = self.parse_arguments(args)

        if len(args) == 1 and '/' not in args[0]:
            self.send_error(400)
            return

        model_type = yield self.get_model_from_path(args)
        yield signals.pre_delete_instance.send(model_type, arguments=args, handler=self)

        path, pk = args[0].split('/')
        root = yield self.get_instance(pk)
        instance = None

        if len(args) > 1:
            instance, parent = yield self.get_instance_property(root, args[1:])
            property_name, pk = args[-1], None
            if '/' in property_name:
                property_name, pk = property_name.split('/')
            instance, error = yield self.handle_delete_association(parent, instance, property_name)
        else:
            instance = yield self.handle_delete_instance(pk)
            error = None

        if error is not None:
            status_code, error = error
            self.set_status(status_code)
            self.write(str(error))
            return

        if instance:
            yield signals.post_delete_instance.send(model_type, instance=instance, handler=self)
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

        _, error = yield self.save_instance(parent)

        raise gen.Return((instance, error))

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

                if key in data:
                    if not isinstance(data[key], (tuple, list)):
                        old = data[key]
                        data[key] = []
                        data[key].append(old)
                    data[key].append(unquote(value))
                else:
                    data[key] = unquote(value)
        else:
            for arg in list(self.request.arguments.keys()):
                data[arg] = self.get_argument(arg)
                if data[arg] == '':  # Tornado 3.0+ compatibility... Hard to test...
                    data[arg] = None

        return data

    def dump_object(self, instance):
        return utils.dumps(instance)
