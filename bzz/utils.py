#!/usr/bin/python
# -*- coding: utf-8 -*-

# This file is part of bzz.
# https://github.com/heynemann/bzz

# Licensed under the MIT license:
# http://www.opensource.org/licenses/MIT-license
# Copyright (c) 2014 Bernardo Heynemann heynemann@gmail.com

import jwt
import re
import calendar
import datetime
from six.moves import reduce

try:
    import ujson as json
    UJSON_ENABLED = True
except ImportError:
    UJSON_ENABLED = False
    import json


first_cap_re = re.compile('(.)([A-Z][a-z]+)')
all_cap_re = re.compile('([a-z0-9])([A-Z])')


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


class Jwt(object):
    '''Json Web Tokens encoding/decoding utility class.
    Usage:
    >>> jwt = Jwt('SECRET')
    >>> token = jwt.encode(dict(sub='user@email.com', iss='provider',
                           token='123456789', iat=now(),
                           exp=datetime_expiration))
    >>> jwt.decode(token)
    {'sub':'user@email.com', 'iss':'provider', 'token':'123456789',
     'iat': <datetime>, 'exp': <datetime>}
    >>> jwt.try_to_decode('invalid-token')
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
