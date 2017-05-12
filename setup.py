#!/usr/bin/env python

from setuptools import setup
from gospel_pdf import __version__

setup(
      name='gospel-pdf',
      version=__version__,
      description='Poppler based fast PDF Viewer written in PyQt4',
      long_description='''To run it you need PyQt4 and popplerqt4 module.  
Install python-qt4 and python-poppler-qt4 (for PyQt4 and popplerqt4 module) in debian based distros''',
      keywords='pyqt pyqt4 pdf-viewer poppler poppler-qt4',
      url='http://github.com/ksharindam/gospel-pdf-viewer',
      author='Arindam Chaudhuri',
      author_email='ksharindam@gmail.com',
      license='GNU GPLv3',
      packages=['gospel_pdf'],
#      install_requires=['PyQt4',      ],
      classifiers=[
      'Development Status :: 5 - Production/Stable',
      'Environment :: X11 Applications :: Qt',
      'License :: OSI Approved :: GNU General Public License v3 (GPLv3)',
      'Operating System :: POSIX :: Linux',
      'Programming Language :: Python :: 2.7',
      ],
      entry_points={
          'console_scripts': ['gospel-pdf=gospel_pdf.main:main'],
      },
#      include_package_data=True,
      zip_safe=False)
