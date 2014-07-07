#!/usr/bin/python
# -*- coding: utf-8 -*-

# This file is part of bzz.
# https://github.com/heynemann/bzz

# Licensed under the MIT license:
# http://www.opensource.org/licenses/MIT-license
# Copyright (c) 2014 Bernardo Heynemann heynemann@gmail.com

import slugify
import mongoengine


class User(mongoengine.Document):
    name = mongoengine.StringField(required=True)
    email = mongoengine.StringField(required=True)
    slug = mongoengine.StringField(required=False)

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


class Parent(mongoengine.Document):
    name = mongoengine.StringField(required=True)
    child = mongoengine.EmbeddedDocumentField(Child, required=False)
