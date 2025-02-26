import socket
import sys
import time
from kafka import KafkaConsumer
from kafka import KafkaProducer
import os
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.primitives.hashes import SHA256
from cryptography.hazmat.primitives.serialization import load_pem_public_key

FORMAT = "utf-8"
EXIT = "exit"
MAX_CONEXIONES = 5

import requests
import ssl

def menu_inicial():
    # python nombre_archivo.py <IP_Sensor> <PORT_sensor> <IP_Central> <PORT_Central> <IP_KAFKA> <PORT_KAFKA_CENTRAL> <IP_API_REGISTER> <PORT_API_REGISTER>
    if len(sys.argv) == 9:
        IP_SENSOR = sys.argv[1]
        PORT_SENSOR = int(sys.argv[2])
        IP_CENTRAL = sys.argv[3]
        PORT_CENTRAL = int(sys.argv[4])
        IP_KAFKA = sys.argv[5]
        PORT_KAFKA_CENTRAL = int(sys.argv[6])
        IP_REGISTER = sys.argv[7]
        PORT_REGISTER = int(sys.argv[8])
        
        ID_TAXI = input("Ingrese el ID del taxi: ")

        
        print("1. Registrar Taxi")
        print("2. Autenticar Taxi")
        opcion = input("Seleccione una opción: ")

        if opcion == "1":
            registrar_taxi(ID_TAXI, IP_REGISTER, PORT_REGISTER)

            menu_inicial()
        elif opcion == "2":
            token = autenticacion(IP_CENTRAL, PORT_CENTRAL, ID_TAXI)
            if "no" in token:
                menu_inicial()
            else:
                sensorTaxi(IP_SENSOR, PORT_SENSOR, IP_KAFKA, PORT_KAFKA_CENTRAL, ID_TAXI, token)
        else:
            print("Opción no válida.")
            menu_inicial()

    else:
        print("Format error: must be \"python nombre_archivo.py <IP_Sensor> <PORT_sensor> <IP_Central> <PORT_Central> <IP_KAFKA> <PORT_KAFKA_CENTRAL> <IP_REGISTER> <PORT_REGISTER>\"")

    

def registrar_taxi(ID_TAXI, IP_REGISTER, PORT_REGISTER):
    taxi_id = ID_TAXI.upper()
    url = f"https://{IP_REGISTER}:{PORT_REGISTER}/register"
    data = {"id": taxi_id}

    
    cert_path = os.path.join(os.path.dirname(__file__), "EC_Registry", "certificate.crt")

    # ssl_context = ssl.create_default_context()
    # ssl_context.check_hostname = False
    # ssl_context.load_verify_locations(cert_path)
    try:
        response = requests.put(url, json=data, verify=False)  # Certificado SSL
        if response.status_code == 201:
            print(response.json()['message'])
        elif response.status_code == 409:
            print("El taxi ya está registrado.")
        else:
            print("Error al registrar el taxi:", response.text)
    except requests.RequestException as e:
        print("Error en la comunicación con EC_Registry:", e)

