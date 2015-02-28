#!/usr/bin/python

from collections import defaultdict
import gtk
import re
import svgwrite

class struct:
    def __init__(self,**kwargs):
        for k in kwargs:
            setattr(self,k,kwargs[k])


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

        self.pixmap = gtk.gdk.Pixmap(self.content.window, 1, 1)
        self.content.connect('expose-event', self.expose_event)

    def expose_event(self, widget, event):
        x , y, width, height = event.area
        widget.window.draw_drawable(self.gc, self.pixmap, x, y, x, y, width, height)
        return False


appWindow=AppWindow()

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
    m=re.match('(.*[^ ]) +([0-9]*) +([0-9]*\\.[0-9]*): +([^ ]*): +(.*)',line)
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
                print "WARNING: deduced exec call by %d from %s to %s at %f" % (ev.pid, fake_ev.oldcomm, ev.comm, ev.time)
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
gotwoken={}
runs=defaultdict(lambda:[])
links=[]

starttime=evs[0].time
endtime=evs[-1].time

for ev in evs:
    if ev.event=='sched:sched_switch':
        oldp='%s(%s)'%(ev.args.prev_comm,ev.args.prev_pid)
        newp='%s(%s)'%(ev.args.next_comm,ev.args.next_pid)
        if oldp in switchedin:
            if switchedin[oldp]==-1:
                print "ERROR: %s switched out without being in at %f" % (oldp, ev.time)
            else:
                runs[oldp].append(struct(start=switchedin[oldp], end=ev.time))
                switchedin[oldp]=-1
        else:
            runs[oldp].append(struct(start=starttime, end=ev.time))
            switchedin[oldp]=-1
        if newp in switchedin and switchedin[newp]!=-1:
            print "ERROR: %s switched in twice (%f and %f)"%(newp,ev.time,switchedin[newp])
        else:
            switchedin[newp]=ev.time
        if newp in gotwoken:
            links.append(struct(source=gotwoken[newp].source, start=gotwoken[newp].start, target=newp, end=ev.time))
            del gotwoken[newp]
    elif ev.event=='sched:sched_wakeup':
        is_interrupt=False
        for frame in ev.stack:
            if frame.function=='irq_exit':
                is_interrupt=True
                break
        if is_interrupt:
            continue
        source='%s(%s)'%(ev.comm,ev.pid)
        target='%s(%s)'%(ev.args.comm, ev.args.pid)
        gotwoken[target]=struct(source=source, start=ev.time)
    elif ev.event=='sched:sched_process_exec':
        source='%s(%d)'%(ev.oldcomm,ev.pid)
        target='%s(%d)'%(ev.comm,ev.pid)
        links.append(struct(source=source, start=ev.time, target=target, end=ev.time))
        if source in switchedin and switchedin[source]!=-1:
            print 'making run for %s from %f to %f'%(source,switchedin[source],ev.time)
            runs[source].append(struct(start=switchedin[source], end=ev.time))
        switchedin[source]=-1
        switchedin[target]=ev.time
    else:
        print 'ERROR: unhandled event "%s"'%ev.event

for p in switchedin:
    if switchedin[p]!=-1:
        runs[p].append(struct(start=switchedin[p], end=endtime))

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

# Assign heights to processes with a simple greedy algorithm
heights={}
h=0
p='swapper/0(0)'
while True:
    heights[p]=h
    label=gtk.Label(p)
    appWindow.legend.pack_start(label, expand=False, fill=False)
    h+=label.size_request()[1]
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
width=2000



def xfromt(t):
    return int(width*(t-starttime)/(endtime-starttime))

def redraw():
    appWindow.content.set_size_request(width,height)
    appWindow.pixmap = gtk.gdk.Pixmap(appWindow.content.window, width, height)
    appWindow.pixmap.draw_rectangle(appWindow.white_gc, True, 0, 0, width, height)
    for p in runs:
        if p not in heights:
            continue
        h=heights[p]
        for r in runs[p]:
            x1=xfromt(r.start)
            x2=xfromt(r.end)
            y1=h
            y2=h+10
            appWindow.pixmap.draw_rectangle(appWindow.gc, True, x1, y1, x2-x1, y2-y1)
    for l in links:
        if l.source not in heights or l.target not in heights:
            continue
        x1=xfromt(l.start)
        y1=heights[l.source]+5
        x2=xfromt(l.end)
        y2=heights[l.target]+5
        appWindow.pixmap.draw_line(appWindow.red_gc, x1, y1, x2, y2)

redraw()

def zoom(ratio):
    global width
    width=int(ratio*width)
    redraw()
    appWindow.hadj.set_value(int(appWindow.hadj.get_value()*ratio))

zi=gtk.Button('Zoom In')
appWindow.toolbar.add(zi)
zi.connect('clicked',lambda(event): zoom(2))
zo=gtk.Button('Zoom Out')
appWindow.toolbar.add(zo)
zo.connect('clicked',lambda(event): zoom(0.5))

appWindow.window.show_all()
gtk.main()
