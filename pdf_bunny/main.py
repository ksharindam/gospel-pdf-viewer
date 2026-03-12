#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# This file is a part of PDF Bunny Program which is GNU GPLv3 licensed
# Copyright (C) 2017-2026 Arindam Chaudhuri <arindamsoft94@gmail.com>

import sys, os
from subprocess import Popen
from shutil import which
from PyQt5.QtCore import ( Qt, qVersion, QObject, pyqtSignal, QRectF, QPoint, QSettings,
    QTimer, QThread, QEventLoop, QDir, QUrl )
from PyQt5.QtGui import ( QPainter, QColor, QPixmap, QImage, QIcon, QStandardItem,
    QIntValidator, QStandardItemModel, QDesktopServices
)
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QFrame, QAction,
    QVBoxLayout, QGridLayout,
    QLabel, QMessageBox, QSystemTrayIcon,
    QLineEdit, QComboBox, QRadioButton, QHeaderView,
    QDialog, QFileDialog, QInputDialog,
)
from PyQt5.QtPrintSupport import QPrintDialog, QPrinter

sys.path.append(os.path.dirname(__file__)) # for enabling python 2 like import

import resources_rc
from __init__ import __version__, COPYRIGHT_YEAR, AUTHOR_NAME, AUTHOR_EMAIL
from ui_mainwindow import Ui_window
from dialogs import ExportToImageDialog, DocInfoDialog
from pdf_lib import PdfDocument, backend, backend_version
from plugin_manager import loadPlugins


DEBUG = False
def debug(*args):
    if DEBUG: print(*args)

SCREEN_DPI = 100
HOMEDIR = os.path.expanduser("~")

#pt2pixel = lambda point, dpi : dpi*point/72.0

class App:
    """ container for global variables """
    window = None
    plugins = []
    manager = None
    doc = None
    filename = ''
    passwd = ''
    page_dpis = {}


class Worker(QObject):
    renderFinished = pyqtSignal(int, QImage, int)
    searchFinished = pyqtSignal(int, list)

    def __init__(self):
        QObject.__init__(self)
        self.doc = None
        self.link_color = QColor(0,0,127, 40)

    def loadDocument(self, filename, password=''):
        """ Main thread uses this slot to load document for rendering """
        self.doc = PdfDocument(filename)
        if self.doc.isLocked():
            self.doc.unlock(password)

    def render(self, worker, page_no, dpi):
        """ render(int, int)
        This slot takes page no. and dpi and renders that page, then emits a signal with QImage"""
        if worker!=self:
            return
        img = self.doc.renderPage(page_no, dpi)
        # Add Heighlight over Link Annotation
        painter = QPainter(img)
        annots = self.doc.pageLinkAnnotations(page_no)
        for subtype,rect,data in annots:
            x,y,w,h = [x*dpi/72 for x in rect]
            painter.fillRect(QRectF(x, y, w+1, h+1), self.link_color)
        painter.end()
        self.renderFinished.emit(page_no, img, dpi)


    def findText(self, worker, text, start, direction):
        if worker!=self:
            return
        end = 1 if direction==-1 else self.doc.pageCount()
        pages = [i for i in range(start, end+direction, direction)]
        for page_no in pages:
            textareas = self.doc.findText(page_no, text)
            if textareas != []:
                self.searchFinished.emit(page_no, textareas)
                return
        self.searchFinished.emit(0, [])


class Manager(QObject):
    # signals
    renderRequested = pyqtSignal(Worker, int, int)# worker, page_no, dpi
    searchRequested = pyqtSignal(Worker, str, int, int)#worker, text, start, direction

    def __init__(self, parent):
        QObject.__init__(self, parent)
        self.curr_page_no = -1
        self.threads = []
        self.workers = {} # {worker:state} dictionary, state = free|busy
        self.render_cache = {} #{page_no:image} dictionary
        self.being_rendered = [] # sent to worker for rendering
        self.search_text = None
        # Create separate thread and move worker to it
        self.thread_count = 3
        for i in range(self.thread_count):
            thread = QThread(self)
            self.threads.append(thread)
            worker = Worker()
            worker.moveToThread(thread) # must be moved before connecting signals
            App.window.loadFileRequested.connect(worker.loadDocument)
            self.renderRequested.connect(worker.render)
            worker.renderFinished.connect(self.onRenderFinished)
            self.searchRequested.connect(worker.findText)
            worker.searchFinished.connect(self.onSearchFinished)
            thread.start()
            # add to workers dict
            self.workers[worker] = "free"

    def clear_cache(self):
        self.render_cache.clear()

    def set_current_page_no(self, page_no):
        self.curr_page_no = page_no
        self.run_free_workers()

    def find_text(self, text, start_page, direction):
        self.search_text = [text, start_page, direction]
        self.run_free_workers()

    def run_free_workers(self):
        # get which pages to render
        to_render = []
        for x in (0, -1, 1):
            page_no = self.curr_page_no + x
            if page_no>0 and page_no<=App.window.pages_count:
                if not page_no in self.render_cache and not page_no in self.being_rendered:
                    to_render.append(page_no)

        free_workers = [worker for worker,state in self.workers.items() if state=="free"]
        for worker in free_workers:
            if self.search_text:
                self.workers[worker] = "busy"
                self.searchRequested.emit(worker, *self.search_text)
                self.search_text = None
            elif to_render:
                self.workers[worker] = "busy"
                page_no = to_render.pop(0)
                self.renderRequested.emit(worker, page_no, App.page_dpis[page_no])
                self.being_rendered.append(page_no)

    def onRenderFinished(self, page_no, image, dpi):
        worker = self.sender()
        self.workers[worker] = "free"
        self.being_rendered.remove(page_no)
        # if page resized while rendering, rendered image is of no use
        if dpi!=App.page_dpis[page_no]:
            self.run_free_workers()
            return
        # remove old rendered pages
        if len(self.render_cache)>10:
            cleared_page_no = list(self.render_cache.keys())[0]
            del self.render_cache[cleared_page_no]
            App.window.clearPageImage(cleared_page_no)
            debug("Clear Page :", cleared_page_no)
        # set rendered image
        self.render_cache[page_no] = QPixmap.fromImage(image)
        App.window.onNewPageRendered(page_no, self.render_cache[page_no])
        self.run_free_workers()


    def onSearchFinished(self, page_nos, areas):
        worker = self.sender()
        self.workers[worker] = "free"
        App.window.onSearchFinished(page_nos, areas)

    def close_threads(self):
        """ Close running threads """
        for thread in self.threads:
            loop = QEventLoop()
            thread.finished.connect(loop.quit)
            thread.quit()
            loop.exec()



