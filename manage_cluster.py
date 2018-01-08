#!/usr/bin/python

import subprocess as sub 
import json
import sys

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
            ps = sub.Popen(["ifconfig"], stdout=sub.PIPE)
            output = str(sub.check_output(["grep", "192.168.1.*"], stdin=ps.stdout))
            ps.wait()
            return output.split(' ')[11].split(':')[1]

class Cluster:
    def __init__(self, machineFile=None):
        # json file
        if machineFile:
            self.machineFile = machineFile
        else:
            self.machineFile = self.FindMachineFile()
        # properties
        self.startTime = 0
        self.uptime = 0
        self.numMachines = 0
        self.managerToken = None
        self.workerToken = None
        # nodes
        self.leader = None
        self.managers = []
        self.workers = []
        # init methods
        self.ProcessMachineList()
        self.NodeStatus()
    
    def FindMachineFile(self):
        ps = sub.Popen(["find", "/home/pi/", "-name", "cluster.json"], stdout=sub.PIPE)
        (output, err) = ps.communicate()
        return output[:-1]
    
    def ProcessMachineList(self):
        if self.machineFile:
            with open(self.machineFile, 'r') as f:
                ds = json.load(f)
        else:
            ds = self.MapNetwork()
        self.processDataStore(ds) 
    
    def processDataStore(self, dataStore):
        # add each node to the cluster
        for machine in dataStore["cluster"]["machines"]:
            orderNum = machine["number"]
            if orderNum == 0:
                self.leader = Node("Leader", machine["user"], machine["host"], machine["number"], machine["ip"])
            elif orderNum == 1:
                self.managers.append(Node("Manager", machine["user"], machine["host"], machine["number"], machine["ip"]))
            else:
                self.workers.append(Node("Worker", machine["user"], machine["host"], machine["number"], machine["ip"]))

    def NodeStatus(self):
        # leader
        print ("Leader ---> {0} @ {1}".format(self.leader.host, self.leader.ip))
        
        # managers
        for node in self.managers:
            print ("Manager ---> {0} @ {1}".format(node.host, node.ip))
        
        # workers
        for node in self.workers:
            print ("Worker ---> {0} @ {1}".format(self.leader.host, self.leader.ip))

    def MapNetwork(self):
        # nmap process
        ps = sub.Popen(["nmap", "-sn", "192.168.1.0/24"], stdout=sub.PIPE)
        output = str(sub.check_output(["grep", "Pi"], stdin=ps.stdout))
        ps.wait()

        #  find servers for cluster and remove last empty value
        nodes = output.split('\n')
        nodes = nodes[:-1]
        
        # building the json object
        dataStore = {}
        dataStore["cluster"] = {"machines": []}
        
        for node in nodes:
            machine = {}
            data = node.split(' ')
            machine["user"] = "pi"
            machine["host"] = data[4]
            if machine["host"] == "PiController":
                num = 0
            else:
                num = int(machine["host"].split('Pi')[1])
            machine["number"] = num
            machine["ip"] = data[5].split('(')[1].split(')')[0]
            dataStore["cluster"]["machines"].append(machine)
        
        # saving the json object
        with open("/home/pi/docker_examples/cluster/cluster.json", 'w') as f:
            json.dump(dataStore, f, indent=4, sort_keys=True)
        
        return dataStore

    def GetTokens(self):
        # manager
        ps = sub.Popen(["sudo", "docker", "swarm", "join-token", "manager"], stdout=sub.PIPE)
        (output, err) = ps.communicate()   
        manToken = output.split(' ')[18]
        
        # worker
        ps = sub.Popen(["sudo", "docker", "swarm", "join-token", "worker"], stdout=sub.PIPE)
        (output, err) = ps.communicate()   
        workToken = output.split(' ')[18]
        
        return (manToken, workToken)
    
    def sshNode(self, hostMachine, command):
        ssh = sub.Popen(["ssh", hostMachine, command], 
                              shell=False,
                              stdout=sub.PIPE,
                              stderr=sub.PIPE,
                              universal_newlines=True,
                              bufsize=0)
        result = ssh.stdout.readlines()
        
        if result == []:
            error = ssh.stderr.readlines()
            print >>sys.stderr, "ERROR: %s" % error
 
    def Build(self):
        # start the leader
        self.leader.InitLeader()
        (self.managerToken, self.workerToken) = self.GetTokens()
        
        # join managers
        for manager in self.managers:
            hostMachine = "{0}@{1}".format(manager.user, manager.host)
            command = "sudo docker swarm join --token {0} {1}:2377".format(self.managerToken, self.leader.ip)
            self.sshNode(hostMachine, command)

        # join workers
        for worker in self.workers:
            hostMachine = "{0}@{1}".format(worker.user, worker.host)
            command = "sudo docker swarm join --token {0} {1}:2377".format(self.workerToken, self.leader.ip)
            self.sshNode(hostMachine, command)

    def Destroy(self):
        # remove managers
        for manager in self.managers:
            hostMachine = "{0}@{1}".format(manager.user, manager.host)
            command = "sudo docker swarm leave --force"
            self.sshNode(hostMachine, command)

        # remove workers
        for worker in self.workers:
            hostMachine = "{0}@{1}".format(worker.user, worker.host)
            command = "sudo docker swarm leave --force"
            self.sshNode(hostMachine, command)

        # remove leader
        ps = sub.Popen(["sudo", "docker", "swarm", "leave", "--force"], stdout=sub.PIPE)
        (output, err) = ps.communicate()
    
def ParseCli():
    pass

def main(args):
    myCluster = Cluster()
    command = args[1]
    
    if command == "build":   
        print ("Building the cluster")
        myCluster.Build()
    elif command == "destroy":
        print ("Destroying the cluster")
        myCluster.Destroy()


if __name__ == '__main__':
    main(sys.argv)

