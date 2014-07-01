#!/usr/bin/python
# -*- coding: utf-8 -*-

# This file is part of bzz.
# https://github.com/heynemann/bzz

# Licensed under the MIT license:
# http://www.opensource.org/licenses/MIT-license
# Copyright (c) 2014 Bernardo Heynemann heynemann@gmail.com

import math

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

    def get_model_id(self, instance):
        return getattr(instance, 'get_id', lambda: str(instance.id))()

    @gen.coroutine
    def save_new_instance(self, data):
        values = {}
        for key, value in data.items():
            values[key] = value[0]

        instance = self.model(**values)
        instance.save()

        raise gen.Return(instance)

    @gen.coroutine
    def update_instance(self, pk, data):
        instance = yield self.get_instance(pk)
        for field, value in self.get_request_data().items():
            setattr(instance, field, value)
        instance.save()

    @gen.coroutine
    def delete_instance(self, pk):
        instance = yield self.get_instance(pk)
        if instance is not None:
            instance.delete()
        raise gen.Return(instance)

    @gen.coroutine
    def get_instance(self, instance_id):
        instance = None
        field = self.get_id_field_name()

        if instance_id:
            instance = self.model.objects.get(**{field: instance_id})

        raise gen.Return(instance)

    @gen.coroutine
    def get_list(self, per_page=20):
        pages = int(math.ceil(self.model.objects.count() / float(per_page)))
        try:
            page = int(self.get_argument('page', 1))
        except ValueError:
            page = 1

        if page > pages:
            page = pages

        page -= 1

        start = per_page * page
        stop = start + per_page

        items = self.model.objects.all()[start:stop]
        raise gen.Return(items)

    def dump_object(self, instance):
        method = getattr(instance, 'to_dict', None)

        if method:
            return method()

        data = {}
        for field in instance._fields.keys():
            data[field] = str(getattr(instance, field, None))
        return data

    def get_instance_id(self, instance):
        field = getattr(instance, 'get_id_field_name', None)
        if field:
            return getattr(instance, field().name)

        return str(instance.id)

    def get_id_field_name(self):
        field = getattr(self.model, 'get_id_field_name', None)
        if field:
            return field().name

        return 'id'

