#!/usr/bin/python

import gtk

class AppWindow:
    def __init__(self):
        self.window = gtk.Window(gtk.WINDOW_TOPLEVEL)
        self.window.connect("delete_event",gtk.main_quit)
        self.window.connect("destroy_event",gtk.main_quit)

        self.mainVBox = gtk.VBox()
        self.hbox = gtk.HBox()

        self.toolbar = gtk.HBox()
        for i in range(10):
            self.toolbar.add(gtk.Button('B%d'%i))

        self.vscroll = gtk.ScrolledWindow()
        self.vscroll.set_policy(gtk.POLICY_NEVER, gtk.POLICY_ALWAYS)
        self.vscroll.set_border_width(10)

        self.hscroll = gtk.ScrolledWindow()
        self.hscroll.set_policy(gtk.POLICY_ALWAYS, gtk.POLICY_NEVER)
        self.hscroll.set_border_width(10)

        self.legend = gtk.VBox()
        for i in range(20):
            self.legend.add(gtk.Label('proc%d'%i))

        self.content = gtk.DrawingArea()
        self.content.set_size_request(200,1000)

        self.window.add(self.mainVBox)
        self.mainVBox.add(self.toolbar)
        self.mainVBox.add(self.vscroll)
        self.vscroll.add_with_viewport(self.hbox)
        self.hbox.add(self.legend)
        self.hbox.add(self.hscroll)
        self.hscroll.add_with_viewport(self.content)
        self.window.show_all()

appWindow=AppWindow()




gtk.main()

