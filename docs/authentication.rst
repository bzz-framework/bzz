Authentication Support
===================

bzz comes with decorators and classes to support OAuth2 authentication on specific providers that is easy to plug to your tornado server.

It's worth noting that `AuthHive` is just an extension to the regular tornado routes. That said, it needs to add some dependencies to the application being run.

To enable authentication, call the `AuthHive.configure` method passing your tornado app instance. To get all the routes you need to add to your app, just call `AuthHive.routes_for`:

.. testsetup:: auth_example_1

   import time
   import tornado.ioloop
   from tornado.httpclient import AsyncHTTPClient
   io_loop = tornado.ioloop.IOLoop()
   http_client = AsyncHTTPClient(io_loop=io_loop)

.. testcode:: auth_example_1

    from tornado.web import Application
    from tornado.ioloop import IOLoop
    import bzz
    import bzz.providers.google as google

    providers = [
        google.GoogleProvider,
        # MyCustomProvider
    ]

    app = Application(bzz.flatten([
        # ('/', MyHandler),
        bzz.AuthHive.routes_for(providers)
    ]))

    bzz.AuthHive.configure(app, secret_key='app-secret-key')
    app.listen(9999)

Note that :py:meth:`~bzz.utils.flatten` method encapsulates the list of handlers.
It is important because the `routes_for` method returns a list of routes, but
`Application` constructor only support routes, so :py:meth:`~bzz.utils.flatten` does the magic.


The :mod:`AuthHive` class
-------------------------

.. automodule:: bzz.auth
   :members:

Currently Supported Providers
-----------------------------

.. autoclass:: bzz.providers.google.GoogleProvider
   :members:

Signing-In
----------

In order to sign-in, the authentication route must be called. Both `access_token` and `provider` arguments
must be specified. This request must be sent using a `POST` in `JSON` format::

    POST /auth/signin/ - {'access_token': '1234567890abcdef', 'provider': 'google'}

This method returns a 401 HTTP status code if the access_token or provider is invalid.

On success it set a cookie with the name that was specified when you called `AuthHive.configure` (or defaults to AUTH_TOKEN)
and returns::

    200 {authenticated: true}

Signing-Out
-----------

Signing-out means clearing the authentication cookie. To do that, a `POST` to the sign-out route must be sent::

    POST /auth/signout/

If your request is not authenticated, a HTTP 401 is returned.

If authenticated, the response clear the authentication cookie and returns::

    200 {loggedOut: true}

Getting User Data
-----------------

Retrieving information about the authenticated user is as simple as doing a get request to the `/me` route::

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

Authoring a custom provider
---------------------------

Creating a custom provider is as simple as extending :py:class:`bzz.AuthProvider`. You must override the `authenticate` method.

It receives an `access_token` as argument and should return a dict with whatever should be stored in the JSON Web Token::

    {
        id: "1234567890abcdef",
        email: "...@gmail.com",
        name: "Ricardo L. Dani",
        provider: "google"
    }
