#!/usr/bin/python
# -*- coding: utf-8 -*-

# This file is part of bzz.
# https://github.com/heynemann/bzz

# Licensed under the MIT license:
# http://www.opensource.org/licenses/MIT-license
# Copyright (c) 2014 Bernardo Heynemann heynemann@gmail.com

import sqlalchemy as sa
import sqlalchemy.sql.functions as func
import sqlalchemy.orm as orm

from bzz.providers.sqlalchemy_provider import Base


class CustomQuerySet(Base):
    __tablename__ = 'CustomQuerySetTable'
    id = sa.Column(sa.Integer, primary_key=True)
    prop = sa.Column(sa.String(2000))

    @classmethod
    def get_list_queryset(cls, queryset, handler):
        return queryset.filter(CustomQuerySet.prop=='Bernardo Heynemann')

    @classmethod
    def get_instance_queryset(cls, model, queryset, instance_id, handler):
        return queryset.filter(CustomQuerySet.prop=='Bernardo Heynemann')

    def save(self, db):
        db.add(self)
        db.flush()
        db.commit()
