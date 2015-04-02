#!/usr/bin/python

import gtk
import pango
from collections import defaultdict

from appWindow import AppWindow
from flameWindow import FlameWindow

class MainWindow(AppWindow):
    def __init__(self, data):
        AppWindow.__init__(self, data.starttime, data.endtime)
        self.window.connect("delete_event",gtk.main_quit)
        self.window.connect("destroy_event",gtk.main_quit)
        self.window.set_title('Runs and Links View')

        self.data=data
        self.boxes=data.boxes
        self.links=data.links

        self.show_sleeps=False

        ts=gtk.ToggleButton('Show Sleeps')
        ts.connect('clicked', self.toggle_sleeps)
        self.toolbar.add(ts)
        
        # This whole connectedness thing is just to pick heights that group related processes together
        connectedness=defaultdict(lambda:defaultdict(lambda:0))
        for p1 in data.procs:
            prefix1=p1.split('/')[0].split('(')[0]
            for p2 in data.procs:
                prefix2=p2.split('/')[0].split('(')[0]
                if prefix1==prefix2:
                    connectedness[p1][p2]+=20
                    connectedness[p2][p1]+=20
        for l in self.links:
            connectedness[l.source][l.target]+=1
            connectedness[l.target][l.source]+=1

        
        # Assign heights to processes with a simple greedy algorithm
        self.heights={}
        h=0
        p='swapper/0(0)'
        self.rowheight=40
        while True:
            self.heights[p]=h
            button=gtk.Button(label=p)
            button.connect('clicked', self.launchFlameWindow, p)
            self.legend.pack_start(button, expand=False, fill=False)
            bh=button.size_request()[1]
            if bh-1<self.rowheight:
                self.rowheight=bh-5
            h+=bh
            bestv=-1
            bestp=''
            for nextp in data.procs:
                if nextp in self.heights:
                    continue
                conn=connectedness[p][nextp]
                if conn>bestv:
                    bestv=conn
                    bestp=nextp
            if bestv==-1: # Nothing left to assign
                break
            p=bestp
        self.height=h


    def toggle_sleeps(self, event):
        self.show_sleeps = not self.show_sleeps
        self.redraw()


    def redraw(self):
        self.content.set_size_request(self.width, self.height)
        self.pixmap = gtk.gdk.Pixmap(self.content.window, self.width, self.height)
        self.pixmap.draw_rectangle(self.white_gc, True, 0, 0, self.width, self.height)
        for b in self.boxes:
            if b.proc not in self.heights:
                continue
            h=self.heights[b.proc]
            if b.type=='sleep' and not self.show_sleeps:
                continue
            if b.type=='run':
                gc=self.gc
                text=''
            else:
                gc=self.blue_gc
                text=b.repframe
            self.draw_rectangle(gc, b.start, b.end, h, text)
        for l in self.links:
            if l.source not in self.heights or l.target not in self.heights:
                continue
            y1=self.heights[l.source]+int(self.rowheight/2)
            y2=self.heights[l.target]+int(self.rowheight/2)
            if l.istransfer:
                gc=self.red_gc
            else:
                gc=self.blue_gc
            self.draw_line(gc, l.start, y1, l.end, y2)
        self.content.queue_draw_area(0, 0, self.width, self.height)

    def launchFlameWindow(self, ev, p):
        flame=FlameWindow(self.data, p)
