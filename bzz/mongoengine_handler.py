#!/usr/bin/python
# -*- coding: utf-8 -*-

# This file is part of bzz.
# https://github.com/heynemann/bzz

# Licensed under the MIT license:
# http://www.opensource.org/licenses/MIT-license
# Copyright (c) 2014 Bernardo Heynemann heynemann@gmail.com

import math
import re

import tornado.gen as gen
import mongoengine

import bzz.rest_handler as bzz


first_cap_re = re.compile('(.)([A-Z][a-z]+)')
all_cap_re = re.compile('([a-z0-9])([A-Z])')


def convert(name):
    s1 = first_cap_re.sub(r'\1_\2', name)
    return all_cap_re.sub(r'\1_\2', s1).lower()


class MongoEngineRestHandler(bzz.ModelRestHandler):
    @classmethod
    def routes_for(cls, document_type, prefix='', resource_name=None):
        name = resource_name
        if name is None:
            name = convert(document_type.__name__)

        details_url = r'/%s%s(?:/(?P<pk>[^/]+)?)/?' % (prefix.lstrip('/'), name)

        routes = [
            (details_url, cls, dict(model=document_type, name=name, prefix=prefix))
        ]

        #for field_name, field in document_type._fields.items():
            #if isinstance(field, mongoengine.EmbeddedDocumentField):
                #embedded_url = r'/%s%s(?:/(?P<pk>[^/]+))/%s/?' % (prefix.lstrip('/'), name, field_name)
                #routes.append(
                    #(embedded_url, cls, dict(model=document_type, name=name, prefix=prefix))
                #)

        return routes

    @gen.coroutine
    def save_new_instance(self, data):
        instance = self.model()

        for key, value in data.items():
            if '.' in key:
                self.fill_property(self.model, instance, key, value)
            else:
                setattr(instance, key, value)

        instance.save()

        raise gen.Return(instance)

    def fill_property(self, model, instance, key, value):
        parts = key.split('.')
        field_name = parts[0]
        property_name = '.'.join(parts[1:])
        property_model = model

        if getattr(instance, field_name, None) is None:
            field = model._fields[field_name]
            embedded_document = field.document_type()
            setattr(instance, field_name, embedded_document)

        if '.' not in property_name:
            setattr(getattr(instance, field_name), property_name, value)
        else:
            new_instance = getattr(instance, field_name)
            self.fill_property(new_instance.__class__, new_instance, property_name, value)

    @gen.coroutine
    def update_instance(self, pk, data):
        updated_fields = {}
        instance = yield self.get_instance(pk)
        for field, value in self.get_request_data().items():
            updated_fields[field] = {
                'from': getattr(instance, field),
                'to': value
            }
            setattr(instance, field, value)
        instance.save()
        raise gen.Return((instance, updated_fields))

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
            instance = self.model.objects.filter(**{field: instance_id}).first()

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
        field = getattr(self.model, 'get_id_field_name', None)
        if field:
            return str(getattr(instance, field().name))

        return str(instance.id)

    def get_id_field_name(self):
        field = getattr(self.model, 'get_id_field_name', None)
        if field:
            return field().name

        return 'id'
