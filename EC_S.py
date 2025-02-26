import sys
import socket
import time

socket1 = socket.socket()

if len(sys.argv) == 3:
    IP_DE = sys.argv[1]
    PORT = int(sys.argv[2])
    socket1.connect((IP_DE, PORT))
    print("Connecting to the server")
    print("Sensor activado ")
    print("--------------------------------")
    
    try:
        while True:
            # Pedir al usuario que ingrese un mensaje
            message = input("Introduzca un mensaje ('FIN' para salir): ")


            socket1.sendall(message.encode('utf-8').upper())

            print("Digital Engine response: ",socket1.recv(4096).decode('utf-8'))
            if message.upper() != "FIN": message = input("Desea enviar otro mensaje (S/n): ")
            if message.lower() == "n":
                message = "FIN"
            socket1.sendall(message.encode('utf-8'))
            # Enviar el mensaje al servidor
           
           
            # Si el mensaje es "FIN", terminar la conexión
            if message.upper().strip() == "FIN":
                break
    finally:
        socket1.close()


else:
    print("Format error: must be \"python filename.py <DIGITAL ENGINE IP> <PORT>\"")

socket1.close()  # Cerrar el socket después de salir del bucle
