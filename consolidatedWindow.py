#!/usr/bin/python

import gtk
import pango
from collections import defaultdict
from copy import copy

from appWindow import AppWindow
from parse import struct

def treeNode():
    return struct(time=0, type='', children=defaultdict(treeNode), async=[])

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
        self.inas=0
        self.intimeout=0
        self.inhardware=0
        self.dblcnt=0
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

    def statsrow(self,tab,text,time):
        tab.attach(gtk.Label(text), 0, 1, self.row, self.row+1)
        tab.attach(gtk.Label(' %.1f%s' % unitify(time)), 1, 2, self.row, self.row+1)
        self.row+=1

    def stats(self, ev):
        win = gtk.Window(gtk.WINDOW_TOPLEVEL)
        win.set_title('Stats')
        win.set_keep_above(True)
        tab = gtk.Table(2,11)
        win.add(tab)
        self.row=0
        self.statsrow(tab,'Wall time:',self.data.endtime-self.data.starttime)
        self.statsrow(tab,'Total time:',self.root.time)
        self.statsrow(tab,'In understood functions:',self.infn)
        self.statsrow(tab,'Running but not sampled:',self.inrunns)
        self.statsrow(tab,'In blocking I/O:',self.inbio)
        self.statsrow(tab,'Waiting on other path:',self.inas)
        self.statsrow(tab,'Waits that timed out:',self.intimeout)
        self.statsrow(tab,'Waits "for" hardware:',self.inhardware)
        self.statsrow(tab,'Double counted (early starts):',self.dblcnt)
        total=self.infn + self.inrunns + self.inbio + self.inas + self.intimeout + self.inhardware - self.dblcnt
        self.statsrow(tab,'Total Accounted:',total)
        self.statsrow(tab,'Unaccounted:',self.root.time - total)
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

    def get_text(self, box):
        if box.type == 'bio':
            return box.iotype + ' of '+box.dev
        elif box.type == 'queue':
            return box.iotype + ' of '+box.dev + ' '
        else:
            return box.proc

    def accumulate(self, node, box, h):
        h+=1
        if 'cutstart' in box.wdata[self.flameId].__dict__:
            start=box.wdata[self.flameId].cutstart
        else:
            start=box.start
        if box.wdata[self.flameId].parent and start<box.wdata[self.flameId].parent.start:
            self.dblcnt +=  box.wdata[self.flameId].parent.start - start
        node = node.children[self.get_text(box)]
        topframe = node
        if box.type in ['bio', 'queue']:
            node.type=box.type
            self.inbio += box.end-start
        else:
            node.type='proc'
        node.time += box.end-start
        if 'stack' in box.__dict__:
            topframe = self.put_stack(node, box.stack, box.end-start, box.type)
            h += len(box.stack)
        elif 'stacks' in box.__dict__ and len(box.stacks)>0:
            self.infn += box.end-start
            nstacks=len(box.stacks)
            biggeststack=0
            for stack in box.stacks:
                self.put_stack(node, stack, (box.end-start)/nstacks, box.type)
                if len(stack)>biggeststack:
                    biggeststack=len(stack)
            h+=biggeststack
        elif box.type=='run':
            self.put_stack(node, [struct(function='no samples', file='no samples')], box.end-start, box.type)
            self.inrunns += box.end-start
        elif box.type=='sleep':
            topframe=self.put_stack(node, [struct(function='no stack, WTF?', file='no stack, WTF?')], box.end-start, box.type)
            h+=1
        if h>self.lheight:
            self.lheight=h
        time=box.end-start
        if 'children' in box.wdata[self.flameId].__dict__:
            for child in box.wdata[self.flameId].children:
                self.accumulate(topframe, child, h+1)
                time -= child.end-child.start
        if 'interrupt' in box.__dict__:
            node = topframe.children[box.interrupt+'?']
            node.type='interrupt'
            node.time+=time
            if box.interrupt=='timeout':
                self.intimeout+=time
            else:
                self.inhardware+=time
        elif 'async' in box.wdata[self.flameId].__dict__:
            topframe.async.append(struct(aschild=box.wdata[self.flameId].async,maxtime=time))

    def addEmpty(self, node):
        if node.type in ['empty', 'async']:
            return
        children = node.children.keys()
        node.children[''].time = node.time
        node.children[''].type = 'empty'
        for child in children:
            node.children[''].time -= node.children[child].time
        for async in node.async:
            print 'making async'
            astime = min(async.aschild.end - async.aschild.start, async.maxtime)
            if node.children[''].time > astime:
                node.children[''].time -= astime
            else:
                astime = node.children[''].time
                node.children[''].time = 0
            asyncname = 'latter part of '+self.get_text(async.aschild)
            if astime>0:
                node.children[asyncname].time+=astime
                node.children[asyncname].type='async'
                self.inas+=astime
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

