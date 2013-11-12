tornado_elasticsearch
=====================
Extends the official Elasticsearch Python API adding Tornado AsyncHTTPClient
support.

|PyPI version| |Downloads|

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
- 0.2.0: Bugfix, force method to POST if GET and body passed
- 0.1.0: Initial version

LICENSE
-------
Copyright (c) 2013 Gavin M. Roy
All rights reserved.

Redistribution and use in source and binary forms, with or without modification,
are permitted provided that the following conditions are met:

 * Redistributions of source code must retain the above copyright notice, this
   list of conditions and the following disclaimer.
 * Redistributions in binary form must reproduce the above copyright notice,
   this list of conditions and the following disclaimer in the documentation
   and/or other materials provided with the distribution.
 * Neither the name of the mrcreosote nor the names of its
   contributors may be used to endorse or promote products derived from this
   software without specific prior written permission.

THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS" AND
ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED
WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE DISCLAIMED.
IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT,
INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING,
BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE,
DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF
LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE
OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF
ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.

.. |PyPI version| image:: https://badge.fury.io/py/tornado_elasticsearch.png
   :target: http://badge.fury.io/py/tornado_elasticsearch
.. |Downloads| image:: https://pypip.in/d/tornado_elasticsearch/badge.png
   :target: https://crate.io/packages/tornado_elasticsearch
