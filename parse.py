#!/usr/bin/python

from collections import defaultdict
import re
from copy import copy

class struct:
    def __init__(self,**kwargs):
        for k in kwargs:
            setattr(self,k,kwargs[k])

def parse(fn):
    f = file(fn)

    commbypid={} # Needed to handle exec correctly
    evs = []

    # First parse the events
    for line in f:
        if line[0]=='#':
            continue
        if line=='\n':
            continue
        m=re.match('(.*[^ ]) +([0-9]+)(?: \\[[0-9]*\\])? +([0-9]*\\.[0-9]*): +([^ ]*): +(.*)',line)
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
        if m and evs:
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
    runningstacks={}
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
                    if oldp in runningstacks:
                        runs[oldp][-1].stacks=runningstacks[oldp]
                    else:
                        runs[oldp][-1].stacks=[]
                    switchedin[oldp]=-1
            else:
                runs[oldp].append(struct(start=starttime, end=ev.time))
                switchedin[oldp]=-1
            if oldp in runningstacks:
                del runningstacks[oldp]
            runningstacks[newp]=[]
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
        elif ev.event=='cycles':
            proc='%s(%d)'%(ev.comm,ev.pid)
            if proc in runningstacks:
                runningstacks[proc].append(ev.stack)
            else:
                print 'WARNING: sample for %s at %f which is not running according to sched events'%(proc,ev.time)
        else:
            print 'ERROR: unhandled event "%s"'%ev.event

    # Only include completed links
    links = [link for link in links if 'end' in link.__dict__];

    # Finish ongoing runs
    for p in switchedin:
        if switchedin[p]!=-1:
            runs[p].append(struct(start=switchedin[p], end=endtime))

    # Create repframes for sleeps
    for p in sleeps:
        for s in sleeps[p]:
            for frame in s.stack:
                if frame.file!='[kernel.kallsyms]':
                    s.repframe=frame.function
                    break
                s.repframe='?'

    # Mark boxes with types
    for p in runs:
        for r in runs[p]:
            r.proc=p
            r.type='run'
    for p in sleeps:
        for s in sleeps[p]:
            s.proc=p
            s.type='sleep'

    # Mark links as transfer
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

    boxes=[]
    for p in runs:
        boxes+=runs[p]
    for p in sleeps:
        boxes+=sleeps[p]

    procs=set(runs.keys()) | set(sleeps.keys());
    
    return struct(runs=runs, 
                  sleeps=sleeps, 
                  links=links, 
                  boxes=boxes, 
                  procs=procs, 
                  evs=evs,
                  starttime=starttime, 
                  endtime=endtime)
