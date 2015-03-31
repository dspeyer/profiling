#!/bin/sh

./pass &
sudo perf record -a -g -e 'sched:sched_wakeup,sched:sched_switch,sched:sched_process_exec' sleep 1
killall pass

sudo perf script -f trace:tid,comm,time,event,trace,sym,ip,dso > perf.scr

./parse.py

