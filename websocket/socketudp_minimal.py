import logging
import json
import random
import time
from socket import *

address = ("localhost", 8080)
socket = socket(AF_INET, SOCK_DGRAM)
data = {
'features':{
    'N': 3,
    '0': [1,2,3], 
    '1': [4,5,6],
    '2': [4,5,6]
},
'audio_path': 
    'voice.wav'
}
socket.sendto((json.dumps(data) + '\n').encode(), address)

# Tiempo mínimo entre un envío y el siguiente
MIN_TIME = 4200000 # 240fps

class SocketUDP():

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

    def send(self, message, frame=None):
        """Manda el mensaje, utilizando el número de frame como ID.

        Al ser comunicación UDP, para detectar duplicados o envíos fuera de orden,
        se usa el número de frame como ID, para poder descartarlo en el receptor.

        El parámetro frame es opcional. Si no se especifica, se usa un ID autoincremental.
        """

        current = time.time_ns()

        logging.debug(f"Current: {current}")
        logging.debug(f"Last   : {self.last_call}")

        if current - self.last_call < self.min_time:
            logging.warning(f"Llamadas muy próximas. Ignorando frame {frame}")
            return 

        if self._debug is not None:
            if not self._debug(message):
                return
            
        if frame is None:
            self._frame += 1
            frame = self._frame 

        data = {'frame': frame,
                'data': message}

        self.socket.sendto((json.dumps(data) + '\n').encode(), self.address)
        self.last_call = current

        logging.debug(f"Sent message: {message}")

def _debug_vr(message):
    """
    Analiza el JSON que se envía para la experiencia VR.
    Devuelve True si es correcto, False en caso contrario.
    """
    logging.debug(f"Sending message: {message}")
    for key in message.keys():
        logging.debug(f"Checking key: {key}")
        if not str(key).isdecimal():
            logging.error(f"Key {key} is not valid.")
            return False
        for id, points in message[key].items():
            if id < 0 or id > 17:
                logging.error(f"Key {key}:{id} is not valid.")
                return False
            if len(points) != 3:
                logging.error(f"Point {points} doesn't have 3 values.")
                return False
            for point in points:
                pass # Check min/max values
    
    return True

def send_array(array, i):
    with SocketUDP("localhost", debug= None) as socket:
        socket.send(list(array), i)

if __name__ == "__main__":

    logging.basicConfig(level=logging.INFO)
    logging.debug("Start")

    with SocketUDP("localhost", debug=_debug_vr) as socket:

        for i in range(100):
            print(i)
            time.sleep(0.005)
            socket.send({0: {random.randint(0, 10): [random.random(), random.random(), random.random()]}}, i)