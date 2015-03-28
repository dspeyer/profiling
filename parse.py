#!/usr/bin/python

from collections import defaultdict
import gtk
import pango
import re
import svgwrite
import code
from copy import copy
import ipdb

class struct:
    def __init__(self,**kwargs):
        for k in kwargs:
            setattr(self,k,kwargs[k])


class AppWindow:
    def __init__(self, ismain=False):
        self.window = gtk.Window(gtk.WINDOW_TOPLEVEL)
        if ismain:
            self.window.connect("delete_event",gtk.main_quit)
            self.window.connect("destroy_event",gtk.main_quit)

        self.ismain=ismain

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

        self.pixmap = gtk.gdk.Pixmap(self.content.window, 1, 1)
        self.content.connect('expose-event', self.expose_event)

        self.normalfont = self.window.create_pango_context()
        self.smallfont = self.window.create_pango_context()
        fontdesc=self.smallfont.get_font_description()
        fontdesc.set_size(fontdesc.get_size()/2)
        self.smallfont.set_font_description(fontdesc)

        self.width=2000

    def zoom(self, widget, ratio):
        self.width=int(ratio*self.width)
        redraw(self, with_depths=not self.ismain)
        self.hadj.set_value(int(self.hadj.get_value()*ratio))

    def expose_event(self, widget, event):
        x , y, width, height = event.area
        widget.window.draw_drawable(self.gc, self.pixmap, x, y, x, y, width, height)
        return False


appWindow=AppWindow(True)

evs = []

fn='perf.scr' # TODO: command line argument or something
f = file(fn)

commbypid={} # Needed to handle exec correctly


# First parse the events
for line in f:
    if line[0]=='#':
        continue
    if line=='\n':
        continue
    m=re.match('(.*[^ ]) +([0-9]+) +([0-9]*\\.[0-9]*): +([^ ]*): +(.*)',line)
    if m:
        ev=struct()
        (ev.comm, ev.pid, ev.time, ev.event, args) = m.groups()
        ev.pid = int(ev.pid)
        ev.time = float(ev.time)
        ev.args = struct()
        ev.stack = []
        if ev.event=='sched:sched_process_exec':
            if ev.pid in commbypid:
                ev.oldcomm=commbypid[ev.pid]
            else:
                ev.oldcomm='unknown(%d)'%ev.pid
        elif ev.pid in commbypid:
            if (commbypid[ev.pid]!=ev.comm):
                fake_ev=struct()
                fake_ev.comm=ev.comm
                fake_ev.pid=ev.pid
                fake_ev.time=ev.time
                fake_ev.event='sched:sched_process_exec'
                fake_ev.oldcomm=commbypid[ev.pid]
                #print "WARNING: deduced exec call by %d from %s to %s at %f" % (ev.pid, fake_ev.oldcomm, ev.comm, ev.time)
                evs.append(fake_ev)
        commbypid[ev.pid]=ev.comm
        for i in args.split(' '):
            m=re.match('([a-zA-Z_]*)=(.*)',i)
            if m:
                setattr(ev.args, m.group(1), m.group(2))
        evs.append(ev)
        continue
    m=re.search('[0-9a-f]* ([^ ]*) \\((.*)\\)',line)
    if m:
        evs[-1].stack.append(struct(function=m.group(1),file=m.group(2)))
    else:
        print 'ERROR: Could not parse "%s"'%line

# Now assemble the events into run blocks and links between them

switchedin={}
switchedout={}
switchedoutstack={}
inlinks=defaultdict(lambda:[])
outlinks=defaultdict(lambda:[])
runs=defaultdict(lambda:[])
sleeps=defaultdict(lambda:[])
links=[]

starttime=evs[0].time
endtime=evs[-1].time

