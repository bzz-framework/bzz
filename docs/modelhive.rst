Model Hive
==========

bzz kickstarts your development process by handling CRUD operations in your API for your registered models.

Currently bzz supports mongoengine_, but support for other ORMs will be done soon.
If you would like to see a different ORM supported, please create an issue for it.

.. _mongoengine: http://mongoengine.readthedocs.org

What does Model Hive support
----------------------------

* [POST] Create new instances;
* [PUT] Update existing instances;
* [DELETE] Delete existing instances;
* [GET] Retrieve existing instances with the id for the instance;
* [GET] List existing instances (and filter them);

All those operations also work in inner properties. What this means is that if your model has a many-to-one relationship to another model, you get free restful routes to update both.

.. testsetup:: model_hive_example_1

   import time
   import tornado.ioloop
   from tornado.httpclient import AsyncHTTPClient
   from tornado.httpserver import HTTPServer
   from mongoengine import *
   io_loop = tornado.ioloop.IOLoop()
   connect("doctest", host="localhost", port=3334)
   http_client = AsyncHTTPClient(io_loop=io_loop)

:mod:`ModelHive` class
----------------------

.. autoclass:: bzz.model.ModelHive
   :members:
   :undoc-members:

Errors
------

In the event of a POST, PUT or DELETE, if the model being changed fails validation, a status code of 400 (Bad Request) is returned.

If the model being changed violates an uniqueness constraint, bzz will return a status code of 409 (Conflict), instead.

Supported Providers
-------------------

:mod:`MongoEngine` provider

Provider that supports the rest operations for the MongoEngine ORM.

Allows users to override `get_instance_queryset` and `get_list_queryset` in their models to change how queries should be performed for this provider. Both methods should return a mongoengine queryset and receive as arguments:

* `get_instance_queryset` - model type, original queryset, instance_id and the tornado request handler processing the request
* `get_list_queryset` - original queryset and the tornado request handler processing the request

.. autoclass:: bzz.providers.mongoengine_provider.MongoEngineProvider
   :members:
   :undoc-members:
