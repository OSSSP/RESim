from simics import *
import taskUtils
class TraceOpen():
    OPEN = 5
    def __init__(self, param, mem_utils, task_utils, cpu, cell, lgr):
        self.cpu = cpu
        self.cell = cell
        self.pid = None
        self.param = param
        self.mem_utils = mem_utils
        self.task_utils = task_utils
        self.open_break = None
        self.open_hap = None
        self.report_fh = None
        self.lgr = lgr
        self.lgr.debug('TraceOpen __init__ done')


    def traceOpenSyscall(self, pid = None):
        self.lgr.debug('traceOpen called')
        self.pid = pid
        entry = self.task_utils.getSyscallEntry(self.OPEN)
        self.lgr.debug('traceOpen set break at 0x%x' % entry)
        self.open_break = SIM_breakpoint(self.cell, Sim_Break_Linear, Sim_Access_Execute, entry, self.mem_utils.WORD_SIZE, 0)
        self.open_hap = SIM_hap_add_callback_index("Core_Breakpoint_Memop", self.openHap, self.cpu, self.open_break)
        self.report_fh = open('/tmp/open.txt', 'w')

    def openHap(self, hap_cpu, third, forth, memory):
        #cpu = SIM_current_processor()
        #if cpu != hap_cpu:
        #    self.lgr.debug('openHap, wrong cpu %s %s' % (cpu.name, hap_cpu.name))
        #    return
        cpu, comm, pid = self.task_utils.curProc() 
        #stack_frame = self.task_utils.frameFromStack()
        stack_frame = self.task_utils.frameFromStackSyscall()
        self.lgr.debug('frame: %s' % taskUtils.stringFromFrame(stack_frame))
        
        fname = self.mem_utils.readString(cpu, stack_frame['ebx'], 512)
        mode = stack_frame['edx']
        self.report_fh.write('fopen from %d (%s) mode: 0x%x file: %s  \n' % (pid, comm, mode, fname))
        #SIM_break_simulation('fopen from %d (%s) ebx: 0x%x\n' % (pid, comm, stack_frame['ebx'])) 
