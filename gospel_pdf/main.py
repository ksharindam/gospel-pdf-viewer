#!/usr/bin/env python3
# -*- coding: utf-8 -*-

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
    QLineEdit, QComboBox, QRadioButton,
    QDialog, QFileDialog, QInputDialog,
)
from PyQt5.QtPrintSupport import QPrintDialog, QPrinter

sys.path.append(os.path.dirname(__file__)) # for enabling python 2 like import

import resources_rc
from __init__ import __version__, COPYRIGHT_YEAR, AUTHOR_NAME, AUTHOR_EMAIL
from ui_mainwindow import Ui_window
from dialogs import ExportToImageDialog, DocInfoDialog
from pdf_lib import PdfDocument, backend, backend_version

DEBUG = False
def debug(*args):
    if DEBUG: print(*args)

SCREEN_DPI = 100
HOMEDIR = os.path.expanduser("~")

#pt2pixel = lambda point, dpi : dpi*point/72.0

class Renderer(QObject):
    rendered = pyqtSignal(int, QImage)
    textFound = pyqtSignal(int, list)

    def __init__(self, page_set=1):
        # page_set = 1 for odd, and 0 for even
        QObject.__init__(self)
        self.doc = None
        self.page_set = page_set
        self.painter = QPainter()
        self.link_color = QColor(0,0,127, 40)

    def loadDocument(self, filename, password=''):
        """ Main thread uses this slot to load document for rendering """
        self.doc = PdfDocument(filename)
        if self.doc.isLocked():
            self.doc.unlock(password)

    def render(self, page_no, dpi):
        """ render(int, int)
        This slot takes page no. and dpi and renders that page, then emits a signal with QImage"""
        # Returns when both is true or both is false
        if page_no%2 != self.page_set:
            return
        img = self.doc.renderPage(page_no, dpi)
        # Add Heighlight over Link Annotation
        self.painter.begin(img)
        annots = self.doc.pageLinkAnnotations(page_no)
        for subtype,rect,data in annots:
            x,y,w,h = [x*dpi/72 for x in rect]
            self.painter.fillRect(QRectF(x, y, w+1, h+1), self.link_color)
        self.painter.end()
        self.rendered.emit(page_no, img)


    def findText(self, text, page_num, find_reverse):
        if find_reverse:
            pages = [i for i in range(1,page_num+1)]
            pages.reverse()
        else:
            pages = [i for i in range(page_num, self.doc.pageCount()+1)]
        for page_no in pages:
            textareas = self.doc.findText(page_no, text)
            if textareas != []:
                self.textFound.emit(page_no, textareas)
                break


