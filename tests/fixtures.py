#!/usr/bin/python
# -*- coding: utf-8 -*-

# This file is part of marketplace-v2.
# https://github.com/globoi/marketplacev2


import slugify
import factory
import factory.mongoengine as mongofactory

import tests.models.mongoengine_models as models


class UserFactory(mongofactory.MongoEngineFactory):
    name = factory.Sequence(lambda i: u'user %d' % i)
    slug = factory.LazyAttribute(lambda user: slugify.slugify(user.name))
    email = factory.Sequence(lambda i: u'user-%d@whatever.foo' % i)

    class Meta:
        model = models.User


class OtherUserFactory(mongofactory.MongoEngineFactory):
    name = factory.Sequence(lambda i: u'other-user %d' % i)
    slug = factory.LazyAttribute(lambda user: slugify.slugify(user.name))
    email = factory.Sequence(lambda i: u'other-user-%d@whatever.foo' % i)

    class Meta:
        model = models.OtherUser
