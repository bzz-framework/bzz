#!/usr/bin/python
# -*- coding: utf-8 -*-

# This file is part of bzz.
# https://github.com/heynemann/bzz

# Licensed under the MIT license:
# http://www.opensource.org/licenses/MIT-license
# Copyright (c) 2014 Bernardo Heynemann heynemann@gmail.com


from blinker import signal

pre_get_instance = signal('bzz.pre-get-instance')
post_get_instance = signal('bzz.post-get-instance')

pre_get_list = signal('bzz.pre-get-list')
post_get_list = signal('bzz.post-get-list')

pre_create_instance = signal('bzz.pre-create-instance')
post_create_instance = signal('bzz.post-create-instance')

pre_update_instance = signal('bzz.pre-update-instance')
post_update_instance = signal('bzz.post-update-instance')

pre_delete_instance = signal('bzz.pre-delete-instance')
post_delete_instance = signal('bzz.post-delete-instance')
