Authentication Support
===================

bzz comes with decorators and classes to support oAuth2 authentication on specific providers that is easy to plug in your tornado server.

Currently Supported Providers
-----------------------------

* GoogleProvider

Basic usage
-----------

To enable authentication on your application, just create your tornado server as usual, and call the `AuthHive.routes_for` method to get a list of the configured handlers, and then add it to the app:

.. testsetup:: mongoengine_handler_example

   import time
   import tornado.ioloop
   from tornado.httpclient import AsyncHTTPClient
   from tornado.httpserver import HTTPServer
   from mongoengine import *
   io_loop = tornado.ioloop.IOLoop()
   connect("doctest", host="localhost", port=3334)
   http_client = AsyncHTTPClient(io_loop=io_loop)

.. testcode:: auth_example_1

    from tornado.web import Application
    from tornado.ioloop import IOLoop
    import bzz

    providers = [
        bzz.GoogleProvider,
        # MyCustomProvider
    ]

    app = Application(bzz.flatten([
        # ('/', MyHandler),
        bzz.AuthHive.routes_for(providers)
    ]))
    bzz.AuthHive.configure(app, secret_key='app-secret-key')
    app.listen(8888)
    IOLoop.instance().start()

The AuthHive class
------------------

The bzz framework gives you a `AuthHive` class to allow easy oAuth2 authentication with a few steps.


.. automethod:: bzz.auth.AuthHive.routes_for

.. automethod:: bzz.auth.AuthHive.configure

The authenticated decorator
---------------------------

.. automethod:: bzz.auth.authenticated

For example:

.. testcode:: auth_example_2

    import tornado
    import bzz

    class MyHandler(tornado.web.RequestHandler):

        @bzz.authenticated
        def get(self):
            self.write('I`m autheticated! :)')
