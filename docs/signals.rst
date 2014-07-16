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

pre_get_instance
----------------

This signal is sent before an instance is retrieved (GET with a PK).

If a list would be returned the `pre_get_list` signal should be used instead.

**Please note that since this signal is sent before getting the instance, the instance is not available yet.**

Arguments:

* sender - The model that assigned the signal
* arguments - URL arguments that will be used to get the instance.
* handler - The tornado handler that will be used to get the instance of your model.

Example handler::

    def handle_pre_get_instance(sender, arguments, handler):
        if handler.application.config.SEND_TO_URL:
            # sends something somewhere
            pass

post_get_instance
-----------------

This signal is sent after an instance is retrieved (GET with a PK).

If a list would be returned the `post_get_list` signal should be used instead.

Arguments:

* sender - The model that assigned the signal
* instance - The instance of your model that was retrieved.
* handler - The tornado handler that was used to get the instance of your model.

Example handler::

    def handle_post_get_instance(sender, instance, handler):
        # do something with instance

pre_get_list
------------

This signal is sent before a list of instances is retrieved (GET without a PK).

If an instance would be returned the `pre_get_instance` signal should be used instead.

**Please note that since this signal is sent before getting the list, the list is not available yet.**

Arguments:

* sender - The model that assigned the signal
* arguments - URL arguments that will be used to get the instance.
* handler - The tornado handler that will be used to get the instance of your model.

Example handler::

    def handle_pre_get_list(sender, arguments, handler):
        if handler.application.config.SEND_TO_URL:
            # sends something somewhere
            pass

post_get_list
-------------

This signal is sent after a list of instances is retrieved (GET without a PK).

If an instane would be returned the `post_get_instance` signal should be used instead.

Arguments:

* sender - The model that assigned the signal
* items - The list of instances of your model that was retrieved.
* handler - The tornado handler that was used to get the instance of your model.

Example handler::

    def handle_post_get_list(sender, items, handler):
        # do something with the list of items

pre_create_instance
--------------------

This signal is sent before a new instance is created (POST).

**Please note that since this signal is sent before creating the instance, the instance is not available yet.**

Arguments:

* sender - The model that assigned the signal
* arguments - URL arguments that will be used to create the instance.
* handler - The tornado handler that will be used to create the new instance of your model.

Example handler::

    def handle_before_instance_created(sender, arguments, handler):
        if handler.application.config.SEND_TO_URL:
            # sends something somewhere
            pass

post_create_instance
--------------------

This signal is sent after a new instance is created (POST).

Arguments:

* sender - The model that assigned the signal
* instance - The instance that was created.
* handler - The tornado handler that created the new instance of your model.

Example handler::

    def handle_post_instance_created(sender, instance, handler):
        if handler.application.config.SEND_TO_URL:
            # sends something somewhere
            pass

        # do something else with instance

pre_update_instance
-------------------

This signal is sent before an instance is updated (PUT).

**Please note that since this signal is sent before updating the instance, the instance is not available yet.**

Arguments:

* sender - The model that assigned the signal
* arguments - URL arguments that will be used to update the instance.
* handler - The tornado handler that will be used to update the instance of your model.

Example handler::

    def handle_before_instance_updated(sender, arguments, handler):
         # if something is wrong, raise error

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

    def handle_post_instance_updated(sender, instance, updated_fields, handler):
        # do something else with instance and/or updated_fields

pre_delete_instance
-------------------

This signal is sent before an instance is deleted (DELETE).

**Please note that since this signal is sent before deleting the instance, the instance is not available yet.**

Arguments:

* sender - The model that assigned the signal
* arguments - URL arguments that will be used to delete the instance.
* handler - The tornado handler that will be used to delete the instance of your model.

Example handler::

    def handle_before_instance_deleted(sender, arguments, handler):
        # do something with arguments

post_delete_instance
--------------------

This signal is sent after a new instance is deleted (DELETE).

Arguments:

* sender - The model that assigned the signal
* instance - The instance that was created.
* handler - The tornado handler that created the new instance of your model.

**WARNING: The instance returned on this signal has already been removed. How each ORM handles this is peculiar to the given ORM.**

Example handler::

    def handle_post_instance_deleted(sender, instance, handler):
        # do something else with instance
        # just remember the instance has already been deleted!