for ev in evs:
    if ev.event=='sched:sched_switch':
        oldp='%s(%s)'%(ev.args.prev_comm,ev.args.prev_pid)
        newp='%s(%s)'%(ev.args.next_comm,ev.args.next_pid)
        # Handle runs
        if oldp in switchedin:
            if switchedin[oldp]==-1:
                print "ERROR: %s switched out without being in at %f" % (oldp, ev.time)
                exit()
            else:
                runs[oldp].append(struct(start=switchedin[oldp], end=ev.time))
                switchedin[oldp]=-1
        else:
            runs[oldp].append(struct(start=starttime, end=ev.time))
            switchedin[oldp]=-1
        if sleeps[oldp]:
            runs[oldp][-1].prev=sleeps[oldp][-1]
        if newp in switchedin and switchedin[newp]!=-1:
            print "ERROR: %s switched in twice (%f and %f)"%(newp,ev.time,switchedin[newp])
        else:
            switchedin[newp]=ev.time
        # Handle sleeps (TODO: maybe unify with the above?)
        if newp in switchedout:
            if switchedout[newp]==-1:
                print "ERROR: %s switched in without being out at %f" % (newp, ev.time)
                exit()
            else:
                sleeps[newp].append(struct(start=switchedout[newp], end=ev.time, stack=switchedoutstack[newp]))
                switchedout[newp]=-1
        if runs[newp]:
            sleeps[newp][-1].prev=runs[newp][-1]
        if oldp in switchedout and switchedout[oldp]!=-1:
            print "ERROR: %s switched out twice (%f and %f)"%(oldp,ev.time,switchedout[oldp])
        else:
            switchedout[oldp]=ev.time
            switchedoutstack[oldp]=ev.stack
        # Handle links
        if inlinks[newp]:
            for inlink in inlinks[newp]:
                inlink.end=ev.time
        if inlinks[oldp]:
            for inlink in inlinks[oldp]:
                inlink.targetrun=runs[oldp][-1]
                if 'end' not in inlink.__dict__:
                    inlink.end=inlink.start
                runs[oldp][-1].inlink=inlink
            inlinks[oldp]=[]
        if outlinks[oldp]:
            for outlink in outlinks[oldp]:
                outlink.outtime=ev.time
                outlink.sourcerun=runs[oldp][-1]
            outlinks[oldp]=[]
        is_interrupt=False
        for frame in ev.stack:
            if frame.function in ['retint_careful']:
                is_interrupt=True
                break
        if is_interrupt:
            links.append(struct(source=oldp,target=oldp,start=ev.time,outtime=ev.time,sourcerun=runs[oldp][-1],horizontal=True))
            inlinks[oldp].append(links[-1])
    elif ev.event=='sched:sched_wakeup':
        is_interrupt=False
        for frame in ev.stack:
            if frame.function in ['do_IRQ', 'apic_timer_interrupt']:
                is_interrupt=True
                break
        if is_interrupt:
            continue
        source='%s(%s)'%(ev.comm,ev.pid)
        target='%s(%s)'%(ev.args.comm, ev.args.pid)
        links.append(struct(source=source,target=target,start=ev.time))
        inlinks[target].append(links[-1])
        if ev.pid==int(ev.args.pid): #exactly what a process waking itself means is unclear, but it happens
            links[-1].outtime=ev.time
        else:
            outlinks[source].append(links[-1])
    elif ev.event=='sched:sched_process_exec':
        source='%s(%d)'%(ev.oldcomm,ev.pid)
        target='%s(%d)'%(ev.comm,ev.pid)
        links.append(struct(source=source, start=ev.time, target=target, end=ev.time,outtime=ev.time))
        if source in switchedin and switchedin[source]!=-1:
            runs[source].append(struct(start=switchedin[source], end=ev.time))
            links[-1].sourcerun=runs[source][-1]
        inlinks[target].append(links[-1])
        switchedin[source]=-1
        switchedin[target]=ev.time
    else:
        print 'ERROR: unhandled event "%s"'%ev.event

links = [link for link in links if 'end' in link.__dict__];
for p in switchedin:
    if switchedin[p]!=-1:
        runs[p].append(struct(start=switchedin[p], end=endtime))

for p in sleeps:
    for s in sleeps[p]:
        for frame in s.stack:
            if frame.file!='[kernel.kallsyms]':
                s.repframe=frame.function
                break
            s.repframe='?'

for p in runs:
    for r in runs[p]:
        r.proc=p
        r.type='run'

for p in sleeps:
    for s in sleeps[p]:
        s.proc=p
        s.type='sleep'

threshold=1e-4
for l in links:
    if 'outtime' in l.__dict__:
        if l.outtime-l.start<threshold:
            l.istransfer=True
        else:
            l.istransfer=False
    else:
        l.istransfer=False
        print 'no outtime at %f (%s->%s)'%(l.start,l.source,l.target)
    if 'istransfer' not in l.__dict__:
        print 'WTF %s->%s %f'%(l.source,l.target,l.start)

# This whole connectedness thing is just to pick heights that group related processes together
ps=runs.keys()
connectedness=defaultdict(lambda:defaultdict(lambda:0))
for p1 in ps:
    prefix1=p1.split('/')[0].split('(')[0]
    for p2 in ps:
        prefix2=p2.split('/')[0].split('(')[0]
        if prefix1==prefix2:
            connectedness[p1][p2]+=20
            connectedness[p2][p1]+=20
for l in links:
    connectedness[l.source][l.target]+=1
    connectedness[l.target][l.source]+=1

def rtag(run,depth,onstack,aw):
    if 'depth' in run.__dict__:
        return
    if depth>aw.maxdepth:
        aw.maxdepth=depth
    run.depth=depth
    if 'inlink' in run.__dict__ and run.inlink.istransfer and 'sourcerun' in run.inlink.__dict__:
        if run.inlink.source in onstack and run.inlink.source!=run.proc:
            return
        newstack=copy(onstack)
        newstack[run.proc]=1
        if 'horizontal' in run.inlink.__dict__:
            newdepth=depth
        else:
            newdepth=depth+1
        rtag(run.inlink.sourcerun,newdepth,newstack,aw)
    if 'prev' in run.__dict__:
        rtag(run.prev,depth,onstack,aw)

