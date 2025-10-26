
from setuptools import setup
from gospel_pdf import __version__, AUTHOR_NAME, AUTHOR_EMAIL

setup(
      name='gospel-pdf',
      version=__version__,
      description='Poppler or pymupdf based fast PDF Viewer',
      keywords='pyqt pyqt5 pdf-viewer poppler poppler-qt5',
      url='http://github.com/ksharindam/gospel-pdf-viewer',
      author=AUTHOR_NAME,
      author_email=AUTHOR_EMAIL,
      license='GNU GPLv3',
      packages=['gospel_pdf'],
      classifiers=[
      'License :: OSI Approved :: GNU General Public License v3 (GPLv3)',
      'Operating System :: POSIX :: Linux',
      'Programming Language :: Python :: 3',
      ],
      entry_points={
          'gui_scripts': ['gospel-pdf=gospel_pdf.main:main'],
      },
      data_files=[
                 ('share/applications', ['data/gospel-pdf.desktop']),
                 ('share/icons/hicolor/scalable/apps', ['data/gospel-pdf.png'])
      ],
      include_package_data=True,
      zip_safe=False
)
