#!/bin/sh

FN="perf`date|tr -c 0-9 _`.scr"

sudo perf record -a --call-graph dwarf -F 9999 -e 'sched:sched_wakeup,sched:sched_switch,sched:sched_process_exec,cycles,sched:sched_process_fork,block:block_rq_issue,block:block_rq_complete,block:block_rq_insert,irq:irq_handler_entry' -m 16M "$@"

sudo perf script -f trace:tid,comm,time,event,trace,sym,ip,dso > $FN

echo "Saved to $FN"

`echo $0 | sed "s/profile.sh/main.py/"` $FN

