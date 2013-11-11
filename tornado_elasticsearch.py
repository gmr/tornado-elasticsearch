"""tornado_elasticsearch extends the official elasticsearch library adding
asynchronous support for the Tornado stack.

See http://elasticsearch-py.readthedocs.org/en/latest/ for information
on how to use the API beyond the introduction for how to use with Tornado::

    from tornado import gen
    from tornado import web
    from tornado_elasticsearch import AsyncElasticsearch


    class Info(web.RequestHandler):

        @web.asynchronous
        @gen.engine
        def get(self, *args, **kwargs):
            es = AsyncElasticsearch()
            info = yield es.info()
            self.finish(info)

"""
from elasticsearch.connection.base import Connection
from elasticsearch.exceptions import ConnectionError, \
    HTTP_EXCEPTIONS, \
    NotFoundError
from elasticsearch.client import Elasticsearch
from elasticsearch.transport import Transport, TransportError
from elasticsearch.client.utils import query_params, _make_path

from tornado import concurrent
from tornado import gen
from tornado import httpclient
import logging
import time
try:
    from urllib import urlencode
except ImportError:
    from urllib.parse import urlencode
from tornado import version

__version__ = '0.1.3'

LOGGER = logging.getLogger(__name__)


class AsyncHttpConnection(Connection):
    """Add Tornado Asynchronous support to ElasticSearch.

    :param str host: The host for the connection
    :param int port: The port for the connection
    :param str|tuple http_auth: optional http auth information as either a
      colon delimited string `("username:password")` or
      tuple `(username, password)`
    :arg use_ssl: use ssl for the connection if `True`

    """
    _auth_user = None
    _auth_password = None
    _user_agent = 'tornado_elasticsearch %s/Tornado %s' % (__version__, version)
    ssl_transport_schema = 'https'

    def __init__(self, host='localhost', port=9200, http_auth=None,
                 use_ssl=False, **kwargs):
        super(AsyncHttpConnection, self).__init__(host=host, port=port,
                                                  **kwargs)
        self._assign_auth_values(http_auth)
        self.base_url = '%s://%s:%s%s' % (self.ssl_transport_schema if use_ssl
                                          else self.transport_schema,
                                          host, port, self.url_prefix)
        self._client = httpclient.AsyncHTTPClient()
        self._headers = {'Content-Type': 'application/json; charset=UTF-8'}
        self._start_time = None

    @concurrent.return_future
    def perform_request(self, method, url, params=None, body=None,
                        timeout=None, ignore=(), callback=None):
        request_uri = self._request_uri(url, params)
        LOGGER.debug('%s, %r, %r', url, body, params)
        kwargs = self._request_kwargs(method, body, timeout)
        self._start_time = time.time()

        def on_response(response):
            duration = time.time() - self._start_time
            LOGGER.info('Response from %s: %s', url, response.code)
            if not (200 <= response.code < 300) and response.code not in ignore:
                LOGGER.debug('Error: %r', response.body)
                self.log_request_fail(method, url, duration, response.code)
                error = HTTP_EXCEPTIONS.get(response.code, TransportError)
                raise error(response.code, response.body)
            self.log_request_success(method, request_uri, url, body,
                                     response.code, response.body, duration)
            callback((response.code, response.body))

        LOGGER.debug('Fetching [%s] %s', kwargs['method'], request_uri)
        LOGGER.debug('kwargs: %r', kwargs)
        self._client.fetch(httpclient.HTTPRequest(request_uri, **kwargs),
                           callback=on_response)

    def _assign_auth_values(self, http_auth):
        """Take the http_auth value and split it into the attributes that
        carry the http auth username and password

        :param str|tuple http_auth: The http auth value

        """
        if not http_auth:
            pass
        elif isinstance(http_auth, (tuple, list)):
            self._auth_user, self._auth_password = http_auth
        elif isinstance(http_auth, str):
            self._auth_user, self._auth_password = http_auth.split('.')
        else:
            raise ValueError('HTTP Auth Credentials should be str or '
                             'tuple, not %s' % type(http_auth))

    def _request_kwargs(self, method, body, timeout):
        kwargs = {'method': method, 'user_agent': self._user_agent}
        if self._auth_user and self._auth_password:
            kwargs['auth_username'] = self._auth_user
            kwargs['auth_password'] = self._auth_password
        if body:
            kwargs['body'] = body
        if timeout:
            kwargs['request_timeout'] = timeout
        return kwargs

    def _request_uri(self, url, params):
        uri = self.url_prefix + url
        if params:
            uri = '%s?%s' % (uri, urlencode(params or {}))
        return '%s%s' % (self.base_url, uri)


