MongoEngine Support
===================

bzz comes pre-bundled with mongoengine_ support.

.. _mongoengine: http://mongoengine.readthedocs.org

Currently Supported Features
----------------------------

* Document creation(POST);
* Document updating(PUT);
* Document deleting(DELETE);
* Document retrieval(GET with pk);
* Document list(GET without pk);
* Single instance Embedded Document Field (not list field).

Using the MongoEngineRestHandler
--------------------------------

Just create your tornado server as usual, and call the `routes_for` method:

.. automethod:: bzz.mongoengine_handler.MongoEngineRestHandler.routes_for

Let's create a new server to save users:

.. testsetup:: mongoengine_handler_example

   import time
   import tornado.ioloop
   from tornado.httpclient import AsyncHTTPClient
   from tornado.httpserver import HTTPServer
   from mongoengine import *
   io_loop = tornado.ioloop.IOLoop()
   connect("doctest", host="localhost", port=3334)
   http_client = AsyncHTTPClient(io_loop=io_loop)

.. testcode:: mongoengine_handler_example

   import tornado.web
   from mongoengine import *
   import bzz

   server = None

   # just create your own documents
   class User(Document):
      __collection__ = "MongoEngineHandlerUser"
      name = StringField()

   def create_user():
      # let's create a new user by posting it's data
      http_client.fetch(
         'http://localhost:8890/user/',
         method='POST',
         body='name=Bernardo%20Heynemann',
         callback=handle_user_created
      )

   def handle_user_created(response):
      # just making sure we got the actual user
      try:
         assert response.code == 200, response.code
      finally:
         io_loop.stop()

   # bzz includes a helper to return the routes for your models
   # returns a list of routes that match '/user/<user-id>/' and allows for:
   routes = bzz.ModelHive.routes_for('mongoengine', User)

   User.objects.delete()
   application = tornado.web.Application(routes)
   server = HTTPServer(application, io_loop=io_loop)
   server.listen(8890)
   io_loop.add_timeout(1, create_user)
   io_loop.start()
