#!/usr/bin/python
# -*- coding: utf-8 -*-

# This file is part of bzz.
# https://github.com/heynemann/bzz

# Licensed under the MIT license:
# http://www.opensource.org/licenses/MIT-license
# Copyright (c) 2014 Bernardo Heynemann heynemann@gmail.com


from blinker import signal

post_create_instance = signal('bzz.post-create-instance')
post_update_instance = signal('bzz.post-update-instance')
post_delete_instance = signal('bzz.post-update-instance')
