import requests
import sys

# Configuración
if len(sys.argv)==3:
    HOST_API = sys.argv[1]
    PORT_API = sys.argv[2]
    URL = f"http://{HOST_API}:{PORT_API}/clima"  # Cambia la IP y el puerto si es necesario
    print(URL)
    OUTPUT_FILE = "estado_clima.txt"  # Archivo donde se guardará el resultado

    def consumir_api(url):
        try:
            response = requests.get(url)
            response.raise_for_status()  # Lanza una excepción si el status no es 2xx
            data = response.json()

            # Obtener el estado
            estado = data.get("status", "KO")  # Por defecto "KO" si no está presente
            guardar_estado(estado)

            print(f"Estado obtenido: {estado}")
        except requests.RequestException as e:
            print(f"Error al consumir la API: {e}")
            guardar_estado("KO")

    def guardar_estado(estado):
        try:
            with open(OUTPUT_FILE, "a") as file:
                file.write(f"{estado}\n")
            print(f"Estado '{estado}' guardado en {OUTPUT_FILE}")
        except Exception as e:
            print(f"Error al guardar el estado: {e}")
    consumir_api(URL)

else:
    print("error argument, must be: \" python consumirAPI.py IP_API PORT_API\"")
