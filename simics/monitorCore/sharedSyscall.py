from simics import *
import pageUtils
import memUtils
import net
import ipc
import allWrite
import syscall
'''
Handle returns to user space from system calls.  May result in call_params matching.  NOTE: stop actions (stop_action) for matched parameters
are handled by the stopHap in the syscall module that handled the call.
'''
class SharedSyscall():
    def __init__(self, top, cpu, cell, cell_name, param, mem_utils, task_utils, context_manager, traceProcs, traceFiles, soMap, dataWatch, traceMgr, lgr):
        self.pending_execve = []
        self.lgr = lgr
        self.cpu = cpu
        self.cell = cell
        self.cell_name = cell_name
        self.task_utils = task_utils
        self.param = param
        self.mem_utils = mem_utils
        self.context_manager = context_manager
        self.traceProcs = traceProcs
        self.exit_info = {}
        self.exit_pids = {}
        self.trace_procs = []
        self.exit_hap = {}
        self.exit_names = {} 
        self.debugging = False
        self.traceMgr = traceMgr
        self.traceFiles = traceFiles
        self.soMap = soMap
        self.dataWatch = dataWatch
        self.top = top
        self.track_so = True
        self.all_write = False
        self.allWrite = allWrite.AllWrite()

    def trackSO(self, track_so):
        #self.lgr.debug('sharedSyscall track_so %r' % track_so)
        self.track_so = track_so

    def setDebugging(self, debugging):
        self.lgr.debug('SharedSyscall set debugging %r' % debugging)
        self.debugging = debugging

    def getPendingCall(self, pid, name):
        if pid in self.exit_info:
            if name in self.exit_info[pid]:
                return self.exit_info[pid][name].callnum
            elif len(self.exit_info[pid]) > 0:
                existing = next(iter(self.exit_info[pid]))
                self.lgr.debug('sharedSyscall getPendingCall, no call for %s, returning for %s' % (name, existing))
                return self.exit_info[pid][existing].callnum
          
        return None

    def stopTrace(self):
        #self.lgr.debug('sharedSyscall stopTrace')
        for eip in self.exit_hap:
            self.context_manager.genDeleteHap(self.exit_hap[eip])
        self.exit_pids = {}
        self.exit_info = {}

    def showExitHaps(self):
        for eip in self.exit_pids:
            print('eip: 0x%x' % eip)
            for pid in self.exit_pids[eip]:
                prog = self.task_utils.getProgName(pid)
                if prog is not None:
                    print('\t%d %s' % (pid, prog))
                else:
                    print('\t%d' % (pid))

    def rmExitHap(self, pid):
        if pid is not None:
            self.lgr.debug('rmExitHap for pid %d' % pid)
            for eip in self.exit_pids:
                if pid in self.exit_pids[eip]:
                    self.exit_pids[eip].remove(pid)
                    if len(self.exit_pids[eip]) == 0:
                        self.context_manager.genDeleteHap(self.exit_hap[eip])
            self.exit_info[pid] = {}     

        else:
            ''' assume the exitHap was for a one-off syscall such as execve that
                broke the simulation. '''
            ''' TBD NOTE procs returning from blocked syscalls will not be caught! '''
            for eip in self.exit_pids:
                del self.exit_pids[eip][:]
                self.context_manager.genDeleteHap(self.exit_hap[eip])
                self.lgr.debug('sharedSyscall rmExitHap, assume one-off syscall, cleared exit hap')


    def addExitHap(self, pid, exit_eip1, exit_eip2, exit_eip3, exit_info, traceProcs, name):
        if pid not in self.exit_info:
            self.exit_info[pid] = {}
        self.exit_info[pid][name] = exit_info
        self.lgr.debug('sharedSyscall addExitHap name %s' % name)
        if traceProcs is not None:
            self.trace_procs.append(pid)
        self.exit_names[pid] = name

        if exit_eip1 not in self.exit_pids:
            self.exit_pids[exit_eip1] = []

        if exit_eip1 is not None: 
            if len(self.exit_pids[exit_eip1]) == 0:
                self.lgr.debug('addExitHap new exit EIP1 0x%x for pid %d' % (exit_eip1, pid))
                exit_break = self.context_manager.genBreakpoint(self.cell, 
                                    Sim_Break_Linear, Sim_Access_Execute, exit_eip1, 1, 0)
                self.exit_hap[exit_eip1] = self.context_manager.genHapIndex("Core_Breakpoint_Memop", self.exitHap, 
                                   None, exit_break, 'exit hap')
                #self.lgr.debug('sharedSyscall added exit hap %d' % self.exit_hap[exit_eip1])
            self.exit_pids[exit_eip1].append(pid)

        if exit_eip2 is not None:
            if exit_eip2 not in self.exit_pids:
                self.exit_pids[exit_eip2] = []

            if len(self.exit_pids[exit_eip2]) == 0:
                #self.lgr.debug('addExitHap new exit EIP2 0x%x for pid %d' % (exit_eip2, pid))
                exit_break = self.context_manager.genBreakpoint(self.cell, 
                                    Sim_Break_Linear, Sim_Access_Execute, exit_eip2, 1, 0)
                self.exit_hap[exit_eip2] = self.context_manager.genHapIndex("Core_Breakpoint_Memop", self.exitHap, 
                                   None, exit_break, 'exit hap2')
                #self.lgr.debug('sharedSyscall added exit hap2 %d' % self.exit_hap[exit_eip2])
            self.exit_pids[exit_eip2].append(pid)

        if exit_eip3 is not None:
            if exit_eip3 not in self.exit_pids:
                self.exit_pids[exit_eip3] = []

            if len(self.exit_pids[exit_eip3]) == 0:
                #self.lgr.debug('addExitHap new exit EIP3 0x%x for pid %d' % (exit_eip3, pid))
                exit_break = self.context_manager.genBreakpoint(self.cell, 
                                    Sim_Break_Linear, Sim_Access_Execute, exit_eip3, 1, 0)
                self.exit_hap[exit_eip3] = self.context_manager.genHapIndex("Core_Breakpoint_Memop", self.exitHap, 
                                   None, exit_break, 'exit hap3')
                #self.lgr.debug('sharedSyscall added exit hap3 %d' % self.exit_hap[exit_eip3])
            self.exit_pids[exit_eip3].append(pid)

        callname = self.task_utils.syscallName(exit_info.callnum, exit_info.compat32)
        if callname == 'execve':
            self.addPendingExecve(pid)


        #self.lgr.debug('sharedSyscall addExitHap return pid %d' % pid)


    def addPendingExecve(self, pid):
        self.lgr.debug('sharedSyscall addPendingExecve pid:%d' % pid)
        if pid not in self.pending_execve:
            self.pending_execve.append(pid)

    def rmPendingExecve(self, pid):
        if pid in self.pending_execve:
            self.lgr.debug('sharedSyscall rmPendingExecve remove %d' % pid)
            self.pending_execve.remove(pid)
        else:
            self.lgr.debug('sharedSyscall rmPendingExecve nothing pending for %d' % pid)
        self.rmExitHap(pid)

    def isPendingExecve(self, pid):
        if pid in self.pending_execve:
            return True
        else:
            return False

    def getEIP(self):
        eip = self.mem_utils.getRegValue(self.cpu, 'eip')
        return eip

    def doSockets(self, exit_info, eax, pid):
        trace_msg = ''
        if exit_info.callnum == self.task_utils.syscallNumber('socketcall', exit_info.compat32):
            socket_callname = exit_info.socket_callname
            socket_syscall = self.top.getSyscall(self.cell_name, 'socketcall')
        else:
            socket_callname = self.task_utils.syscallName(exit_info.callnum, exit_info.compat32) 
            socket_syscall = self.top.getSyscall(self.cell_name, socket_callname)
                    
        if socket_callname == "socket" and eax >= 0:
            if pid in self.trace_procs:
                self.traceProcs.socket(pid, eax)
            trace_msg = ('\treturn from socketcall SOCKET pid:%d, FD: %d\n' % (pid, eax))
        elif socket_callname == "connect":
            if eax < 0:
                trace_msg = ('\texception from socketcall CONNECT pid:%d FD: %d, eax %s  addr: 0x%x\n' % (pid, 
                    exit_info.sock_struct.fd, eax, exit_info.sock_struct.addr))
            else:     
                ss = exit_info.sock_struct
                if pid in self.trace_procs:
                    self.traceProcs.connect(pid, ss.fd, ss.getName())
                trace_msg = ('\treturn from socketcall CONNECT pid:%d, %s  addr: 0x%x\n' % (pid, ss.getString(), exit_info.sock_struct.addr))
        elif socket_callname == "bind":
            if eax < 0:
                trace_msg = ('\texception from socketcall BIND eax:%d, %s\n' % (pid, eax))
            else:
                ss = exit_info.sock_struct
                if pid in self.trace_procs:
                    self.traceProcs.bind(pid, ss.fd, ss.getName())
                    prog_name = self.traceProcs.getProg(pid)
                    if socket_syscall is not None:
                        binders = socket_syscall.getBinders()
                        if binders is not None:
                            binders.add(pid, prog_name, ss.dottedIP(), ss.port)
                trace_msg = ('\treturn from socketcall BIND pid:%d, %s\n' % (pid, ss.getString()))
                    
        elif socket_callname == "getsockname":
            ss = net.SockStruct(self.cpu, exit_info.sock_struct.addr, self.mem_utils, exit_info.sock_struct.fd)
            trace_msg = ('\t return from getsockname pid:%d %s\n' % (pid, ss.getString()))

        elif socket_callname == "accept":
            new_fd = eax
            if new_fd < 0:
                trace_msg = ('\terror return from socketcall ACCEPT pid:%d, error: %d\n' % (pid, eax))
            elif exit_info.sock_struct.addr != 0:
                in_ss = exit_info.sock_struct
                addr_len = self.mem_utils.readWord32(self.cpu, in_ss.length)
                self.lgr.debug('accept addr 0x%x  len_addr 0x%x, len %d' % (in_ss.addr, in_ss.length, addr_len))
                ss = net.SockStruct(self.cpu, exit_info.sock_struct.addr, self.mem_utils, fd=new_fd)
                if ss.sa_family == 1:
                    if pid in self.trace_procs:
                        self.traceProcs.accept(pid, exit_info.sock_struct.fd, new_fd, None)
                    trace_msg = ('\treturn from socketcall ACCEPT pid:%d, sock_fd: %d  new_fd: %d sa_family: %s  name: %s\n' % (pid, exit_info.sock_struct.fd,
                       new_fd, ss.famName(), ss.getName()))
                elif ss.sa_family == 2:
                    if pid in self.trace_procs:
                        self.traceProcs.accept(pid, exit_info.sock_struct.fd, new_fd, ss.getName())
                    trace_msg = ('\treturn from socketcall ACCEPT pid:%d, sock_fd: %d  new_fd: %d sa_family: %s  addr: %s\n' % (pid, exit_info.sock_struct.fd,
                       new_fd, ss.famName(), ss.getName()))
                else:
                    trace_msg = ('\treturn from socketcall ACCEPT pid:%d, sock_fd: %d  new_fd: %d sa_family: %s  SA Family not handled addr: 0x%x\n' % (pid, 
                         exit_info.sock_struct.fd, new_fd, ss.famName(), exit_info.sock_struct.addr))
                    #SIM_break_simulation(trace_msg)
                my_syscall = exit_info.syscall_instance
                if exit_info.call_params is not None and (exit_info.call_params.break_simulation or my_syscall.linger) and self.dataWatch is not None:
                    ''' in case we want to break on a read of address data '''
                    self.dataWatch.setRange(in_ss.addr, addr_len, trace_msg)
                    #if my_syscall.linger: 
                    ''' TBD better way to distinguish linger from trackIO '''
                    if not self.dataWatch.wouldBreakSimulation():
                        self.dataWatch.stopWatch() 
                        #self.dataWatch.watch(break_simulation=False)
                        self.lgr.debug('sharedSyscall accept call dataWatch watch')
                        self.dataWatch.watch(break_simulation=exit_info.call_params.break_simulation)
            else:
                trace_msg = ('\treturn from socketcall ACCEPT pid:%d, sock_fd: %d  new_fd: %d NULL addr\n' % (pid, exit_info.sock_struct.fd, new_fd))
        elif socket_callname == "socketpair":
            fd1 = self.mem_utils.readWord32(self.cpu, exit_info.retval_addr)
            fd2 = self.mem_utils.readWord32(self.cpu, exit_info.retval_addr+4)
            if pid in self.trace_procs:
                self.traceProcs.socketpair(pid, fd1, fd2)
            trace_msg = ('\treturn from socketcall SOCKETPAIR pid:%d, fd1: %s fd2: %s\n' % (pid, str(fd1), str(fd2)))
            #self.lgr.debug('\treturn from socketcall SOCKETPAIR pid:%d, fd1: %d fd2: %d' % (pid, fd1, fd2))

        elif socket_callname == "send" or socket_callname == "sendto" or \
             socket_callname == "sendmsg": 
            if eax >= 0:
                nbytes = min(eax, 256)
                byte_string, byte_array = self.mem_utils.getBytes(self.cpu, nbytes, exit_info.retval_addr)
                if byte_array is not None:
                    s = ''.join(map(chr,byte_array))
                else:
                    s = '<< NOT MAPPED >>'
                trace_msg = ('\treturn from socketcall %s pid:%d, FD: %d, count: %d from 0x%x\n%s\n' % (socket_callname, pid, exit_info.old_fd, 
                    eax, exit_info.retval_addr, s))
            else:
                trace_msg = ('\terror return from socketcall %s pid:%d, FD: %d, exception: %d\n' % (socket_callname, pid, exit_info.old_fd, eax))

            if exit_info.call_params is not None:
                if syscall.DEST_PORT in exit_info.call_params.param_flags: 
                    self.lgr.debug('sharedSyscall sendto found dest port match.')
                elif type(exit_info.call_params.match_param) is str and eax > 0:
                    self.lgr.debug('sharedSyscall SEND check string %s against %s' % (s, exit_info.call_params.match_param))
                    if exit_info.call_params.match_param not in s:
                        ''' no match, set call_param to none '''
                        exit_info.call_params = None

        elif socket_callname == "recv" or socket_callname == "recvfrom":
            if eax >= 0:
                nbytes = min(eax, 256)
                byte_string, byte_array = self.mem_utils.getBytes(self.cpu, nbytes, exit_info.retval_addr)
                if byte_array is not None:
                    s = ''.join(map(chr,byte_array))
                else:
                    s = '<< NOT MAPPED >>'
                src = ''
                if exit_info.fname_addr is not None:
                    ''' obscure use of fname_addr to store source of recvfrom '''
                    src_ss = net.SockStruct(self.cpu, exit_info.fname_addr, self.mem_utils, fd=-1)
                    src = 'from: %s' % src_ss.getString()

                trace_msg = ('\treturn from socketcall %s pid:%d, FD: %d, len: %d count: %d into 0x%x %s\n%s\n' % (socket_callname, pid, 
                     exit_info.old_fd, exit_info.sock_struct.length, eax, exit_info.retval_addr, src, s))
                my_syscall = exit_info.syscall_instance
                if exit_info.call_params is not None and (exit_info.call_params.break_simulation or my_syscall.linger) and self.dataWatch is not None:
                    ''' in case we want to break on a read of this data.  NOTE: length is the given length '''
                    self.dataWatch.setRange(exit_info.retval_addr, exit_info.sock_struct.length, msg=trace_msg, 
                               max_len=exit_info.sock_struct.length)
                    if exit_info.fname_addr is not None:
                        count = self.mem_utils.readWord32(self.cpu, exit_info.count)
                        msg = 'recvfrom source for above, addr 0x%x %d bytes' % (exit_info.fname_addr, count)
                        self.dataWatch.setRange(exit_info.fname_addr, count, msg)
                    if my_syscall.linger: 
                        self.dataWatch.stopWatch() 
                        self.dataWatch.watch(break_simulation=False)
            else:
                trace_msg = ('\terror return from socketcall %s pid:%d, FD: %d, exception: %d into 0x%x\n' % (socket_callname, pid, exit_info.old_fd, eax, exit_info.retval_addr))

        elif socket_callname == "recvmsg": 
            self.lgr.debug('doSockets recvmsg')
            if eax < 0:
                trace_msg = ('\terror return from socketcall %s pid:%d FD: %d exception: %d \n' % (socket_callname, pid, exit_info.old_fd, eax))
                exit_info.call_params = None
            else:
                msghdr = net.Msghdr(self.cpu, self.mem_utils, exit_info.retval_addr)
                trace_msg = ('\treturn from socketcall %s pid:%d FD: %d count: %d %s' % (socket_callname, pid, exit_info.old_fd, eax, msghdr.getString()))
                if pid in self.trace_procs:
                    if self.traceProcs.isExternal(pid, exit_info.old_fd):
                        trace_msg = trace_msg +' EXTERNAL'
                trace_msg = trace_msg + '\n'
                msg_iov = msghdr.getIovec()
                nbytes = min(eax, 256)
                byte_string, byte_array = self.mem_utils.getBytes(self.cpu, nbytes, msg_iov[0].base)
                if byte_array is not None:
                    s = ''.join(map(chr,byte_array))
                else:
                    s = '<< NOT MAPPED >>'
                trace_msg = trace_msg+'\t'+s+'\n'
                if exit_info.call_params is not None:
                    if exit_info.call_params.break_simulation and self.dataWatch is not None:
                        ''' in case we want to break on a read of this data.  NOTE: length is the given length '''
                        self.dataWatch.setRange(msg_iov[0].base, exit_info.sock_struct.length, trace_msg)
                        self.lgr.debug('recvmsg set dataWatch')
                    if type(exit_info.call_params.match_param) is str:
                        self.lgr.debug('sharedSyscall recvmsg check string %s against %s' % (s, exit_info.call_params.match_param))
                        if exit_info.call_params.match_param not in s: 
                            exit_info.call_params = None
                    else:
                        self.lgr.error('sharedSyscall unhandled call_param %s' % (exit_info.call_params))
                        exit_info.call_params = None
            
        elif socket_callname == "getpeername":
            ss = net.SockStruct(self.cpu, exit_info.sock_struct.addr, self.mem_utils)
            trace_msg = ('\treturn from socketcall GETPEERNAME pid:%d, %s  eax: 0x%x\n' % (pid, ss.getString(), eax))
        elif socket_callname == 'setsockopt':
            trace_msg = ('\treturn from socketcall SETSOCKOPT pid:%d eax: 0x%x\n' % (pid, eax))
        elif socket_callname == 'getsockopt':
            optval_val = ''
            if exit_info.retval_addr != 0 and eax == 0:
                ''' note exit_info.count is ptr to returned count '''
                count = self.mem_utils.readWord32(self.cpu, exit_info.count)
                rcount = min(count, 80)
                thebytes, dumb = self.mem_utils.getBytes(self.cpu, rcount, exit_info.retval_addr)
                optval_val = 'optlen: %d option: %s' % (count, thebytes)
            trace_msg = ('\treturn from getsockopt %s result %d\n' % (optval_val, eax))
          
        else:
            #fd = self.mem_utils.readWord32(self.cpu, params)
            #addr = self.mem_utils.readWord32(self.cpu, params+4)
            #trace_msg = ('\treturn from socketcall %s pid:%d FD: %d addr:0x%x eax: 0x%x\n' % (socket_callname, pid, fd, addr, eax)) 
            if exit_info.sock_struct is not None:
                trace_msg = ('\treturn from socketcall %s pid:%d FD: %d addr:0x%x eax: 0x%x\n' % (socket_callname, pid, exit_info.sock_struct.fd, exit_info.sock_struct.addr, eax)) 
            elif socket_callname != 'socket':
                self.lgr.error('sharedSyscall pid:%d %s missing sock_struct' % (pid, socket_callname))
        return trace_msg

    def exitHap(self, dumb, third, forth, memory):
        cpu, comm, pid = self.task_utils.curProc() 
        #self.lgr.debug('sharedSyscall exitHap %d (%s) third: %s  forth: %s' % (pid, comm, str(third), str(forth)))
        did_exit = False
        if pid in self.exit_info:
            for name in self.exit_info[pid]:
                exit_info = self.exit_info[pid][name]
                self.lgr.debug('exitHap pid:%d name: %s' % (pid, name))
                did_exit = self.handleExit(exit_info, pid, comm)
        else:
            did_exit = self.handleExit(None, pid, comm)
        if did_exit:
            self.lgr.debug('exitHap remove exitHap for %d' % pid)
            self.rmExitHap(pid)

    def fcntl(self, pid, eax, exit_info):
        if net.fcntlCmdIs(exit_info.cmd, 'F_DUPFD'):
            if pid in self.trace_procs:
                self.traceProcs.dup(pid, exit_info.old_fd, eax)
            trace_msg = ('\treturn from fcntl64 F_DUPFD pid %d, old_fd: %d new: %d\n' % (pid, exit_info.old_fd, eax))
        elif net.fcntlCmdIs(exit_info.cmd, 'F_GETFL'):
            trace_msg = ('\treturn from fcntl64 F_GETFL pid %d, old_fd: %d  flags: 0%o\n' % (pid, exit_info.old_fd, eax))
        else:
            trace_msg = ('\treturn from fcntl64  pid %d, old_fd: %d retval: %d\n' % (pid, exit_info.old_fd, eax))
            return trace_msg
        
    def handleExit(self, exit_info, pid, comm):
        ''' 
           Invoked on (almost) return to user space after a system call.
           Includes parameter checking to see if the call meets criteria given in
           a paramter buried in exit_info (see ExitInfo class).
        '''
        trace_msg = ''
        if pid == 0:
            self.lgr.debug('exitHap cell %s pid is zero' % (self.cell_name))
            return False
        ''' If this is a new pid, assume it is a child clone or fork return '''
        if exit_info is None:
            ''' no pending syscall for this pid '''
            if not self.traceProcs.pidExists(pid):
                ''' new PID, add it without parent for now? ''' 
                '''
                clonenum = self.task_utils.syscallNumber('clone', exit_info.compat32)
                for ppid in self.exit_info:
                    if self.exit_info[ppid].callnum == clonenum:
                        if self.exit_info[ppid].call_params is not None:
                            self.lgr.debug('clone returning in child %d parent maybe %d' % (pid, ppid))
                            SIM_break_simulation('clone returning in child %d parent maybe %d' % (pid, ppid))
                            return    
                '''
                leader_pid = self.task_utils.getCurrentThreadLeaderPid()
                self.lgr.debug('exitHap clone child return no parent pid %d (%s)  group leader is %s' % (pid, comm, leader_pid))
                if leader_pid != pid:
                    self.traceProcs.addProc(pid, leader_pid, comm=comm)
                    if self.context_manager.amWatching(leader_pid):
                        self.context_manager.addTask(pid)
                else:
                    self.traceProcs.addProc(pid, None, comm=comm)
                return False
            if self.isPendingExecve(pid):
                self.lgr.debug('exitHap cell %s call reschedule from execve?  for pid %d  Remove pending' % (self.cell_name, pid))
                self.rmPendingExecve(pid)
                return False 
            else:
                ''' pid exists, but no execve syscall pending, assume reschedule? '''
                #self.lgr.debug('exitHap call reschedule for pid %d' % pid)
                return False 
        
        ''' check for nested interrupt return '''
        eip = self.getEIP()
        instruct = SIM_disassemble_address(self.cpu, eip, 1, 0)
        if instruct[1].startswith('iret'):
            reg_num = self.cpu.iface.int_register.get_number(self.mem_utils.getESP())
            esp = self.cpu.iface.int_register.read(reg_num)
            ret_addr = self.mem_utils.readPtr(self.cpu, esp)
            if ret_addr > self.param.kernel_base:
                ''' nested '''
                #self.lgr.debug('sharedSyscall cell %s exitHap nested' % (self.cell_name))
                #SIM_break_simulation('nested ?')
                return False
            else:
                self.lgr.debug('exitHap ret_addr 0x%x  kbase 0x%x ' % (ret_addr, self.param.kernel_base))

        if eip == exit_info.syscall_entry:
            self.lgr.error('exitHap entered from syscall breakpoint.  wtf?, over.')
            return False

        eax = self.mem_utils.getRegValue(self.cpu, 'syscall_ret')
        ueax = self.mem_utils.getUnsigned(eax)
        eax = self.mem_utils.getSigned(eax)
        callname = self.task_utils.syscallName(exit_info.callnum, exit_info.compat32)
        #self.lgr.debug('exitHap cell %s callnum %d name %s  pid %d ' % (self.cell_name, exit_info.callnum, callname, pid))
        if callname == 'clone':
            self.lgr.debug('exitHap is clone pid %d  eax %d' % (pid, eax))
            if eax > 20000:
                SIM_break_simulation('confused clone')
                return False
            #if eax == 120:
            #    SIM_break_simulation('clone faux return?')
            #    return
            self.top.recordStackBase(eax, exit_info.fname_addr)
            if  pid in self.trace_procs and self.traceProcs.addProc(eax, pid, clone=True):
                trace_msg = ('\treturn from clone (tracing), new pid:%d  calling pid:%d\n' % (eax, pid))
                #self.lgr.debug('exitHap clone called addProc for pid:%d parent %d' % (eax, pid))
                self.traceProcs.copyOpen(pid, eax)
            elif pid not in self.trace_procs:
                trace_msg = ('\treturn from clone, new pid:%d  calling pid:%d\n' % (eax, pid))
            else:
                ''' must be repeated hap or trackThreads already added the clone '''
                self.lgr.debug('exitHap clone repeated call? pid: %d eax %d' % (pid, eax))
                trace_msg = ('\treturn from clone, new pid:%d  calling pid:%d\n' % (eax, pid))
                
            if exit_info.call_params is not None:
                if exit_info.call_params.nth is not None:
                    self.lgr.debug('exitHap clone, nth is %d' % exit_info.call_params.nth)
                    if exit_info.call_params.nth >= 0:
                        self.lgr.debug('exitHap clone, run to pid %d' % eax)
                        SIM_run_alone(self.top.toProcPid, eax)
                        exit_info.call_params = None
                        my_syscall = exit_info.syscall_instance
                        my_syscall.stopTrace()
            
            #dumb_pid, dumb, dumb2 = self.context_manager.getDebugPid() 
            #if dumb_pid is not None:
            #    self.lgr.debug('sharedSyscall adding clone %d to watched pids' % eax)
            #    self.context_manager.addTask(eax)
             
        elif callname == 'mkdir':
            #fname = self.mem_utils.readString(exit_info.cpu, exit_info.fname_addr, 256)
            if exit_info.fname is None:
                self.lgr.error('fname is None? in exit from mkdir pid %d fname addr was 0x%x' % (pid, exit_info.fname_addr))
                #SIM_break_simulation('fname is none on exit of open')
                exit_info.fname = 'unknown'
            trace_msg = ('\treturn from mkdir pid:%d file: %s flags: 0x%x mode: 0x%x eax: 0x%x\n' % (pid, exit_info.fname, exit_info.flags, exit_info.mode, eax))
                
        elif callname == 'open' or callname == 'openat':
            #fname = self.mem_utils.readString(exit_info.cpu, exit_info.fname_addr, 256)
            if exit_info.fname is None:
                self.lgr.error('fname is None? in exit from open pid %d fname addr was 0x%x' % (pid, exit_info.fname_addr))
                #ptable_info = pageUtils.findPageTableIA32E(self.cpu, exit_info.fname_addr, self.lgr)
                SIM_break_simulation('fname is none on exit of open')
                exit_info.fname = 'unknown'
            trace_msg = ('\treturn from open pid:%d FD: %d file: %s flags: 0%o mode: 0x%x eax: 0x%x\n' % (pid, eax, 
                   exit_info.fname, exit_info.flags, exit_info.mode, eax))
            self.lgr.debug('return from open pid:%d (%s) FD: %d file: %s flags: 0%o mode: 0x%x eax: 0x%x' % (pid, comm, 
                   eax, exit_info.fname, exit_info.flags, exit_info.mode, eax))
            if eax >= 0:
                if pid in self.trace_procs:
                    self.traceProcs.open(pid, comm, exit_info.fname, eax)
                ''' TBD cleaner way to know if we are getting ready for a debug session? '''
                if ('.so.' in exit_info.fname or exit_info.fname.endswith('.so')) and self.track_so:
                    self.lgr.debug('is open so')
                    #open_syscall = self.top.getSyscall(self.cell_name, 'open')
                    open_syscall = exit_info.syscall_instance
                    if open_syscall is not None: 
                        open_syscall.watchFirstMmap(pid, exit_info.fname, eax, exit_info.compat32)
                    else:
                        self.lgr.debug('sharedSyscall no syscall_instance in exit_info %d' % pid)
                if self.traceFiles is not None:
                    self.traceFiles.open(exit_info.fname, eax)
            if exit_info.call_params is not None and type(exit_info.call_params.match_param) is str:
                self.lgr.debug('sharedSyscall open check string %s against %s' % (exit_info.fname, exit_info.call_params.match_param))
                #if eax < 0 or exit_info.call_params.match_param not in exit_info.fname:
                if exit_info.call_params.match_param not in exit_info.fname:
                    ''' no match, set call_param to none '''
                    exit_info.call_params = None
                
        elif callname == 'pipe' or \
             callname == 'pipe2':
            if eax == 0:
                fd1 = self.mem_utils.readWord32(self.cpu, exit_info.retval_addr)
                fd2 = self.mem_utils.readWord32(self.cpu, exit_info.retval_addr+4)
                #self.lgr.debug('return from pipe pid:%d fd1 %d fd2 %d from 0x%x' % (pid, fd1, fd2, exit_info.retval_addr))
                trace_msg = ('\treturn from pipe pid:%s fd1 %s fd2 %s from 0x%x\n' % (str(pid), str(fd1), str(fd2), exit_info.retval_addr))
                if pid in self.trace_procs:
                    self.traceProcs.pipe(pid, fd1, fd2)

        elif callname == 'read':
            #self.lgr.debug('is read eax 0x%x' % eax)
            if eax >= 0 and exit_info.retval_addr is not None:
                limit = min(eax, 80)
                #byte_string, dumb = self.mem_utils.getBytes(cpu, limit, exit_info.retval_addr)
                byte_string, byte_array = self.mem_utils.getBytes(self.cpu, limit, exit_info.retval_addr)
                if byte_array is not None:
                    s = ''.join(map(chr,byte_array))
                else:
                    s = '<<NOT MAPPED>>'
                trace_msg = ('\treturn from read pid:%d (%s) FD: %d count: %d into 0x%x\n\t%s\n' % (pid, comm, exit_info.old_fd, 
                              eax, exit_info.retval_addr, s))
                my_syscall = exit_info.syscall_instance
                if exit_info.call_params is not None and (exit_info.call_params.break_simulation or my_syscall.linger) and self.dataWatch is not None \
                   and type(exit_info.call_params.match_param) is int:
                    ''' in case we want to break on a read of this data. NOTE break range is based on given count, not returned length '''
                    self.lgr.debug('sharedSyscall bout to call dataWatch.setRange for read')
                    self.dataWatch.setRange(exit_info.retval_addr, exit_info.count, trace_msg)
                    if my_syscall.linger: 
                        self.dataWatch.stopWatch() 
                        self.dataWatch.watch(break_simulation=False)
                elif exit_info.call_params is not None and exit_info.call_params.match_param.__class__.__name__ == 'Dmod':
                    if eax < 16000:
                        dmod = exit_info.call_params.match_param
                        self.lgr.debug('sharedSyscall %s read check dmod %s count %d %s' % (self.cell_name, dmod.getPath(), eax, s))
                        if dmod.checkString(self.cpu, exit_info.retval_addr, eax, pid, exit_info.old_fd):
                            self.lgr.debug('sharedSyscall read found final dmod')
                            self.top.stopTrace(cell_name=self.cell_name, syscall=exit_info.syscall_instance)
                            self.stopTrace()
                            if not self.top.remainingCallTraces() and SIM_simics_is_running():
                                self.top.notRunning(quiet=True)
                                SIM_break_simulation('dmod done on cell %s file: %s' % (self.cell_name, dmod.getPath()))
                            else:
                                print('%s performed' % dmod.getPath())
                    exit_info.call_params = None


            elif exit_info.old_fd is not None:
                trace_msg = ('\treturn from read pid:%d FD: %d exception %d\n' % (pid, exit_info.old_fd, eax))
                exit_info.call_params = None

        elif callname == 'write':
            if eax >= 0 and exit_info.retval_addr is not None:
                    max_len = min(eax, 1024)
                    byte_string, byte_array = self.mem_utils.getBytes(self.cpu, eax, exit_info.retval_addr)
                    if byte_array is not None:
                        s = ''.join(map(chr,byte_array[:max_len]))
                    else:
                        s = '<<NOT MAPPED>>'
                    #trace_msg = ('\treturn from write pid:%d FD: %d count: %d\n\t%s\n' % (pid, exit_info.old_fd, eax, byte_string))
                    trace_msg = ('\treturn from write pid:%d FD: %d count: %d\n\t%s\n' % (pid, exit_info.old_fd, eax, s))
                    if self.traceFiles is not None:
                        #self.lgr.debug('sharedSyscall write call tracefiles with fd %d' % exit_info.old_fd)
                        self.traceFiles.write(pid, exit_info.old_fd, byte_array)
                    if exit_info.call_params is not None and type(exit_info.call_params.match_param) is str:
                        self.lgr.debug('sharedSyscall write check string %s against %s' % (s, exit_info.call_params.match_param))
                        if exit_info.call_params.match_param not in s:
                            ''' no match, set call_param to none '''
                            exit_info.call_params = None
                        else:
                            self.lgr.debug('MATCHED')
                    elif exit_info.call_params is not None:
                        self.lgr.debug('type of param %s' % (type(exit_info.call_params.match_param)))
                    if self.all_write:
                        self.allWrite.write(comm, pid, exit_info.old_fd, s)
            else:
                exit_info.call_params = None

        elif callname == '_llseek':
            if self.mem_utils.WORD_SIZE == 4:
                result = self.mem_utils.readWord32(self.cpu, exit_info.retval_addr)
                trace_msg = ('\treturn from _llseek pid:%d FD: %d result: 0x%x\n' % (pid, exit_info.old_fd, result))
            else:
                trace_msg = ('\treturn from _llseek pid:%d FD: %d eax: 0x%x\n' % (pid, exit_info.old_fd, eax))

        elif callname == 'ioctl':
            if exit_info.retval_addr is not None:
                result = self.mem_utils.readWord32(self.cpu, exit_info.retval_addr)
                if result is not None:
                    trace_msg = ('\treturn from ioctl pid:%d FD: %d cmd: 0x%x result: 0x%x\n' % (pid, exit_info.old_fd, exit_info.cmd, result))
                else:
                    self.lgr.debug('sharedSyscall read None from 0x%x cmd: 0x%x' % (exit_info.retval_addr, exit_info.cmd))
            else:
                trace_msg = ('\treturn from ioctl pid:%d FD: %d cmd: 0x%x eax: 0x%x\n' % (pid, exit_info.old_fd, exit_info.cmd, eax))

        elif callname == 'gettimeofday': 
            if exit_info.retval_addr is not None:
                result = self.mem_utils.readWord32(self.cpu, exit_info.retval_addr)
                trace_msg = ('\treturn from gettimeofday pid:%d result: 0x%x\n' % (pid, result))
                timer_syscall = self.top.getSyscall(self.cell_name, 'gettimeofday')
                if timer_syscall is not None:
                    timer_syscall.checkTimeLoop('gettimeofday', pid)

        elif callname == 'waitpid': 
            timer_syscall = self.top.getSyscall(self.cell_name, 'waitpid')
            if timer_syscall is not None:
                timer_syscall.checkTimeLoop('waitpid', pid)
            else:
                self.lgr.debug('timer_syscall is None')


        elif callname == 'close':
            if eax == 0:
                if pid in self.trace_procs:
                    #self.lgr.debug('exitHap for close pid %d' % pid)
                    self.traceProcs.close(pid, exit_info.old_fd)
                trace_msg = ('\treturn from close pid:%d, FD: %d  eax: 0x%x\n' % (pid, exit_info.old_fd, eax))
                if self.traceFiles is not None:
                    self.traceFiles.close(exit_info.old_fd)
                if exit_info.call_params is not None:
                    self.dataWatch.close(exit_info.old_fd)
            else:
                trace_msg = ('\terror return from close pid:%d, FD: %d  eax: 0x%x\n' % (pid, exit_info.old_fd, eax))
            
        elif callname == 'fcntl64':        
            if eax >= 0:
                trace_msg = self.fcntl(pid, eax, exit_info)
            else:
                trace_msg = ('\terror return from fcntl64  pid %d, old_fd: %d retval: %d\n' % (pid, exit_info.old_fd, eax))

        elif callname == 'dup':
            #self.lgr.debug('exit pid %d from dup eax %x, old_fd is %d' % (pid, eax, exit_info.old_fd))
            if eax >= 0:
                if pid in self.trace_procs:
                    self.traceProcs.dup(pid, exit_info.old_fd, eax)
                trace_msg = ('\treturn from dup pid %d, old_fd: %d new: %d\n' % (pid, exit_info.old_fd, eax))
        elif callname == 'dup2':
            #self.lgr.debug('return from dup2 pid %d eax %x, old_fd is %d new_fd %d' % (pid, eax, exit_info.old_fd, exit_info.new_fd))
            if eax >= 0:
                if exit_info.old_fd != exit_info.new_fd:
                    if pid in self.trace_procs:
                        self.traceProcs.dup(pid, exit_info.old_fd, exit_info.new_fd)
                    trace_msg = ('\treturn from dup2 pid:%d, old_fd: %d new: %d\n' % (pid, exit_info.old_fd, eax))
                else:
                    trace_msg = ('\treturn from dup2 pid:%d, old_fd: and new both %d   Eh?\n' % (pid, eax))
        elif callname == 'mmap2' or callname == 'mmap':
            ''' TBD error handling? '''
            if exit_info.fname is not None and self.soMap is not None:
                self.lgr.debug('return from mmap pid:%d, addr: 0x%x so fname: %s' % (pid, ueax, exit_info.fname))
                trace_msg = ('\treturn from mmap pid:%d, addr: 0x%x so fname: %s\n' % (pid, ueax, exit_info.fname))
                if '/etc/ld.so.cache' not in exit_info.fname:
                    self.soMap.addSO(pid, exit_info.fname, ueax, exit_info.count)
            else:
                trace_msg = ('\treturn from mmap pid:%d, addr: 0x%x \n' % (pid, ueax))
        elif callname == 'ipc':
            callname = exit_info.socket_callname
            #callname = ipc.call[call]
            if callname == ipc.MSGGET or callname == ipc.SHMGET:
                trace_msg = ('\treturn from ipc %s pid:%d key: 0x%x quid: 0x%x\n' % (callname, pid, exit_info.fname, ueax)) 
                #SIM_break_simulation('msgget pid %d ueax 0x%x eax 0x%x' % (pid, ueax, eax))
            else:
                if eax < 0:
                    trace_msg = ('\treturn ERROR from ipc %s pid:%d result: %d\n' % (callname, pid, eax)) 
                else:
                    trace_msg = ('\treturn from ipc %s pid:%d result: 0x%x\n' % (callname, pid, ueax)) 

        elif callname == 'select' or callname == '_newselect':
            trace_msg = ('\treturn from %s pid:%d %s  result: %d\n' % (callname, pid, exit_info.select_info.getString(), eax))
        elif callname == 'vfork':
            trace_msg = ('\treturn from vfork in parent %d child pid:%d\n' % (pid, ueax))
            if pid in self.trace_procs:
                self.traceProcs.addProc(ueax, pid)
                self.traceProcs.copyOpen(pid, eax)
        elif callname == 'execve':
            #self.lgr.debug('exitHap from execve pid:%d  remove from pending_execve' % pid)
            if self.isPendingExecve(pid):
                self.rmPendingExecve(pid)
        elif callname == 'socketcall' or callname.upper() in net.callname:
            trace_msg = self.doSockets(exit_info, eax, pid)
        else:
            trace_msg = ('\treturn from call %s code: 0x%x  pid:%d\n' % (callname, ueax, pid))


        ''' if debugging a proc, and clone call, add the new process '''
        dumb_pid, dumb2 = self.context_manager.getDebugPid() 
        if dumb_pid is not None and callname == 'clone':
            if eax == 0:
                self.lgr.debug('sharedSyscall clone but eax is zero ??? pid is %d' % pid)
                return True
            self.lgr.debug('sharedSyscall adding clone %d to watched pids' % eax)
            self.context_manager.addTask(eax)

        if exit_info.call_params is not None and exit_info.call_params.break_simulation:
            '''  Use syscall module that got us here to handle stop actions '''
            self.lgr.debug('exitHap found matching call parameter %s' % str(exit_info.call_params.match_param))
            self.context_manager.setIdaMessage(trace_msg)
            #self.lgr.debug('exitHap found matching call parameters callnum %d name %s' % (exit_info.callnum, callname))
            #my_syscall = self.top.getSyscall(self.cell_name, callname)
            my_syscall = exit_info.syscall_instance
            if not my_syscall.linger: 
                self.stopTrace()
            if my_syscall is None:
                self.lgr.error('sharedSyscall could not get syscall for %s' % callname)
            else:
                SIM_run_alone(my_syscall.stopAlone, 'found matching call parameters')
    
        if trace_msg is not None and len(trace_msg.strip())>0:
            self.lgr.debug('cell %s %s'  % (self.cell_name, trace_msg.strip()))
            self.traceMgr.write(trace_msg) 
        return True

    def startAllWrite(self):
        self.all_write = True
        
