#!/usr/bin/python

from parse import parse
from mainWindow import MainWindow
import gtk
from sys import argv

data=parse(argv[1])

win=MainWindow(data)
win.window.show_all()
win.redraw()
gtk.main()
