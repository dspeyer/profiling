#!/usr/bin/python

import gtk
import pango
from collections import defaultdict
from copy import copy

from appWindow import AppWindow
from parse import struct

def treeNode():
    return struct(time=0, type='', children=defaultdict(treeNode))

def unitify(t):
    if t>1:
        return (t, 's')
    elif t>1e-3:
        return (1e3*t, 'ms')
    elif t>1e-6:
        return (1e6*t, 'us')
    else:
        return (1e9*t, 'ns')

class ConsolidatedWindow(AppWindow):
    def __init__(self, data, cps, flameId, target):
        AppWindow.__init__(self, 0, 1) # We'll reset these later
        self.window.set_title('Consolidated Flame View: %s' % target)
        self.data = data
        self.flameId=flameId
        self.rowheight=20
        self.lheight=0
        self.infn=0
        self.inrunns=0
        self.inbio=0
        self.root=treeNode()
        self.root.type='root'
        for cp in cps:
            for run in cp:
                self.root.time += run.end - run.start
                self.accumulate(self.root, run, 1)
        self.addEmpty(self.root)
        self.height=self.lheight * self.rowheight
        self.endtime = self.root.time

        ss=gtk.Button('Show Stats')
        ss.connect('clicked', self.stats)
        self.toolbar.add(ss)

        self.rectmargin = 2

        self.redraw()
        self.window.show_all()

    def stats(self, ev):
        win = gtk.Window(gtk.WINDOW_TOPLEVEL)
        win.set_title('Stats')
        win.set_keep_above(True)
        tab = gtk.Table(2,7)
        win.add(tab)
        tab.attach(gtk.Label('Wall time:'),0,1,0,1)
        tab.attach(gtk.Label(' %.1f%s' % unitify(self.data.endtime-self.data.starttime)), 1,2,0,1)
        tab.attach(gtk.Label('Total time:'),0,1,1,2)
        tab.attach(gtk.Label('%.1f%s' % unitify(self.root.time)),1,2,1,2)
        tab.attach(gtk.Label('In understood functions:'),0,1,2,3)
        tab.attach(gtk.Label('%.1f%s' % unitify(self.infn)), 1,2,2,3)
        tab.attach(gtk.Label('Running but not sampled:'),0,1,3,4)
        tab.attach(gtk.Label('%.1f%s' % unitify(self.inrunns)), 1,2,3,4)
        tab.attach(gtk.Label('In blocking I/O:'),0,1,4,5)
        tab.attach(gtk.Label('%.1f%s'% unitify(self.inbio)), 1,2,4,5)
        tab.attach(gtk.Label('Total Accounted:'),0,1,5,6)
        tab.attach(gtk.Label('%.1f%s' % unitify(self.infn + self.inrunns + self.inbio)), 1,2,5,6)
        tab.attach(gtk.Label('Unaccounted:'),0,1,6,7)
        tab.attach(gtk.Label('%.1f%s' % unitify(self.root.time - self.infn - self.inrunns - self.inbio)), 1,2,6,7)
        win.show_all()

    def put_stack(self, node, stack, dur, typ):
        for frame in reversed(stack):
            node=node.children[frame.function]
            node.time += dur
            if node.type=='':
                node.type=typ
            elif node.type!=typ:
                node.type='mixed'
        return node

    def accumulate(self, node, box, h):
        h+=1
        if box.type == 'bio':
            text = box.iotype + ' of '+box.proc
        elif box.type == 'queue':
            text = '[queue] '+ box.iotype + ' of '+box.proc
        else:
            text=box.proc
        node = node.children[text]
        if box.type in ['bio', 'queue']:
            node.type=box.type
            self.inbio += box.end-box.start
        else:
            node.type='proc'
        node.time += box.end-box.start
        if 'stack' in box.__dict__:
            topframe = self.put_stack(node, box.stack, box.end-box.start, box.type)
            h += len(box.stack)
        elif 'stacks' in box.__dict__ and len(box.stacks)>0:
            self.infn += box.end-box.start
            nstacks=len(box.stacks)
            biggeststack=0
            for stack in box.stacks:
                self.put_stack(node, stack, (box.end-box.start)/nstacks, box.type)
                if len(stack)>biggeststack:
                    biggeststack=len(stack)
            h+=biggeststack
        elif box.type=='run':
            self.put_stack(node, [struct(function='no samples', file='no samples')], box.end-box.start, box.type)
            self.inrunns += box.end-box.start
        elif box.type=='sleep':
            topframe=self.put_stack(node, [struct(function='no stack, WTF?', file='no stack, WTF?')], box.end-box.start, box.type)
            h+=1
        if h>self.lheight:
            self.lheight=h
        if 'children' in box.wdata[self.flameId].__dict__:
            for child in box.wdata[self.flameId].children:
                self.accumulate(topframe, child, h+1)

    def addEmpty(self, node):
        if node.type=='empty':
            return
        children = node.children.keys()
        node.children[''].time = node.time
        node.children[''].type = 'empty'
        for child in children:
            node.children[''].time -= node.children[child].time
        for child in children:
            self.addEmpty(node.children[child])

    def redraw(self):
        self.content.set_size_request(self.width, self.height)
        self.pixmap.draw_rectangle(self.white_gc, True, 0, 0, self.width, self.height)
        self.draw_children(self.root, 0, 0)
        self.content.queue_draw_area(0, 0, self.width, self.height)

    def draw_children(self, node, h, t1):
        if node.type=='empty':
            return
        children = node.children.keys()
        children.sort(key=lambda(x):node.children[x].time)
        for childname in reversed(children):
            child=node.children[childname]
            t2 = t1 +  child.time
            self.draw_rectangle(self.gcByType[child.type], t1, t2, self.physFromLogY(h), childname)
            self.draw_children(child, h+1, t1)
            t1 = t2
    
    def physFromLogY(self, logY):
        return  (self.lheight-logY-1)*self.rowheight

