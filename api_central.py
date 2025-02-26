from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS
import requests
import sys

# Verificar argumentos de línea de comandos
if len(sys.argv) != 5:
    print("Uso: python app.py <IP_HOST> <PORT> <IP_CTC> <PORT_CTC>")
    sys.exit(1)

IP_HOST = sys.argv[1]
PORT = int(sys.argv[2])
IP_CTC = sys.argv[3]
PORT_CTC = int(sys.argv[4])

app = Flask(__name__, static_folder='static')
CORS(app)

# Datos iniciales
taxis_autenticados = []
clientes = []
tokenTaxis = []

def elementosMapa(mapa, filename):
    with open(filename, 'r') as archivo:
        for linea in archivo:
            id_loc, x, y = linea.split()
            coor_x, coor_y = int(x), int(y)
            mapa[coor_x][coor_y] = id_loc

@app.route('/api/taxis', methods=['GET', 'POST'])
def manage_taxis():
    global taxis_autenticados
    if request.method == 'POST':
        taxis_autenticados = request.json
        return jsonify({"message": "Datos de taxis actualizados"}), 200
    return jsonify(taxis_autenticados)

@app.route('/api/tokens', methods=['GET', 'POST'])
def manage_tokens():
    global tokenTaxis
    if request.method == 'POST':
        tokenTaxis = request.json
        return jsonify({"message": "Datos de tokens actualizados"}), 200
    return jsonify(tokenTaxis)

@app.route('/api/clientes', methods=['GET', 'POST'])
def manage_clientes():
    global clientes
    if request.method == 'POST':
        clientes = request.json
        return jsonify({"message": "Datos de clientes actualizados"}), 200
    return jsonify(clientes)

@app.route('/api/mapa', methods=['GET'])
def get_mapa():
    mapa = [["" for _ in range(20)] for _ in range(20)]
    for cliente in clientes:
        x, y = cliente["coordenadas"]
        mapa[x][y] = f"{cliente['ID']}"
    for taxi in taxis_autenticados:
        x, y = taxi["pos_actual"]
        mapa[x][y] = f"{taxi['ID']}"
    elementosMapa(mapa, "localizaciones.txt")
    return jsonify(mapa)

@app.route('/api/clima', methods=['GET'])
def get_clima():
    try:
        clima_url = f'http://{IP_CTC}:{PORT_CTC}/clima'
        response = requests.get(clima_url)
        clima_data = response.json()
        return jsonify(clima_data)
    except requests.exceptions.RequestException as e:
        return jsonify({'error': str(e)}), 500

# Ruta para servir el archivo index.html
@app.route('/')
def index():
    return send_from_directory(app.static_folder, 'index.html')

# Ruta para otros archivos estáticos (CSS, imágenes, etc.)
@app.route('/<path:path>')
def static_files(path):
    return send_from_directory(app.static_folder, path)

if __name__ == '__main__':
    app.run(host=IP_HOST, port=PORT, debug=True)
