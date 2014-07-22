#!/usr/bin/python
# -*- coding: utf-8 -*-

# This file is part of bzz.
# https://github.com/heynemann/bzz

# Licensed under the MIT license:
# http://www.opensource.org/licenses/MIT-license
# Copyright (c) 2014 Bernardo Heynemann heynemann@gmail.com

from preggy import expect

import bzz.core as core
import tests.base as base


class MetaModelsTestCase(base.TestCase):
    def test_can_get_property_by_path_inside_node(self):
        node = core.Node('test')
        node.model_type = 123

        inner = core.Node('inner')
        inner.model_type = 456

        node.children[inner.name] = inner

        found = node.find_by_path('inner')
        expect(found).to_equal(inner)

        innerer = core.Node('innerer')  # like that's a word
        inner.children[innerer.name] = innerer

        found = node.find_by_path('inner.innerer')
        expect(found).to_equal(innerer)
