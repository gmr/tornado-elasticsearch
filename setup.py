import os
import setuptools

desc = ('Extends the official Elasticsearch Python API adding '
        'Tornado AsyncHTTPClient support')

try:
    license = open('LICENSE').read()
except IOError:
    license = 'BSD'

try:
    readme = open('README.rst').read()
except IOError:
    readme = ''


setuptools.setup(name='tornado_elasticsearch',
                 version='0.1.3',
                 description=desc,
                 long_description=readme,
                 author='Gavin M. Roy',
                 author_email='gavinmroy@gmail.com',
                 url='https://github.com/gmr/tornado_elasticsearch',
                 py_modules=['tornado_elasticsearch'],
                 install_requires=['elasticsearch', 'tornado'],
                 license=license,
                 classifiers=['Development Status :: 3 - Alpha',
                              'Intended Audience :: Developers',
                              'License :: OSI Approved :: BSD License',
                              'Operating System :: OS Independent',
                              'Programming Language :: Python :: 2',
                              'Programming Language :: Python :: 2.6',
                              'Programming Language :: Python :: 2.7',
                              'Programming Language :: Python :: 3',
                              'Programming Language :: Python :: 3.2',
                              'Programming Language :: Python :: 3.3',
                              'Programming Language :: Python :: Implementation :: CPython',
                              'Programming Language :: Python :: Implementation :: PyPy',
                              'Topic :: Communications',
                              'Topic :: Internet',
                              'Topic :: Software Development :: Libraries'],
                 zip_safe=True)
