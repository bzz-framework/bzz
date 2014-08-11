#!/usr/bin/python
# -*- coding: utf-8 -*-

# This file is part of bzz.
# https://github.com/heynemann/bzz

# Licensed under the MIT license:
# http://www.opensource.org/licenses/MIT-license
# Copyright (c) 2014 Bernardo Heynemann heynemann@gmail.com


from tornado.concurrent import is_future
import tornado.gen as gen
import blinker


class Signal(blinker.NamedSignal):
    @gen.coroutine
    def send(self, *sender, **kwargs):
        if len(sender) == 0:
            sender = None
        elif len(sender) > 1:
            raise TypeError('send() accepts only one positional argument, '
                            '%s given' % len(sender))
        else:
            sender = sender[0]

        if not self.receivers:
            raise gen.Return([])

        results = []
        for receiver in self.receivers_for(sender):
            result = receiver(sender, **kwargs)

            if is_future(result):
                result = yield result
            results.append((receiver, result))

        raise gen.Return(results)


class Namespace(dict):
    """A mapping of signal names to signals."""

    def signal(self, name, doc=None):
        """Return the :class:`NamedSignal` *name*, creating it if required.

        Repeated calls to this function will return the same signal object.

        """
        try:
            return self[name]
        except KeyError:
            return self.setdefault(name, Signal(name, doc))


signal = Namespace().signal

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

authorized_user = signal('bzz.authorized-user')
unauthorized_user = signal('bzz.unauthorized-user')

pre_get_user_details = signal('bzz.pre-get-user-details')
