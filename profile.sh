#!/bin/sh

FN="perf`date|tr -c 0-9 _`.scr"

sudo perf record -a --call-graph dwarf -F 999 -e 'sched:sched_wakeup,sched:sched_switch,sched:sched_process_exec,cycles,block:block_bio_queue,sched:sched_process_fork' "$@"

sudo perf script -f trace:tid,comm,time,event,trace,sym,ip,dso > $FN

echo "Saved to $FN"

`echo $0 | sed "s/profile.sh/main.py/"` $FN

