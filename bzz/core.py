#!/usr/bin/python
# -*- coding: utf-8 -*-

# This file is part of bzz.
# https://github.com/heynemann/bzz

# Licensed under the MIT license:
# http://www.opensource.org/licenses/MIT-license
# Copyright (c) 2014 Bernardo Heynemann heynemann@gmail.com

import slugify


class Node(object):
    def __init__(self, name):
        if not name:
            raise ValueError("Can't create unnamed node.")

        self.name = name
        self.slug = slugify.slugify(self.name.lower())
        self.target_name = name
        self.model_type = None
        self.is_multiple = False
        self.allow_create_on_associate = False
        self.children = {}
        self.required_children = []

    def add_child(self, node):
        if not isinstance(node, Node):
            raise ValueError("Can't add non-Node(%s) to child_nodes of '%s' when mapping models." % (node, self.name))

        self.children[node.name] = node

    def find_by_path(self, path):
        if '.' not in path:
            return self

        obj = self
        for part in path.split('.')[1:]:
            obj = obj.children.get(part, None)

            if obj is None:
                break

        return obj
