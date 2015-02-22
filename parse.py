#!/usr/bin/python

import re
import svgwrite
from collections import defaultdict

class struct:
    def __init__(self,**kwargs):
        for k in kwargs:
            setattr(self,k,kwargs[k])

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
                continue
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
            runs[oldp].append(struct(start=switchedin[source], end=ev.time))
        switchedin[source]=-1                        
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
h=20
p='swapper/0(0)'
while True:
    heights[p]=h
    h+=20
    bestv=-1
    bestp=''
    for nextp in ps:
        if nextp in heights:
            continue
        if nextp[0:6]=='mysqld': # There are so many of these, they make things unreadable
            continue
        conn=connectedness[p][nextp]
        if conn>bestv:
            bestv=conn
            bestp=nextp
    if bestv==-1: # Nothing left to assign
        break
    p=bestp

def xfromt(t):
    return 200+2000*(t-starttime)/(endtime-starttime)


# Now draw
d=svgwrite.Drawing('perf.svg') # TODO: flexible file name
for p in runs:
    if p not in heights:
        continue
    h=heights[p]
    d.add(d.text(p,insert=(0,h)))
    for r in runs[p]:
        x1=xfromt(r.start)
        x2=xfromt(r.end)
        y1=h-10
        y2=h
        d.add(d.rect(insert=(x1,y1), size=(x2-x1,y2-y1)))
for l in links:
    if l.source not in heights or l.target not in heights:
        continue
    x1=xfromt(l.start)
    y1=heights[l.source]-5
    x2=xfromt(l.end)
    y2=heights[l.target]-5
    d.add(d.line((x1,y1),(x2,y2),stroke=svgwrite.rgb(100, 0, 0, '%')))

d.save()
