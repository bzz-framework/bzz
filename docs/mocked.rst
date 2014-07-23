Mocked Responses
================

Most of the time creating a new API is a time-consuming task. Other teams (or people) might be depending on your API to create clients or the application that will consume your data.

Usually you'd give them the contract of your API (or worse, they'd have to wait until your API is ready). bzz comes packed with a mocked responses API that allows you to easily craft a mock API that can be used by clients/partners/teams/aliens.

This way you can keep focus in the development of your API, while at the same time allowing people to work with what will eventually be replaced by the real API.

Using Mocked Responses
----------------------

.. autoclass:: bzz.mocked_routes.MockedRoutes
.. automethod:: bzz.mocked_routes.MockedRoutes.handlers

Let's create a new server with a few mocked routes.
MockedRoutes expects a list of tuples with

[('METHOD', 'URL or regex', dict(body="string or function", status="200", cookies={'cookie': 'yum'}))]

.. testsetup:: mocked_routes_example

   import tornado.ioloop
   from tornado.httpclient import AsyncHTTPClient
   from tornado.httpserver import HTTPServer
   from mongoengine import *
   import six
   io_loop = tornado.ioloop.IOLoop()
   connect("doctest", host="localhost", port=3334)
   http_client = AsyncHTTPClient(io_loop=io_loop)

.. testcode:: mocked_routes_example

   import tornado.web
   from bzz.mocked_routes import MockedRoutes

   server = None

   #first create the routes
   mocked_routes = MockedRoutes([
      ('GET', '/much/api', dict(body='much api')),
      ('POST', '/much/api'),
      ('*', '/much/match', dict(body='such match')),
      ('*', r'/such/.*', dict(body='such match')),
      ('GET', '/much/error', dict(body='WOW', status=404)),
      ('GET', '/much/authentication', dict(body='WOW', cookies={'super': 'cow'})),
      ('GET', '/such/function', dict(body=lambda x: x.method)),
   ])

   handlers = mocked_routes.handlers()

   def handle_api_response(response):
      # making sure we get the right route
      try:
         assert response.code == 200, response.code
         assert response.body == six.b('much api'), response.body
      finally:
         server.stop()
         io_loop.stop()

   def get_route():
      # let's test one of them
      http_client.fetch(
         'http://localhost:8891/much/api',
         method='GET',
         callback=handle_api_response
      )

   application = tornado.web.Application(handlers)
   server = HTTPServer(application, io_loop=io_loop)
   server.listen(8891)
   io_loop.add_timeout(1, get_route)
   io_loop.start()
