#!/usr/bin/python
# -*- coding: utf-8 -*-

# This file is part of bzz.
# https://github.com/heynemann/bzz

# Licensed under the MIT license:
# http://www.opensource.org/licenses/MIT-license
# Copyright (c) 2014 Bernardo Heynemann heynemann@gmail.com

import slugify


class RouteList(list):
    pass


class Node(object):
    def __init__(self, name, is_root=False):
        if not name:
            raise ValueError("Can't create unnamed node.")

        self.is_root = is_root
        self.name = name
        self.slug = slugify.slugify(self.name.lower())
        self.target_name = name
        self.model_type = None
        self.is_multiple = False
        self.allows_create_on_associate = False
        self.lazy_loaded = False
        self.children = {}
        self.required_children = []

    def find_by_path(self, path):
        if not path:
            return self
        if '.' not in path:
            return self.children.get(path, None)

        obj = self
        for part in path.split('.'):
            obj = obj.children.get(part, None)

            if obj is None:
                break

        return obj
