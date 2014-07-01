#!/usr/bin/python
# -*- coding: utf-8 -*-

# This file is part of bzz.
# https://github.com/heynemann/bzz

# Licensed under the MIT license:
# http://www.opensource.org/licenses/MIT-license
# Copyright (c) 2014 Bernardo Heynemann heynemann@gmail.com

import math
import tornado

try:
    import ujson as json
except ImportError:
    import json


class ModelRestHandler(tornado.web.RequestHandler):
    def initialize(self, model):
        self.model = model

    def get(self, pk=None):
        instance = self.get_instance(pk)

        if instance:
            self.write(json.dumps(self.dump_object(instance)))
        else:
            self.list()

    def post(self, pk=None):
        instance = self.model(**self.get_request_data())
        instance.save()
        pk = self.get_object_id(instance)
        self.set_header('X-Created-Id', pk)
        self.write('OK')

    def put(self, pk):
        instance = self.get_instance(pk)

        for field, value in self.get_request_data().items():
            setattr(instance, field, value)

        instance.save()
        self.write('OK')

    def delete(self, pk):
        instance = self.get_instance(pk)
        if instance:
            instance.delete()
            self.write('OK')
        else:
            self.write('FAIL')

    def list(self):
        dump = []
        for obj in self.paginate(self.model.objects):
            dump.append(self.dump_object(obj))

        self.write(json.dumps(dump))

    def paginate(self, queryset, per_page=20):
        pages = int(math.ceil(queryset.count() / float(per_page)))
        try:
            page = int(self.get_argument('page', 1))
        except ValueError:
            page = 1

        if page > pages:
            page = pages

        page -= 1

        start = per_page * page
        stop = start + per_page

        return queryset.all()[start:stop]

    def get_request_data(self):
        data = {}
        for arg in list(self.request.arguments.keys()):
            data[arg] = self.get_argument(arg)
            if data[arg] == '':  # Tornado 3.0+ compatibility
                data[arg] = None
        return data

    def get_object_id(self, instance):
        field = getattr(instance, 'get_id_field', None)
        instance_id = instance.id
        if field:
            return getattr(instance, field().name)

        return str(instance_id)

    def get_id_field(self):
        field = getattr(self.model, 'get_id_field', None)
        if field:
            return field().name

        return 'id'

    def dump_object(self, instance):
        method = getattr(instance, 'to_dict', None)

        if method:
            return method()

        data = {}
        for field in instance._fields.keys():
            data[field] = str(getattr(instance, field, None))
        return data

    def get_instance(self, instance_id):
        instance = None
        field = self.get_id_field()

        if instance_id:
            instance = self.model.objects.get(**{field: instance_id})
        return instance