class Window(QMainWindow, Ui_window):
    loadFileRequested = pyqtSignal(str, str)
    fileOpened = pyqtSignal(str) # for plugin manager

    def __init__(self, parent=None):
        QMainWindow.__init__(self, parent)
        self.setupUi(self)
        self.setWindowTitle("PDF Bunny - " + __version__)
        self.dockSearch.hide()
        self.dockWidget.hide()
        self.dockWidget.setMinimumWidth(310)
        self.findTextEdit.setFocusPolicy(Qt.StrongFocus)
        self.treeView.setAlternatingRowColors(True)
        self.treeView.clicked.connect(self.onOutlineClick)
        # resizing pages requires some time to take effect
        self.resize_page_timer = QTimer(self)
        self.resize_page_timer.setSingleShot(True)
        self.resize_page_timer.timeout.connect(self.onWindowResize)
        # Add shortcut actions
        self.gotoPageAction = QAction(QIcon(":/icons/goto.png"), "GoTo Page", self)
        self.gotoPageAction.triggered.connect(self.gotoPage)
        self.copyTextAction = QAction(QIcon(":/icons/copy.png"), "Copy Text", self)
        self.copyTextAction.setCheckable(True)
        self.copyTextAction.triggered.connect(self.toggleCopyText)
        self.findTextAction = QAction(QIcon(":/icons/search.png"), "Find Text", self)
        self.findTextAction.setShortcut('Ctrl+F')
        self.findTextAction.triggered.connect(self.dockSearch.show)
        self.exitPresentationAction = QAction("Exit Presentation", self)
        self.exitPresentationAction.setShortcut('Esc')
        self.exitPresentationAction.triggered.connect(self.exitPresentationMode)
        self.addAction(self.exitPresentationAction)
        self.addAction(self.nextPageAction)# these are added to work in presentation mode
        self.addAction(self.prevPageAction)
        # connect menu actions signals
        self.openFileAction.triggered.connect(self.openFile)
        self.lockUnlockAction.triggered.connect(self.lockUnlock)
        self.printAction.triggered.connect(self.printFile)
        self.quitAction.triggered.connect(self.close)
        self.pageToImageAction.triggered.connect(self.exportPageToImage)
        self.docInfoAction.triggered.connect(self.docInfo)
        self.zoominAction.triggered.connect(self.zoomIn)
        self.zoomoutAction.triggered.connect(self.zoomOut)
        self.presentationAction.triggered.connect(self.enterPresentationMode)
        self.undoJumpAction.triggered.connect(self.undoJump)
        self.prevPageAction.triggered.connect(self.goPrevPage)
        self.nextPageAction.triggered.connect(self.goNextPage)
        self.firstPageAction.triggered.connect(self.goFirstPage)
        self.lastPageAction.triggered.connect(self.goLastPage)
        self.aboutAction.triggered.connect(self.showAbout)
        # Create widgets for menubar / toolbar
        self.gotoPageEdit = QLineEdit(self)
        self.gotoPageEdit.setPlaceholderText("Jump to page...")
        self.gotoPageEdit.setMaximumWidth(120)
        self.gotoPageEdit.returnPressed.connect(self.gotoPage)
        self.gotoPageValidator = QIntValidator(1,1, self.gotoPageEdit)
        self.gotoPageEdit.setValidator(self.gotoPageValidator)
        self.pageNoLabel = QLabel(self)
        self.pageNoLabel.setFrameShape(QFrame.StyledPanel)
        spacer = QWidget(self)
        spacer.setSizePolicy(1|2|4,1|4)
        self.zoomLevelCombo = QComboBox(self)
        self.zoomLevelCombo.addItems(["Fit Width", "75%", "90%","100%","110%","121%","133%","146%", "175%", "200%"])
        self.zoomLevelCombo.activated.connect(self.setZoom)
        self.zoom_levels = [0, 75, 90, 100, 110 , 121, 133, 146, 175, 200]
        # Add toolbar actions
        self.toolBar.addAction(self.openFileAction)
        self.toolBar.addAction(self.printAction)
        self.toolBar.addSeparator()
        self.toolBar.addAction(self.docInfoAction)
        self.toolBar.addSeparator()
        self.toolBar.addAction(self.zoomoutAction)
        self.toolBar.addWidget(self.zoomLevelCombo)
        self.toolBar.addAction(self.zoominAction)
        self.toolBar.addSeparator()
        self.toolBar.addAction(self.firstPageAction)
        self.toolBar.addAction(self.prevPageAction)
        self.toolBar.addWidget(self.pageNoLabel)
        self.toolBar.addAction(self.nextPageAction)
        self.toolBar.addAction(self.lastPageAction)
        self.toolBar.addAction(self.undoJumpAction)
        self.toolBar.addWidget(self.gotoPageEdit)
        self.toolBar.addAction(self.gotoPageAction)
        self.toolBar.addSeparator()
        self.toolBar.addAction(self.copyTextAction)
        self.toolBar.addAction(self.findTextAction)
        #self.toolBar.addAction(self.saveUnlockedAction)
        self.toolBar.addWidget(spacer)
        self.toolBar.addAction(self.presentationAction)
        self.attachAction = self.toolBar.addAction(QIcon(":/icons/attachment.png"), "A")
        self.attachAction.setVisible(False)
        self.toolBar.addSeparator()
        self.toolBar.addAction(self.quitAction)
        # Add widgets
        self.statusbar = QLabel(self)
        self.statusbar.setStyleSheet("QLabel { font-size: 12px; border-radius: 2px; padding: 2px; background: palette(highlight); color: palette(highlighted-text); }")
        self.statusbar.setMaximumHeight(16)
        self.statusbar.hide()
        # Impoort settings
        desktop = QApplication.desktop()
        self.settings = QSettings("pdf-bunny", "main", self)
        # QSettings.value() function returns None if previously saved value
        # was empty list. In that case adding "or []" avoids crash.
        self.file_history = {}# <filename : page_no> dictionary
        size = self.settings.beginReadArray("FileHistory")
        for i in range(size):
            self.settings.setArrayIndex(i)
            filename = self.settings.value("Filename")
            self.file_history[filename] = self.settings.value("PageNo")
        self.settings.endArray()
        self.available_area = [desktop.availableGeometry().width(), desktop.availableGeometry().height()]
        self.zoomLevelCombo.setCurrentIndex(int(self.settings.value("ZoomLevel", 0)))
        # Connect Signals
        self.scrollArea.verticalScrollBar().valueChanged.connect(self.onPageScroll)
        self.findTextEdit.returnPressed.connect(self.findNext)
        self.findNextButton.clicked.connect(self.findNext)
        self.findBackButton.clicked.connect(self.findBack)
        self.findCloseButton.clicked.connect(self.dockSearch.hide)
        self.dockSearch.visibilityChanged.connect(self.toggleFindMode)
        # Initialize Variables
        App.window = self
        App.manager = Manager(self) # thread manager
        self.pages = [] # page widgets
        self.render_on_scroll = True
        self.jumped_from = None
        self.copy_text_mode = False
        self.presentation_mode = False
        self.first_file_opened = False # to prevent resize trigger on program startup
        self.outlines_visible = False
        self.updateRecentFilesMenu()
        QDir.setCurrent(QDir.homePath())
        # Show Window
        width = int(self.settings.value("WindowWidth", 1040))
        height = int(self.settings.value("WindowHeight", 640))
        maximized = self.settings.value("WindowMaximized", "false")=="true"
        self.resize(width, height)
        if maximized:
            self.showMaximized()
        else:
            self.show()
        loadPlugins(App)
        if not App.plugins:
            self.pluginsMenu.menuAction().setVisible(False)

    def updateRecentFilesMenu(self):
        self.recentFilesMenu.clear()
        recent_files = list(self.file_history.keys())[-10:]
        for filename in reversed(recent_files):
            name = elideMiddle(os.path.basename(filename), 60)
            action = self.recentFilesMenu.addAction(name, self.openRecentFile)
            action.filename = filename
        self.recentFilesMenu.addSeparator()
        self.recentFilesMenu.addAction(QIcon(':/icons/edit-clear.png'), 'Clear Recents', self.clearRecents)

    def openRecentFile(self):
        action = self.sender()
        self.loadPDFfile(action.filename)

    def clearRecents(self):
        self.recentFilesMenu.clear()
        self.file_history.clear()
        self.settings.remove("FileHistory")

    def removeOldDoc(self):
        if not App.doc:
            return
        self.updateFileHistory()
        self.removeAllPages()
        self.attachAction.setVisible(False)
        self.jumped_from = None
        self.updateRecentFilesMenu()

    def loadPDFfile(self, filename):
        """ Loads pdf document in all threads """
        debug("opening : ", filename)
        filename = os.path.expanduser(filename)
        doc = PdfDocument(filename)
        if not doc.isValid():
            return
        password = ''
        if doc.isLocked() :
            password = QInputDialog.getText(self, 'This PDF is locked', 'Enter Password :', 2)[0]
            if password == '' :
                if App.doc == None: sys.exit(1)#exit if first document
                else : return
            unlocked = doc.unlock(password)
            if not unlocked:
                return QMessageBox.critical(self, "Failed !","Incorrect Password")
            App.passwd = password
            self.lockUnlockAction.setText("Save Unlocked")
        else:
            self.lockUnlockAction.setText("Encrypt PDF")
        self.removeOldDoc()
        App.doc = doc
        App.filename = filename
        self.pages_count = App.doc.pageCount()
        self.curr_page_no = 1
        self.getOutlines()
        # Load Document in other threads
        self.loadFileRequested.emit(App.filename, password)
        if collapseUser(filename) in self.file_history:
            page_no = int(self.file_history[collapseUser(filename)])
            self.curr_page_no = min(page_no, self.pages_count)
        # Show/Add widgets
        if App.doc.hasEmbeddedFiles():
            self.attachAction.setVisible(True)
        self.pageNoLabel.setText('<b>%i/%i</b>' % (self.curr_page_no, self.pages_count) )
        self.gotoPageValidator.setTop(self.pages_count)
        self.setWindowTitle(os.path.basename(App.filename)+ " - PDF Bunny " + __version__)
        # load pages
        self.addPages()
        self.first_file_opened = True
        self.fileOpened.emit(App.filename)

    def onNewPageRendered(self, page_no, image):
        if self.presentation_mode:
            if page_no == self.curr_page_no:
                self.pages[0].setImage(image)
            return
        # though i have never seen, when loading file
        # the page may be rendered before adding pages.
        if page_no<=len(self.pages):
            links = App.doc.pageLinkAnnotations(page_no)
            self.pages[page_no-1].setImage(image, links)

    def clearPageImage(self, page_no):
        """ To save memory, clear pixmap """
        if self.presentation_mode:
            return
        self.pages[page_no-1].clear()

    def renderCurrentPage(self):
        """ Requests manager to render current page """
        App.manager.set_current_page_no(self.curr_page_no)

    def onPageScroll(self, pos):
        """ It is called when vertical scrollbar value is changed.
            Get the current page number on scrolling, then requests to render"""
        if not self.render_on_scroll:
            return
        # we have to also check little lower to avoid page spacings
        for dy in (0,20):
            child = self.frame.childAt(int(self.frame.width()/2), int(pos)+dy)
            if isinstance(child,PageWidget):
                index = self.pages.index(child)
                self.pageNoLabel.setText('<b>%i/%i</b>' % (index+1, self.pages_count) )
                self.curr_page_no = index+1
                self.renderCurrentPage()
                break

    def addPages(self):
        """ add pages for normal mode """
        self.calculatePageDpis()
        self.renderCurrentPage()# render current page while pages are being resized
        # add Pages
        self.render_on_scroll = False
        self.frame = Frame(self.scrollAreaWidgetContents, self.scrollArea)
        self.scrollLayout.addWidget(self.frame)
        # Add page widgets
        for page_no in range(1, self.pages_count+1):
            page = PageWidget(page_no, self.frame)
            self.frame.pageLayout.addWidget(page, 0, Qt.AlignCenter)
            self.pages.append(page)
        self.render_on_scroll = True
        self.resizePages()
        if self.curr_page_no!=1:
            self.jumpToPage(self.curr_page_no)

    def removeAllPages(self):
        App.manager.clear_cache()# remove old rendered images
        App.page_dpis.clear()
        while self.pages:
            page = self.pages.pop()
            self.frame.pageLayout.removeWidget(page)
            page.deleteLater()
        self.frame.deleteLater()

    def calculatePageDpis(self):
        if self.zoomLevelCombo.currentIndex() != 0:
            percent_zoom = self.zoom_levels[self.zoomLevelCombo.currentIndex()]
            dpi = int(SCREEN_DPI*percent_zoom/100)
            for i in range(self.pages_count):
                App.page_dpis[i+1] = dpi
            return
        # Fit width
        wait(100) # get proper viewport width
        fixed_width = self.scrollArea.viewport().width() - 30
        for page_no in range(1, self.pages_count+1):
            page_w, page_h = App.doc.pageSize(page_no) # width in points
            App.page_dpis[page_no] = int(72.0*fixed_width/page_w)

    def resizePages(self):
        ''' Resize all pages according to zoom level '''
        self.render_on_scroll = False
        for i in range(self.pages_count):
            page_w, page_h = App.doc.pageSize(i+1) # width in points
            dpi = App.page_dpis[i+1]
            self.pages[i].dpi = dpi
            self.pages[i].setFixedSize(int(round(page_w*dpi/72)), int(round(page_h*dpi/72)))
        # wait for resize to take effect
        wait(100)
        self.render_on_scroll = True


    def enterPresentationMode(self):
        """ show fullscreen with black background """
        if self.presentation_mode:
            return
        self.scrollArea.setStyleSheet("QScrollArea { background-color:black; }")
        self.scrollAreaWidgetContents.setStyleSheet("background-color: black;")
        self.window_state = self.windowState(), self.saveState()
        self.outlines_visible = self.dockWidget.isVisible()
        self.showFullScreen()
        self.toolBar.hide()
        self.menubar.hide()
        self.dockWidget.hide()
        self.presentation_mode = True
        self.render_on_scroll = False
        # Remove all pages
        self.removeAllPages()
        # in presentation mode, we need to add only one page
        self.frame = Frame(self.scrollAreaWidgetContents, self.scrollArea)
        self.scrollLayout.addWidget(self.frame)
        self.frame.pageLayout.setContentsMargins(0,0,0,0)
        page = PageWidget(self.curr_page_no, self.frame)
        self.frame.pageLayout.addWidget(page, 0, Qt.AlignCenter)
        self.pages.append(page)
        # wait for resize to take effect
        wait(100)
        max_w = self.scrollArea.viewport().width()
        max_h = self.scrollArea.viewport().height()
        page_no = self.curr_page_no
        for page_no in range(1,self.pages_count+1):
            page_w, page_h = App.doc.pageSize(page_no) # size in points
            dpi = min(int(72*max_w/page_w), int(72*max_h/page_h))
            App.page_dpis[page_no] = dpi

        self.showCurrentSlide()

    def exitPresentationMode(self):
        # enter normal mode
        if not self.presentation_mode:
            return
        self.removeAllPages()
        self.setWindowState(self.window_state[0])# restores normal or maximized state
        self.restoreState(self.window_state[1])# restores menubar, toolbar and dockwidgets
        self.scrollArea.setStyleSheet("QScrollArea { background-color: #efefef; }")
        self.scrollAreaWidgetContents.setStyleSheet("QWidget {background-color: #efefef;}")
        wait(50)# in this time, resizeEvent() is called
        self.render_on_scroll = True
        self.presentation_mode = False
        self.addPages()

    def showCurrentSlide(self):
        """ show presentation slide """
        self.pages[0].clear()
        dpi = App.page_dpis[self.curr_page_no]
        page_w, page_h = App.doc.pageSize(self.curr_page_no) # size in points
        self.pages[0].setFixedSize(int(round(page_w*dpi/72)), int(round(page_h*dpi/72)))
        if image := App.manager.render_cache.get(self.curr_page_no,None):
            self.pages[0].setImage(image)
        self.renderCurrentPage()


    def openFile(self):
        filename, sel_filter = QFileDialog.getOpenFileName(self,
                                      "Select Document to Open", App.filename,
                                      "Portable Document Format (*.pdf);;All Files (*)" )
        if filename != "":
            self.loadPDFfile(filename)

    def lockUnlock(self):
        if which("qpdf")==None :
            self.lockUnlockAction.setEnabled(False)
            QMessageBox.warning(self, "qpdf Required","qpdf command not found.\nInstall qpdf program.")
            return
        if self.lockUnlockAction.text()=="Encrypt PDF":
            self.encryptPDF()
            return
        filename, ext = os.path.splitext(App.filename)
        new_name = filename + "-unlocked.pdf"
        proc = Popen(["qpdf", "--decrypt", "--password="+App.passwd, App.filename, new_name])
        stdout, stderr = proc.communicate()
        if proc.returncode==0:
            notifier = Notifier(self)
            notifier.showNotification("Successful !", "File saved as\n"+os.path.basename(new_name))
        else:
            QMessageBox.warning(self, "Failed !", "Failed to save as unlocked")

    def encryptPDF(self):
        password, ok = QInputDialog.getText(self, "Lock PDF", "Enter Password :",
                                                QLineEdit.PasswordEchoOnEdit)
        if not ok or password=="":
            return
        filename, ext = os.path.splitext(App.filename)
        new_name = filename + "-locked.pdf"
        proc = Popen(["qpdf", "--encrypt", password, password, '128', '--', App.filename, new_name])
        stdout, stderr = proc.communicate()
        if proc.returncode == 0:
            basename = os.path.basename(new_name)
            notifier = Notifier(self)
            notifier.showNotification("Successful !", "File saved as\n"+basename)
        else:
            QMessageBox.warning(self, "Failed !", "Failed to save as Encrypted")

    def printFile(self):
        if which("quikprint"):
            Popen(["quikprint", App.filename])
            return
        printer = QPrinter(QPrinter.HighResolution)
        dlg = QPrintDialog(printer, self)
        dlg.setOption(dlg.PrintCurrentPage, True)
        dlg.setMinMax(1, App.doc.pageCount())
        # add a tab for Scaling options
        widget = QWidget(dlg)
        widget.setWindowTitle("Scaling")
        layout = QGridLayout(widget)
        fitToPageBtn = QRadioButton("Fit To Page", widget)
        fitToPageBtn.setChecked(True)
        originalSizeBtn = QRadioButton("Original Size", widget)
        customScalingBtn = QRadioButton("Custom Scaling (%)", widget)
        scalingEdit = QLineEdit(widget)
        scalingEdit.setPlaceholderText("20%-400%")
        scalingEdit.setValidator(QIntValidator(20, 400, scalingEdit))
        scalingEdit.setEnabled(False)
        customScalingBtn.toggled.connect(scalingEdit.setEnabled)
        layout.addWidget(fitToPageBtn, 0,0,1,2)
        layout.addWidget(originalSizeBtn, 1,0,1,2)
        layout.addWidget(customScalingBtn, 2,0,1,1)
        layout.addWidget(scalingEdit, 2,1,1,1)
        layout.setColumnStretch(2,1)
        layout.setRowStretch(3,1)
        dlg.setOptionTabs([widget])

        if (dlg.exec() != QDialog.Accepted):
            return
        if printer.printRange()==QPrinter.CurrentPage:
            from_page = self.curr_page_no
            to_page = from_page
        else:
            from_page = printer.fromPage() or 1
            to_page = printer.toPage() or App.doc.pageCount()
        # get cups options
        o = {}
        props = printer.printEngine().property(0xfe00)# cups property
        if props and isinstance(props, list) and len(props) % 2 == 0:
            for key, value in zip(props[0::2], props[1::2]):
                if value and isinstance(key, str) and isinstance(value, str):
                    o[key] = value
        #print(o)
        page_set = o.get("page-set", "all")
        page_ranges = o.get("page-ranges", "")
        page_nos = []
        if page_ranges:
            ranges = page_ranges.split(",")
            for page_range in ranges:
                if "-" in page_range:
                    start, end = page_range.split("-")
                    page_nos += list(range(int(start), int(end)+1))
                else:
                    page_nos.append(int(page_range))
        else:
            page_nos = list(range(from_page, to_page+1))
            # CUPS shows opposite page-set value, if From page is even number
            if from_page%2==0:
                page_set = {"odd": "even", "even":"odd"}.get(page_set, "all")

        # filter odd/even
        if page_set=="odd":
            page_nos = list(filter(lambda n: n%2, page_nos))
        elif page_set=="even":
            page_nos = list(filter(lambda n: n%2-1, page_nos))

        page_nos = set(page_nos)# set allows quick searching

        render_dpi = 300

        if originalSizeBtn.isChecked():
            printer.setFullPage(True)
            scale = printer.physicalDpiX()/render_dpi
        elif customScalingBtn.isChecked() and len(scalingEdit.text())>1:
            scaling = int(scalingEdit.text())/100
            scale = scaling * printer.physicalDpiX()/render_dpi
        else: # fit to page (need to calculate for each page)
            scale = 0

        painter = QPainter(printer)
        for page_no in range(from_page, to_page+1):
            if page_no!=from_page:
                printer.newPage()
                # needed when any transformation was applied on previous page
                painter.resetTransform()
            if page_no not in page_nos:
                continue
            # tried Poppler.Page.renderToPainter() but always fails
            img = App.doc.renderPage(page_no, render_dpi)
            rect = painter.viewport()
            scale_ = scale or min(rect.width()/img.width(), rect.height()/img.height())
            painter.scale(scale_, scale_)
            painter.drawImage(0, 0, img)
        painter.end()


    def exportPageToImage(self):
        dialog = ExportToImageDialog(self.curr_page_no, self.pages_count, self)
        if dialog.exec_() == QDialog.Accepted:
            try:
                dpi = int(dialog.dpiEdit.text())
                for page_no in range(dialog.pageNoSpin.value(), dialog.toPageNoSpin.value()+1):
                    filename = os.path.splitext(App.filename)[0]+'-'+str(page_no)+'.jpg'
                    img = App.doc.renderPage(page_no, dpi)
                    img.save(filename)
                notifier = Notifier(self)
                notifier.showNotification("Successful !","Image(s) has been saved")
            except:
                QMessageBox.warning(self, "Failed !","Failed to export to Image")

    def docInfo(self):
        info = App.doc.info()
        page_size = "%.1f x %.1f pts" % App.doc.pageSize(self.curr_page_no)
        info['Page Size'] = page_size
        dialog = DocInfoDialog(info, self)
        dialog.exec_()


    def jumpToPage(self, page_num, top=0.0):
        """ scrolls to a particular page and position """
        if page_num < 1: page_num = 1
        elif page_num > self.pages_count: page_num = self.pages_count
        self.jumped_from = self.curr_page_no
        self.curr_page_no = page_num
        if self.presentation_mode:
            self.showCurrentSlide()
            return
        top *= self.pages[page_num-1].dpi/72
        if not (0 < top < self.pages[page_num-1].height()): top = 0
        scrollbar_pos = self.pages[page_num-1].pos().y()
        scrollbar_pos += top
        if int(scrollbar_pos) != self.scrollArea.verticalScrollBar().value():
            self.scrollArea.verticalScrollBar().setValue(int(scrollbar_pos))
        else:# when scrollbar value does not change
            self.renderCurrentPage()

    def undoJump(self):
        if self.jumped_from == None: return
        self.jumpToPage(self.jumped_from)

    def goNextPage(self):
        if self.curr_page_no == self.pages_count : return
        self.jumpToPage(self.curr_page_no + 1)

    def goPrevPage(self):
        if self.curr_page_no == 1 : return
        self.jumpToPage(self.curr_page_no - 1)

    def goFirstPage(self):
        self.jumpToPage(1)

    def goLastPage(self):
        self.jumpToPage(self.pages_count)

    def gotoPage(self):
        text = self.gotoPageEdit.text()
        if text=="" : return
        self.jumpToPage(int(text))
        self.gotoPageEdit.clear()
        self.gotoPageEdit.clearFocus()

