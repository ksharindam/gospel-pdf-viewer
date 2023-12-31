# -*- coding: utf-8 -*-
from PyQt5.QtCore import QRectF
from PyQt5.QtGui import QImage


def import_fitz():
    global fitz, backend_version
    import fitz
    backend_version = fitz.version[0]

def import_poppler():
    global Poppler, backend_version
    from popplerqt5 import Poppler, poppler_version
    backend_version = "%i.%i.%i" % poppler_version()

#backends = [("fitz", import_fitz), ("poppler", import_poppler), ]
backends = [("poppler", import_poppler), ("fitz", import_fitz), ]

for backend, import_func in backends:
    try:
        import_func()
        break
    except : pass



class PdfDocument:
    """ Wrapper class of pdf backend library """
    def __init__(self, filename):
        if backend=="poppler":
            self.doc = Poppler.Document.load(filename)
            if self.doc:
                self.doc.setRenderHint(Poppler.Document.TextAntialiasing | Poppler.Document.TextHinting |
                         Poppler.Document.Antialiasing | Poppler.Document.ThinLineSolid )

        elif backend=="fitz":
            try:
                self.doc = fitz.open(filename, filetype="pdf")
            except:
                self.doc = None

    def isValid(self):
        return bool(self.doc)

    def isLocked(self):
        """ returns False after document is unlocked """
        if backend=="poppler":
            return self.doc.isLocked()
        elif backend=="fitz":
            return self.doc.is_encrypted

    def unlock(self, password):
        """ Unlock a password protected PDF. returns True on success """
        if backend=="poppler":
            locked = self.doc.unlock(password.encode(), password.encode())
            self.doc.setRenderHint(Poppler.Document.TextAntialiasing | Poppler.Document.TextHinting |
                         Poppler.Document.Antialiasing | Poppler.Document.ThinLineSolid )
            return not locked

        elif backend=="fitz":
            return self.doc.authenticate(password)# returns 1,2,4 or 6 if successful

    def pageCount(self):
        if backend=="poppler":
            return self.doc.numPages()
        elif backend=="fitz":
            return len(self.doc)# or self.doc.page_count

    def hasEmbeddedFiles(self):
        if backend=="poppler":
            return self.doc.hasEmbeddedFiles()
        elif backend=="fitz":
            return self.doc.embfile_count()

    def info(self):
        """ returns document info as dict """
        if backend=="poppler":
            return {key:self.doc.info(key) for key in self.doc.infoKeys()}
        elif backend=="fitz":
            metadata = self.doc.metadata or {}
            return {key:val for key,val in metadata.items() if val}

    def toc(self):
        """ returns list of lists. each entry is in [level, title, page_no, top]
         format. level starts from 1. top has value in point """
        result = []
        if backend=="poppler":
            toc = self.doc.toc()
            if not toc:
                return []
            stack = [(toc.firstChild(), 1)]
            while stack:
                node, level = stack.pop()
                elm = node.toElement()

                linkDestination = None
                if elm.hasAttribute("Destination"):
                    linkDestination = Poppler.LinkDestination(elm.attribute("Destination"))
                elif elm.hasAttribute("DestinationName"):
                    linkDestination = self.doc.linkDestination(elm.attribute("DestinationName"))

                page_no, top = -1, 0.0

                if linkDestination:
                    # top may be not in range 0.0->1.0, we have to take care of that
                    page_num = linkDestination.pageNumber()
                    if 0 < page_num <= self.doc.numPages():
                        page_no = page_num
                        top = linkDestination.top() if linkDestination.isChangeTop() else 0
                        top *= self.doc.page(page_num-1).pageSizeF().height()# convert to pt

                result.append([level, elm.tagName(), page_no, top])

                # Load next sibling
                siblingNode = node.nextSibling()
                if not siblingNode.isNull():
                    stack.append((siblingNode,level))

                # Load its child
                childNode = node.firstChild()
                if not childNode.isNull():
                    stack.append((childNode,level+1))

        elif backend=="fitz":
            toc = self.doc.get_toc(simple=False)
            for lvl,title,page_no,dest in toc:
                top = dest["to"].y if dest["kind"]==fitz.LINK_GOTO else 0.0
                result.append([lvl, title, page_no, top])

        return result


    def pageSize(self, page_no):
        """ returns page (width,height) in points """
        if backend=="poppler":
            page_size = self.doc.page(page_no-1).pageSizeF()
            return page_size.width(), page_size.height()
        elif backend=="fitz":
            rect  = self.doc[page_no-1].rect
            return rect.width, rect.height

    def renderPage(self, page_no, dpi):
        """ @int page_no, @int dpi (mupdf only accepts int as dpi val)"""
        if backend=="poppler":
            page = self.doc.page(page_no-1)
            if page:
                return page.renderToImage(dpi, dpi)

        elif backend=="fitz":
            pix = self.doc.get_page_pixmap(page_no-1, dpi=int(dpi))
            return QImage(pix.samples, pix.w, pix.h, pix.stride, QImage.Format_RGB888)


    def pageLinkAnnotations(self, page_no):
        """ returns list of annotations. Each annot is in [type, rect, target] format.
        If type is 'GoTo', target is (page_no,top) tuple.
        If type is URI, target is url str """
        result = []
        if backend=="poppler":
            page = self.doc.page(page_no-1)
            page_w, page_h = page.pageSizeF().width(), page.pageSizeF().height()
            if not page:
                return []
            annots = page.annotations()
            for annot in annots:
                if annot.subType() == Poppler.Annotation.ALink:
                    dest = annot.linkDestination()
                    if not dest:
                        continue
                    x, y = annot.boundary().left()*page_w, annot.boundary().top()*page_h
                    w, h = annot.boundary().width()*page_w, annot.boundary().height()*page_h
                    if dest.linkType() == Poppler.Link.Goto:
                        page_num = dest.destination().pageNumber()
                        # top has val from 0.0 to 1.0
                        top = dest.destination().isChangeTop() and dest.destination().top() or 0.0
                        result.append(["GoTo", (x,y,w,h), (page_num,top*page_h)])
                    elif dest.linkType() == Poppler.Link.Browse:
                        url = dest.url()
                        result.append(["URI", (x,y,w,h), url])

        elif backend=="fitz":
            page = self.doc.load_page(page_no-1)
            page_rect = page.rect
            if not page:
                return []
            links = page.get_links()
            for link in links:
                rect = link["from"]
                x, y, w, h = rect.x0-page_rect.x0, rect.y0-page_rect.y0, rect.width, rect.height
                if link["kind"]==fitz.LINK_URI:
                    result.append(["URI", [x,y,w,h], link["uri"]])
                elif link["kind"]==fitz.LINK_GOTO:
                    top = link["to"].y
                    result.append(["GoTo", [x,y,w,h], (link["page"]+1,top)])
                elif link["kind"]==fitz.LINK_NAMED:
                    page_no = parse_named_dest(link["name"])
                    if page_no>0:
                        result.append(["GoTo", [x,y,w,h], (page_no,0)])
                    #print(link["name"])
        return result

    def getPageText(self, page_no, rect):
        """ rect must be in [x,y,w,h] format with vals in points. returns text str """
        if backend=="poppler":
            return self.doc.page(page_no-1).text(QRectF(*rect))

        elif backend=="fitz":
            #see https://github.com/pymupdf/PyMuPDF-Utilities/tree/master/textbox-extraction
            page = self.doc.load_page(page_no-1)
            x,y,w,h = rect
            return page.get_textbox(fitz.Rect(x,y,x+w,y+h))

    def findText(self, page_no, text):
        """ returns a list of rects """
        if backend=="poppler":
            page = self.doc.page(page_no-1)
            rects = page.search(text,Poppler.Page.CaseInsensitive,0)
            return [list(rect.getRect()) for rect in rects]
        elif backend=="fitz":
            rects = self.doc.search_page_for(page_no-1, text)
            return [[rect.x0,rect.y0,rect.width,rect.height] for rect in rects ]


# text is like 'page=645&zoom=100,-5,338' or page=95&view=Fit
def parse_named_dest(text):
    # still could not find any documentation. so can not parse other information
    i = text.find("page=")
    if i<0:
        return -1
    text = text[i+5:]
    page_no = ""
    for ch in text:
        if not ch.isdigit():
            break
        page_no += ch
    return int(page_no)
