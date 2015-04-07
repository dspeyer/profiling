#!/usr/bin/python

import gtk
import pango
import math

class AppWindow:
    def __init__(self, starttime, endtime):

        self.start_expose_event=1
        self.finish_expose_event=1

        self.starttime=starttime
        self.endtime=endtime

        self.window = gtk.Window(gtk.WINDOW_TOPLEVEL)
        self.window.set_default_size(800,600)

        mainVBox = gtk.VBox()
        hbox = gtk.HBox()

        self.toolbar = gtk.HBox()

        zi=gtk.Button('Zoom In')
        zi.connect('clicked', self.zoom, 2)
        zo=gtk.Button('Zoom Out')
        zo.connect('clicked', self.zoom, 0.5)

        vscroll = gtk.ScrolledWindow()
        vscroll.set_policy(gtk.POLICY_NEVER, gtk.POLICY_ALWAYS)

        hscroll = gtk.ScrolledWindow()
        hscroll.set_policy(gtk.POLICY_ALWAYS, gtk.POLICY_NEVER)
        hscroll.get_hscrollbar().set_child_visible(False)
    
        tscroll = gtk.ScrolledWindow(hadjustment=hscroll.get_hadjustment())
        tscroll.set_policy(gtk.POLICY_ALWAYS, gtk.POLICY_NEVER)
        tscroll.get_hscrollbar().set_child_visible(False)

        self.legend = gtk.VBox()

        self.content = gtk.DrawingArea()
        self.timing = gtk.DrawingArea()

        self.hadj=adjustment=hscroll.get_hadjustment()
        hscrollbar = gtk.HScrollbar(self.hadj)

        self.window.add(mainVBox)
        mainVBox.pack_start(self.toolbar, expand=False, fill=False)
        mainVBox.pack_start(vscroll, expand=True, fill=True)
        mainVBox.pack_start(tscroll, expand=False, fill=False)
        mainVBox.pack_start(hscrollbar, expand=False, fill=False)
        self.toolbar.add(zi)
        self.toolbar.add(zo)
        vscroll.add_with_viewport(hbox)
        hbox.pack_start(self.legend, expand=False, fill=False)
        hbox.pack_start(hscroll, expand=True, fill=True)
        hscroll.add_with_viewport(self.content)
        tscroll.add_with_viewport(self.timing)

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
        self.purple_gc =  self.content.window.new_gc()
        self.purple_gc.copy(self.gc)
        self.purple_gc.foreground=colormap.alloc_color(gtk.gdk.Color(red=49152, green=32768, blue=65535))

        self.timing.realize()

        self.pmwidth = 1
        self.offset = 0

        self.pixmap = gtk.gdk.Pixmap(self.content.window, 23, 1)
        self.content.connect('expose-event', self.expose_event, 'pixmap')

        self.timingpixmap = gtk.gdk.Pixmap(self.timing.window, 34, 1)
        self.timing.connect('expose-event', self.expose_event, 'timingpixmap')

        self.font = self.window.create_pango_context()

        self.width=2000
        self.rowheight=20

        self.id=AppWindow.id
        AppWindow.id+=1
        self.redraw_time()

    def redraw_time(self):
        lx, ly, lwidth, lheight = self.legend.get_allocation()
        self.timing.set_size_request(self.width+lwidth, self.rowheight)
        self.timingpixmap.draw_rectangle(self.white_gc, True, 0, 0, self.width+lwidth, self.rowheight)
        gc = self.timing.get_style().fg_gc[gtk.STATE_NORMAL]
        gap=(150./self.width)*(self.endtime-self.starttime)
        t=self.starttime
        while t<self.endtime:
            layout=pango.Layout(self.font)
            layout.set_text('%f'%t)
            self.timingpixmap.draw_layout(gc, self.xfromt(t)+lwidth, 0, layout)
            t+=gap
        self.timing.queue_draw_area(0, 0, self.width, self.rowheight)


    def zoom(self, widget, ratio):
        self.width=int(ratio*self.width)
        self.content.set_size_request(self.width, self.height)
        self.redraw()
        self.hadj.set_value(int(self.hadj.get_value()*ratio))
        self.redraw_time()

    def expose_event(self, widget, event, pmname):
        if self.finish_expose_event != self.start_expose_event:
            print '%d!=%d'%(self.finish_expose_event,self.start_expose_event)
        self.start_expose_event+=1
        x , y, width, height = event.area
        #print "x=%d y=%d w=%d h=%d hadj=%f offset=%d pmwidth=%d"%(x,y,width,height,self.hadj.get_value(),self.offset,self.pmwidth)
        if x-self.offset<0 or x+width-self.offset>self.pmwidth:
            winwidth=self.window.get_size()[0]
            if self.pmwidth<2*winwidth:
                self.pmwidth=2*winwidth
                #print "new width: %d"%self.pmwidth
                self.pixmap=gtk.gdk.Pixmap(widget.window, self.pmwidth, self.height)
                self.timingpixmap=gtk.gdk.Pixmap(widget.window, self.pmwidth, self.rowheight)
            self.offset=max(0,int(self.hadj.get_value()-winwidth/2))
            self.redraw()
            self.redraw_time()
        #widget.window.draw_rectangle(self.blue_gc, True, x, y, width, height)
        #print "copying %d...%d from a %d wide pixmap"%(x-self.offset, x-self.offset+width, self.__dict__[pmname].get_size()[0])
        widget.window.draw_drawable(self.gc, self.__dict__[pmname], x-self.offset, y, x, y, width, height)
        self.finish_expose_event+=1
        return False

    def xfromt(self,t):
        return int(self.width*(t-self.starttime)/(self.endtime-self.starttime))-self.offset

    def draw_rectangle(self, gc, start, end, h, text):
        x1 = self.xfromt(start)
        x2 = self.xfromt(end)
        if x2<0 or x1>self.pmwidth:
            return
        y1 = h
        self.pixmap.draw_rectangle(gc, True, x1, y1, x2-x1, self.rowheight-1)
        if text:
            layout=pango.Layout(self.font)
            layout.set_text(text)
            self.gc.set_clip_rectangle(gtk.gdk.Rectangle(x1, y1, x2-x1, self.rowheight-1))
            tw=layout.get_pixel_size()[0]
            x=x1
            while x==x1 or x+tw<x2:
                self.pixmap.draw_layout(self.gc, x, y1, layout)
                x+=max(2*tw,400)
            self.gc.set_clip_rectangle(gtk.gdk.Rectangle(0, 0, max(self.width,self.pmwidth), self.height))

    def draw_line(self, gc, t1, y1, t2, y2):
        x1=self.xfromt(t1)
        x2=self.xfromt(t2)
        if x2<0 or x1>self.pmwidth:
            return        
        self.pixmap.draw_line(gc, x1, y1, x2, y2)


AppWindow.id=0
