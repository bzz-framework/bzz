MockedRoutes
============

bzz comes with an API mock.
For mocking responses in url's before implementing

Using the MockedRoutes
--------------------------------

.. autoclass:: bzz.mocked_routes.MockedRoutes
.. automethod:: bzz.mocked_routes.MockedRoutes.handlers

Let's create a new server with a few mocked routes:

.. testsetup:: mocked_routes_example

   import tornado.ioloop
   from tornado.httpclient import AsyncHTTPClient
   from tornado.httpserver import HTTPServer
   from mongoengine import *
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
   ])

   handlers = mocked_routes.handlers()

   def handle_api_response(response):
      # making sure we get the right route
      try:
         assert response.code == 200, response.code
         assert response.body == 'much api', response.body
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
