#!/bin/sh

FN="perf`date|tr -c 0-9a-zA-Z _`.scr"

if sudo perf probe -l | grep tcp > /dev/null; then
    echo "net probes already in place"
else
    sudo perf probe --add 'tcp_v4_connect sk'
    sudo perf probe --add 'tcp_rcv_established sk'
    sudo perf probe --add 'tcp_finish_connect sk'
    sudo perf probe --add 'tcp_sendmsg sk'
    sudo perf probe --add 'udp_sendmsg sk'
    sudo perf probe --add 'udp_queue_rcv_skb sk'
fi

sudo perf record -a --call-graph dwarf -F 12500 -e 'sched:sched_wakeup,sched:sched_switch,sched:sched_process_exec,cycles,sched:sched_process_fork,block:block_rq_issue,block:block_rq_complete,block:block_rq_insert,irq:irq_handler_entry,probe:*' -m 16M "$@"

sudo perf script -f trace:tid,comm,time,event,trace,sym,ip,dso > $FN

echo "Saved to $FN"

`echo $0 | sed "s/profile.sh/main.py/"` $FN