class AsyncTransport(Transport):

    @gen.coroutine
    def perform_request(self, method, url, params=None, body=None):
        """Perform the actual request. Retrieve a connection from the connection
        pool, pass all the information to it's perform_request method and
        return the data.

        If an exception was raised, mark the connection as failed and retry (up
        to `max_retries` times).

        If the operation was successful and the connection used was previously
        marked as dead, mark it as live, resetting it's failure count.

        :param method: HTTP method to use
        :param url: absolute url (without host) to target
        :param params: dictionary of query parameters, will be handed over to
            the underlying :class:`~torando_elasticsearch.AsyncHTTPConnection`
            class for serialization
        :param body: body of the request, will be serialized using serializer
            and passed to the connection

        """
        if body is not None:
            body = self.serializer.dumps(body)

        ignore = ()
        if params and 'ignore' in params:
            ignore = params.pop('ignore')
            if isinstance(ignore, int):
                ignore = (ignore, )

        for attempt in range(self.max_retries + 1):
            connection = self.get_connection()
            try:
                (status,
                 raw_data) = yield connection.perform_request(method, url,
                                                              params, body,
                                                              ignore=ignore)
            except ConnectionError:
                self.mark_dead(connection)

                # raise exception on last retry
                if attempt == self.max_retries:
                    raise
            else:
                # connection didn't fail, confirm it's live status
                self.connection_pool.mark_live(connection)

                raise gen.Return((status,
                                  self.serializer.loads(raw_data)
                                  if raw_data else None))


