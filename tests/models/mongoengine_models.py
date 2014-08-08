#!/usr/bin/python
# -*- coding: utf-8 -*-

# This file is part of bzz.
# https://github.com/heynemann/bzz

# Licensed under the MIT license:
# http://www.opensource.org/licenses/MIT-license
# Copyright (c) 2014 Bernardo Heynemann heynemann@gmail.com

import slugify
import mongoengine


class Address(mongoengine.Document):
    street = mongoengine.StringField(required=True)


class User(mongoengine.Document):
    name = mongoengine.StringField(required=True)
    email = mongoengine.StringField(required=True)
    slug = mongoengine.StringField(required=False)
    addresses = mongoengine.ListField(mongoengine.ReferenceField(Address), required=False)

    def save(self, *args, **kw):
        self.slug = slugify.slugify(self.name, to_lower=True)
        super(User, self).save(*args, **kw)


class OtherUser(mongoengine.Document):
    name = mongoengine.StringField(required=True)
    email = mongoengine.StringField(required=True)
    slug = mongoengine.StringField(required=False)

    def to_dict(self):
        return {
            "user": "%s <%s>" % (self.name, self.email)
        }

    def save(self, *args, **kw):
        self.slug = slugify.slugify(self.name, to_lower=True)
        super(OtherUser, self).save(*args, **kw)

    @classmethod
    def get_id_field_name(cls):
        return OtherUser.slug


class Team(mongoengine.Document):
    name = mongoengine.StringField(required=True)
    users = mongoengine.ListField(mongoengine.ReferenceField(User))


class GrandChild(mongoengine.EmbeddedDocument):
    first_name = mongoengine.StringField(required=True)
    last_name = mongoengine.StringField(required=True)


class Child(mongoengine.EmbeddedDocument):
    first_name = mongoengine.StringField(required=True)
    last_name = mongoengine.StringField(required=True)
    child = mongoengine.EmbeddedDocumentField(GrandChild, required=False)

    @classmethod
    def get_id_field_name(cls):
        return Child.first_name


class Parent(mongoengine.Document):
    name = mongoengine.StringField(required=True)
    child = mongoengine.EmbeddedDocumentField(Child, required=False)


class Parent2(mongoengine.Document):
    name = mongoengine.StringField(required=True)
    children = mongoengine.ListField(mongoengine.EmbeddedDocumentField(Child))


class Person(mongoengine.Document):
    name = mongoengine.StringField(required=True)


class Student(mongoengine.Document):
    code = mongoengine.StringField(required=True)
    person = mongoengine.ReferenceField(Person)


class CustomQuerySet(mongoengine.Document):
    prop = mongoengine.StringField()
    meta = {'collection': 'custom_queryset'}

    @classmethod
    def get_list_queryset(cls, queryset, handler):
        return queryset(prop='Bernardo Heynemann')

    @classmethod
    def get_instance_queryset(cls, model, queryset, instance_id, handler):
        return queryset.filter(prop='Bernardo Heynemann')


class UniqueUser(mongoengine.Document):
    name = mongoengine.StringField(unique=True)
    meta = {'collection': 'unique_user'}


class ValidationUser(mongoengine.Document):
    name = mongoengine.StringField(required=True)
    items = mongoengine.ListField(mongoengine.ReferenceField(UniqueUser), required=True)
    meta = {'collection': 'validation_user'}

    def clean(self):
        if len(self.items) > 1:
            raise mongoengine.ValidationError(field_name='items', message='something went wrong')