def tag(widget, proc):
    newWindow=AppWindow()
    newWindow.maxdepth=0
    for p in runs:
        for r in runs[p]:
            if 'depth' in r.__dict__:
                del r.depth
    for r in runs[proc]:
        rtag(r,0,{},newWindow)
    redraw(newWindow, with_depths=True)
    newWindow.window.show_all()
    

# Assign heights to processes with a simple greedy algorithm
heights={}
h=0
p='swapper/0(0)'
while True:
    heights[p]=h
    button=gtk.Button(label=p)
    button.connect('clicked',tag,p)
    appWindow.legend.pack_start(button, expand=False, fill=False)
    h+=button.size_request()[1]
    bestv=-1
    bestp=''
    for nextp in ps:
        if nextp in heights:
            continue
        conn=connectedness[p][nextp]
        if conn>bestv:
            bestv=conn
            bestp=nextp
    if bestv==-1: # Nothing left to assign
        break
    p=bestp

height=h

show_sleeps=False

def xfromt(appWindow,t):
    return int(appWindow.width*(t-starttime)/(endtime-starttime))

def redraw(appWindow,with_depths=False):
    appWindow.content.set_size_request(appWindow.width,height)
    appWindow.pixmap = gtk.gdk.Pixmap(appWindow.content.window, appWindow.width, height)
    appWindow.pixmap.draw_rectangle(appWindow.white_gc, True, 0, 0, appWindow.width, height)
    for p in runs:
        if p not in heights:
            continue
        h=heights[p]
        for r in runs[p]:
            if with_depths:
                if 'depth' in r.__dict__:
                    y1=(appWindow.maxdepth-r.depth)*20
                else:
                    continue
            else:
                y1=h
            x1=xfromt(appWindow,r.start)
            x2=xfromt(appWindow,r.end)
            if with_depths:
                gc=appWindow.pink_gc
            else:
                gc=appWindow.gc
            appWindow.pixmap.draw_rectangle(gc, True, x1, y1, x2-x1, (with_depths+1)*10)
            if with_depths:
                layout=pango.Layout(appWindow.normalfont)
                layout.set_text(r.proc)
                appWindow.gc.set_clip_rectangle(gtk.gdk.Rectangle(x1,y1,x2-x1,20))
                appWindow.pixmap.draw_layout(appWindow.gc, x1, y1, layout)
                appWindow.gc.set_clip_rectangle(gtk.gdk.Rectangle(0,0,appWindow.width,height))
    if show_sleeps or with_depths:
        for p in sleeps:
            if p not in heights:
                continue
            h=heights[p]
            for s in sleeps[p]:
                if with_depths:
                    if 'depth' in s.__dict__:
                        y1=(appWindow.maxdepth-s.depth)*20
                    else:
                        continue
                else:
                    y1=h
                x1=xfromt(appWindow,s.start)
                x2=xfromt(appWindow,s.end)
                appWindow.pixmap.draw_rectangle(appWindow.blue_gc, True, x1, y1, x2-x1, (with_depths+1)*10)
                if s.repframe:
                    if with_depths:
                        layout=pango.Layout(appWindow.normalfont)
                        layout.set_text(s.proc+' '+s.repframe)
                    else:
                        layout=pango.Layout(appWindow.smallfont)
                        layout.set_text(s.repframe)
                    appWindow.gc.set_clip_rectangle(gtk.gdk.Rectangle(x1,y1,x2-x1,(with_depths+1)*10))
                    appWindow.pixmap.draw_layout(appWindow.gc, x1, y1, layout)
                    appWindow.gc.set_clip_rectangle(gtk.gdk.Rectangle(0,0,appWindow.width,height))
    for l in links:
        if l.source not in heights or l.target not in heights:
            continue
        if with_depths:
            if ('sourcerun' in l.__dict__ and 'targetrun' in l.__dict__ and
                'depth' in l.sourcerun.__dict__ and 'depth' in l.targetrun.__dict__):
                y1=(appWindow.maxdepth-l.sourcerun.depth)*20+10
                y2=(appWindow.maxdepth-l.targetrun.depth)*20+10
            else:
                continue
        else:
            y1=heights[l.source]+5
            y2=heights[l.target]+5
        x1=xfromt(appWindow,l.start)
        x2=xfromt(appWindow,l.end)
        if with_depths:
            gc=appWindow.gc
        else:
            if l.istransfer:
                gc=appWindow.red_gc
            else:
                gc=appWindow.blue_gc
        appWindow.pixmap.draw_line(gc, x1, y1, x2, y2)
    appWindow.content.queue_draw_area(0,0,appWindow.width,height)

redraw(appWindow)

def toggle_sleeps(event):
    global show_sleeps
    show_sleeps = not show_sleeps
    redraw(appWindow)

ts=gtk.ToggleButton('Show Sleeps')
ts.connect('clicked',toggle_sleeps)
appWindow.toolbar.add(ts)

appWindow.window.show_all()
gtk.main()
