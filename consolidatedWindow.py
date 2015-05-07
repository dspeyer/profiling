#!/usr/bin/python

import gtk
import pango
from collections import defaultdict
from copy import copy

from appWindow import AppWindow
from parse import struct

def treeNode():
    return struct(time=0, type='', children=defaultdict(treeNode), async=[], extra=0, parent=None)

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
    def __init__(self, data, cps, flameId, target, fn, mergethreads=False):
        AppWindow.__init__(self, 0, 1, fn) # We'll reset these later
        self.mergethreads=mergethreads
        self.window.set_title('Consolidated Flame View: %s [%s]' % (target,fn))
        self.data = data
        self.cps = cps
        self.flameId=flameId
        self.target=target
        self.wallstart=float('inf')
        self.wallend=float('-inf')
        self.rowheight=20
        self.lheight=0
        self.infn=0
        self.inrunns=0
        self.inbio=0
        self.inqueue=0
        self.inas=0
        self.intimeout=0
        self.inhardware=0
        self.dblcnt=0
        self.involuntary=0
        self.misckern=0
        self.overhead=0
        self.root=treeNode()
        self.root.type='root'
        for cp in cps:
            for run in cp:
                if 'cutstart' in run.wdata[self.flameId].__dict__:
                    start=run.wdata[self.flameId].cutstart
                else:
                    start=run.start
                self.root.time += run.end - start
                if run.end>self.wallend:
                    self.wallend=run.end
                if start<self.wallstart:
                    self.wallstart=start
                self.accumulate(self.root, run, 1)
        self.addEmpty(self.root)
        self.height=self.lheight * self.rowheight
        self.endtime = self.root.time+self.root.extra

        ss=gtk.Button('Save Stats')
        ss.connect('clicked', self.get_filename_and_callback, self.stats_part_2, 'txt')
        self.toolbar.add(ss)

        mt=gtk.Button('Merge Threads')
        mt.connect('clicked', self.make_merge_threads)
        self.toolbar.add(mt)

        self.rectmargin = 2

        self.flame_or_consolidated_legend('consolidated')

        lab=gtk.Label('<span size="large">Summary Stats</span>')
        lab.set_use_markup(True)
        self.nsLegend.pack_start(lab, expand=False)

        self.tab = gtk.Table(2,15)
        self.row=0
        self.allstats(self.statsrow)
        self.nsLegend.pack_start(self.tab, expand=False)

        self.redraw()
        self.window.show_all()

    def statsrow(self,text,time):
        lab=gtk.Label(text)
        lab.set_alignment(1,.5)
        lab.set_selectable(True)
        self.tab.attach(lab, 0, 1, self.row, self.row+1, xoptions=gtk.FILL)
        val=gtk.Label(' %.1f%s' % unitify(time))
        val.set_selectable(True)
        val.set_alignment(0,.5)
        self.tab.attach(val, 1, 2, self.row, self.row+1, xoptions=gtk.FILL)
        self.row+=1

    def allstats(self, callback):
        callback('Wall time:',self.wallend-self.wallstart)
        callback('Total time:',self.root.time+self.root.extra)
        callback('In understood functions:',self.infn)
        callback('Running but not sampled:',self.inrunns)
        callback('In blocking I/O:',self.inbio)
        callback('I/O queue overhead:',self.inqueue)
        callback('Waiting on other path:',self.inas)
        callback('Waits that timed out:',self.intimeout)
        callback('Waits "for" hardware:',self.inhardware)
        callback('Involuntary sleeps:',self.involuntary)
        callback('Miscellaneous kernel blocks:',self.misckern)
        callback('Scheduler overhead:',self.overhead)
        total=self.infn + self.inrunns + self.inbio + self.inqueue + self.inas + self.intimeout + self.inhardware + self.involuntary + self.misckern + self.overhead
        callback('Total Accounted:',total)
        callback('Unaccounted:',self.root.time + self.root.extra - total)


    def stats_part_2(self, widget, entry):
        fn = entry.get_text()
        entry.get_parent().get_parent().destroy()
        f=file(fn,'w')
        f.write('Category\ttime\n')
        self.allstats(lambda text,time: f.write('%s\t%.9f\n'%(text,time)))
        f.close()

    def put_stack(self, node, stack, dur, typ):
        for frame in reversed(stack):
            newnode=node.children[frame.function]
            newnode.parent=node
            node=newnode
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
        elif self.mergethreads:
            return box.proc.split('(')[0]
        else:
            return box.proc

    def accumulate(self, node, box, h):
        h+=1
        if 'cutstart' in box.wdata[self.flameId].__dict__:
            start=box.wdata[self.flameId].cutstart
        else:
            start=box.start
        if box.wdata[self.flameId].parent:
            extra=0
            if start<self.de_facto_start(box.wdata[self.flameId].parent):
                extra +=  self.de_facto_start(box.wdata[self.flameId].parent) - start
            if box.end>box.wdata[self.flameId].parent.end:
                extra  +=  box.end - box.wdata[self.flameId].parent.end
            #self.dblcnt += extra
            if extra>0.1:
                print 'found extra of %f in %s %f-%f at height %d'%(extra,box.proc,start,box.end,h)
            par=node
            while par:
                par.extra+=extra
                par=par.parent
        newnode = node.children[self.get_text(box)]
        newnode.parent=node
        node=newnode
        topframe = node
        if box.type in ['bio', 'queue']:
            node.type=box.type
            if box.type=='bio':
                self.inbio += box.end-start
            elif 'children' not in box.wdata[self.flameId].__dict__:
                self.inqueue += box.end-start
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
        if box.type=='run' and 'inlink' in box.__dict__ and box.inlink.outtime<start:
            self.overhead += start - box.inlink.outtime
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
                print "timeout is %s %f-%f"%(box.proc,box.start,box.end)
                self.intimeout+=time
            else:
                self.inhardware+=time
        elif 'asyncstart' in box.wdata[self.flameId].__dict__:
            topframe.async.append(struct(aschild=box.wdata[self.flameId].asyncstart,maxtime=time))
        elif 'asyncend' in box.wdata[self.flameId].__dict__:
            topframe.async.append(struct(aschild=box.wdata[self.flameId].asyncend,maxtime=time))
        elif 'special' in box.__dict__:
            if box.special=='retint_careful':
                self.involuntary += time
            if box.special=='wait_for_completion':
                self.misckern += time
                

    def addEmpty(self, node):
        if node.type in ['empty', 'async']:
            return
        children = node.children.keys()
        node.children[''].time = node.time
        node.children[''].type = 'empty'
        for child in children:
            node.children[''].time -= node.children[child].time
        for async in node.async:
            #print 'making async'
            astime = min(async.aschild.end - async.aschild.start, async.maxtime)
            if node.children[''].time > astime:
                node.children[''].time -= astime
            else:
                astime = node.children[''].time
                node.children[''].time = 0
            asyncname = 'part of '+self.get_text(async.aschild)
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
            #if h==2:
                #print 'drawing %s of %s from %f to %f with %f extra' % (child.type, childname, t1, t2, child.extra)
            self.draw_rectangle(self.gcByType[child.type], t1, t2, self.physFromLogY(h), childname)
            self.draw_children(child, h+1, t1)
            t1 = t2 + child.extra
    
    def physFromLogY(self, logY):
        return  (self.lheight-logY-1)*self.rowheight

    def make_merge_threads(self, widget):
        ConsolidatedWindow(self.data, self.cps, self.flameId, self.target, self.fn, True)
