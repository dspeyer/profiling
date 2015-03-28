#include<unistd.h>

int toc[2], top[2], tome, fromme;

void __attribute__ ((noinline)) block(){
  char buf[2];
  read(tome,buf,1);
}

void  __attribute__ ((noinline)) realtrigger(){
  write(fromme,"\n",1);
}

void  __attribute__ ((noinline)) trigger(){
  realtrigger();
}

void __attribute__ ((noinline)) do_remaining_work(int* data){
  for (int j=0; j<2000; j++) {
    for (int i=1000; i<1024; i++) {
      data[i]*=i;
    }
  }
}

void __attribute__ ((noinline)) work(){
  int data[1024];
  for (int i=0; i<1024; i++) {
    data[i]=i;
  }
  for (int j=0; j<1000; j++) {
    for (int i=0; i<1024; i++) {
      data[i]*=i;
    }
  }
  do_remaining_work(data);
}

void __attribute__ ((noinline)) realmain(){
  pipe(toc);
  pipe(top);
  if (fork()){
    tome=toc[0];
    fromme=top[1];
    block();
  } else {
    tome=top[0];
    fromme=toc[1];
  }
  while(1) {
    work();
    trigger();
    block();
  }
}

int main() {
  realmain();
}
