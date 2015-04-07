import gtk
import pango
from collections import defaultdict
from copy import copy

from appWindow import AppWindow
from parse import struct

grace=1e-4

class FlameWindow(AppWindow):
    def __init__(self, data, target):
        AppWindow.__init__(self, data.starttime, data.endtime)
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
            'proc': self.grey_gc
        }

        self.redraw()
        self.window.show_all()

    def redraw(self):
        self.content.set_size_request(self.width, self.height)
        self.pixmap.draw_rectangle(self.white_gc, True, 0, 0, self.width, self.height)
        self.ipFrames=defaultdict(lambda:None)
        for cp in self.roots:
            self.mergeAndDrawBoxes(self.roots[cp])
        for y in self.ipFrames:
            if self.ipFrames[y]:
                self.finalize_frame(self.ipFrames[y], y)
        self.ipFrames=None
        for l in self.links:
            if (not l.istransfer and
                'sourcerun' in l.__dict__ and 'targetrun' in l.__dict__ and
                'bottom' in l.sourcerun.wdata[self.id].__dict__ and 'bottom' in l.targetrun.wdata[self.id].__dict__):
                y1=self.getY(l.sourcerun)+int(self.rowheight/2)
                y2=self.getY(l.targetrun)+int(self.rowheight/2)
                self.draw_line(self.red_gc, l.start, y1, l.end, y2)
        for y in self.cpStartHeights[:-1]:
            py=int((self.lheight-y+.5)*self.rowheight)
            self.draw_line(self.gc, self.data.starttime, py, self.data.endtime, py)
        self.content.queue_draw_area(0, 0, self.width, self.height)


    def mergeAndDrawBoxes(self, boxes):
        if len(boxes)==0:
            return
        for box in sorted(boxes,key=lambda(box):box.start):
            y=box.wdata[self.id].bottom
            self.put_frame(box.proc, box.start, box.end, y, 'proc')
            y+=1
            if 'stack' in box.__dict__:
                for frame in reversed(box.stack):
                    self.put_frame(frame.function, box.start, box.end, y, box.type)
                    y+=1
            elif 'stacks' in box.__dict__ and len(box.stacks)>0:
                nstacks=len(box.stacks)
                for i in range(len(box.stacks)):
                    y=box.wdata[self.id].bottom+1
                    t1=box.start+i*(box.end-box.start)/nstacks
                    t2=box.start+(i+1)*(box.end-box.start)/nstacks
                    for frame in reversed(box.stacks[i]):
                        self.put_frame(frame.function, t1, t2, y, box.type)
                        y+=1
            else:
                self.put_frame('?', box.start, box.end, y, box.type)
                y+=1
            if 'children' in box.wdata[self.id].__dict__:
                self.mergeAndDrawBoxes(box.wdata[self.id].children)

    def put_frame(self, text, start, end, y, typ):
        if self.xfromt(end)-self.xfromt(start)<2:
            return
        if self.ipFrames[y]:
            if text==self.ipFrames[y].text and self.xfromt(start)-self.xfromt(self.ipFrames[y].end)<5:
                self.ipFrames[y].end=end
                if self.ipFrames[y].typ!=typ:
                    self.ipFrames[y].typ='mixed'
            else:
                self.finalize_frame(self.ipFrames[y], y)
                self.ipFrames[y]=None
        if not self.ipFrames[y]:
            self.ipFrames[y]=struct(text=text,start=start,end=end,typ=typ)

    def finalize_frame(self, frame, y):
        self.draw_rectangle(self.gcByType[frame.typ], frame.start, frame.end, self.physFromLogY(y), frame.text)



    def rtag(self, box, parent, onstack={}, dbgdep=0):
        d=box.wdata[self.id]
        if 'cp' in d.__dict__:
            return
        if parent:
            if 'cp' not in parent.wdata[self.id].__dict__:
                return
            if box.start+grace<parent.start or box.end-grace>parent.end:
                if box.type=='run':
                    self.maxcp+=1
                    d.cp=self.maxcp
                    d.bottom=0
                else:
                    return
            else:
                d.parent=parent
                if 'children' not in parent.wdata[self.id].__dict__:
                    parent.wdata[self.id].children=[]
                parent.wdata[self.id].children.append(box)
                d.cp=parent.wdata[self.id].cp
                d.bottom=parent.wdata[self.id].top
        else:
            d.cp=0
            d.bottom=0
        if d.bottom==0:
            self.roots[d.cp].append(box)
        d.top = d.bottom+self.runheight(box)
        if d.top>self.maxdepth[d.cp]:
            self.maxdepth[d.cp]=d.top
        if 'inlink' in box.__dict__ and box.inlink.source in onstack:
            return
        if 'prev' in box.__dict__:
            self.rtag(box.prev, parent, onstack, dbgdep+1)
            if 'inlink' in box.__dict__ and 'sourcerun' in box.inlink.__dict__:
                if 'horizontal' in box.inlink.__dict__:
                    self.rtag(box.prev, parent, onstack, dbgdep+1)
                else:
                    newstack=copy(onstack)
                    newstack[box.proc]=1
                    self.rtag(box.inlink.sourcerun, box.prev, newstack, dbgdep+1)


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
