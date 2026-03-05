from setuptools import setup
from setuptools.command.install import install
try:
    from setuptools.command.bdist_wheel import bdist_wheel
except:
    from wheel.bdist_wheel import bdist_wheel
from subprocess import check_call
import platform

# allows to run commands before 'setup.py install' (used by dh-python)
class Install(install):
    def run(self):
        check_call("pyrcc5 -o ./gospel_pdf/resources_rc.py ./data/resources.qrc".split())
        check_call("pyuic5 -o ./gospel_pdf/ui_mainwindow.py ./data/mainwindow.ui".split())
        install.run(self)

# allows to run commands before building wheel
class BdistWheel(bdist_wheel):
    def finalize_options(self):
        check_call("pyrcc5 -o ./gospel_pdf/resources_rc.py ./data/resources.qrc".split())
        check_call("pyuic5 -o ./gospel_pdf/ui_mainwindow.py ./data/mainwindow.ui".split())
        bdist_wheel.finalize_options(self)


if platform.system()=='Linux':
    data_files = [('share/applications', ['data/gospel-pdf.desktop']),
                ('share/icons/hicolor/scalable/apps', ['data/gospel-pdf.png'])]
else:
    data_files = []

setup(
    name='gospel-pdf',
    #version="3.4.0",
    packages=['gospel_pdf'],
    entry_points={
      'gui_scripts': ['gospel_pdf=gospel_pdf.main:main'],
    },
    data_files = data_files,
    cmdclass = {'bdist_wheel': BdistWheel, 'install': Install},
    include_package_data=True,
    zip_safe=False
    )
