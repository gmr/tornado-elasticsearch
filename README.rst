tornado_elasticsearch
=====================
Extends the official Elasticsearch Python API adding Tornado AsyncHTTPClient
support.

|Version| |LICENSE|

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

        def initialize(self):
            self.es = AsyncElasticsearch()

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
                result = yield self.es.search(index='test-index')
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


Version History
---------------
- 0.5.0:
  - Bugfixes:
    - HTTP Auth
    - Add timeout support
    - Allow scroll to use post, since scroll_id can be too long
    - Fix yield issue
  - Add max_clients to AsyncElasticSearch constructor
  - Added get_alias
  - Added get_mapping
  - Add cluster health
- 0.4.0: Bugfix: Python3 decoding issues
- 0.3.0: Bugfix: Add body to log_request_fail call (#1)
- 0.2.0: Bugfix: force method to POST if GET and body passed
- 0.1.0: Initial version

.. |Version| image:: https://img.shields.io/pypi/v/tornado_elasticsearch.svg?
   :target: http://badge.fury.io/py/tornado_elasticsearch

.. |License| image:: https://img.shields.io/pypi/l/tornado_elasticsearch.svg?
   :target: https://tornado_elasticsearch.readthedocs.org