######################  Zoom and Size Management  ##########################

    def setZoom(self, index):
        """ Gets called when zoom level is changed"""
        scrollbar = self.scrollArea.verticalScrollBar()
        rel_pos = scrollbar.value()/scrollbar.maximum() if scrollbar.maximum() else 0
        App.manager.clear_cache()# remove old rendered images
        self.calculatePageDpis()
        self.resizePages()
        new_pos = int(rel_pos * scrollbar.maximum())
        if scrollbar.value()!=new_pos:
            scrollbar.setValue(new_pos)# renders current page
        else:
            self.renderCurrentPage()

    def zoomIn(self):
        index = self.zoomLevelCombo.currentIndex()
        if index == len(self.zoom_levels) - 1 : return
        if index == 0 : index = 3
        self.zoomLevelCombo.setCurrentIndex(index+1)
        self.setZoom(index+1)

    def zoomOut(self):
        index = self.zoomLevelCombo.currentIndex()
        if index == 1 : return
        if index == 0: index = 4
        self.zoomLevelCombo.setCurrentIndex(index-1)
        self.setZoom(index-1)


#########            Search Text            #########
    def toggleFindMode(self, enable):
        if enable:
          self.findTextEdit.setText('')
          self.findTextEdit.setFocus()
          self.search_text = ''
          self.search_result_page = 0
        elif self.search_result_page != 0:
          self.pages[self.search_result_page-1].highlight_area = None
          self.pages[self.search_result_page-1].updateImage()

    def findText(self, text, direction):
        """ direction is +1 for forward and -1 for backward """
        text = self.findTextEdit.text()
        if text == "" : return
        # search from current page when text changed
        if self.search_text != text or self.search_result_page == 0:
            search_from_page = self.curr_page_no
        else:
            search_from_page = self.search_result_page + direction
        App.manager.find_text(text, search_from_page, direction)
        if self.search_result_page != 0:     # clear previous highlights
            self.pages[self.search_result_page-1].highlight_area = None
            self.pages[self.search_result_page-1].updateImage()
            self.search_result_page = 0
        self.search_text = text

    def findNext(self):
        self.findText(self.findTextEdit.text(), +1)

    def findBack(self):
        self.findText(self.findTextEdit.text(), -1)

    def onSearchFinished(self, page_no, areas):
        """ page_no is zero if no result found """
        if not page_no:
            return
        self.pages[page_no-1].highlight_area = areas
        self.search_result_page = page_no
        if self.pages[page_no-1].pixmap():
            self.pages[page_no-1].updateImage()
        first_result_pos = areas[0][1]
        self.jumpToPage(page_no, first_result_pos)


