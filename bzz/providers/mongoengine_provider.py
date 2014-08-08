#!/usr/bin/python
# -*- coding: utf-8 -*-

# This file is part of bzz.
# https://github.com/heynemann/bzz

# Licensed under the MIT license:
# http://www.opensource.org/licenses/MIT-license
# Copyright (c) 2014 Bernardo Heynemann heynemann@gmail.com

import sys
import math

import tornado.gen as gen
import mongoengine

import bzz.model as bzz
import bzz.utils as utils


class MongoEngineProvider(bzz.ModelProvider):
    @classmethod
    def get_model_name(cls, model):
        return model.__name__

    @classmethod
    def get_model_collection(cls, model):
        return model._meta.get('collection', None)

    @classmethod
    def get_model_fields(cls, model):
        return model._fields

    @classmethod
    def get_model(cls, field):
        return cls.get_document_type(field)

    @classmethod
    def get_field_target_name(cls, field):
        return field.db_field

    @classmethod
    def get_document_type(cls, field):
        if cls.is_list_field(field):
            field = field.field
        return getattr(field, 'document_type', None)

    @classmethod
    def allows_create_on_associate(cls, field):
        if cls.is_list_field(field):
            field = field.field

        return cls.is_embedded_field(field)

    @classmethod
    def is_lazy_loaded(cls, field):
        if cls.is_list_field(field):
            field = field.field

        return cls.is_reference_field(field)

    @classmethod
    def is_list_field(cls, field):
        return isinstance(field, mongoengine.ListField)

    @classmethod
    def is_reference_field(cls, field):
        return isinstance(field, mongoengine.ReferenceField)

    @classmethod
    def is_embedded_field(cls, field):
        return isinstance(field, mongoengine.EmbeddedDocumentField)

    @gen.coroutine
    def save_new_instance(self, model, data):
        instance = model()

        for key, value in data.items():
            if '.' in key or '[]' in key:
                yield self.fill_property(model, instance, key, value)
            else:
                field = instance._fields.get(key)
                if self.is_reference_field(field):
                    value = yield self.get_instance(
                        value,
                        self.get_model(field)
                    )
                setattr(instance, key, value)

        if isinstance(instance, mongoengine.Document):
            try:
                instance.save()
            except mongoengine.NotUniqueError:
                err = sys.exc_info()[1]
                raise gen.Return((None, (409, err)))
            except mongoengine.ValidationError:
                err = sys.exc_info()[1]
                raise gen.Return((None, (400, err)))

        raise gen.Return((instance, None))

    @gen.coroutine
    def fill_property(self, model, instance, key, value, updated_fields=None):
        parts = key.split('.')
        field_name = parts[0]
        multiple = False
        if field_name.endswith('[]'):
            multiple = True
            field_name = field_name.replace('[]', '')

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

            field = getattr(model, field_name, None)
            child_model = self.get_model(field)
            if multiple and self.is_list_field(field):
                if not isinstance(value, (tuple, list)):
                    value = [value]

                list_property = getattr(instance, field_name)
                for item in value:
                    child_instance = yield self.get_instance(
                        item, model=child_model
                    )
                    list_property.append(child_instance)
            else:
                setattr(getattr(instance, field_name), property_name, value)
        else:
            new_instance = getattr(instance, field_name)
            yield self.fill_property(
                new_instance.__class__, new_instance,
                property_name, value
            )

    @gen.coroutine
    def update_instance(
            self, pk, data, model=None, instance=None, parent=None):
        if model is None:
            model = self.model

        if instance is None:
            instance = yield self.get_instance(pk, model)

        updated_fields = {}
        for field_name, value in self.get_request_data().items():
            if '.' in field_name:
                yield self.fill_property(
                    model, instance, field_name, value, updated_fields
                )
            else:
                field = instance._fields.get(field_name)
                if self.is_reference_field(field):
                    value = yield self.get_instance(
                        value, self.get_model(field)
                    )
                updated_fields[field_name] = {
                    'from': getattr(instance, field_name),
                    'to': value
                }
                setattr(instance, field_name, value)

        if parent and isinstance(instance, mongoengine.EmbeddedDocument):
            _, error = yield self.save_instance(parent)
        else:
            _, error = yield self.save_instance(instance)

        raise gen.Return((error, instance, updated_fields))

    @gen.coroutine
    def save_instance(self, instance):
        error = None
        try:
            instance.save()
        except mongoengine.NotUniqueError:
            err = sys.exc_info()[1]
            raise gen.Return((None, (409, err)))
        except mongoengine.ValidationError:
            err = sys.exc_info()[1]
            raise gen.Return((None, (400, err)))

        raise gen.Return((instance, error))

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

        queryset = model.objects
        if hasattr(model, 'get_instance_queryset'):
            queryset = model.get_instance_queryset(model, queryset, instance_id, self)

        instance = None
        field = self.get_id_field_name(model)

        if instance_id:
            instance = queryset.filter(**{field: instance_id}).first()

        raise gen.Return(instance)

    @gen.coroutine
    def get_list(self, items=None, page=1, per_page=20, filters=None):
        if filters is None:
            filters = {}

        queryset = self.model.objects
        if hasattr(self.model, 'get_list_queryset'):
            queryset = self.model.get_list_queryset(queryset, self)

        if filters:
            queryset = queryset.filter(**dict([
                (key.replace('.', '__'), value)
                for key, value in filters.items()
            ]))

        pages = int(math.ceil(queryset.count() / float(per_page)))
        if pages == 0:
            raise gen.Return([])

        if page > pages:
            page = pages

        page -= 1

        start = per_page * page
        stop = start + per_page

        items = queryset.all()[start:stop]
        raise gen.Return(items)

    def dump_list(self, items):
        dumped = []

        for item in items:
            dumped.append(self.dump_instance(item))

        return dumped

    def dump_instance(self, instance):
        if instance is None:
            return {}

        method = getattr(instance, 'to_dict', None)

        if method:
            return method()

        return utils.loads(instance.to_json())

    @gen.coroutine
    def get_instance_id(self, instance):
        field = getattr(instance.__class__, 'get_id_field_name', None)
        if field:
            raise gen.Return(str(getattr(instance, field().name)))

        raise gen.Return(str(instance.id))

    def get_id_field_name(self, model=None):
        if model is None:
            model = self.model
        field = getattr(model, 'get_id_field_name', None)
        if field:
            return field().name

        return 'id'

    @gen.coroutine
    def associate_instance(self, obj, field_name, instance):
        if obj is None:
            return

        field = obj._fields.get(field_name)
        if self.is_list_field(field):
            getattr(obj, field_name).append(instance)
        else:
            setattr(obj, field_name, instance)

        try:
            obj.save()
        except mongoengine.NotUniqueError:
            err = sys.exc_info()[1]
            raise gen.Return((None, (409, err)))
        except mongoengine.ValidationError:
            err = sys.exc_info()[1]
            raise gen.Return((None, (400, err)))

        raise gen.Return((obj, None))

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

    @gen.coroutine
    def is_reference(self, path):
        parts = [part.lstrip('/').split('/') for part in path if part]
        to_return = False
        model = self.model

        for part in parts[1:]:
            to_return = False
            model_path = part[0]
            field = getattr(model, model_path)

            if self.is_list_field(field):
                field = field.field

            to_return = self.is_reference_field(field)
            model = self.get_model(field)

        raise gen.Return(to_return)

    @gen.coroutine
    def get_model_from_path(self, path):
        parts = [part.lstrip('/').split('/') for part in path if part]
        model = self.model

        if len(parts) == 1 and len(parts[0]) == 1:
            raise gen.Return(model)

        for part in parts[1:]:
            path = part[0]
            field = getattr(model, path)
            model = self.get_model(field)

        raise gen.Return(model)
