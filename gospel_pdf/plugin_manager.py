# -*- coding: utf-8 -*-
import importlib.util
import os
import traceback

from PyQt5.QtCore import QStandardPaths


PLUGIN_DIR =  QStandardPaths.writableLocation(QStandardPaths.AppDataLocation) + "/GospelPdfViewer/plugins"
#PLUGIN_DIR =  os.path.dirname(__file__) + "/plugins"


def import_from_path(module_name, file_path):
    spec = importlib.util.spec_from_file_location(module_name, file_path)
    module = importlib.util.module_from_spec(spec)
    #sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def loadPlugins(app):
    if not os.path.exists(PLUGIN_DIR):
        return
    global App
    App = app
    files = [f for f in os.listdir(PLUGIN_DIR) if f.endswith(".py")]
    files = [f for f in files if os.path.isfile(PLUGIN_DIR +"/"+f)]# filter files only
    for i,filename in enumerate(files):
        try:
            import_from_path(filename[:-3], PLUGIN_DIR +"/"+filename)
        except:
            print(traceback.format_exc())
            print("Failed to load plugin : ", filename)


class Plugin():
    def __init__(self, app):
        self.name = "Unnamed Plugin"
        self.description = "No description available"
        self.app = app
        self.window = app.window
        self.window.fileOpened.connect(self.onFileOpen)

    @property
    def filename(self):
        return self.app.filename

    def renderPage(self, page_no, dpi):
        return self.app.doc.renderPage(page_no, dpi)

    def onFileOpen(self, filename):
        """ connected to fileOpened signal of window """
        pass


def register_plugin(PluginClass):
    try:
        plugin = PluginClass(App)
        App.plugins.append(plugin)# storing it prevents getting deleted by python
    except:
        print(traceback.format_exc())
