import subprocess as sub

class Node:
    def __init__(self, nodeType, user, host, number, ip):
        # enumeration
        self.nodeTypes = ['Leader', 'Manager', 'Worker']
        # init properties
        if nodeType in self.nodeTypes:
            self.nodeType = nodeType
        self.user = user
        self.host = host
        self.number = number
        self.ip = ip
        
    def InitLeader(self):
        ps = sub.Popen(["sudo", "docker", "swarm", "init", "--advertise-addr", self.ip], stdout=sub.PIPE)
        (output, err) = ps.communicate()
    
    def GetLocalIp(self):
        # TODO -- the IP addr below needs not be hard coded ...
        ps = sub.Popen(["ifconfig"], stdout=sub.PIPE)
        output = str(sub.check_output(["grep", "192.168.1.*"], stdin=ps.stdout))
        ps.wait()
        return output.split(' ')[11].split(':')[1]


