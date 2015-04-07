#!/bin/sh

./pass &
sudo perf record -a -g -F 999 -e 'sched:sched_wakeup,sched:sched_switch,sched:sched_process_exec,cycles,block:block_bio_queue,sched:sched_process_fork' sleep 1
killall pass

sudo perf script -f trace:tid,comm,time,event,trace,sym,ip,dso > perf.scr

./main.py perf.scr

