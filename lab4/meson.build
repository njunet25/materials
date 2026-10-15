project('bpf_cc', 'c')

custom_target('bpf_cc.o',
  input: 'src/bpf_cc.bpf.c',
  output: 'bpf_cc.o',
  command: [
    'clang', '-target', 'bpf',
    '-O2', '-g', '-Wall',
    '-D__TARGET_ARCH_x86',
    '-I..', '-I.', '-I/usr/include',
    '-c', '@INPUT@', '-o', '@OUTPUT@'
  ],
)
