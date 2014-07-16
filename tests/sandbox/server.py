#!/usr/bin/python
# -*- coding: utf-8 -*-

# This file is part of bzz.
# https://github.com/heynemann/bzz

# Licensed under the MIT license:
# http://www.opensource.org/licenses/MIT-license
# Copyright (c) 2014 Bernardo Heynemann heynemann@gmail.com

import tornado.web
import tornado.ioloop
from tornado.httpserver import HTTPServer
import mongoengine as me

import bzz


class User(me.Document):
    __collection__ = "GettingStartedUser"
    name = me.StringField()


def main():
    me.connect("doctest", host="localhost", port=3334)
    routes = bzz.flatten([
        bzz.ModelRestHandler.routes_for('mongoengine', User),
        bzz.DocsHandler.routes()
    ])

    application = tornado.web.Application(routes, debug=True)
    server = HTTPServer(application)
    server.listen(8888)
    tornado.ioloop.IOLoop.instance().start()


if __name__ == "__main__":
    main()
