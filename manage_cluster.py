#!/usr/bin/python

# Project : Raspberry Pi 4 node cluster computer
# Author  : Connor McCann
# Date    : 07 Jan 2018
# Purpose : Manage the cluster with various OS commands
#           with hopes of integrating some MPI parallel
#           processing functionality and threading for
#           utility and learning purposes.

from service import Service
from image import Image
from node import Node
import subprocess as sub 
import json
import sys


class Cluster:

    def __init__(self, machineFile=None):
        # json file
        if machineFile:
            self.machineFile = machineFile
        else:
            self.machineFile = self.FindMachineFile()
        
        # properties
        self.state = self.GetState()
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
    
    def GetState(self):
        ps = sub.Popen(["sudo", "docker", "node", "ls"], stdout=sub.PIPE)
        (output, err) = ps.communicate()
        firstWord = output.split(' ')[0].strip()
        if firstWord == "":
            return "down"
        elif firstWord == "ID":
            return "up"

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
            role = machine["role"]
            if role == 'leader':
                self.leader = Node("Leader", machine["user"], machine["host"], machine["role"], machine["ip"])
            elif role == 'manager':
                self.managers.append(Node("Manager", machine["user"], machine["host"], machine["role"], machine["ip"]))
            else:
                self.workers.append(Node("Worker", machine["user"], machine["host"], machine["role"], machine["ip"]))

    def NodeStatus(self):
        # leader
        print ("Leader ---> {0} @ {1}".format(self.leader.host, self.leader.ip))
        
        # managers
        for node in self.managers:
            print ("Manager ---> {0} @ {1}".format(node.host, node.ip))
        
        # workers
        for node in self.workers:
            print ("Worker ---> {0} @ {1}".format(node.host, node.ip))

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
                role = "leader"
            elif machine["host"] == "Pi01":
                role = "manager"
            else:
                role = "worker"
            machine["role"] = role
            machine["ip"] = data[5].split('(')[1].split(')')[0]
            dataStore["cluster"]["machines"].append(machine)
        
        # saving the json object
        with open("/home/pi/swarm-manager/cluster.json", 'w') as f:
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

        # change the state of the cluster
        self.state = "up"

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

        # change the state
        self.state = "down"
    
    def GetImages(self):
        ps = sub.Popen(["sudo", "docker", "images"], stdout=sub.PIPE)
        (output, err) = ps.communicate()
        lines = output.split('\n')
        
        images = []
        lines = lines [1:-1]
        for line in lines:
            properties = []
            words = line.split(' ')
            for i, word in enumerate(words):
                if word != '' and word != None:
                    properties.append(word)
            if len(properties) == 7:
                images.append(Image(properties))
        return images

    def StartServices(self):
        # check the state of the cluster
        if self.state == "down":
            return

        images = self.GetImages()
        self.services = {} # key:image name, value: image
        
        # build service structure
        for image in images:
            status = ""
            status = raw_input("Do you want to start " + image.repo + " [y/n]:  ").lower()
            if (status == 'y' or status == 'yes'):
                status = 'RUN'
            else:
                status = 'STOP'
            self.services[image.repo] = Service(image, 1, status, 3000, 3000)
        
        # start services
        # could use threads here to go through and start them all, asssuming
        # docker is cool with that...
        for key in self.services:
            if self.services[key].state == "RUN":
                #execute the run command
                print('Starting service: {0}'.format(key))
                self.services[key].start()
            elif self.services[key].state == 'STOP':
                print('Stopping service: {0}'.format(key))
                self.services[key].stop()

    def ParseCli(self, args):
        options = { "--build"          : self.Build,
                    "--destroy"        : self.Destroy,
                    "--process-services" : self.StartServices
        }

        for command in args:
            try:
                options[command]()
            except KeyError:
                print('Command not found ... Program Exiting')
                               

def main(args):
    try:
        myCluster = Cluster()
        commands = args[1:]
        myCluster.ParseCli(commands)
    except KeyboardInterrupt:
        print('\n ... Program Exiting')

if __name__ == '__main__':
    sys.exit(main(sys.argv))