#########      Cpoy Text to Clip Board      #########
    def toggleCopyText(self, checked):
        self.copy_text_mode = checked

    def copyText(self, page_no, rect):
        zoom = self.pages[page_no-1].dpi/72
        rect = [x/zoom for x in rect]
        # Copy text to clipboard
        text = App.doc.getPageText(page_no, rect)
        QApplication.clipboard().setText(text)
        self.copyTextAction.setChecked(False)
        self.toggleCopyText(False)

##########      Other Functions      ##########

    def getOutlines(self):
        toc = App.doc.toc()
        if not toc:
            self.dockWidget.hide()
            return
        self.dockWidget.show()
        outline_model = QStandardItemModel(self)
        root_item = outline_model.invisibleRootItem()
        parent_items = [root_item]

        for level,title,page_no,top in toc:
            parent_item = parent_items[level-1]
            item = QStandardItem(title)
            if page_no>0:
                item.setData(page_no, Qt.UserRole + 1)
                item.setData(top, Qt.UserRole + 2)

                pageItem = QStandardItem(str(page_no))
                pageItem.setTextAlignment(Qt.AlignRight)
                parent_item.appendRow([item, pageItem])
            else:
                # without this empty second item, sometimes page_no column is not visible
                parent_item.appendRow([item, QStandardItem("")])

            while len(parent_items)!=level:
                parent_items.pop()
            parent_items.append(item)

        self.treeView.setModel(outline_model)
        if root_item.rowCount() < 4:
            self.treeView.expandToDepth(0)
        self.treeView.setHeaderHidden(True)
        self.treeView.header().setSectionResizeMode(0, QHeaderView.Stretch)
        self.treeView.header().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.treeView.header().setStretchLastSection(False)

    def onOutlineClick(self, m_index):
        page_num = self.treeView.model().data(m_index, Qt.UserRole+1)
        top = self.treeView.model().data(m_index, Qt.UserRole+2)
        if not page_num: return
        self.jumpToPage(page_num, top)

    def showStatus(self, text):
        if not text:
            self.statusbar.hide()
            return
        self.statusbar.setText(text)
        self.statusbar.adjustSize()
        self.statusbar.move(0, self.height()-self.statusbar.height())
        self.statusbar.show()

    def showNotification(self, title, text):
        notifier = Notifier(self)
        notifier.showNotification(title, text)

    def showWarning(self, title, text):
        QMessageBox.warning(self, title, text)

    def resizeEvent(self, ev):
        # if program starts at maximized window, this event is called twice
        QMainWindow.resizeEvent(self, ev)
        # prevents page resize trigger on program startup
        # also handles both enter and exiting presentation mode
        if not self.first_file_opened or self.presentation_mode:
            return
        self.resize_page_timer.start(200)

    def onWindowResize(self):
        if self.zoomLevelCombo.currentIndex() == 0:
            App.manager.clear_cache()# remove old rendered images
            self.calculatePageDpis()
            self.resizePages()
            self.jumpToPage(self.curr_page_no)
        if not self.isMaximized():
            self.settings.setValue("WindowWidth", self.width())
            self.settings.setValue("WindowHeight", self.height())

    def updateFileHistory(self):
        if not App.filename:
            return
        filename = collapseUser(App.filename)
        if filename in self.file_history:
            self.file_history.pop(filename)# remove so that new entry adds to the end
        self.file_history[filename] = self.curr_page_no


    def showAbout(self):
        lines = ("<h1>PDF Bunny</h1>",
            "A Fast Simple Pdf Viewer using PyMupdf or Poppler<br><br>",
            "Version : %s<br>" % __version__,
            "Qt : %s<br>" % qVersion(),
            "%s : %s<br>" % (backend, backend_version),
            "Copyright &copy; %s %s &lt;%s&gt;" % (COPYRIGHT_YEAR, AUTHOR_NAME, AUTHOR_EMAIL))
        QMessageBox.about(self, "About PDF Bunny", "".join(lines))

    def closeEvent(self, ev):
        """ Save all settings on window close """
        self.settings.setValue("WindowMaximized", self.isMaximized())
        self.updateFileHistory()
        self.settings.setValue("ZoomLevel", self.zoomLevelCombo.currentIndex())
        self.settings.beginWriteArray("FileHistory")
        for i,filename in enumerate( list(self.file_history.keys())[-100:] ):
            self.settings.setArrayIndex(i)
            self.settings.setValue("Filename", filename)
            self.settings.setValue("PageNo", self.file_history[filename])
        self.settings.endArray()
        return QMainWindow.closeEvent(self, ev)

    def onAppQuit(self):
        App.manager.close_threads()