def sensorTaxi(IP_SENSOR, PORT_SENSOR, IP_KAFKA, PORT_KAFKA_CENTRAL,  ID_TAXI, token):
    # Crear socket
    socket1 = socket.socket()
    socket1.bind((IP_SENSOR, PORT_SENSOR))
    socket1.listen(MAX_CONEXIONES)

    print("Digital Engine ON in ", IP_SENSOR, " ", PORT_SENSOR)
    (conexion, addr) = socket1.accept()

    print("New connection")
    print(addr)

    # Establecer el mensaje inicial como vacío
    obstaculo = ""

    try:
        # Bucle principal del servidor
        while True:
            # Recibir datos del cliente
            conexion.settimeout(None)  # Sin límite de tiempo inicialmente
            data = conexion.recv(1024).decode('utf-8')
            
            if not data:
                break

            # Si el mensaje es "FIN", terminar el ciclo y cerrar la conexión
            if data.strip() == "FIN":
                print("El cliente ha cerrado la conexión.")
                break

            # Actualizar el mensaje que se imprimirá
            obstaculo = data.strip()
            answer = "continuar"
            result = "continuar"
            if obstaculo != "OK":
                if obstaculo == "SR":
                    result = "Semaforo en rojo"
                    answer = "Frenar coche"
                elif obstaculo == "SV":
                    result = "Semaforo en verde"
                    answer = "Continuar"
                elif obstaculo == "PC":
                    result = "Peaton Cruzando"
                    answer = "Frenar coche"
                elif obstaculo == "A":
                    result = "Accidente"
                    answer = "Llamar Policía"
                else:
                    result = "Obstaculo no encontrado"
            
            conexion.send(answer.encode(FORMAT))
            print("obstaculo recibido: ", obstaculo)
            print(f"enviando {obstaculo} a central")
            producer = enviarEstadoACentral(IP_KAFKA, PORT_KAFKA_CENTRAL, obstaculo, ID_TAXI, token)
            producer.close()

            # Bucle de impresión continua
            while True:
                print(answer)
                time.sleep(1)
                
                # Cambiar el tiempo de espera para la recepción de nuevos mensajes
                conexion.settimeout(0.1)  # Verifica cada 100ms si hay nuevos mensajes
                try:
                    # Intenta recibir nuevos datos
                    new_data = conexion.recv(1024).decode('utf-8')
                    
                    # Si recibe un nuevo mensaje
                    if new_data.strip():
                        # Actualiza el mensaje a imprimir
                        obstaculo = new_data.strip()
                        break  # Sale del bucle de impresión y vuelve al bucle principal
                except socket.timeout:
                    # Si no hay nuevos datos, sigue imprimiendo el mensaje actual
                    continue
    finally:
        conexion.close()
        socket1.close()

 
def autenticacion(IP_CENTRAL, PORT, ID_TAXI):
    socket1 = socket.socket()
    socket1.connect((IP_CENTRAL, PORT))
    print("Connecting to the Central...")
    try:
        # Enviar el mensaje de autenticación
        message = ID_TAXI
        socket1.sendall(message.encode('utf-8'))
        print("autenticando taxi")
        # Recibir la respuesta del servidor
        response = socket1.recv(4096).decode('utf-8')
        print("Central response: ", response)
        if "token" in response:
            token = response.split("token: ")[1]
            print("Token:", token)
        else:
            return "no autenticado"

        
    finally:
        socket1.close()
    
    return token

# Envia el estado del taxi recibido por los sensores a central
def enviarEstadoACentral(IP_KAFKA, PORT_KAFKA_CENTRAL, estado, ID_TAXI, token):
    ID_TAXI = ID_TAXI[-2:]
    print(IP_KAFKA, PORT_KAFKA_CENTRAL)

    # Cargar la clave pública del Taxi
    with open("clave_publica_taxi.pem", "rb") as archivo:
        clave_publica_taxi = load_pem_public_key(archivo.read())

    # Generar y escribir la clave simétrica inicial en un archivo
    clave_simetrica = Fernet.generate_key()
    with open("clave_simetrica.key", "wb") as archivo_clave:
        archivo_clave.write(clave_simetrica)

    # Cifrar la clave simétrica con la clave pública RSA del Taxi
    clave_simetrica_cifrada = clave_publica_taxi.encrypt(
        clave_simetrica,
        padding.OAEP(
            mgf=padding.MGF1(algorithm=SHA256()),
            algorithm=SHA256(),
            label=None
        )
    )
    topic = f'taxi-central{ID_TAXI}'
    print(topic)
    producer = KafkaProducer(bootstrap_servers=f"{IP_KAFKA}:{PORT_KAFKA_CENTRAL}", value_serializer=lambda v: v)

    # Enviar la clave cifrada una sola vez al inicio
    producer.send(topic, b"KEY:" + clave_simetrica_cifrada)
    print("Clave simétrica cifrada enviada")

    try:
        # Leer la clave simétrica desde el archivo
        with open("clave_simetrica.key", "rb") as archivo_clave:
            clave_simetrica_actual = archivo_clave.read()

        # Crear un nuevo cifrador con la clave simétrica cargada
        cipher = Fernet(clave_simetrica_actual)

        # Cifrar y enviar un mensaje
        mensaje_original = f"{estado}, {token}".encode('utf-8')
        mensaje_cifrado = cipher.encrypt(mensaje_original)
        producer.send(topic, b"MSG:" + mensaje_cifrado)
        producer.flush()
        print(f'Enviando a el topic taxi-central{ID_TAXI}')
        print("Mensaje cifrado enviado:", mensaje_cifrado)

    except Exception as e:
        print(f"Error al cifrar o enviar mensaje: {e}")
    return producer


if __name__ == "__main__":
    menu_inicial()
