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
        check_call("pyrcc5 -o ./pdf_bunny/resources_rc.py ./data/resources.qrc".split())
        check_call("pyuic5 -o ./pdf_bunny/ui_mainwindow.py ./data/mainwindow.ui".split())
        install.run(self)

# allows to run commands before building wheel
class BdistWheel(bdist_wheel):
    def finalize_options(self):
        check_call("pyrcc5 -o ./pdf_bunny/resources_rc.py ./data/resources.qrc".split())
        check_call("pyuic5 -o ./pdf_bunny/ui_mainwindow.py ./data/mainwindow.ui".split())
        bdist_wheel.finalize_options(self)


if platform.system()=='Linux':
    data_files = [('share/applications', ['data/pdf-bunny.desktop']),
                ('share/icons/hicolor/scalable/apps', ['data/pdf-bunny.png'])]
else:
    data_files = []

setup(
    name='pdf-bunny',
    #version="3.4.0",
    packages=['pdf_bunny'],
    entry_points={
      'gui_scripts': ['pdf_bunny=pdf_bunny.main:main'],
    },
    data_files = data_files,
    cmdclass = {'bdist_wheel': BdistWheel, 'install': Install},
    include_package_data=True,
    zip_safe=False
    )