class Frame(QWidget):
    """ This widget is a container of PageWidgets """
    # parent is scrollAreaWidgetContents
    def __init__(self, parent, scrollArea):
        QWidget.__init__(self, parent)
        self.pageLayout = QVBoxLayout(self)
        self.vScrollbar = scrollArea.verticalScrollBar()
        self.hScrollbar = scrollArea.horizontalScrollBar()
        self.setMouseTracking(True)
        self.mouse_pressed = False

    def mousePressEvent(self, ev):
        self.click_pos = ev.globalPos()
        self.v_scrollbar_pos = self.vScrollbar.value()
        self.h_scrollbar_pos = self.hScrollbar.value()
        self.mouse_pressed = True

    def mouseReleaseEvent(self, ev):
        self.mouse_pressed = False

    def mouseMoveEvent(self, ev):
        """ drag to scroll """
        if not self.mouse_pressed : return
        self.vScrollbar.setValue(self.v_scrollbar_pos + self.click_pos.y() - ev.globalY())
        self.hScrollbar.setValue(self.h_scrollbar_pos + self.click_pos.x() - ev.globalX())


class PageWidget(QLabel):
    """ This widget shows a rendered page """
    def __init__(self, page_num, parent):
        QLabel.__init__(self, parent)
        self.setMouseTracking(True)
        self.setSizePolicy(0,0)#fixed
        self.link_annots = [] # list of (QRectF area, LinkAnnotation) tuple
        self.click_point, self.highlight_area = None, None
        self.page_num = page_num
        self.image = QPixmap()
        self.dpi = 72# dpi is set when pages are resized

    def setImage(self, image, links=[]):
        self.image = image
        self.updateImage()
        for link in links:
            subtype,rect,data = link
            x,y,w,h = [x*self.dpi/72 for x in rect]
            self.link_annots.append((QRectF(x,y, w+1, h+1), link))

    def updateImage(self):
        """ repaint page widget, and draw highlight areas """
        if self.highlight_area:
            img = self.image.copy()
            painter = QPainter(img)
            zoom = self.dpi/72.0
            for area in self.highlight_area:
                rect = [x*zoom for x in area]
                painter.fillRect(QRectF(*rect), QColor(0,255,0, 127))
            painter.end()
            self.setPixmap(img)
        else:
            self.setPixmap(self.image)

    def clear(self):
        QLabel.clear(self)
        self.image = QPixmap()
        self.link_annots.clear()


    def mouseMoveEvent(self, ev):
        # Draw rectangle when mouse is clicked and dragged in copy text mode.
        if App.window.copy_text_mode:
            if self.click_point:
                pm = self.pm.copy()
                painter = QPainter()
                painter.begin(pm)
                painter.drawRect(QRectF(self.click_point, ev.pos()))
                painter.end()
                self.setPixmap(pm)
            return

        # Change cursor if cursor is over link annotation
        for rect, link in self.link_annots:
            if rect.contains(ev.pos()):
                subtype,rect,data = link
                # For jump to page link
                if subtype == "GoTo":
                    App.window.showStatus("Jump To Page : %i" % data[0])
                    self.setCursor(Qt.PointingHandCursor)
                # For URL link
                elif subtype == "URI":
                    App.window.showStatus("URL : %s" % data)
                    self.setCursor(Qt.PointingHandCursor)
                return
        App.window.showStatus("")
        self.unsetCursor()
        ev.ignore()         # pass to underlying frame if not over link or copy text mode

    def mousePressEvent(self, ev):
        # In text copy mode
        if App.window.copy_text_mode:
            self.click_point = ev.pos()
            self.pm = self.pixmap().copy()
            return
        # In normal mode
        for rect, link in self.link_annots:
            if not rect.contains(ev.pos()):
                continue
            subtype,rect,data = link
            # For jump to page link, data==(page_no,top)
            if subtype == "GoTo":
                App.window.jumpToPage(*data)
            # For URL link, data==url
            elif subtype == "URI":
                if data.startswith("http"):
                    confirm = QMessageBox.question(self, "Open Url in Browser",
                        "Do you want to open browser to open...\n%s" %data, QMessageBox.Yes|QMessageBox.Cancel)
                    if confirm == QMessageBox.Yes:
                        QDesktopServices.openUrl(QUrl(data))
            return
        ev.ignore()

    def mouseReleaseEvent(self, ev):
        if App.window.copy_text_mode:
            rect = QRectF(self.click_point, ev.pos()).getRect()
            App.window.copyText(self.page_num, list(rect))
            self.setPixmap(self.pm)
            self.click_point = None
            self.pm = None
            return
        ev.ignore()



