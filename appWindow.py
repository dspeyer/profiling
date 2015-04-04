#!/usr/bin/python

import gtk
import pango

class AppWindow:
    def __init__(self, starttime, endtime):
        self.starttime=starttime
        self.endtime=endtime

        self.window = gtk.Window(gtk.WINDOW_TOPLEVEL)

        mainVBox = gtk.VBox()
        hbox = gtk.HBox()

        self.toolbar = gtk.HBox()

        zi=gtk.Button('Zoom In')
        zi.connect('clicked', self.zoom, 2)
        zo=gtk.Button('Zoom Out')
        zo.connect('clicked', self.zoom, 0.5)

        vscroll = gtk.ScrolledWindow()
        vscroll.set_policy(gtk.POLICY_NEVER, gtk.POLICY_ALWAYS)
        vscroll.set_size_request(800,600)

        hscroll = gtk.ScrolledWindow()
        hscroll.set_policy(gtk.POLICY_ALWAYS, gtk.POLICY_NEVER)
        hscroll.get_hscrollbar().set_child_visible(False)

        self.legend = gtk.VBox()

        self.content = gtk.DrawingArea()

        self.hadj=adjustment=hscroll.get_hadjustment()
        hscrollbar = gtk.HScrollbar(self.hadj)

        self.window.add(mainVBox)
        mainVBox.pack_start(self.toolbar, expand=False, fill=False)
        mainVBox.pack_start(vscroll, expand=True, fill=True)
        mainVBox.pack_start(hscrollbar, expand=False, fill=False)
        self.toolbar.add(zi)
        self.toolbar.add(zo)
        vscroll.add_with_viewport(hbox)
        hbox.pack_start(self.legend, expand=False, fill=False)
        hbox.pack_start(hscroll, expand=True, fill=True)
        hscroll.add_with_viewport(self.content)

        self.content.realize()
        self.gc = self.content.get_style().fg_gc[gtk.STATE_NORMAL]
        self.white_gc = self.content.get_style().white_gc
        colormap = self.content.get_colormap()
        self.red_gc =  self.content.window.new_gc()
        self.red_gc.copy(self.gc)
        self.red_gc.foreground=colormap.alloc_color(gtk.gdk.Color(red=65535, green=0, blue=0))
        self.pink_gc =  self.content.window.new_gc()
        self.pink_gc.copy(self.gc)
        self.pink_gc.foreground=colormap.alloc_color(gtk.gdk.Color(red=65535, green=32768, blue=32768))
        self.blue_gc =  self.content.window.new_gc()
        self.blue_gc.copy(self.gc)
        self.blue_gc.foreground=colormap.alloc_color(gtk.gdk.Color(red=32768, green=32768, blue=65535))
        self.grey_gc =  self.content.window.new_gc()
        self.grey_gc.copy(self.gc)
        self.grey_gc.foreground=colormap.alloc_color(gtk.gdk.Color(red=49152, green=49152, blue=49152))

        self.pixmap = gtk.gdk.Pixmap(self.content.window, 1, 1)
        self.content.connect('expose-event', self.expose_event)

        self.font = self.window.create_pango_context()

        self.width=2000


    def zoom(self, widget, ratio):
        self.width=int(ratio*self.width)
        self.redraw()
        self.hadj.set_value(int(self.hadj.get_value()*ratio))

    def expose_event(self, widget, event):
        x , y, width, height = event.area
        widget.window.draw_drawable(self.gc, self.pixmap, x, y, x, y, width, height)
        return False

    def xfromt(self,t):
        return int(self.width*(t-self.starttime)/(self.endtime-self.starttime))

    def draw_rectangle(self, gc, start, end, h, text):
        x1 = self.xfromt(start)
        x2 = self.xfromt(end)
        y1 = h
        self.pixmap.draw_rectangle(gc, True, x1, y1, x2-x1, self.rowheight)
        if text:
            layout=pango.Layout(self.font)
            layout.set_text(text)
            self.gc.set_clip_rectangle(gtk.gdk.Rectangle(x1, y1, x2-x1, self.rowheight))
            self.pixmap.draw_layout(self.gc, x1, y1, layout)
            self.gc.set_clip_rectangle(gtk.gdk.Rectangle(0, 0, self.width, self.height))

    def draw_line(self, gc, t1, y1, t2, y2):
        self.pixmap.draw_line(gc, self.xfromt(t1), y1, self.xfromt(t2), y2)
