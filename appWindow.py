#!/usr/bin/python

import gtk
import pango
import math

class AppWindow:
    def __init__(self, starttime, endtime, fn):

        self.start_expose_event=1
        self.finish_expose_event=1

        self.starttime=starttime
        self.endtime=endtime
        self.starttimelabels=starttime
        self.endtimelabels=endtime
        self.fn=fn

        self.window = gtk.Window(gtk.WINDOW_TOPLEVEL)
        self.window.set_default_size(800,600)

        mainHBox = gtk.HBox()
        mainVBox = gtk.VBox()
        vbox2 = gtk.VBox()
        hbox = gtk.HBox()

        self.toolbar = gtk.HBox()

        zi=gtk.Button('Zoom In')
        zi.connect('clicked', self.zoom, 2)
        zo=gtk.Button('Zoom Out')
        zo.connect('clicked', self.zoom, 0.5)
        self.raw_times = False;
        rt=gtk.ToggleButton('Raw Times')
        rt.connect('clicked', self.toggle_raw_times)
        save=gtk.Button('Save as Image')
        save.connect('clicked', self.get_filename_and_callback, self.save_part2, 'png')

        vscroll = gtk.ScrolledWindow()
        vscroll.set_policy(gtk.POLICY_NEVER, gtk.POLICY_ALWAYS)

        hscroll = gtk.ScrolledWindow()
        hscroll.set_policy(gtk.POLICY_ALWAYS, gtk.POLICY_NEVER)
        hscroll.get_hscrollbar().set_child_visible(False)
    
        tscroll = gtk.ScrolledWindow(hadjustment=hscroll.get_hadjustment())
        tscroll.set_policy(gtk.POLICY_ALWAYS, gtk.POLICY_NEVER)
        tscroll.get_hscrollbar().set_child_visible(False)

        self.legend = gtk.VBox()
        self.nsLegend = gtk.VBox()

        self.content = gtk.DrawingArea()
        self.timing = gtk.DrawingArea()

        self.hadj=adjustment=hscroll.get_hadjustment()
        hscrollbar = gtk.HScrollbar(self.hadj)

        self.window.add(mainVBox)
        mainVBox.pack_start(self.toolbar, expand=False, fill=False)
        mainVBox.pack_start(mainHBox, expand=True, fill=True)
        mainHBox.pack_start(self.nsLegend, expand=False, fill=False)
        mainHBox.pack_start(vbox2, expand=True, fill=True)
        vbox2.pack_start(vscroll, expand=True, fill=True)
        vbox2.pack_start(tscroll, expand=False, fill=False)
        vbox2.pack_start(hscrollbar, expand=False, fill=False)
        self.toolbar.add(zi)
        self.toolbar.add(zo)
        self.toolbar.add(rt)
        self.toolbar.add(save)
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
        self.cyan_gc =  self.content.window.new_gc()
        self.cyan_gc.copy(self.gc)
        self.cyan_gc.foreground=colormap.alloc_color(gtk.gdk.Color(red=0, green=65535, blue=65535))
        self.grey_gc =  self.content.window.new_gc()
        self.grey_gc.copy(self.gc)
        self.grey_gc.foreground=colormap.alloc_color(gtk.gdk.Color(red=49152, green=49152, blue=49152))
        self.purple_gc =  self.content.window.new_gc()
        self.purple_gc.copy(self.gc)
        self.purple_gc.foreground=colormap.alloc_color(gtk.gdk.Color(red=57343, green=32768, blue=65535))
        self.green_gc =  self.content.window.new_gc()
        self.green_gc.copy(self.gc)
        self.green_gc.foreground=colormap.alloc_color(gtk.gdk.Color(red=32768, green=65535, blue=32768))
        self.yellow_gc =  self.content.window.new_gc()
        self.yellow_gc.copy(self.gc)
        self.yellow_gc.foreground=colormap.alloc_color(gtk.gdk.Color(red=65535, green=65535, blue=0))
        self.orange_gc =  self.content.window.new_gc()
        self.orange_gc.copy(self.gc)
        self.orange_gc.foreground=colormap.alloc_color(gtk.gdk.Color(red=65535, green=49152, blue=0))

        self.gcByType={
            'run': self.pink_gc,
            'sleep': self.blue_gc,
            'mixed': self.purple_gc,
            'proc': self.grey_gc,
            'bio': self.green_gc,
            'queue': self.cyan_gc,
            '': self.gc,
            'empty': self.white_gc,
            'async': self.yellow_gc,
            'interrupt': self.orange_gc
        }

        self.timing.realize()

        self.pmwidth = 1
        self.offset = 0

        self.pixmap = gtk.gdk.Pixmap(self.content.window, 23, 1)
        self.content.connect('expose-event', self.expose_event, 'pixmap')

        self.timingpixmap = gtk.gdk.Pixmap(self.timing.window, 34, 1)
        self.timing.connect('expose-event', self.expose_event, 'timingpixmap')

        self.font = self.window.create_pango_context()
        self.layout=pango.Layout(self.font)

        self.rectmargin=0

        self.width=2000
        self.rowheight=20

        self.id=AppWindow.id
        AppWindow.id+=1

    def redraw_time(self):
        lx, ly, lwidth, lheight = self.legend.get_allocation()
        self.lwidth=lwidth
        self.timing.set_size_request(self.width+lwidth, self.rowheight)
        self.timingpixmap.draw_rectangle(self.white_gc, True, 0, 0, self.pmwidth, self.rowheight)
        gc = self.timing.get_style().fg_gc[gtk.STATE_NORMAL]
        gap=(150./self.width)*(self.endtime-self.starttime)
        if not self.raw_times:
            pt=10 ** math.floor(math.log(gap,10))
            mant=gap/pt
            mant=int(math.ceil(mant))
            gap=mant*pt
        t=0
        while t+self.starttimelabels<self.endtimelabels:
            if self.raw_times:
                self.layout.set_text('%f'%(self.starttimelabels+t))
            else:
                if gap > 1:
                    self.layout.set_text('%ds' % round(t))
                elif gap > 1e-3:
                    self.layout.set_text('%ds %dms' % (int(t), round(1e3*(t%1))))
                elif gap > 1e-6:
                    self.layout.set_text('%ds %dms %dus' % (int(t), int(1e3*(t%1)), round(1e6*(t%1e-3))))
                elif gap > 1e-9:
                    self.layout.set_text('%ds %dms %dus %dns' % (int(t), int(1e3*(t%1)), int(1e6*(t%1e-3)), round(1e9*(t%1e-6))))
                else:
                    self.layout.set_text('%ds %dms %dus %fns' % (int(t), int(1e3*(t%1)), int(1e6*(t%1e-3)), 1e9*(t%1e-6)))
            x = self.xfromt(self.starttimelabels+t)+lwidth
            if x < self.pmwidth and x+self.layout.get_pixel_size()[0] > 0 :
                self.timingpixmap.draw_line(self.red_gc, x, 0, x, 10)
                self.timingpixmap.draw_layout(gc, x+2, 0, self.layout)
            t+=gap
        self.timing.queue_draw_area(0, 0, self.width, self.rowheight)

    def toggle_raw_times(self, event):
        self.raw_times = not self.raw_times
        self.redraw_time()



    def zoom(self, widget, ratio):
        self.width=int(ratio*self.width)
        self.content.set_size_request(self.width, self.height)
        self.redraw()
        self.hadj.set_value(int(self.hadj.get_value()*ratio))
        self.redraw_time()

    def expose_event(self, widget, event, pmname):
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
        widthToShow = self.width + (self.lwidth if pmname=='timingpixmap' else 0)
        if x+width > widthToShow:
            widget.window.draw_rectangle(self.grey_gc, True, widthToShow+1, y, x+width-widthToShow, height)
        if y+height > self.height:
            widget.window.draw_rectangle(self.grey_gc, True, x, self.height+1, width, y+height-self.height)
        return False

    def xfromt(self,t):
        return int(self.width*(t-self.starttime)/(self.endtime-self.starttime))-self.offset

    def draw_rectangle(self, gc, start, end, h, text, is_instant=False):
        x1 = self.xfromt(start)
        x2 = self.xfromt(end)
        if x2-x1>self.rectmargin:
            x2-=self.rectmargin
        if x2<0 or x1>self.pmwidth:
            return
        if x1<0:
            x1=0
        if x2>self.pmwidth:
            x2=self.pmwidth
        y1 = h
        if text:
            self.layout.set_text(text)
            textwidth=self.layout.get_pixel_size()[0]
        if is_instant and x2-x1 > textwidth:
            x1=x2-textwidth
        self.pixmap.draw_rectangle(gc, True, x1, y1, x2-x1, self.rowheight-1)
        if text:
            self.gc.set_clip_rectangle(gtk.gdk.Rectangle(x1, y1, x2-x1, self.rowheight-1))
            repeat=int(math.ceil(textwidth/400.0)*400)
            x=x1
            while x==x1 or x+textwidth<x2:
                self.pixmap.draw_layout(self.gc, x, y1, self.layout)
                x+=repeat
                self.gc.set_clip_rectangle(gtk.gdk.Rectangle(0, 0, max(self.width,self.pmwidth), self.height))
        if is_instant:
            self.pixmap.draw_polygon(self.white_gc, True, [(x1,y1+13),(x1,y1+self.rowheight-1),(x2,y1+self.rowheight-1)])

    def draw_line(self, gc, t1, y1, t2, y2):
        x1=self.xfromt(t1)
        x2=self.xfromt(t2)
        if x2<0 or x1>self.pmwidth:
            return        
        if x1<0:
            x1=0
        if x2>self.pmwidth:
            x2=self.pmwidth
        self.pixmap.draw_line(gc, x1, y1, x2, y2)


    def get_filename_and_callback(self, widget, callback, extension):
        window = gtk.Window(gtk.WINDOW_TOPLEVEL)
        vb=gtk.VBox()
        window.add(vb)
        vb.add(gtk.Label('Filename:'))
        suggestion = self.fn.split('.')[0]
        suggestion += '_' + self.__class__.__name__
        if 'target' in self.__dict__:
            suggestion += '_' + self.target
        suggestion+='.'+extension
        entry=gtk.Entry()
        entry.set_text(suggestion)
        vb.add(entry)
        button=gtk.Button('Save')
        button.connect('clicked', callback, entry)
        vb.add(button)
        window.show_all()

    def save_part2(self, widget, entry):
        fn = entry.get_text()
        entry.get_parent().get_parent().destroy()
        try:
            pb = gtk.gdk.Pixbuf(gtk.gdk.COLORSPACE_RGB, False, 8, self.width, self.height+self.rowheight)
            oldoffset=self.offset
            self.offset=0
            cmap=gtk.gdk.colormap_get_system()
            while self.offset<self.width:
                self.redraw()
                pb.get_from_drawable(self.pixmap, cmap, 0, 0, self.offset, 0, min(self.pmwidth,self.width-self.offset), self.height)
                self.redraw_time()
                pb.get_from_drawable(self.timingpixmap, cmap, 0, 0, self.offset, self.height, min(self.pmwidth,self.width-self.offset), self.rowheight)
                self.offset += self.pmwidth
            pb.save(fn, 'png')
            self.offset=oldoffset
            self.redraw()
            self.redraw_time()
        except RuntimeError:
            self.show_error("Can't save image at that zoom level")

    def show_error(self, message):
        md = gtk.MessageDialog(None,
            gtk.DIALOG_DESTROY_WITH_PARENT, gtk.MESSAGE_ERROR,
            gtk.BUTTONS_CLOSE, message)
        md.run()
        md.destroy()


    def flame_or_consolidated_legend(self, which):
        lab=gtk.Label('<span font="serif" size="large">Legend</span>')
        lab.set_use_markup(True)
        self.nsLegend.pack_start(lab, expand=False, fill=False)
        eb = gtk.EventBox()
        eb.set_border_width(3)
        self.nsLegend.pack_start(eb, expand=False, fill=False)
        eb.modify_bg(gtk.STATE_NORMAL, gtk.gdk.Color(red=65535, green=65535, blue=65535))
        leg = gtk.VBox()
        leg.set_border_width(3)
        leg.set_spacing(3)
        eb.add(leg)
        entries=[('running', 'run'),
                 ('blocked', 'sleep'),
                 ('running and blocked', 'mixed'),
                 ('device I/O', 'bio'),
                 ('device queue', 'queue'),
                 ('process or thread', 'proc'),
                 ('waiting on other control path', 'async'),
                 ('interrupt', 'interrupt')];
        if which=='flame':
            entries.append(('caused to run', 'empty'))
            entries.append(('control path separator', 'empty'))                           
        for disp,name in entries:
            pm = gtk.gdk.Pixmap(self.content.window, 20, 20)
            pm.draw_rectangle(self.gcByType[name],True,0,0,20,20);
            if which=='flame':
                if name=='interrupt':
                    pm.draw_polygon(self.white_gc, True, [(0,13), (0,20), (20,20)])
                elif disp=='caused to run':
                    pm.draw_line(self.red_gc, 0, 20, 20, 0)
                elif disp=='control path separator':
                    pm.draw_line(self.gc, 0, 10, 20, 10)
            img = gtk.Image()
            img.set_from_pixmap(pm,None)
            lab = gtk.Label(disp)
            box=gtk.HBox()
            box.pack_start(img, expand=False)
            box.pack_start(lab, expand=False)
            leg.pack_start(box, expand=False)
        self.nsLegend.show_all()


    def de_facto_start(self, sleep):
        try:
            prevrun=sleep.prev
            prevsleep=prevrun.prev
            if prevrun.end-prevrun.start > 1e-4:
                return sleep.start
            if prevsleep.stack != sleep.stack:
                return sleep.start
            is_timeouty_wait=False
            for frame in sleep.stack:
                if frame.function=='poll_schedule_timeout':
                    is_timeouty_wait=True
                    break
            if not is_timeouty_wait:
                return sleep.start
            if 'inlink' in prevrun.__dict__:
                return sleep.start
            return self.de_facto_start(prevsleep)
        except AttributeError as e:
            return sleep.start            


    def clear_preceding_timeouts(self, sleep, start):
        if start>sleep.end:
            return
        if 'interrupt' in sleep.__dict__ and sleep.interrupt=='timeout':
            del sleep.interrupt
        try:
            prevrun=sleep.prev
            prevsleep=prevrun.prev
            if prevrun.end-prevrun.start > 1e-4:
                return
            if prevsleep.stack != sleep.stack:
                return
            is_timeouty_wait=False
            for frame in sleep.stack:
                if frame.function=='poll_schedule_timeout':
                    is_timeouty_wait=True
                    break
            if not is_timeouty_wait:
                return
            if 'inlink' in prevrun.__dict__:
                return
            return self.clear_preceding_timeouts(prevsleep,start)
        except AttributeError as e:
            return



AppWindow.id=0
