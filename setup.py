import distutils.core

desc = ('Extends the official Elasticsearch Python API adding '
        'Tornado AsyncHTTPClient support')


distutils.core.setup(name='tornado_elasticsearch',
                     version='0.1.0',
                     description=desc,
                     long_description=open('README.rst').read(),
                     author='Gavin M. Roy',
                     author_email='gavinmroy@gmail.com',
                     url='https://github.com/gmr/tornado_elasticsearch',
                     py_modules=['tornado_elasticsearch'],
                     package_data={'': ['LICENSE', 'README.md']},
                     include_package_data=True,
                     install_requires=['elasticsearch', 'tornado'],
                     license=open('LICENSE').read(),
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
