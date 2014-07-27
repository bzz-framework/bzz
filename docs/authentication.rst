Authentication Support
===================

bzz comes with decorators and classes to support OAuth2 authentication on specific providers that is easy to plug to your tornado server.

Currently Supported Providers
-----------------------------

* GoogleProvider

Configuration
-------------

To enable authentication on your application, just create your tornado server as usual, then configure your application instance calling the `AuthHive.routes_for` method to get a list of the configured handlers and then add it to the app:

.. testsetup:: mongoengine_handler_example

   import time
   import tornado.ioloop
   from tornado.httpclient import AsyncHTTPClient
   io_loop = tornado.ioloop.IOLoop()
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


Note that :py:meth:`~bzz.utils.flatten` method encapsulates the list of handlers.
It is important because the `routes_for` method returns a list of routes, but
`Application` constructor only support routes, so :py:meth:`~bzz.utils.flatten` does the magic.



The AuthHive class
------------------

The bzz framework gives you a `AuthHive` class to allow easy OAuth2 authentication with a few steps.


.. automethod:: bzz.auth.AuthHive.routes_for

.. automethod:: bzz.auth.AuthHive.configure

How to Signin on a Provider
---------------------------

First, users need to authenticate your requests. To do that a `access_token` and `provider`
must be sent via `POST` in `JSON` format to the authenticate route::

    POST /auth/signin/ - {'access_token': '1234567890abcdef', 'provider': 'google'}

This method returns a 401 HTTP status code if the access_token or provider is invalid.

On success it set a cookie named on `AuthHive.configure` `cookie_name` parameter
and returns::

    200 {authenticated: true}

How to Signout
--------------

Sign out means clearing the authentication cookie. To do that, a `POST` to the signout
rout must be sent::

    POST /auth/signout/

If your request is not authenticated, a HTTP 401 is returned.

If authenticated, the response clear the authentication cookie and returns::

    200 {loggedOut: true}

How to check if user is logged in and get users data
----------------------------------------------------

Information of the users authenticated on provider are stored on the cookie via JSON Web Token and are
only accessible by the server. To get this info or check if user is authenticated make a GET on::

    GET /auth/me/

If user is not authenticated, the returned value is a `JSON` in this format::

    200 {authenticated: false}

If authenticated::

    200 {authenticated: true, userData: {}}

The authenticated decorator
---------------------------

.. automethod:: bzz.auth.authenticated

.. testcode:: auth_example_2

    import tornado
    import bzz

    class MyHandler(tornado.web.RequestHandler):

        @bzz.authenticated
        def get(self):
            self.write('I`m authenticated! :)')

How to write your own provider
------------------------------

To write your on provider just create a class extending :py:class:`bzz.AuthProvider` and
implement a `authenticate` method that receives a `access_token`, authenticate on
the provider and returns a user payload like::

    {
        id: "1234567890abcdef",
        email: "...@gmail.com",
        name: "Ricardo L. Dani",
        provider: "google"
    }

