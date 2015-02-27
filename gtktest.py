#!/usr/bin/python

import gtk

class AppWindow:
    def __init__(self):
        self.window = gtk.Window(gtk.WINDOW_TOPLEVEL)
        self.window.connect("delete_event",gtk.main_quit)
        self.window.connect("destroy_event",gtk.main_quit)

        mainVBox = gtk.VBox()
        hbox = gtk.HBox()

        self.toolbar = gtk.HBox()

        vscroll = gtk.ScrolledWindow()
        vscroll.set_policy(gtk.POLICY_NEVER, gtk.POLICY_ALWAYS)
        vscroll.set_border_width(10)

        hscroll = gtk.ScrolledWindow()
        hscroll.set_policy(gtk.POLICY_ALWAYS, gtk.POLICY_NEVER)
        hscroll.get_hscrollbar().set_child_visible(False)

        self.legend = gtk.VBox()

        self.content = gtk.DrawingArea()
        self.content.set_size_request(1000,1000)


        adj=adjustment=hscroll.get_hadjustment()
        hscrollbar = gtk.HScrollbar(adj)

        self.window.add(mainVBox)
        mainVBox.pack_start(self.toolbar, expand=False, fill=False)
        mainVBox.pack_start(vscroll, expand=True, fill=True)
        mainVBox.pack_start(hscrollbar, expand=False, fill=False)
        vscroll.add_with_viewport(hbox)
        hbox.pack_start(self.legend, expand=False, fill=False)
        hbox.pack_start(hscroll, expand=True, fill=True)
        hscroll.add_with_viewport(self.content)


appWindow=AppWindow()


appWindow.content.realize()
pixmap = gtk.gdk.Pixmap(appWindow.content.window, 1000, 1000)
gc = appWindow.content.get_style().fg_gc[gtk.STATE_NORMAL]


def expose_event(widget, event):
    x , y, width, height = event.area
    widget.window.draw_drawable(widget.get_style().fg_gc[gtk.STATE_NORMAL],
                                pixmap, x, y, x, y, width, height)
    return False

appWindow.content.connect('expose-event', expose_event)

pixmap.draw_rectangle(gc,True,5,5,20,20)
appWindow.content.queue_draw_area(0,0,1000,1000)



appWindow.window.show_all()

gtk.main()

