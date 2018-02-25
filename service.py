import subprocess as sub

class Service:
    def __init__(self, img, reps, state, internal, external):
        self.image = img
        self.replicas = reps
        self.state = state
        self.internalPort = internal
        self.externalPort = external
    
    def start(self):
        command = ["sudo", "docker", "service", "create",
                    "--name", self.image.repo.split('/')[1],
                    "--publish", "{}:{}/tcp".format(self.internalPort, self.externalPort),
                    "--replicas", str(self.replicas), self.image.repo]
        ps = sub.Popen(command, stdout=sub.PIPE)
        (output, err) = ps.communicate()   


