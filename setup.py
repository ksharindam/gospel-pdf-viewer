
from setuptools import setup
from gospel_pdf import __version__

setup(
      name='gospel-pdf',
      version=__version__,
      description='Poppler based fast PDF Viewer written in PyQt5',
      keywords='pyqt pyqt5 pdf-viewer poppler poppler-qt5',
      url='http://github.com/ksharindam/gospel-pdf-viewer',
      author='Arindam Chaudhuri',
      author_email='ksharindam@gmail.com',
      license='GNU GPLv3',
      packages=['gospel_pdf'],
      classifiers=[
      'License :: OSI Approved :: GNU General Public License v3 (GPLv3)',
      'Operating System :: POSIX :: Linux',
      'Programming Language :: Python :: 3',
      ],
      entry_points={
          'console_scripts': ['gospel_pdf=gospel_pdf.main:main'],
      },
      data_files=[
                 ('share/applications', ['files/gospel-pdf.desktop']),
                 ('share/icons', ['files/gospel-pdf.png'])
      ],
      include_package_data=True,
      zip_safe=False
)
