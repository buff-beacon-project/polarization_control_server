from zmqhelper import ZMQServiceBase

class AbbyServer(ZMQServiceBase):
    """
    AbbyServer is a ZMQ service that provides an interface to control
    the polarization settings of an experimental setup.
    It extends ZMQServiceBase for handling requests and responses.
    """

    def __init__(self, port=5565):
        super().__init__(rep_port = 5565, 
            n_workers= 1,
            http_port = 5566,
            service_name = 'Abby Server'
        )
        
    def handle_request(self, message):
        '''
        Process the message received from the client.
        '''
        
        print(f"Received message: {message}")
        return f"Response from AbbyServer: {message}"
    
if __name__ == "__main__":
    server = AbbyServer()
    print("Starting AbbyServer...")
    server.start()
   