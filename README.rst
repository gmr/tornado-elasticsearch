tornado_elasticsearch
=====================
Extends the official Elasticsearch Python API adding Tornado AsyncHTTPClient
support.

Installation
------------
tornado_elasticsearch is available on the Python Package Index and can be
installed using pip or easy_install:

.. code-block:: sh

    pip install tornado_elasticsearch

Example Request Handlers
------------------------

.. code-block:: python

    from tornado import gen
    from tornado import web
    from tornado_elasticsearch import AsyncElasticsearch
    import uuid

    class Example(web.RequestHandler):

        @web.asynchronous
        @gen.engine
        def delete(self, *args, **kwargs):
            result = yield self.es.delete(index='test-index', doc_type='tweet',
                                          id=self.get_argument('id'))
            self.finish(result)

        @web.asynchronous
        @gen.engine
        def get(self, *args, **kwargs):
            if self.get_argument('id', None):
                result = yield self.es.get(index='test-index', doc_type='tweet',
                                           id=self.get_argument('id'))
            else:
                result = yield self.es.search(index='test-index',
                                              body={'query': {'match_all': {}}})
            self.finish(result)

        @web.asynchronous
        @gen.engine
        def post(self, *args, **kwargs):
            doc = {
                'author': self.get_current_user() or 'Unknown',
                'text': self.get_argument('text'),
                'timestamp': datetime.datetime.now()
            }
            result = yield self.es.index(index='test-index',
                                         doc_type='tweet',
                                         body=doc,
                                         id=str(uuid.uuid4()))
            self.finish(result)


    class Info(web.RequestHandler):

        @web.asynchronous
        @gen.engine
        def get(self, *args, **kwargs):
            es = AsyncElasticsearch()
            info = yield es.info()
            self.finish(info)
