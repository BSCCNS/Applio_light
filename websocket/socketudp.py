import logging
import json
import random
import time
from socket import *

# Tiempo mínimo entre un envío y el siguiente
MIN_TIME = 4200000 # 240fps


class SocketUDP():
    """Clase para enviar datos por UDP

    Crea un objeto SocketUDP que tiene un método send para
    mandar los datos que se requieran.

    Comprueba que ha habido un tiempo mínimo entre un envío y otro, para
    no saturar al receptor. Por defecto el equivalente para 240fps.

    Debe usarse con with para eliminar automáticamente el socket una vez
    finalizado el programa.

    Tiene una variable opcional de debug que comprueba que los mensajes
    estén bien construidos antes de mandarlos. Se debe pasar una función que
    reciba un mensaje y devuelva True si es correcto, False en caso contrario.
    """

    def __init__(self, host, port= 8080, min_time=MIN_TIME, debug=None):
        self.address = (host, port)
        self.socket = socket(AF_INET, SOCK_DGRAM)
        self._debug = debug
        self.last_call = 0
        self._frame = 1
        self.min_time = min_time

    def __enter__(self):
        return self
    
    def __exit__(self, *exc_info):
        try:
            close_it = self.socket.close
        except AttributeError:
            pass
        else:
            close_it()

    def send(self, message_dict):
        """
        """

        current = time.time_ns()

        logging.debug(f"Current: {current}")
        logging.debug(f"Last   : {self.last_call}")

        if current - self.last_call < self.min_time:
            logging.warning(f"Llamadas muy próximas. Ignorando frame")
            return 
            
        self.socket.sendto((json.dumps(message_dict)).encode(), self.address)
        self.last_call = current

        logging.debug(f"Message sent")

def send_wf_point(y):
    d = {'type': 'waveform',
        'message': {'data': y}}
    
    with SocketUDP("localhost", debug= None) as socket:
        socket.send(d)

def send_ls_slice(array_xyz, frame = 0):
    d = {'type': 'latent',
        'message': {'frame': frame, 'data': array_xyz}}

    with SocketUDP("localhost", debug= None) as socket:    
        socket.send(d)

def send_ls_finish():
    d = {'type': 'end_latent',
        'message': {'frame': -1}}
    with SocketUDP("localhost", debug= None) as socket:
        socket.send(d)

if __name__ == "__main__":

    logging.basicConfig(level=logging.INFO)
    logging.debug("Start")

    with SocketUDP("localhost", debug=None) as socket:

        for i in range(100):
            print(i)
            time.sleep(0.005)
            socket.send({0: {random.randint(0, 10): [random.random(), random.random(), random.random()]}}, i)