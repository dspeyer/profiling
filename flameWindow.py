import gtk
import pango
from collections import defaultdict
from copy import copy

from appWindow import AppWindow

class FlameWindow(AppWindow):
    def __init__(self, data, target):
        AppWindow.__init__(self, data.starttime, data.endtime)
        self.window.set_title('Flameview: '+target)

        self.boxes=data.boxes
        self.links=data.links

        self.maxdepth=defaultdict(lambda:0)
        self.maxcp=0
        for p in data.runs:
            for r in data.runs[p]:
                if 'depth' in r.__dict__:
                    del r.depth
        for r in data.runs[target]:
            self.rtag(r,0,0,{})
        self.cumHeights=[]
        self.lheight=0
        self.rowheight=20
        for i in range(self.maxcp+1):
            self.cumHeights.append(self.lheight+1)
            self.lheight+=self.maxdepth[i]+1
        self.height=self.lheight*self.rowheight
        self.redraw()
        self.window.show_all()

    def redraw(self):
        self.content.set_size_request(self.width, self.height)
        self.pixmap = gtk.gdk.Pixmap(self.content.window, self.width, self.height)
        self.pixmap.draw_rectangle(self.white_gc, True, 0, 0, self.width, self.height)
        for b in self.boxes:
            if 'depth' not in b.__dict__ or 'cp' not in b.__dict__:
                continue
            y=self.getY(b)
            if 'stacks' in b.__dict__ and b.stacks:
                nstacks=len(b.stacks)
                for i in range(len(b.stacks)):
                    t1=b.start+i*(b.end-b.start)/nstacks
                    t2=b.start+(i+1)*(b.end-b.start)/nstacks
                    self.drawStack(b.proc, b.stacks[i], self.red_gc, t1, t2, y)
            elif 'stack' in b.__dict__ and b.stack:
                self.drawStack(b.proc, b.stack, self.blue_gc, b.start, b.end, y)
            else:
                self.draw_rectangle(self.grey_gc, b.start, b.end, y, b.proc)
        for l in self.links:
            if ('sourcerun' in l.__dict__ and 'targetrun' in l.__dict__ and
                'depth' in l.sourcerun.__dict__ and 'depth' in l.targetrun.__dict__):
                y1=self.getY(l.sourcerun)+int(self.rowheight/2)
                y2=self.getY(l.targetrun)+int(self.rowheight/2)
                self.draw_line(self.red_gc, l.start, y1, l.end, y2)
        for y in self.cumHeights[:-1]:
            self.pixmap.draw_line(gc, self.data.starttime, (y+.5)*self.rowheight, self.data.endtime, (y+.5)*self.rowheight)
        self.content.queue_draw_area(0, 0, self.width, self.height)


    def rtag(self, run, depth, cp, onstack):
        if 'depth' in run.__dict__:
            return
        if depth+self.runheight(run)>self.maxdepth[cp]:
            self.maxdepth[cp]=depth+self.runheight(run)
        run.depth=depth
        run.cp=cp
        if 'inlink' in run.__dict__ and 'sourcerun' in run.inlink.__dict__ and run.inlink.source in onstack and run.inlink.source!=run.proc:
            return
        if 'prev' in run.__dict__:
            self.rtag(run.prev,depth,cp,onstack)
        if 'inlink' in run.__dict__ and 'sourcerun' in run.inlink.__dict__:
            if run.inlink.source in onstack and run.inlink.source!=run.proc:
                return
            newstack=copy(onstack)
            newstack[run.proc]=1
            if 'horizontal' in run.inlink.__dict__:
                newdepth=depth
            elif 'prev' in run.__dict__:
                newdepth=run.prev.depth+self.runheight(run.prev)
            else:
                newdepth=depth+1
            if run.inlink.istransfer:
                newcp=cp
            else:
                self.maxcp+=1
                newcp=self.maxcp
            self.rtag(run.inlink.sourcerun,newdepth,newcp,newstack)

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
        depth = self.cumHeights[run.cp] + run.depth
        out = (self.lheight-depth)*self.rowheight
        return out