class AsyncElasticsearch(Elasticsearch):
    """Extends the official elasticsearch.Elasticsearch object to make the
    client invoked methods coroutines.

    """
    def __init__(self, hosts=None, **kwargs):
        """Create a new AsyncElasticsearch instance

        """
        kwargs['connection_class'] = AsyncHttpConnection
        kwargs['transport_class'] = AsyncTransport
        super(AsyncElasticsearch, self).__init__(hosts, **kwargs)

    @gen.coroutine
    @query_params()
    def ping(self, params=None):
        """ Returns True if the cluster is up, False otherwise. """
        try:
            self.transport.perform_request('HEAD', '/', params=params)
        except TransportError:
            raise gen.Return(False)
        raise gen.Return(True)

    @gen.coroutine
    @query_params()
    def info(self, params=None):
        """Get the basic info from the current cluster.

        :rtype: dict

        """
        _, data = yield self.transport.perform_request('GET', '/',
                                                       params=params)
        raise gen.Return(data)

    @gen.coroutine
    @query_params('consistency', 'id', 'parent', 'percolate', 'refresh',
                  'replication', 'routing', 'timeout', 'timestamp', 'ttl',
                  'version', 'version_type')
    def create(self, index, doc_type, body, id=None, params=None):
        """
        Adds a typed JSON document in a specific index, making it searchable.
        Behind the scenes this method calls index(..., op_type='create')
        `<http://elasticsearch.org/guide/reference/api/index_/>`_

        :arg index: The name of the index
        :arg doc_type: The type of the document
        :arg id: Document ID
        :arg body: The document
        :arg consistency: Explicit write consistency setting for the operation
        :arg id: Specific document ID (when the POST method is used)
        :arg parent: ID of the parent document
        :arg percolate: Percolator queries to execute while indexing the doc
        :arg refresh: Refresh the index after performing the operation
        :arg replication: Specific replication type (default: sync)
        :arg routing: Specific routing value
        :arg timeout: Explicit operation timeout
        :arg timestamp: Explicit timestamp for the document
        :arg ttl: Expiration time for the document
        :arg version: Explicit version number for concurrency control
        :arg version_type: Specific version type
        """
        result = self.index(index, doc_type, body, id=id, params=params,
                            op_type='create')
        raise gen.Return(result)

    @gen.coroutine
    @query_params('consistency', 'op_type', 'parent', 'percolate', 'refresh',
                  'replication', 'routing', 'timeout', 'timestamp', 'ttl',
                  'version', 'version_type')
    def index(self, index, doc_type, body, id=None, params=None):
        """
        Adds or updates a typed JSON document in a specific index, making it
        searchable. `<http://elasticsearch.org/guide/reference/api/index_/>`_

        :arg index: The name of the index
        :arg doc_type: The type of the document
        :arg body: The document
        :arg id: Document ID
        :arg consistency: Explicit write consistency setting for the operation
        :arg op_type: Explicit operation type (default: index)
        :arg parent: ID of the parent document
        :arg percolate: Percolator queries to execute while indexing the doc
        :arg refresh: Refresh the index after performing the operation
        :arg replication: Specific replication type (default: sync)
        :arg routing: Specific routing value
        :arg timeout: Explicit operation timeout
        :arg timestamp: Explicit timestamp for the document
        :arg ttl: Expiration time for the document
        :arg version: Explicit version number for concurrency control
        :arg version_type: Specific version type

        """
        _, data = yield self.transport.perform_request('PUT' if id else 'POST',
                                                       _make_path(index,
                                                                  doc_type, id),
                                                       params=params, body=body)
        raise gen.Return(data)

    @gen.coroutine
    @query_params('parent', 'preference', 'realtime', 'refresh', 'routing')
    def exists(self, index, id, doc_type='_all', params=None):
        """
        Returns a boolean indicating whether or not given document exists in
        Elasticsearch. `<http://elasticsearch.org/guide/reference/api/get/>`_

        :arg index: The name of the index
        :arg id: The document ID
        :arg doc_type: The type of the document (uses `_all` by default to
            fetch the first document matching the ID across all types)
        :arg parent: The ID of the parent document
        :arg preference: Specify the node or shard the operation should be
            performed on (default: random)
        :arg realtime: Specify whether to perform the operation in realtime or
            search mode
        :arg refresh: Refresh the shard containing the document before
            performing the operation
        :arg routing: Specific routing value
        """
        try:
            self.transport.perform_request('HEAD',
                                           _make_path(index, doc_type, id),
                                           params=params)
        except NotFoundError:
            return gen.Return(False)
        raise gen.Return(True)

    @gen.coroutine
    @query_params('_source', '_source_exclude', '_source_include', 'fields',
                  'parent', 'preference', 'realtime', 'refresh', 'routing')
    def get(self, index, id, doc_type='_all', params=None):
        """
        Get a typed JSON document from the index based on its id.
        `<http://elasticsearch.org/guide/reference/api/get/>`_

        :arg index: The name of the index
        :arg id: The document ID
        :arg doc_type: The type of the document (uses `_all` by default to
            fetch the first document matching the ID across all types)
        :arg _source: True or false to return the _source field or not, or a
            list of fields to return
        :arg _source_exclude: A list of fields to exclude from the returned
            _source field
        :arg _source_include: A list of fields to extract and return from the
            _source field
        :arg fields: A comma-separated list of fields to return in the response
        :arg parent: The ID of the parent document
        :arg preference: Specify the node or shard the operation should be
            performed on (default: random)
        :arg realtime: Specify whether to perform the operation in realtime or
            search mode
        :arg refresh: Refresh the shard containing the document before
            performing the operation
        :arg routing: Specific routing value
        """
        _, data = yield self.transport.perform_request('GET',
                                                       _make_path(index,
                                                                  doc_type, id),
                                                       params=params)
        raise gen.Return(data)

    @gen.coroutine
    @query_params('_source_exclude', '_source_include', 'parent', 'preference',
                  'realtime', 'refresh', 'routing')
    def get_source(self, index, id, doc_type='_all', params=None):
        """
        Get the source of a document by it's index, type and id.
        `<http://elasticsearch.org/guide/reference/api/get/>`_

        :arg index: The name of the index
        :arg doc_type: The type of the document (uses `_all` by default to
            fetch the first document matching the ID across all types)
        :arg id: The document ID
        :arg exclude: A list of fields to exclude from the returned
            _source field
        :arg include: A list of fields to extract and return from the
            _source field
        :arg parent: The ID of the parent document
        :arg preference: Specify the node or shard the operation should be
            performed on (default: random)
        :arg realtime: Specify whether to perform the operation in realtime or
            search mode
        :arg refresh: Refresh the shard containing the document before
            performing the operation
        :arg routing: Specific routing value
        """
        _, data = yield self.transport.perform_request('GET',
                                                       _make_path(index,
                                                                  doc_type, id,
                                                                  '_source'),
                                                       params=params)
        raise gen.Return(data)

    @gen.coroutine
    @query_params('_source', '_source_exclude', '_source_include', 'fields',
                  'parent', 'preference', 'realtime', 'refresh', 'routing')
    def mget(self, body, index=None, doc_type=None, params=None):
        """
        Get multiple documents based on an index, type (optional) and ids.
        `<http://elasticsearch.org/guide/reference/api/multi-get/>`_

        :arg body: Document identifiers; can be either `docs` (containing full
            document information) or `ids` (when index and type is provided
                in the URL.
        :arg index: The name of the index
        :arg doc_type: The type of the document
        :arg _source: True or false to return the _source field or not, or a
            list of fields to return
        :arg _source_exclude: A list of fields to exclude from the returned
            _source field
        :arg _source_include: A list of fields to extract and return from the
            _source field
        :arg fields: A comma-separated list of fields to return in the response
        :arg parent: The ID of the parent document
        :arg preference: Specify the node or shard the operation should be
            performed on (default: random)
        :arg realtime: Specify whether to perform the operation in realtime or
            search mode
        :arg refresh: Refresh the shard containing the document before
            performing the operation
        :arg routing: Specific routing value
        """
        _, data = yield self.transport.perform_request('GET',
                                                       _make_path(index,
                                                                  doc_type,
                                                                  '_mget'),
                                                       params=params, body=body)
        raise gen.Return(data)

    @gen.coroutine
    @query_params('consistency', 'fields', 'lang', 'parent', 'percolate',
                  'refresh', 'replication', 'retry_on_conflict', 'routing',
                  'script', 'timeout', 'timestamp', 'ttl', 'version',
                  'version_type')
    def update(self, index, doc_type, id, body=None, params=None):
        """
        Update a document based on a script or partial data provided.
        `<http://elasticsearch.org/guide/reference/api/update/>`_

        :arg index: The name of the index
        :arg doc_type: The type of the document
        :arg id: Document ID
        :arg body: The request definition using either `script` or partial `doc`
        :arg consistency: Explicit write consistency setting for the operation
        :arg fields: A comma-separated list of fields to return in the response
        :arg lang: The script language (default: mvel)
        :arg parent: ID of the parent document
        :arg percolate: Perform percolation during the operation; use specific
            registered query name, attribute, or wildcard
        :arg refresh: Refresh the index after performing the operation
        :arg replication: Specific replication type (default: sync)
        :arg retry_on_conflict: Specify how many times should the operation be
            retried when a conflict occurs (default: 0)
        :arg routing: Specific routing value
        :arg script: The URL-encoded script definition (instead of using
            request body)
        :arg timeout: Explicit operation timeout
        :arg timestamp: Explicit timestamp for the document
        :arg ttl: Expiration time for the document
        :arg version: Explicit version number for concurrency control
        :arg version_type: Explicit version number for concurrency control
        """
        _, data = yield self.transport.perform_request('POST',
                                                       _make_path(index,
                                                                  doc_type, id,
                                                                  '_update'),
                                                       params=params, body=body)
        raise gen.Return(data)

    @gen.coroutine
    @query_params('_source', '_source_exclude', '_source_include',
                  'analyze_wildcard', 'analyzer', 'default_operator', 'df',
                  'explain', 'fields', 'ignore_indices', 'indices_boost',
                  'lenient', 'lowercase_expanded_terms', 'from_', 'preference',
                  'q', 'routing', 'scroll', 'search_type', 'size', 'sort',
                  'source', 'stats', 'suggest_field', 'suggest_mode',
                  'suggest_size', 'suggest_text', 'timeout', 'version')
    def search(self, index=None, doc_type=None, body=None, params=None):
        """
        Execute a search query and get back search hits that match the query.
        `<http://www.elasticsearch.org/guide/reference/api/search/>`_

        :arg index: A comma-separated list of index names to search; use `_all`
            or empty string to perform the operation on all indices
        :arg doc_type: A comma-separated list of document types to search;
            leave empty to perform the operation on all types
        :arg body: The search definition using the Query DSL
        :arg _source: True or false to return the _source field or not, or a
            list of fields to return
        :arg _source_exclude: A list of fields to exclude from the returned
            _source field
        :arg _source_include: A list of fields to extract and return from the
            _source field
        :arg analyze_wildcard: Specify whether wildcard and prefix queries
            should be analyzed (default: false)
        :arg analyzer: The analyzer to use for the query string
        :arg default_operator: The default operator for query string query (AND
            or OR) (default: OR)
        :arg df: The field to use as default where no field prefix is given in
            the query string
        :arg explain: Specify whether to return detailed information about
            score computation as part of a hit
        :arg fields: A comma-separated list of fields to return as part of a hit
        :arg ignore_indices: When performed on multiple indices, allows to
            ignore `missing` ones (default: none)
        :arg indices_boost: Comma-separated list of index boosts
        :arg lenient: Specify whether format-based query failures (such as
            providing text to a numeric field) should be ignored
        :arg lowercase_expanded_terms: Specify whether query terms should be
            lowercased
        :arg from_: Starting offset (default: 0)
        :arg preference: Specify the node or shard the operation should be
            performed on (default: random)
        :arg q: Query in the Lucene query string syntax
        :arg routing: A comma-separated list of specific routing values
        :arg scroll: Specify how long a consistent view of the index should be
            maintained for scrolled search
        :arg search_type: Search operation type
        :arg size: Number of hits to return (default: 10)
        :arg sort: A comma-separated list of <field>:<direction> pairs
        :arg source: The URL-encoded request definition using the Query DSL
            (instead of using request body)
        :arg stats: Specific 'tag' of the request for logging and statistical
            purposes
        :arg suggest_field: Specify which field to use for suggestions
        :arg suggest_mode: Specify suggest mode (default: missing)
        :arg suggest_size: How many suggestions to return in response
        :arg suggest_text: The source text for which the suggestions should be
            returned
        :arg timeout: Explicit operation timeout
        :arg version: Specify whether to return document version as part of a
            hit
        """
        # from is a reserved word so it cannot be used, use from_ instead
        if 'from_' in params:
            params['from'] = params.pop('from_')

        if doc_type and not index:
            index = '_all'
        _, data = yield self.transport.perform_request('GET',
                                                       _make_path(index,
                                                                  doc_type,
                                                                  '_search'),
                                                       params=params,
                                                       body=body)
        raise gen.Return(data)

    @gen.coroutine
    @query_params('_source', '_source_exclude', '_source_include',
                  'analyze_wildcard', 'analyzer', 'default_operator',
                  'df', 'fields', 'lenient', 'lowercase_expanded_terms',
                  'parent', 'preference', 'q', 'routing', 'source')
    def explain(self, index, doc_type, id, body=None, params=None):
        """
        The explain api computes a score explanation for a query and a specific
        document. This can give useful feedback whether a document matches or
        didn't match a specific query.
        `<http://elasticsearch.org/guide/reference/api/explain/>`_

        :arg index: The name of the index
        :arg doc_type: The type of the document
        :arg id: The document ID
        :arg body: The query definition using the Query DSL
        :arg _source: True or false to return the _source field or not, or a
            list of fields to return
        :arg _source_exclude: A list of fields to exclude from the returned
            _source field
        :arg _source_include: A list of fields to extract and return from the
            _source field
        :arg analyze_wildcard: Specify whether wildcards and prefix queries in
            the query string query should be analyzed (default: false)
        :arg analyzer: The analyzer for the query string query
        :arg default_operator: The default operator for query string query (AND
            or OR), (default: OR)
        :arg df: The default field for query string query (default: _all)
        :arg fields: A comma-separated list of fields to return in the response
        :arg lenient: Specify whether format-based query failures (such as
            providing text to a numeric field) should be ignored
        :arg lowercase_expanded_terms: Specify whether query terms should be
            lowercased
        :arg parent: The ID of the parent document
        :arg preference: Specify the node or shard the operation should be
            performed on (default: random)
        :arg q: Query in the Lucene query string syntax
        :arg routing: Specific routing value
        :arg source: The URL-encoded query definition (instead of using the
            request body)
        """
        _, data = yield self.transport.perform_request('GET',
                                                       _make_path(index,
                                                                  doc_type, id,
                                                                  '_explain'),
                                                       params=params, body=body)
        raise gen.Return(data)

    @gen.coroutine
    @query_params('scroll')
    def scroll(self, scroll_id, params=None):
        """
        Scroll a search request created by specifying the scroll parameter.
        `<http://www.elasticsearch.org/guide/reference/api/search/scroll/>`_

        :arg scroll_id: The scroll ID
        :arg scroll: Specify how long a consistent view of the index should be
            maintained for scrolled search
        """
        _, data = yield self.transport.perform_request('GET',
                                                       _make_path('_search',
                                                                  'scroll',
                                                                  scroll_id),
                                                                  params=params)
        raise gen.Return(data)

    @gen.coroutine
    @query_params()
    def clear_scroll(self, scroll_id, params=None):
        """
        Clear the scroll request created by specifying the scroll parameter to
        search.
        `<http://www.elasticsearch.org/guide/reference/api/search/scroll/>`_

        :arg scroll_id: The scroll ID or a list of scroll IDs
        """
        _, data = yield self.transport.perform_request('DELETE',
                                                       _make_path('_search',
                                                                  'scroll',
                                                                  scroll_id),
                                                       params=params)
        raise gen.Return(data)


    @gen.coroutine
    @query_params('consistency', 'parent', 'refresh', 'replication', 'routing',
                  'timeout', 'version', 'version_type')
    def delete(self, index, doc_type, id, params=None):
        """
        Delete a typed JSON document from a specific index based on its id.
        `<http://elasticsearch.org/guide/reference/api/delete/>`_

        :arg index: The name of the index
        :arg doc_type: The type of the document
        :arg id: The document ID
        :arg consistency: Specific write consistency setting for the operation
        :arg parent: ID of parent document
        :arg refresh: Refresh the index after performing the operation
        :arg replication: Specific replication type (default: sync)
        :arg routing: Specific routing value
        :arg timeout: Explicit operation timeout
        :arg version: Explicit version number for concurrency control
        :arg version_type: Specific version type
        """
        _, data = yield self.transport.perform_request('DELETE',
                                                       _make_path(index,
                                                                  doc_type, id),
                                                       params=params)
        raise gen.Return(data)

    @gen.coroutine
    @query_params('ignore_indices', 'min_score', 'preference', 'routing',
                  'source')
    def count(self, index=None, doc_type=None, body=None, params=None):
        """
        Execute a query and get the number of matches for that query.
        `<http://elasticsearch.org/guide/reference/api/count/>`_

        :arg index: A comma-separated list of indices to restrict the results
        :arg doc_type: A comma-separated list of types to restrict the results
        :arg body: A query to restrict the results (optional)
        :arg ignore_indices: When performed on multiple indices, allows to
            ignore `missing` ones (default: none)
        :arg min_score: Include only documents with a specific `_score` value
            in the result
        :arg preference: Specify the node or shard the operation should be
            performed on (default: random)
        :arg routing: Specific routing value
        :arg source: The URL-encoded query definition (instead of using the
            request body)
        """
        _, data = yield self.transport.perform_request('POST',
                                                       _make_path(index,
                                                                  doc_type,
                                                                  '_count'),
                                                       params=params, body=body)
        raise gen.Return(data)

    @gen.coroutine
    @query_params('consistency', 'refresh', 'replication')
    def bulk(self, body, index=None, doc_type=None, params=None):
        """
        Perform many index/delete operations in a single API call.
        `<http://elasticsearch.org/guide/reference/api/bulk/>`_

        See the :func:`~elasticsearch.helpers.bulk_index` for a more friendly
        API.

        :arg body: The operation definition and data (action-data pairs)
        :arg index: Default index for items which don't provide one
        :arg doc_type: Default document type for items which don't provide one
        :arg consistency: Explicit write consistency setting for the operation
        :arg refresh: Refresh the index after performing the operation
        :arg replication: Explicitly set the replication type (efault: sync)
        """
        _, data = yield self.transport.perform_request('POST',
                                                       _make_path(index,
                                                                  doc_type,
                                                                  '_bulk'),
                                                       params=params,
                                                       body=self._bulk_body(body))
        raise gen.Return(data)

    @gen.coroutine
    @query_params('search_type')
    def msearch(self, body, index=None, doc_type=None, params=None):
        """
        Execute several search requests within the same API.
        `<http://www.elasticsearch.org/guide/reference/api/multi-search/>`_

        :arg body: The request definitions (metadata-search request definition
            pairs), separated by newlines
        :arg index: A comma-separated list of index names to use as default
        :arg doc_type: A comma-separated list of document types to use as default
        :arg search_type: Search operation type
        """
        _, data = yield self.transport.perform_request('GET',
                                                       _make_path(index,
                                                                  doc_type,
                                                                  '_msearch'),
                                                       params=params,
                                                       body=self._bulk_body(body))
        raise gen.Return(data)

    @gen.coroutine
    @query_params('consistency', 'ignore_indices', 'replication', 'routing',
                  'source', 'timeout', 'q')
    def delete_by_query(self, index, doc_type=None, body=None, params=None):
        """
        Delete documents from one or more indices and one or more types based
        on a query.
        `<http://www.elasticsearch.org/guide/reference/api/delete-by-query/>`_

        :arg index: A comma-separated list of indices to restrict the operation
        :arg doc_type: A comma-separated list of types to restrict the operation
        :arg body: A query to restrict the operation
        :arg consistency: Specific write consistency setting for the operation
        :arg ignore_indices: When performed on multiple indices, allows to
            ignore `missing` ones (default: none)
        :arg replication: Specific replication type (default: sync)
        :arg routing: Specific routing value
        :arg source: The URL-encoded query definition (instead of using the
        request body)
        :arg q: Query in the Lucene query string syntax
        :arg timeout: Explicit operation timeout
        """
        _, data = yield self.transport.perform_request('DELETE',
                                                       _make_path(index,
                                                                  doc_type,
                                                                  '_query'),
                                                       params=params, body=body)
        raise gen.Return(data)

    @gen.coroutine
    @query_params('ignore_indices', 'preference', 'routing', 'source')
    def suggest(self, index=None, body=None, params=None):
        """
        The suggest feature suggests similar looking terms based on a provided
        text by using a suggester.
        `<http://elasticsearch.org/guide/reference/api/search/suggest/>`_

        :arg index: A comma-separated list of index names to restrict the
            operation; use `_all` or empty string to perform the operation on
            all indices
        :arg body: The request definition
        :arg ignore_indices: When performed on multiple indices, allows to
            ignore `missing` ones (default: none)
        :arg preference: Specify the node or shard the operation should be
            performed on (default: random)
        :arg routing: Specific routing value
        :arg source: The URL-encoded request definition (instead of using
            request body)
        """
        _, data = yield self.transport.perform_request('POST',
                                                       _make_path(index,
                                                                  '_suggest'),
                                                       params=params, body=body)
        raise gen.Return(data)

    @gen.coroutine
    @query_params('prefer_local')
    def percolate(self, index, doc_type, body, params=None):
        """
        Send a percolate request which include a doc, and get back the queries
        that match on that doc out of the set of registered queries.
        `<http://elasticsearch.org/guide/reference/api/percolate/>`_

        :arg index: The name of the index with a registered percolator query
        :arg doc_type: The document type
        :arg body: The document (`doc`) to percolate against registered queries;
            optionally also a `query` to limit the percolation to specific
            registered queries
        :arg prefer_local: With `true`, specify that a local shard should be
            used if available, with `false`, use a random shard (default: true)
        """
        _, data = yield self.transport.perform_request('GET',
                                                       _make_path(index,
                                                                  doc_type,
                                                                  '_percolate'),
                                                       params=params, body=body)
        raise gen.Return(data)

    @gen.coroutine
    @query_params('boost_terms', 'max_doc_freq', 'max_query_terms',
        'max_word_len', 'min_doc_freq', 'min_term_freq', 'min_word_len',
        'mlt_fields', 'percent_terms_to_match', 'routing', 'search_from',
        'search_indices', 'search_query_hint', 'search_scroll', 'search_size',
        'search_source', 'search_type', 'search_types', 'stop_words')
    def mlt(self, index, doc_type, id, body=None, params=None):
        """
        Get documents that are "like" a specified document.
        `<http://elasticsearch.org/guide/reference/api/more-like-this/>`_

        :arg index: The name of the index
        :arg doc_type: The type of the document (use `_all` to fetch the first
            document matching the ID across all types)
        :arg id: The document ID
        :arg body: A specific search request definition
        :arg boost_terms: The boost factor
        :arg max_doc_freq: The word occurrence frequency as count: words with
            higher occurrence in the corpus will be ignored
        :arg max_query_terms: The maximum query terms to be included in the
            generated query
        :arg max_word_len: The minimum length of the word: longer words will
            be ignored
        :arg min_doc_freq: The word occurrence frequency as count: words with
            lower occurrence in the corpus will be ignored
        :arg min_term_freq: The term frequency as percent: terms with lower
            occurence in the source document will be ignored
        :arg min_word_len: The minimum length of the word: shorter words will
            be ignored
        :arg mlt_fields: Specific fields to perform the query against
        :arg percent_terms_to_match: How many terms have to match in order to
            consider the document a match (default: 0.3)
        :arg routing: Specific routing value
        :arg search_from: The offset from which to return results
        :arg search_indices: A comma-separated list of indices to perform the
            query against (default: the index containing the document)
        :arg search_query_hint: The search query hint
        :arg search_scroll: A scroll search request definition
        :arg search_size: The number of documents to return (default: 10)
        :arg search_source: A specific search request definition (instead of
            using the request body)
        :arg search_type: Specific search type (eg. `dfs_then_fetch`, `count`,
            etc)
        :arg search_types: A comma-separated list of types to perform the query
            against (default: the same type as the document)
        :arg stop_words: A list of stop words to be ignored
        """
        _, data = yield self.transport.perform_request('GET',
                                                       _make_path(index,
                                                                  doc_type, id,
                                                                  '_mlt'),
                                                       params=params, body=body)
        raise gen.Return(data)
