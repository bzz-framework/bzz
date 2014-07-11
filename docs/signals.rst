Using signals
=============

bzz uses the blinker library for signals. Using them is very simple:

.. testsetup:: signal_post_create1

   import time
   import tornado.ioloop
   from tornado.httpserver import HTTPServer
   from tornado.httpclient import AsyncHTTPClient
   from mongoengine import *
   from bzz.signals import post_create_instance
   io_loop = tornado.ioloop.IOLoop()
   connect("doctest", host="localhost", port=3334)
   http_client = AsyncHTTPClient(io_loop=io_loop)
   post_create_instance.receivers = {}

.. testcode:: signal_post_create1

   import tornado.web
   from mongoengine import *
   from bzz.mongoengine_handler import MongoEngineRestHandler
   from bzz.signals import post_create_instance

   server = None

   # just create your own documents
   class User(Document):
      __collection__ = "GettingStartedUser"
      name = StringField()

   def create_user():
      # let's create a new user by posting it's data
      # we ignore the callback and response from http client
      # because we only need the signal in this example.
      http_client.fetch(
         'http://localhost:8889/user/',
         method='POST',
         body='name=Bernardo%20Heynemann'
      )

   def handle_post_instance_created(sender, instance, handler):
      # just making sure we got the actual user
      try:
          assert instance.name == 'Bernardo Heynemann'
      finally:
          server.stop()
          io_loop.stop()

   # just connect the signal to the event handler
   post_create_instance.connect(handle_post_instance_created)

   # get routes for our model
   routes = MongoEngineRestHandler.routes_for('mongoengine', User)

   # Make sure our test is clean
   User.objects.delete()

   # create the server and run it
   application = tornado.web.Application(routes)
   server = HTTPServer(application, io_loop=io_loop)
   server.listen(8889)
   io_loop.add_timeout(1, create_user)
   io_loop.start()

Available Signals
=================

post_create_instance
--------------------

This signal is sent after a new instance is created (POST).

Arguments:

* sender - The model that assigned the signal
* instance - The instance that was created.
* handler - The tornado handler that created the new instance of your model.

Example handler::

    def handle_post_instance_created(handler, instance):
        if handler.application.config.SEND_TO_URL:
            # sends something somewhere
            pass

        # do something else with instance


post_update_instance
--------------------

This signal is sent after an instance is updated (PUT).

Arguments:

* sender - The model that assigned the signal
* instance - The instance that was updated.
* updated_fields - The fields that were updated in the instance with the old and new values.
* handler - The tornado handler that updated the instance of your model.

The `updated_fields` format is like::

    {
        'field': {
            'from': 1,
            'to': 2
        },
        'field2': {
            'from': 'a',
            'to': 'b'
        }
    }

Example handler::

    def handle_post_instance_created(handler, instance, updated_fields):
        # do something else with instance and/or updated_fields

post_delete_instance
--------------------

This signal is sent after a new instance is deleted (DELETE).

Arguments:

* sender - The model that assigned the signal
* instance - The instance that was created.
* handler - The tornado handler that created the new instance of your model.

Example handler::

    def handle_post_instance_created(handler, instance):
        # do something else with instance
        # just remember the instance has already been deleted!
