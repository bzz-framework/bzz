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
    def test_can_get_property_by_path(self):
        node = core.Node('test')
        node.model_type = 123

        found = node.find_by_path('test')
        expect(found).to_equal(node)

    def test_cant_create_node_with_invalid_children(self):
        node = core.Node('test')

        msg = "Can't create unnamed node."
        with expect.error_to_happen(ValueError, message=msg):
            core.Node("")

        msg = "Can't add non-Node(123) to child_nodes of 'test' when mapping models."
        with expect.error_to_happen(ValueError, message=msg):
            node.add_child(123)

    def test_can_get_property_by_path_inside_node(self):
        node = core.Node('test')
        node.model_type = 123

        inner = core.Node('inner')
        inner.model_type = 456

        node.add_child(inner)

        found = node.find_by_path('test.inner')
        expect(found).to_equal(inner)

        innerer = core.Node('innerer')  # like that's a word
        inner.add_child(innerer)

        found = node.find_by_path('test.inner.innerer')
        expect(found).to_equal(innerer)