class Window(QMainWindow, Ui_window):
    renderRequested = pyqtSignal(int, int)
    loadFileRequested = pyqtSignal(str, str)
    findTextRequested = pyqtSignal(str, int, bool)

    def __init__(self, parent=None):
        QMainWindow.__init__(self, parent)
        self.setupUi(self)
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
        # connect menu actions signals
        self.openFileAction.triggered.connect(self.openFile)
        self.lockUnlockAction.triggered.connect(self.lockUnlock)
        self.printAction.triggered.connect(self.printFile)
        self.quitAction.triggered.connect(self.close)
        self.pageToImageAction.triggered.connect(self.exportPageToImage)
        self.docInfoAction.triggered.connect(self.docInfo)
        self.zoominAction.triggered.connect(self.zoomIn)
        self.zoomoutAction.triggered.connect(self.zoomOut)
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
        self.settings = QSettings("gospel-pdf", "main", self)
        # QSettings.value() function returns None if previously saved value
        # was empty list. In that case adding "or []" avoids crash.
        self.recent_files = self.settings.value("RecentFiles", []) or []
        self.history_filenames = self.settings.value("HistoryFileNameList", []) or []
        self.history_page_no = self.settings.value("HistoryPageNoList", []) or []
        self.available_area = [desktop.availableGeometry().width(), desktop.availableGeometry().height()]
        self.zoomLevelCombo.setCurrentIndex(int(self.settings.value("ZoomLevel", 2)))
        # Connect Signals
        self.scrollArea.verticalScrollBar().valueChanged.connect(self.onMouseScroll)
        self.scrollArea.verticalScrollBar().sliderReleased.connect(self.onSliderRelease)
        self.findTextEdit.returnPressed.connect(self.findNext)
        self.findNextButton.clicked.connect(self.findNext)
        self.findBackButton.clicked.connect(self.findBack)
        self.findCloseButton.clicked.connect(self.dockSearch.hide)
        self.dockSearch.visibilityChanged.connect(self.toggleFindMode)
        # Create separate thread and move renderer to it
        self.thread1 = QThread(self)
        self.renderer1 = Renderer(0)
        self.renderer1.moveToThread(self.thread1) # this must be moved before connecting signals
        self.renderRequested.connect(self.renderer1.render)
        self.loadFileRequested.connect(self.renderer1.loadDocument)
        self.findTextRequested.connect(self.renderer1.findText)
        self.renderer1.rendered.connect(self.setRenderedImage)
        self.renderer1.textFound.connect(self.onTextFound)
        self.thread1.start()
        self.thread2 = QThread(self)
        self.renderer2 = Renderer(1)
        self.renderer2.moveToThread(self.thread2)
        self.renderRequested.connect(self.renderer2.render)
        self.loadFileRequested.connect(self.renderer2.loadDocument)
        self.renderer2.rendered.connect(self.setRenderedImage)
        self.thread2.start()
        # Initialize Variables
        QDir.setCurrent(QDir.homePath())
        self.doc = None
        self.filename = ''
        self.passwd = ''
        self.pages = []
        self.jumped_from = None
        self.max_preload = 1
        self.recent_files_actions = []
        self.addRecentFiles()
        # Show Window
        width = int(self.settings.value("WindowWidth", 1040))
        height = int(self.settings.value("WindowHeight", 717))
        self.resize(width, height)
        self.show()

    def addRecentFiles(self):
        self.recent_files_actions[:] = [] # pythonic way to clear list
        self.menuRecentFiles.clear()
        for each in self.recent_files:
            name = elideMiddle(os.path.basename(each), 60)
            action = self.menuRecentFiles.addAction(name, self.openRecentFile)
            self.recent_files_actions.append(action)
        self.menuRecentFiles.addSeparator()
        self.menuRecentFiles.addAction(QIcon(':/icons/edit-clear.png'), 'Clear Recents', self.clearRecents)

    def openRecentFile(self):
        action = self.sender()
        index = self.recent_files_actions.index(action)
        self.loadPDFfile(self.recent_files[index])

    def clearRecents(self):
        self.recent_files_actions[:] = []
        self.menuRecentFiles.clear()
        self.recent_files[:] = []

    def removeOldDoc(self):
        if not self.doc:
            return
        # Save current page number
        self.saveFileData()
        # Remove old document
        for i in range(len(self.pages)):
            self.verticalLayout.removeWidget(self.pages[-1])
        for i in range(len(self.pages)):
            self.pages.pop().deleteLater()
        self.frame.deleteLater()
        self.attachAction.setVisible(False)
        self.jumped_from = None
        self.addRecentFiles()

    def loadPDFfile(self, filename):
        """ Loads pdf document in all threads """
        print("opening : ", filename)
        filename = os.path.expanduser(filename)
        doc = PdfDocument(filename)
        if not doc.isValid():
            return
        password = ''
        if doc.isLocked() :
            password = QInputDialog.getText(self, 'This PDF is locked', 'Enter Password :', 2)[0]
            if password == '' :
                if self.doc == None: sys.exit(1)#exit if first document
                else : return
            unlocked = doc.unlock(password)
            if not unlocked:
                return QMessageBox.critical(self, "Failed !","Incorrect Password")
            self.passwd = password
            self.lockUnlockAction.setText("Save Unlocked")
        else:
            self.lockUnlockAction.setText("Encrypt PDF")
        self.removeOldDoc()
        self.doc = doc
        self.filename = filename
        self.pages_count = self.doc.pageCount()
        self.curr_page_no = 1
        self.rendered_pages = []
        self.getOutlines()
        # Load Document in other threads
        self.loadFileRequested.emit(self.filename, password)
        if collapseUser(self.filename) in self.history_filenames:
            self.curr_page_no = int(self.history_page_no[self.history_filenames.index(collapseUser(self.filename))])
        self.curr_page_no = min(self.curr_page_no, self.pages_count)
        self.scroll_render_lock = False
        # Show/Add widgets
        if self.doc.hasEmbeddedFiles():
            self.attachAction.setVisible(True)
        self.frame = Frame(self.scrollAreaWidgetContents, self.scrollArea)
        self.verticalLayout = QVBoxLayout(self.frame)
        self.horizontalLayout_2.addWidget(self.frame)
        self.scrollArea.verticalScrollBar().setValue(0)
        self.frame.jumpToRequested.connect(self.jumpToPage)
        self.frame.copyTextRequested.connect(self.copyText)
        self.frame.showStatusRequested.connect(self.showStatus)

        # Render 4 pages, (Preload 3 pages)
        self.max_preload = min(4, self.pages_count)
        # Add pages
        for i in range(self.pages_count):
            page = PageWidget(i+1, self.frame)
            self.verticalLayout.addWidget(page, 0, Qt.AlignCenter)
            self.pages.append(page)
        self.resizePages()
        self.pageNoLabel.setText('<b>%i/%i</b>' % (self.curr_page_no, self.pages_count) )
        self.gotoPageValidator.setTop(self.pages_count)
        self.setWindowTitle(os.path.basename(self.filename)+ " - Gospel PDF " + __version__)
        if self.curr_page_no != 1 :
            QTimer.singleShot(150+self.pages_count//3, self.jumpToCurrentPage)

    def setRenderedImage(self, page_no, image):
        """ takes a QImage and sets pixmap of the specified page
            when number of rendered pages exceeds a certain number, old page image is
            deleted to save memory """
        debug("Set Rendered Image :", page_no)
        self.pages[page_no-1].setPageData(page_no, QPixmap.fromImage(image), self.doc)
        # Request to render next page
        if self.curr_page_no <= page_no < (self.curr_page_no + self.max_preload - 2):
            if (page_no+2 not in self.rendered_pages) and (page_no+2 <= self.pages_count):
              self.rendered_pages.append(page_no+2)
              self.renderRequested.emit(page_no+2, self.pages[page_no+1].dpi)
        # Replace old rendered pages with blank image
        if len(self.rendered_pages)>10:
            cleared_page_no = self.rendered_pages.pop(0)
            debug("Clear Page :", cleared_page_no)
            self.pages[cleared_page_no-1].clear()
        debug("Rendered Pages :", self.rendered_pages)

    def renderCurrentPage(self):
        """ Requests to render current page. if it is already rendered, then request
            to render next unrendered page """
        requested = 0
        for page_no in range(self.curr_page_no, self.curr_page_no+self.max_preload):
            # using self.pages_count instead of len(self.pages) caused crash sometimes
            if (page_no not in self.rendered_pages) and (page_no <= len(self.pages)):
                self.rendered_pages.append(page_no)
                self.renderRequested.emit(page_no, self.pages[page_no-1].dpi)
                requested += 1
                debug("Render Requested :", page_no)
                if requested == 2: return

    def onMouseScroll(self, pos):
        """ It is called when vertical scrollbar value is changed.
            Get the current page number on scrolling, then requests to render"""
        index = self.verticalLayout.indexOf(self.frame.childAt(int(self.frame.width()/2), int(pos)))
        if index == -1: return
        self.pageNoLabel.setText('<b>%i/%i</b>' % (index+1, self.pages_count) )
        if self.scrollArea.verticalScrollBar().isSliderDown() or self.scroll_render_lock : return
        self.curr_page_no = index+1
        self.renderCurrentPage()

    def onSliderRelease(self):
        self.onMouseScroll(self.scrollArea.verticalScrollBar().value())

    def openFile(self):
        filename, sel_filter = QFileDialog.getOpenFileName(self,
                                      "Select Document to Open", self.filename,
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
        filename, ext = os.path.splitext(self.filename)
        new_name = filename + "-unlocked.pdf"
        proc = Popen(["qpdf", "--decrypt", "--password="+self.passwd, self.filename, new_name])
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
        filename, ext = os.path.splitext(self.filename)
        new_name = filename + "-locked.pdf"
        proc = Popen(["qpdf", "--encrypt", password, password, '128', '--', self.filename, new_name])
        stdout, stderr = proc.communicate()
        if proc.returncode == 0:
            basename = os.path.basename(new_name)
            notifier = Notifier(self)
            notifier.showNotification("Successful !", "File saved as\n"+basename)
        else:
            QMessageBox.warning(self, "Failed !", "Failed to save as Encrypted")

    def printFile(self):
        if which("quikprint"):
            Popen(["quikprint", self.filename])
            return
        printer = QPrinter(QPrinter.HighResolution)
        dlg = QPrintDialog(printer, self)
        dlg.setOption(dlg.PrintCurrentPage, True)
        dlg.setMinMax(1, self.doc.pageCount())
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
            to_page = printer.toPage() or self.doc.pageCount()
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
            img = self.doc.renderPage(page_no, render_dpi)
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
                    filename = os.path.splitext(self.filename)[0]+'-'+str(page_no)+'.jpg'
                    img = self.doc.renderPage(page_no, dpi)
                    img.save(filename)
                notifier = Notifier(self)
                notifier.showNotification("Successful !","Image(s) has been saved")
            except:
                QMessageBox.warning(self, "Failed !","Failed to export to Image")

    def docInfo(self):
        info = self.doc.info()
        page_size = "%.1f x %.1f pts" % self.doc.pageSize(self.curr_page_no)
        info['Page Size'] = page_size
        dialog = DocInfoDialog(info, self)
        dialog.exec_()

    def jumpToCurrentPage(self):
        """ this is used as a slot, to connect with a timer"""
        self.jumpToPage(self.curr_page_no)

    def jumpToPage(self, page_num, top=0.0):
        """ scrolls to a particular page and position """
        if page_num < 1: page_num = 1
        elif page_num > self.pages_count: page_num = self.pages_count
        top *= self.pages[page_num-1].dpi/72
        if not (0 < top < self.pages[page_num-1].height()): top = 0
        self.jumped_from = self.curr_page_no
        self.curr_page_no = page_num
        scrollbar_pos = self.pages[page_num-1].pos().y()
        scrollbar_pos += top
        self.scrollArea.verticalScrollBar().setValue(int(scrollbar_pos))

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

    def availableWidth(self):
        """ Returns available width for rendering a page """
        dock_width = 0 if self.dockWidget.isHidden() else self.dockWidget.width()
        return self.width() - dock_width - 50

    def resizePages(self):
        ''' Resize all pages according to zoom level '''
        page_dpi = self.zoom_levels[self.zoomLevelCombo.currentIndex()]*SCREEN_DPI/100
        fixed_width = self.availableWidth()
        for i in range(self.pages_count):
            pg_width, pg_height = self.doc.pageSize(i+1) # width in points
            if self.zoomLevelCombo.currentIndex() == 0: # if Fit Width
                dpi = int(72.0*fixed_width/pg_width)
            else:
                dpi = int(page_dpi)
            self.pages[i].dpi = dpi
            self.pages[i].setFixedSize(int(pg_width*dpi/72), int(pg_height*dpi/72))
        for page_no in self.rendered_pages:
            self.pages[page_no-1].clear()
        self.rendered_pages = []
        self.renderCurrentPage()

    def setZoom(self, index):
        """ Gets called when zoom level is changed"""
        self.scroll_render_lock = True # rendering on scroll is locked as set scroll position
        self.resizePages()
        QTimer.singleShot(300, self.afterZoom)

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

    def afterZoom(self):
        scrolbar_pos = self.pages[self.curr_page_no-1].pos().y()
        self.scrollArea.verticalScrollBar().setValue(scrolbar_pos)
        self.scroll_render_lock = False
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

    def findNext(self):
        """ search text in current page and next pages """
        text = self.findTextEdit.text()
        if text == "" : return
        # search from current page when text changed
        if self.search_text != text or self.search_result_page == 0:
            search_from_page = self.curr_page_no
        else:
            search_from_page = self.search_result_page + 1
        self.findTextRequested.emit(text, search_from_page, False)
        if self.search_result_page != 0:     # clear previous highlights
            self.pages[self.search_result_page-1].highlight_area = None
            self.pages[self.search_result_page-1].updateImage()
            self.search_result_page = 0
        self.search_text = text

    def findBack(self):
        """ search text in pages before current page """
        text = self.findTextEdit.text()
        if text == "" : return
        if self.search_text != text or self.search_result_page == 0:
            search_from_page = self.curr_page_no
        else:
            search_from_page = self.search_result_page - 1
        self.findTextRequested.emit(text, search_from_page, True)
        if self.search_result_page != 0:
            self.pages[self.search_result_page-1].highlight_area = None
            self.pages[self.search_result_page-1].updateImage()
            self.search_result_page = 0
        self.search_text = text

    def onTextFound(self, page_no, areas):
        self.pages[page_no-1].highlight_area = areas
        self.search_result_page = page_no
        if self.pages[page_no-1].pixmap():
            self.pages[page_no-1].updateImage()
        first_result_pos = areas[0][1]
        self.jumpToPage(page_no, first_result_pos)

#########      Cpoy Text to Clip Board      #########
    def toggleCopyText(self, checked):
        self.frame.enableCopyTextMode(checked)

    def copyText(self, page_no, rect):
        zoom = self.pages[page_no-1].dpi/72
        rect = [x/zoom for x in rect]
        # Copy text to clipboard
        text = self.doc.getPageText(page_no, rect)
        QApplication.clipboard().setText(text)
        self.copyTextAction.setChecked(False)
        self.toggleCopyText(False)

##########      Other Functions      ##########

    def getOutlines(self):
        toc = self.doc.toc()
        if not toc:
            self.dockWidget.hide()
            return
        self.dockWidget.show()
        outline_model = QStandardItemModel(self)
        parent_item = outline_model.invisibleRootItem()
        parent_items = [parent_item]

        for level,title,page_no,top in toc:
            parent_item = parent_items[level-1]
            item = QStandardItem(title)
            if page_no>0:
                item.setData(page_no, Qt.UserRole + 1)
                item.setData(top, Qt.UserRole + 2)

                pageItem = item.clone()
                pageItem.setText(str(page_no))
                pageItem.setTextAlignment(Qt.AlignRight)
                parent_item.appendRow([item, pageItem])
            else:
                parent_item.appendRow([item])

            while len(parent_items)!=level:
                parent_items.pop()
            parent_items.append(item)

        self.treeView.setModel(outline_model)
        if parent_item.rowCount() < 4:
            self.treeView.expandToDepth(0)
        self.treeView.setHeaderHidden(True)
        self.treeView.header().setSectionResizeMode(0, 1)
        self.treeView.header().setSectionResizeMode(1, 3)
        self.treeView.header().setStretchLastSection(False)

    def onOutlineClick(self, m_index):
        page_num = self.treeView.model().data(m_index, Qt.UserRole+1)
        top = self.treeView.model().data(m_index, Qt.UserRole+2)
        if not page_num: return
        self.jumpToPage(page_num, top)

    def showStatus(self, url):
        if url=="":
            self.statusbar.hide()
            return
        self.statusbar.setText(url)
        self.statusbar.adjustSize()
        self.statusbar.move(0, self.height()-self.statusbar.height())
        self.statusbar.show()

    def resizeEvent(self, ev):
        QMainWindow.resizeEvent(self, ev)
        if self.filename == '' : return
        if self.zoomLevelCombo.currentIndex() == 0:
            self.resize_page_timer.start(200)

    def onWindowResize(self):
        for i in range(self.pages_count):
            self.pages[i].annots_listed = False # Clears prev link annotation positions
        self.resizePages()
        wait(300)
        self.jumpToCurrentPage()
        if not self.isMaximized():
            self.settings.setValue("WindowWidth", self.width())
            self.settings.setValue("WindowHeight", self.height())

    def saveFileData(self):
        if self.filename != '':
            filename = collapseUser(self.filename)
            if filename in self.history_filenames:
                index = self.history_filenames.index(filename)
                self.history_page_no[index] = self.curr_page_no
            else:
                self.history_filenames.insert(0, filename)
                self.history_page_no.insert(0, self.curr_page_no)
            if filename in self.recent_files:
                self.recent_files.remove(filename)
            self.recent_files.insert(0, filename)

    def showAbout(self):
        lines = ("<h1>Gospel Pdf Viewer</h1>",
            "A Fast Simple Pdf Viewer using PyMupdf or Poppler<br><br>",
            "Version : %s<br>" % __version__,
            "Qt : %s<br>" % qVersion(),
            "%s : %s<br>" % (backend, backend_version),
            "Copyright &copy; %s %s &lt;%s&gt;" % (COPYRIGHT_YEAR, AUTHOR_NAME, AUTHOR_EMAIL))
        QMessageBox.about(self, "About Gospel Pdf Viewer", "".join(lines))

    def closeEvent(self, ev):
        """ Save all settings on window close """
        self.saveFileData()
        self.settings.setValue("ZoomLevel", self.zoomLevelCombo.currentIndex())
        self.settings.setValue("HistoryFileNameList", self.history_filenames[:100])
        self.settings.setValue("HistoryPageNoList", self.history_page_no[:100])
        self.settings.setValue("RecentFiles", self.recent_files[:10])
        return QMainWindow.closeEvent(self, ev)

    def onAppQuit(self):
        """ Close running threads """
        loop1 = QEventLoop()
        loop2 = QEventLoop()
        self.thread1.finished.connect(loop1.quit)
        self.thread2.finished.connect(loop2.quit)
        self.thread1.quit()
        loop1.exec_()
        self.thread2.quit()
        loop2.exec_()



class Frame(QFrame):
    """ This widget is a container of PageWidgets. PageWidget communicates
        Window through this widget """
    jumpToRequested = pyqtSignal(int, float)
    copyTextRequested = pyqtSignal(int, list)
    showStatusRequested = pyqtSignal(str)
    # parent is scrollAreaWidgetContents
    def __init__(self, parent, scrollArea):
        QFrame.__init__(self, parent)
        self.setFrameShape(QFrame.StyledPanel)
        self.setFrameShadow(QFrame.Raised)
        self.vScrollbar = scrollArea.verticalScrollBar()
        self.hScrollbar = scrollArea.horizontalScrollBar()
        self.setMouseTracking(True)
        self.clicked = False
        self.copy_text_mode = False

    def mousePressEvent(self, ev):
        self.click_pos = ev.globalPos()
        self.v_scrollbar_pos = self.vScrollbar.value()
        self.h_scrollbar_pos = self.hScrollbar.value()
        self.clicked = True

    def mouseReleaseEvent(self, ev):
        self.clicked = False

    def mouseMoveEvent(self, ev):
        if not self.clicked : return
        self.vScrollbar.setValue(self.v_scrollbar_pos + self.click_pos.y() - ev.globalY())
        self.hScrollbar.setValue(self.h_scrollbar_pos + self.click_pos.x() - ev.globalX())

    def jumpTo(self, page_num, top):
        self.jumpToRequested.emit(page_num, top)

    def enableCopyTextMode(self, enable):
        self.copy_text_mode = enable

    def copyText(self, page_num, rect):
        self.copyTextRequested.emit(page_num, rect)

    def showStatus(self, msg):
        self.showStatusRequested.emit(msg)


class PageWidget(QLabel):
    """ This widget shows a rendered page """
    def __init__(self, page_num, frame=None):
        QLabel.__init__(self, frame)
        self.manager = frame
        self.setMouseTracking(True)
        self.setSizePolicy(0,0)
        self.link_areas = []
        self.link_annots = []
        self.annots_listed, self.copy_text_mode = False, False
        self.click_point, self.highlight_area = None, None
        self.page_num = page_num
        self.image = QPixmap()
        self.dpi = 72# dpi is set when pages are resized

    def setPageData(self, page_no, pixmap, doc):
        self.image = pixmap
        self.updateImage()
        if self.annots_listed : return
        links = doc.pageLinkAnnotations(page_no)
        for link in links:
            subtype,rect,data = link
            x,y,w,h = [x*self.dpi/72 for x in rect]
            self.link_areas.append(QRectF(x,y, w+1, h+1))
            self.link_annots.append(link)
        self.annots_listed = True

    def clear(self):
        QLabel.clear(self)
        self.image = QPixmap()

    def mouseMoveEvent(self, ev):
        # Draw rectangle when mouse is clicked and dragged in copy text mode.
        if self.manager.copy_text_mode:
            if self.click_point:
                pm = self.pm.copy()
                painter = QPainter()
                painter.begin(pm)
                painter.drawRect(QRectF(self.click_point, ev.pos()))
                painter.end()
                self.setPixmap(pm)
            return

        # Change cursor if cursor is over link annotation
        for i, area in enumerate(self.link_areas):
            if area.contains(ev.pos()):
                subtype,rect,data = self.link_annots[i]
                # For jump to page link
                if subtype == "GoTo":
                    self.manager.showStatus("Jump To Page : %i" % data[0])
                    self.setCursor(Qt.PointingHandCursor)
                # For URL link
                elif subtype == "URI":
                    self.manager.showStatus("URL : %s" % data)
                    self.setCursor(Qt.PointingHandCursor)
                return
        self.manager.showStatus("")
        self.unsetCursor()
        ev.ignore()         # pass to underlying frame if not over link or copy text mode

    def mousePressEvent(self, ev):
        # In text copy mode
        if self.manager.copy_text_mode:
            self.click_point = ev.pos()
            self.pm = self.pixmap().copy()
            return
        # In normal mode
        for i, area in enumerate(self.link_areas):
            if not area.contains(ev.pos()):
                continue
            subtype,rect,data = self.link_annots[i]
            # For jump to page link, data==(page_no,top)
            if subtype == "GoTo":
                self.manager.jumpTo(*data)
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
        if self.manager.copy_text_mode:
            rect = QRectF(self.click_point, ev.pos()).getRect()
            self.manager.copyText(self.page_num, list(rect))
            self.setPixmap(self.pm)
            self.click_point = None
            self.pm = None
            return
        ev.ignore()

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




class Notifier(QSystemTrayIcon):
    def __init__(self, parent):
        QSystemTrayIcon.__init__(self, QIcon(':/icons/adobe.png'), parent)
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
