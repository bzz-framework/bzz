#!/usr/bin/python
# -*- coding: utf-8 -*-

# This file is part of bzz.
# https://github.com/heynemann/bzz

# Licensed under the MIT license:
# http://www.opensource.org/licenses/MIT-license
# Copyright (c) 2014 Bernardo Heynemann heynemann@gmail.com

import math

import tornado.gen as gen
import mongoengine
import bson

import bzz.rest_handler as bzz


class MongoEngineRestHandler(bzz.ModelRestHandler):
    @gen.coroutine
    def save_new_instance(self, model, data):
        instance = model()

        for key, value in data.items():
            if '.' in key:
                self.fill_property(self.model, instance, key, value)
            else:
                setattr(instance, key, value)

        if not isinstance(instance, mongoengine.EmbeddedDocument):
            instance.save()

        raise gen.Return(instance)

    def fill_property(self, model, instance, key, value, updated_fields=None):
        parts = key.split('.')
        field_name = parts[0]
        property_name = '.'.join(parts[1:])

        if getattr(instance, field_name, None) is None:
            field = model._fields[field_name]
            embedded_document = field.document_type()

            if updated_fields is not None:
                updated_fields[field_name] = {
                    'from': getattr(instance, field_name),
                    'to': value
                }

            setattr(instance, field_name, embedded_document)

        if '.' not in property_name:
            if updated_fields is not None:
                updated_fields[field_name] = {
                    'from': getattr(instance, field_name),
                    'to': str(value)
                }

            setattr(getattr(instance, field_name), property_name, value)
        else:
            new_instance = getattr(instance, field_name)
            self.fill_property(new_instance.__class__, new_instance, property_name, value)

    @gen.coroutine
    def update_instance(self, pk, data, model=None, instance=None, parent=None):
        if model is None:
            model = self.model

        if instance is None:
            instance = yield self.get_instance(pk, model)

        updated_fields = {}
        for field, value in self.get_request_data().items():
            if '.' in field:
                self.fill_property(model, instance, field, value, updated_fields)
            else:
                updated_fields[field] = {
                    'from': getattr(instance, field),
                    'to': value
                }
                setattr(instance, field, value)

        if parent and isinstance(instance, mongoengine.EmbeddedDocument):
            parent.save()
        else:
            instance.save()

        raise gen.Return((instance, updated_fields))

    @gen.coroutine
    def delete_instance(self, pk):
        instance = yield self.get_instance(pk)
        if instance is not None:
            instance.delete()
        raise gen.Return(instance)

    @gen.coroutine
    def get_instance(self, instance_id, model=None):
        if model is None:
            model = self.model

        instance = None
        field = self.get_id_field_name()

        if instance_id:
            # if mongoengine.EmbeddedDocument in model.mro():
            instance = model.objects.filter(**{field: instance_id}).first()

        raise gen.Return(instance)

    @gen.coroutine
    def get_list(self, items=None, per_page=20):
        pages = int(math.ceil(self.model.objects.count() / float(per_page)))
        if pages == 0:
            raise gen.Return([])

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

    def dump_list(self, items, per_page=20):
        dumped = []

        for item in items:
            dumped.append(self.dump_instance(item))

        return dumped

    def dump_instance(self, instance):
        method = getattr(instance, 'to_dict', None)

        if method:
            return method()

        data = {}
        for field_name in instance._fields.keys():
            field = getattr(instance.__class__, field_name)
            value = field.to_mongo(getattr(instance, field_name, None))

            if isinstance(value, bson.ObjectId):
                value = str(value)

            data[field_name] = value
        return data

    @gen.coroutine
    def get_instance_id(self, instance):
        field = getattr(instance.__class__, 'get_id_field_name', None)
        if field:
            raise gen.Return(str(getattr(instance, field().name)))

        raise gen.Return(str(instance.id))

    def get_id_field_name(self):
        field = getattr(self.model, 'get_id_field_name', None)
        if field:
            return field().name

        return 'id'

    def get_document_type(self, field):
        if self.is_list_field(field):
            field = field.field
        return field.document_type

    def get_model(self, field):
        # if obj is None:
        #     raise gen.Return(self.model)

        # field = getattr(obj.__class__, field_name)
        # raise gen.Return(field.field.document_type)
        return self.get_document_type(field)

    @gen.coroutine
    def associate_instance(self, obj, field_name, instance):
        if obj is None:
            return

        field = obj._fields.get(field_name)
        if self.is_list_field(field):
            getattr(obj, field_name).append(instance)
        else:
            setattr(obj, field_name, instance)

        raise gen.Return(obj.save())

    def is_embedded_field(self, field):
        return isinstance(field, mongoengine.EmbeddedDocumentField)

    def is_list_field(self, field):
        return isinstance(field, mongoengine.ListField)

    def get_property_model(self, obj, field_name):
        property_name = field_name
        pk = None

        if '/' in field_name:
            property_name, pk = field_name.split('/')

        field = obj._fields[property_name]
        return self.get_document_type(field)

    @gen.coroutine
    def is_multiple(self, path):
        parts = [part.lstrip('/').split('/') for part in path if part]
        to_return = False
        model = self.model

        if len(parts) == 1 and len(parts[0]) == 1:
            raise gen.Return(True)

        for part in parts[1:]:
            to_return = False
            path = part[0]
            field = getattr(model, path)
            to_return = self.is_list_field(field)
            model = self.get_model(field)

        raise gen.Return(to_return)
