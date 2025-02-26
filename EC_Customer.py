from kafka import KafkaConsumer, KafkaProducer
import sys
import time

FORMAT = "utf-8"

if len(sys.argv) == 4:
    IP_KAFKA = str(sys.argv[1])
    PORT_BROKER = str(sys.argv[2])
    ID_CLIENTE = sys.argv[3]
    print(IP_KAFKA, PORT_BROKER)
    # Conectarse al broker de Kafka
    producer = KafkaProducer(bootstrap_servers=f"{IP_KAFKA}:{PORT_BROKER}")
    
    # Escuchar el tema específico de respuestas para este cliente
    consumer = KafkaConsumer(
        f'central-cliente-{ID_CLIENTE}',  # Tema específico para este cliente
        bootstrap_servers=f'{IP_KAFKA}:{PORT_BROKER}',
        consumer_timeout_ms=60000
    )
    print("consumer "+f'central-cliente-{ID_CLIENTE}')

    # Abrir el archivo y leer localizaciones una por una
    archivo = open("servicioClientes.txt", 'r')
    localizaciones = archivo.readlines()
    
    for linea in localizaciones:
        ID_LOCALIZACION = linea.strip().upper()
        ULTIMA_LOCALIZACION = localizaciones[-1].strip().upper()
        print(f"Solicitando servicio para la localización {ID_LOCALIZACION}")

        # Enviar solicitud al tema común "cliente-central"
        mensaje = f"{ID_LOCALIZACION} {ID_CLIENTE.lower()}".encode(FORMAT)
        producer.send('cliente-central', mensaje)  # Enviar al tema común
        producer.flush()

        # Escuchar respuesta de disponibilidad de servicio en el tema específico del cliente
        servicio_finalizado = False
        while not servicio_finalizado:
            #print(2)
            for mensaje_disp in consumer:
                #print(1)
                servicio_disponible = mensaje_disp.value.decode(FORMAT)
                print(servicio_disponible)

                if servicio_disponible == "KO":
                    print("Taxi no disponible. Reintentando en 4 segundos...")
                    time.sleep(4)
                    # Reenviar solicitud en caso de no disponibilidad
                    producer.send('cliente-central', mensaje)
                    producer.flush()
                    break

                elif servicio_disponible == f"CLIENTE {ID_CLIENTE} SERVICIO FINALIZADO {ID_LOCALIZACION}":
                    print(f"Servicio a {ID_LOCALIZACION} completado.")
                    servicio_finalizado = True
                    print("esperando 4 segundos a solicitar otro servicio")
                    time.sleep(4)  # Espera 4 segundos antes de solicitar el siguiente servicio
                    break
                    
    print(f"SERVICIO {ID_CLIENTE} FINALIZADO")
    print("Finalizar conexión")
    producer.close()
    consumer.close()
    print("Kafka consumer cerrado")
else:
    print("Error en los argumentos. Uso: python EC_Customer.py <IP_KAFKA> <puerto broker kafka> <ID Cliente>")
