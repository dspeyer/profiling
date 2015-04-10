import gtk
import pango
from collections import defaultdict
from copy import copy

from appWindow import AppWindow
from parse import struct

grace=1e-3

class FlameWindow(AppWindow):
    def __init__(self, data, target):
        AppWindow.__init__(self, data.runs[target][0].start, data.runs[target][-1].end)
        self.starttimelabels=data.starttime
        self.endtimelabels=data.endtime
        self.window.set_title('Flameview: '+target)

        self.data=data
        self.boxes=data.boxes
        self.links=data.links

        self.maxdepth=defaultdict(lambda:0)
        self.roots=defaultdict(lambda:[])
        self.maxcp=0
        for r in data.runs[target]:
            self.rtag(r,None)
        self.cpStartHeights=[]
        self.lheight=0
        self.rowheight=20
        for i in range(self.maxcp+1):
            self.cpStartHeights.append(self.lheight)
            self.lheight+=self.maxdepth[i]+1
        self.height=self.lheight*self.rowheight

        self.gcByType={
            'run': self.pink_gc,
            'sleep': self.blue_gc,
            'mixed': self.purple_gc,
            'proc': self.grey_gc,
            'bio': self.green_gc
        }

        self.redraw()
        self.window.show_all()

    def redraw(self):
        self.content.set_size_request(self.width, self.height)
        self.pixmap.draw_rectangle(self.white_gc, True, 0, 0, self.width, self.height)
        self.ipFrames=defaultdict(lambda:None)
        for cp in self.roots:
            print '%d roots at %d'%(len(self.roots[cp]),cp)
            self.mergeAndDrawBoxes(self.roots[cp], True)
        for y in self.ipFrames:
            if self.ipFrames[y]:
                self.finalize_frame(self.ipFrames[y], y)
        self.ipFrames=None
        for l in self.links:
            if  ('sourcerun' in l.__dict__ and 'targetrun' in l.__dict__ and
                 'bottom' in l.sourcerun.wdata[self.id].__dict__ and 
                 'bottom' in l.targetrun.wdata[self.id].__dict__ and
                 l.sourcerun.wdata[self.id].cp!=l.targetrun.wdata[self.id].cp):
                y1=self.getY(l.sourcerun)+int(self.rowheight/2)
                y2=self.getY(l.targetrun)+int(self.rowheight/2)
                self.draw_line(self.red_gc, l.start, y1, l.end, y2)
        for y in self.cpStartHeights[:-1]:
            py=int((self.lheight-y+.5)*self.rowheight)
            self.draw_line(self.gc, self.data.starttime, py, self.data.endtime, py)
        self.content.queue_draw_area(0, 0, self.width, self.height)


    def mergeAndDrawBoxes(self, boxes, can_merge_proc):
        if len(boxes)==0:
            return
        for box in sorted(boxes,key=lambda(box):box.start):
            y=self.getY(box)
            merged=self.put_frame(box.proc, box.start, box.end, y, 'proc' if box.type!='bio' else 'bio', can_merge_proc)
            can_merge_proc=True
            y-=self.rowheight
            if 'stack' in box.__dict__:
                for frame in reversed(box.stack):
                    merged=self.put_frame(frame.function, box.start, box.end, y, box.type, merged)
                    y-=self.rowheight
            elif 'stacks' in box.__dict__ and len(box.stacks)>0:
                nstacks=len(box.stacks)
                for i in range(len(box.stacks)):
                    y=self.getY(box)-self.rowheight
                    t1=box.start+i*(box.end-box.start)/nstacks
                    t2=box.start+(i+1)*(box.end-box.start)/nstacks
                    for frame in reversed(box.stacks[i]):
                        merged=self.put_frame(frame.function, t1, t2, y, box.type, merged)
                        y-=self.rowheight
                    merged=True
            elif box.type=='run':
                stack=None
                try:
                    i=box
                    while i.inlink.horizontal and len(i.stacks)==0:
                        i=i.inlink.sourcerun
                    stack=reversed(i.stacks[-1])
                except (AttributeError,IndexError) as e:
                    pass
                if not stack:
                    try:
                        i=box
                        while len(i.stacks)==0:
                            i=i.horizoutlink.targetrun
                        stack=reversed(i.stacks[0])
                    except (AttributeError,IndexError) as e:
                        pass
                if not stack:
                    stack=[struct(function='?',file='?')]
                for frame in stack:
                    merged=self.put_frame(frame.function, box.start, box.end, y, box.type, merged)
                    y-=self.rowheight
            if 'children' in box.wdata[self.id].__dict__:
                self.mergeAndDrawBoxes(box.wdata[self.id].children, merged)

    def put_frame(self, text, start, end, y, typ, can_connect):
        if self.xfromt(end)-self.xfromt(start)<2:
            return
        if self.ipFrames[y]:
            if can_connect and text==self.ipFrames[y].text and self.xfromt(start)-self.xfromt(self.ipFrames[y].end)<5:
                self.ipFrames[y].end=end
                if self.ipFrames[y].typ!=typ:
                    self.ipFrames[y].typ='mixed'
                return True
            else:
                self.finalize_frame(self.ipFrames[y], y)
                self.ipFrames[y]=None
        self.ipFrames[y]=struct(text=text,start=start,end=end,typ=typ)
        return False

    def finalize_frame(self, frame, y):
        self.draw_rectangle(self.gcByType[frame.typ], frame.start, frame.end, y, frame.text)



    def rtag(self, box, parent, stack=[], cp=0):
        d=box.wdata[self.id]
        if 'cp' in d.__dict__:
            return
        if parent:
            if 'cp' not in parent.wdata[self.id].__dict__:
                return
            if box.start+grace<parent.start or box.end-grace>parent.end:
                #if box.type=='run':
                    if box.proc in ['imap(492)', 'apache2(16380)']:
                        print 'making %s(%f-%f) a new cp'%(box.proc,box.start,box.end)
                    self.maxcp+=1
                    d.cp=self.maxcp
                    d.bottom=0
                    parent=None
                #else:
                #    return
            else:
                d.parent=parent
                if 'children' not in parent.wdata[self.id].__dict__:
                    parent.wdata[self.id].children=[]
                parent.wdata[self.id].children.append(box)
                d.cp=parent.wdata[self.id].cp
                d.bottom=parent.wdata[self.id].top
        else:
            d.cp=cp
            d.bottom=0
        if d.bottom==0:
            self.roots[d.cp].append(box)
        d.top = d.bottom+self.runheight(box)
        if d.top>self.maxdepth[d.cp]:
            self.maxdepth[d.cp]=d.top
        if box.proc=='dovecot(4889)':
            print 'in dovecot %f-%f'%(box.start,box.end)
        if 'prev' in box.__dict__:
            if 'inlink' in box.__dict__ and 'sourcerun' in box.inlink.__dict__:
                if 'horizontal' in box.inlink.__dict__:
                    self.rtag(box.prev, parent, stack, d.cp)
                    self.rtag(box.inlink.sourcerun, parent, stack, d.cp)
                else:
                    for i in xrange(len(stack)):
                        if box.inlink.source==stack[i].proc:
                                self.rtag(box.inlink.sourcerun, stack[i].par, stack[0:i], d.cp)
                                return
                    if box.proc=='dovecot(4889)':
                        print "...going prev"
                    self.rtag(box.prev, parent, stack, d.cp)
                    newstack=copy(stack)
                    newstack.append(struct(proc=box.proc, par=parent))
                    self.rtag(box.inlink.sourcerun, box.prev, newstack, d.cp)
            else:
                self.rtag(box.prev, parent, stack, d.cp)
        elif 'inlink' in box.__dict__ and 'sourcerun' in box.inlink.__dict__:
            if box.proc=='dovecot(4889)':
                print "...following link"
            self.rtag(box.inlink.sourcerun, parent, stack, d.cp)
        else:
            if box.proc=='dovecot(4889)':
                print "...dead end %s %s"%('inlink' in box.__dict__, 'sourcerun' in box.inlink.__dict__)

    def runheight(self, run):
        if run.type=='sleep':
            if 'stack' in run.__dict__:
                return len(run.stack)+1
            else:
                return 1
        else:
            if 'stacks' in run.__dict__ and run.stacks:
                return max([len(i) for i in run.stacks])+1
            else:
                return 1
    
    def drawStack(self, base, stack, color, x1, x2, startY):
        y=startY
        self.draw_rectangle(self.grey_gc, x1, x2, y, base)
        for frame in reversed(stack):
            y-=self.rowheight
            self.draw_rectangle(color, x1, x2, y, frame.function)


    def getY(self,run):
        depth = self.cpStartHeights[run.wdata[self.id].cp] + run.wdata[self.id].bottom
        out = (self.lheight-depth-1)*self.rowheight
        return out

    def physFromLogY(self, logY):
        return  (self.lheight-logY-1)*self.rowheight
