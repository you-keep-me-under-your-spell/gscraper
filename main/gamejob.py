import threading


job_assoc = {}


class GameJobTimeout(Exception): pass


class GameJob:
    def __init__(self, id, instance):
        self.id = id
        self.instance = instance
        self.event = threading.Event()
        self.result = None
        job_assoc[self.id] = self
    
    def get_result(self, timeout):
        done = self.result or self.event.wait(timeout)
        if done:
            return self.result
        else:
            raise GameJobTimeout(
                f"Job #{self.id}"
                " did not post in time")
    
    def complete(self, result):
        self.result = result
        self.event.set()
    
    def cleanup(self):
        del job_assoc[self.id]
        self.instance.terminate()


def get_gamejob(id):
    return job_assoc.get(id)
