import subprocess as sub

class Service:
    def __init__(self, img, reps, state, internal, external):
        # properties
        self.image = img
        self.replicas = reps
        self.state = state
        self.internalPort = internal
        self.externalPort = external
        self.id = ''

        # methods
        self.__get_id()

    def start(self):
        command = ["sudo", "docker", "service", "create",
                    "--name", self.image.repo.split('/')[1],
                    "--publish", "{}:{}/tcp".format(self.internalPort, self.externalPort),
                    "--replicas", str(self.replicas), self.image.repo]
        ps = sub.Popen(command, stdout=sub.PIPE)
        (output, err) = ps.communicate() 
        
        # assign the id to this process
        self.__get_id()

    def stop(self):
        if self.id != '':
            command = ['sudo', 'docker', 'service', 'rm', self.id]
            ps = sub.Popen(command, stdout=sub.PIPE)
            (output, err) = ps.communicate()

    # private methods
    def __get_id(self):
        command = ['sudo', 'docker', 'service', 'ls']
        ps = sub.Popen(command, stdout=sub.PIPE)
        (output, err) = ps.communicate()
        lines = output.split('\n')
        data = lines.pop()
        while data == '':
            data = lines.pop()
        self.id = data.split(' ')[0]
