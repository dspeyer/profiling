#!/usr/bin/python

from parse import parse
from mainWindow import MainWindow
import gtk
from sys import argv
from sys import setrecursionlimit

setrecursionlimit(1500)

data=parse(argv[1])

win=MainWindow(data, argv[1])
gtk.main()
