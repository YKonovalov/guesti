# -*- coding: utf-8 -*-
from setuptools import setup
import sys, os, glob

here = os.path.abspath(os.path.dirname(__file__))
DESCRIPTION = open(os.path.join(here, 'DESCRIPTION')).read()
install_launchers = glob.glob(os.path.join('examples', 'launchers', '*'))
install_installscripts = glob.glob(os.path.join('examples', 'installer-scripts', '*'))

name = 'guesti'
version = '0.0.1'

setup(name=name,
      version=version,
      description="A cloud machine image build automation tool",
      long_description=DESCRIPTION,
      classifiers=[
          'Development Status :: 3 - Alpha',
          'Environment :: Console',
          'Intended Audience :: Developers',
          'License :: OSI Approved :: GNU General Public License v3 or later (GPLv3+)',
          'Operating System :: POSIX :: Linux',
          'Operating System :: POSIX',
          'Programming Language :: Python',
          'Topic :: System :: Systems Administration',
      ],
      author='Yury Konovalov',
      author_email='YKonovalov@gmail.com',
      url='https://github.com/ykonovalov/guesti',
      license='GPLv3+',
      packages=[
          'guesti',
          'guesti.cloud',
          'guesti.cloud.c2'
      ],
      scripts=[
          'tools/guesti'
      ] + install_launchers,
      data_files=[
          (os.path.join('share', name, 'installer-scripts'), install_installscripts)
      ],
      include_package_data=True,
      install_requires=[
          'boto',
          'xml',
          'urlparse'
      ]
)
