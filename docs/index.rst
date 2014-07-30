.. bzz documentation master file, created by
   sphinx-quickstart on Tue Jul  1 11:11:08 2014.
   You can adapt this file completely to your liking, but it should at least
   contain the root `toctree` directive.

bzz - the rest framework for worker bees
========================================

bzz is a rest framework aimed at building restful apis for the tornado web framework.

.. image:: https://travis-ci.org/bzz-framework/bzz.svg?branch=master
    :target: https://travis-ci.org/bzz-framework/bzz

.. image:: https://coveralls.io/repos/bzz-framework/bzz/badge.png
  :target: https://coveralls.io/r/bzz-framework/bzz


Getting Started
---------------

Installing bzz is as simple as::

   $ pip install bzz

After you have it installed, you need to decide what ORM you'll be using for your models. bzz comes bundled with support for the mongoengine library.

We'll assume you'll be using it for the sake of this tutorial. Let's create our model and our tornado server, then:

.. testsetup:: getting_started

   import tornado.ioloop
   import time
   from tornado.httpclient import AsyncHTTPClient
   from tornado.httpserver import HTTPServer
   from mongoengine import *
   io_loop = tornado.ioloop.IOLoop()
   connect("doctest", host="localhost", port=3334)
   http_client = AsyncHTTPClient(io_loop=io_loop)
   from tornado.testing import AsyncTestCase

.. testcode:: getting_started

   import tornado.web
   from mongoengine import *
   import bzz

   # just create your own documents
   class User(Document):
      __collection__ = "GettingStartedUser"
      name = StringField()

   def create_user():
      # let's create a new user by posting it's data
      http_client.fetch(
         'http://localhost:8888/user/',
         method='POST',
         body='name=Bernardo%20Heynemann',
         callback=handle_user_created
      )

   def handle_user_created(response):
      # just making sure we got the actual user
      try:
          assert response.code == 200
      finally:
          io_loop.stop()

   # bzz includes a helper to return the routes for your models
   # returns a list of routes that match '/user/<user-id>/' and allows for:
   # * GET without user-id - Returns list of instances
   # * GET with user-id - Returns instance details
   # * POST with user-id - Creates new instance
   # * PUT with user-id - Updates instance
   # * DELETE with user-id - Removes instance
   routes = [
       bzz.ModelHive.routes_for('mongoengine', User)
       # and your other routes
   ]

   routes = bzz.flatten(routes)  # making sure tornado gets the correct routes

   # Make sure our test is clean
   User.objects.delete()

   application = tornado.web.Application(routes)
   server = HTTPServer(application, io_loop=io_loop)
   server.listen(8888)
   io_loop.add_timeout(1, create_user)
   io_loop.start()

Flattening routes
-----------------

.. automethod:: bzz.utils.flatten

Indices and tables
==================

.. toctree::
   :maxdepth: 2

   modelhive
   mocked
   authentication
   signals

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`