class Notifier(QSystemTrayIcon):
    def __init__(self, parent):
        QSystemTrayIcon.__init__(self, QIcon(':/icons/pdf-bunny.png'), parent)
        self.messageClicked.connect(self.deleteLater)
        self.activated.connect(self.deleteLater)

    def showNotification(self, title, message):
        self.show()
        # Wait for 200ms, otherwise notification bubble will showup in wrong position.
        wait(200)
        self.showMessage(title, message)
        QTimer.singleShot(4000, self.deleteLater)



def wait(millisec):
    loop = QEventLoop()
    QTimer.singleShot(millisec, loop.quit)
    loop.exec_()

def collapseUser(path):
    ''' converts /home/user/file.ext to ~/file.ext '''
    if path.startswith(HOMEDIR):
        return path.replace(HOMEDIR, '~', 1)
    return path

def elideMiddle(text, length):
    if len(text) <= length: return text
    return text[:length//2] + '...' + text[len(text)-length+length//2:]

def main():
    app = QApplication(sys.argv)
    filename = os.path.abspath(sys.argv[-1])
    win = Window()
    if len(sys.argv)>1 and os.path.exists(filename):
        win.loadPDFfile(filename)
    app.aboutToQuit.connect(win.onAppQuit)
    sys.exit(app.exec_())

if __name__ == "__main__":
    main()
