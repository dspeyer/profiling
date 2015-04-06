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
        self.redraw()
        self.window.show_all()

    def redraw(self):
        self.content.set_size_request(self.width, self.height)
        self.pixmap = gtk.gdk.Pixmap(self.content.window, self.width, self.height)
        self.pixmap.draw_rectangle(self.white_gc, True, 0, 0, self.width, self.height)
        for cp in self.roots:
            self.mergeAndDrawBoxes(self.roots[cp])
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
        subboxes=[]
        for box in sorted(boxes,key=lambda(box):box.start):            
            if 'stack' in box.__dict__:
                subboxes.append(struct(color=self.blue_gc, start=box.start, end=box.end, stack=box.stack, proc=box.proc))
                if 'children' in box.wdata[self.id].__dict__:
                    subboxes[-1].children=box.wdata[self.id].children
                else:
                    subboxes[-1].children=[]
            elif 'stacks' in box.__dict__ and len(box.stacks)>0:
                nstacks=len(box.stacks)
                for i in range(len(box.stacks)):
                    t1=box.start+i*(box.end-box.start)/nstacks
                    t2=box.start+(i+1)*(box.end-box.start)/nstacks
                    subboxes.append(struct(color=self.pink_gc, start=t1, end=t2, stack=box.stacks[i], children=[], proc=box.proc))
            else:
                subboxes.append(struct(start=box.start, end=box.end, stack=[struct(function='?',file='?')], proc=box.proc))
                if box.type=='run':
                    subboxes[-1].color=self.pink_gc
                else:
                    subboxes[-1].color=self.blue_gc
                if 'children' in box.wdata[self.id].__dict__:
                    subboxes[-1].children=box.wdata[self.id].children
                else:
                    subboxes[-1].children=[]
        self.mergeAndDrawSubBoxes(subboxes, -1, boxes[0].wdata[self.id].bottom)

    def mergeAndDrawSubBoxes(self, subboxes, frame, bottom):
        if len(subboxes)==0:
            return
        boxToDraw=None
        sn=0
        for i in xrange(len(subboxes)):
            sb=subboxes[i]
            if self.xfromt(sb.end)-self.xfromt(sb.start)<2:
                continue
            if frame==-1:
                text=sb.proc
            elif frame<len(sb.stack):
                text = sb.stack[-1-frame].function
            else:
                text = None
            if boxToDraw and (self.xfromt(sb.start)>self.xfromt(boxToDraw.end)+5 or text!=boxToDraw.text):
                if boxToDraw.text:
                    if frame==-1:
                        boxToDraw.color=self.grey_gc
                    self.draw_rectangle(boxToDraw.color, boxToDraw.start, boxToDraw.end, self.physFromLogY(bottom+1+frame), boxToDraw.text)
                    self.mergeAndDrawSubBoxes(subboxes[sn:i], frame+1, bottom)
                else:
                    self.mergeAndDrawBoxes(boxToDraw.children)
                boxToDraw=None
            if not boxToDraw:
                boxToDraw=struct(color=sb.color, start=sb.start, end=sb.end, text=text, children=sb.children)
                sn=i
            else:
                boxToDraw.end=sb.end
                if boxToDraw.color!=sb.color:
                    boxToDraw.color=self.purple_gc
                for child in sb.children:
                    boxToDraw.children.append(child)
        if boxToDraw:
            if boxToDraw.text:
                if frame==-1:
                    boxToDraw.color=self.grey_gc
                self.draw_rectangle(boxToDraw.color, boxToDraw.start, boxToDraw.end, self.physFromLogY(bottom+1+frame), boxToDraw.text)
                self.mergeAndDrawSubBoxes(subboxes[sn:], frame+1, bottom)
            else:
                self.mergeAndDrawBoxes(boxToDraw.children)

    def rtag(self, box, parent, onstack={}, dbgdep=0):
        d=box.wdata[self.id]
        if 'cp' in d.__dict__:
            return
        if parent:
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
