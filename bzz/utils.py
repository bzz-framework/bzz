#!/usr/bin/python
# -*- coding: utf-8 -*-

# This file is part of bzz.
# https://github.com/heynemann/bzz

# Licensed under the MIT license:
# http://www.opensource.org/licenses/MIT-license
# Copyright (c) 2014 Bernardo Heynemann heynemann@gmail.com

import inspect
import re
import calendar
import datetime
from six.moves import reduce

import jwt

import bzz.core as core

try:
    import ujson as json
    UJSON_ENABLED = True
except ImportError:
    UJSON_ENABLED = False
    import json


first_cap_re = re.compile('(.)([A-Z][a-z]+)')
all_cap_re = re.compile('([a-z0-9])([A-Z])')


def flatten(routes):
    '''
    Gets a list of routes that includes hive-generated routes (model, auth or mock), as well as
    user created routes and flatten the list to the format tornado expects.

    Can be used in bzz namespace::

        import bzz
        bzz.flatten(routes)

    :param routes: list of routes created by bzz hives or by the user
    :returns: List of routes that a tornado app expects.
    '''
    result = []
    for route_list in routes:
        if isinstance(route_list, core.RouteList):
            for route in route_list:
                result.append(route)
        else:
            result.append(route_list)

    return tuple(result)


def convert(name):
    s1 = first_cap_re.sub(r'\1_\2', name)
    return all_cap_re.sub(r'\1_\2', s1).lower()


def get_class(klass):
    module_name, class_name = klass.rsplit('.', 1)

    module = __import__(module_name)

    if '.' in module_name:
        module = reduce(getattr, module_name.split('.')[1:], module)

    return getattr(module, class_name)


def default(obj):
    """Default JSON serializer."""

    if isinstance(obj, datetime.datetime):
        if obj.utcoffset() is not None:
            obj = obj - obj.utcoffset()
    millis = int(
        calendar.timegm(obj.timetuple()) * 1000 +
        obj.microsecond / 1000
    )
    return millis


def loads(data):
    return json.loads(data)


def dumps(instance):
    if UJSON_ENABLED:
        return json.dumps(instance)

    return json.dumps(instance, default=default)

def get_prefix(prefix):
    if not prefix:
        return ''

    return prefix.strip('/')

def add_prefix(prefix, route):
    prefix = get_prefix(prefix)
    route = route.lstrip('/')

    if not prefix:
        return "/%s" % route

    return "/%s/%s" % (prefix, route)

def ensure_instance(provider):
    return provider() if inspect.isclass(provider) else provider


class Jwt(object):
    '''Json Web Tokens encoding/decoding utility class.
    Usage:
    >>> now = datetime.now()
    >>> tokenizer = Jwt('SECRET')
    >>> payload = dict(sub='user@email.com', iss='provider', token='123456789', iat=now, exp=120)
    >>> token = tokenizer.encode(payload)
    >>> tokenizer.decode(token)
    {'sub':'user@email.com', 'iss':'provider', 'token':'123456789',
    'iat': <datetime>, 'exp': <datetime>}
    >>> tokenizer.try_to_decode('invalid-token')
    (False, None)
    '''

    def __init__(self, secret, algo='HS512'):
        self.secret = secret
        self.algo = algo

    def encode(self, payload):
        '''Encodes the payload returning a Json Web Token
        '''
        return jwt.encode(payload, self.secret, self.algo)

    def decode(self, encrypted_payload):
        '''Decodes the Json Web Token returning the payload
        '''
        return jwt.decode(encrypted_payload, self.secret)

    def try_to_decode(self, encrypted_payload):
        '''Tries to decrypt the given encrypted and returns a tuple with
        a decrypted boolean flag and the decrypted object if success is True
        '''
        try:
            return True, self.decode(encrypted_payload)
        except (jwt.ExpiredSignature, jwt.DecodeError, AttributeError):
            return False, None
